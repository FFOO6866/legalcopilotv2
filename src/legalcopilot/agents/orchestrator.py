"""Orchestrator agent — PDCA workflow coordination with SOP routing.

Uses Kaizen SupervisorWrapper with LLM-based routing (no if-else).
The LLM decides which specialist to invoke based on the request context.
SOP templates configure quality thresholds, max iterations, research focus,
and knowledge sources per case type.
"""

import json
import logging
from dataclasses import dataclass, field

from kaizen.core.base_agent import BaseAgent

from legalcopilot.agents.signatures import OrchestratorSignature
from legalcopilot.config import settings
from legalcopilot.agents.paralegal import ParalegalAgent
from legalcopilot.agents.associate import AssociateAgent
from legalcopilot.agents.drafting import DraftingAgent
from legalcopilot.agents.qa_reviewer import QAReviewerAgent
from legalcopilot.agents.researcher import ResearchAgent
from legalcopilot.services.pii_filter import redact_pii
from legalcopilot.services.rag_pipeline import retrieve_context
from legalcopilot.services.sop_service import get_sop_template, validate_case_type

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    llm_provider: str = field(default_factory=lambda: settings.get("LLM_PROVIDER", "openai"))
    model: str = field(default_factory=lambda: settings.DEFAULT_LLM_MODEL)
    temperature: float = 0.3
    max_tokens: int = 4000


class OrchestratorAgent(BaseAgent):
    """PDCA workflow orchestrator — routes to specialists, quality-gates results."""

    def __init__(self, config: OrchestratorConfig | None = None):
        config = config or OrchestratorConfig()
        super().__init__(config=config, signature=OrchestratorSignature())

        # Initialize specialist agents
        self.paralegal = ParalegalAgent()
        self.associate = AssociateAgent()
        self.drafting = DraftingAgent()
        self.qa_reviewer = QAReviewerAgent()
        self.researcher = ResearchAgent()

    def process_request(
        self,
        request: str,
        case_context: str = "{}",
        conversation_history: str = "[]",
    ) -> dict:
        """Execute the full PDCA cycle for a legal request.

        PLAN: Classify case type, load SOP template, route to specialists
        DO: Execute specialist work with SOP-configured RAG context
        CHECK: QA review against SOP quality threshold
        ACT: Return result or trigger rework (up to SOP max_iterations)
        """
        # Redact PII before any LLM calls
        clean_request = redact_pii(request)
        clean_case_context = redact_pii(case_context)
        clean_history = redact_pii(conversation_history)

        # PLAN phase: classify and route
        plan = self.run(
            request=clean_request,
            case_context=clean_case_context,
            conversation_history=clean_history,
        )

        # Load SOP template based on the LLM's case_type classification
        raw_case_type = plan.get("case_type", "general")
        case_type = validate_case_type(raw_case_type)
        sop = get_sop_template(case_type)
        quality_threshold = sop.get("quality_threshold", 0.80)
        max_iterations = sop.get("max_iterations", 3)
        research_focus = sop.get("skills", {}).get("research", {}).get("focus", [])
        knowledge_sources = sop.get("knowledge_sources", {})

        logger.info(
            "PDCA cycle: case_type=%s, quality_threshold=%.2f, max_iterations=%d",
            case_type,
            quality_threshold,
            max_iterations,
        )

        # Retrieve RAG context — use SOP research focus to enrich query
        rag_query = clean_request
        if research_focus:
            rag_query = f"{clean_request} [{' '.join(research_focus)}]"
        rag_result = retrieve_context(
            query=rag_query,
            filter_conditions={"jurisdiction": "SG"},
        )

        # Parse the LLM's routing_decision to determine which agents to invoke
        routing = _parse_routing(plan.get("routing_decision", ""))

        # DO phase: execute specialist work based on routing decision + SOP
        analysis_result = self._execute_specialists(
            plan=plan,
            routing=routing,
            request=clean_request,
            case_context=clean_case_context,
            rag_context=rag_result["context_text"],
            sop=sop,
        )

        # CHECK + ACT phase: iterate until quality gate passes or SOP max iterations
        # Skip adversarial QA review if SOP disables it for this case type
        adversarial_review = sop.get("adversarial_review", True)
        if not adversarial_review:
            return {
                "response": analysis_result,
                "qa_review": {},
                "iterations": 1,
                "sources": rag_result["sources"],
                "confidence": 0,
                "status": "complete",
                "case_type": case_type,
                "sop_template": sop.get("name", ""),
            }

        for iteration in range(max_iterations):
            qa_result = self.qa_reviewer.review(
                analysis=json.dumps(analysis_result),
                original_query=clean_request,
                case_context=clean_case_context,
                quality_threshold=quality_threshold,
            )

            if qa_result.get("quality_verdict") == "pass":
                return {
                    "response": analysis_result,
                    "qa_review": qa_result,
                    "iterations": iteration + 1,
                    "sources": rag_result["sources"],
                    "confidence": qa_result.get("confidence", 0),
                    "status": "complete",
                    "case_type": case_type,
                    "sop_template": sop.get("name", ""),
                }

            if qa_result.get("quality_verdict") == "escalate":
                return {
                    "response": analysis_result,
                    "qa_review": qa_result,
                    "iterations": iteration + 1,
                    "sources": rag_result["sources"],
                    "confidence": qa_result.get("confidence", 0),
                    "status": "escalated",
                    "case_type": case_type,
                    "sop_template": sop.get("name", ""),
                }

            # Rework: re-run with QA feedback, preserving original case_context
            rework_instructions = qa_result.get("rework_instructions", "")
            rework_context = json.dumps(
                {
                    "original_case_context": clean_case_context,
                    "rework_instructions": rework_instructions,
                    "iteration": iteration + 1,
                    "knowledge_sources": knowledge_sources,
                }
            )
            analysis_result = self._execute_specialists(
                plan=plan,
                routing=routing,
                request=clean_request,
                case_context=rework_context,
                rag_context=rag_result["context_text"],
                sop=sop,
            )

        # Max iterations reached
        return {
            "response": analysis_result,
            "qa_review": qa_result,
            "iterations": max_iterations,
            "sources": rag_result["sources"],
            "confidence": qa_result.get("confidence", 0),
            "status": "max_iterations_reached",
            "case_type": case_type,
            "sop_template": sop.get("name", ""),
        }

    def _execute_specialists(
        self,
        plan: dict,
        routing: dict,
        request: str,
        case_context: str,
        rag_context: str,
        sop: dict,
    ) -> dict:
        """Execute specialist agents based on routing decision and SOP config.

        The LLM's routing_decision drives which agents run. SOP skills config
        provides domain-specific parameters (research focus, analysis depth).
        """
        results = {}
        sop_skills = sop.get("skills", {})

        # Paralegal — invoked when routing includes document processing
        if routing.get("paralegal"):
            paralegal_result = self.paralegal.classify_document(
                document_text=request,
                case_context=case_context,
            )
            results["intake"] = paralegal_result

        # Research — invoked for research/analysis tasks (most legal queries)
        # Passes pre-fetched RAG context to avoid duplicate embedding calls
        # Enriches the query with SOP knowledge_sources so the LLM
        # knows which primary/secondary legislation to prioritize
        if routing.get("research", True):
            research_config = sop_skills.get("research", {})
            knowledge_sources = sop.get("knowledge_sources", {})
            enriched_query = request
            if knowledge_sources.get("primary"):
                statute_names = [s.replace("_", " ").title() for s in knowledge_sources["primary"]]
                enriched_query = (
                    f"{request}\n\n[Primary legislation to consider: "
                    f"{', '.join(statute_names)}]"
                )
            research_result = self.researcher.research(
                query=enriched_query,
                practice_area=sop.get("practice_area", "general"),
                rag_context=rag_context,
            )
            if research_config.get("focus"):
                research_result["sop_focus"] = research_config["focus"]
            results["research"] = research_result

        # Associate analysis with RAG context + SOP analysis config
        if routing.get("analysis", True):
            analysis_config = sop_skills.get("analysis", {})
            methodology = analysis_config.get("methodology", "IRAC")
            depth = analysis_config.get("depth", "standard")
            analysis_facts = request
            if methodology or depth:
                analysis_facts = (
                    f"{request}\n\n[Analysis methodology: {methodology}. "
                    f"Depth: {depth}. "
                    f"{'Provide comprehensive coverage of all issues, counter-arguments, and edge cases.' if depth == 'comprehensive' else 'Provide focused analysis of the primary issues.'}]"
                )
            associate_result = self.associate.analyze(
                facts=analysis_facts,
                legal_issues=json.dumps([plan.get("case_type", "general")]),
                rag_context=rag_context,
            )
            results["analysis"] = associate_result

        # Drafting — invoked when routing says so or SOP includes drafting skills
        if routing.get("drafting") or plan.get("include_drafting", False):
            drafting_types = sop_skills.get("drafting", {}).get("types", [])

            # When multiple types are available, pass "auto" so the drafter
            # LLM selects the type based on the request context (LLM-first).
            # When only one type exists, use it directly.
            if len(drafting_types) == 1:
                doc_type = drafting_types[0]
                drafting_instructions = request
            elif len(drafting_types) > 1:
                doc_type = "auto"
                drafting_instructions = (
                    f"{request}\n\n[Available document types for this case: "
                    f"{', '.join(drafting_types)}. "
                    f"Select the most appropriate type and draft accordingly.]"
                )
            else:
                doc_type = "advice_note"
                drafting_instructions = request

            draft_result = self.drafting.draft(
                document_type=doc_type,
                instructions=drafting_instructions,
                facts=request,
                legal_analysis=json.dumps(results.get("analysis", {})),
                rag_context=rag_context,
            )
            results["draft"] = draft_result

        return results


def _parse_routing(routing_decision: str) -> dict:
    """Parse the LLM's routing_decision JSON into a dict of agent flags.

    Falls back to a sensible default (research + analysis) if the LLM
    returns malformed JSON.
    """
    default = {"research": True, "analysis": True, "drafting": False, "paralegal": False}
    if not routing_decision:
        return default
    try:
        parsed = (
            json.loads(routing_decision) if isinstance(routing_decision, str) else routing_decision
        )
        if isinstance(parsed, dict):
            return {
                "research": parsed.get("research", True),
                "analysis": parsed.get("analysis", True),
                "drafting": parsed.get("drafting", False),
                "paralegal": parsed.get("paralegal", False),
            }
    except (json.JSONDecodeError, TypeError):
        logger.debug("Could not parse routing_decision, using defaults: %s", routing_decision)
    return default
