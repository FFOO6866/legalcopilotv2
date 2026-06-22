"""Orchestrator agent — PDCA workflow coordination with SOP routing.

Uses Kaizen SupervisorWrapper with LLM-based routing (no if-else).
The LLM decides which specialist to invoke based on the request context.
Max 3 PDCA iterations before escalating to human review.
"""

import json
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


MAX_PDCA_ITERATIONS = 3


@dataclass
class OrchestratorConfig:
    llm_provider: str = field(default_factory=lambda: settings.get("LLM_PROVIDER", "openai"))
    model: str = field(default_factory=lambda: settings.DEFAULT_LLM_MODEL)
    temperature: float = 0.3
    max_tokens: int = 4000
    quality_threshold: float = 0.80


class OrchestratorAgent(BaseAgent):
    """PDCA workflow orchestrator — routes to specialists, quality-gates results."""

    def __init__(self, config: OrchestratorConfig | None = None):
        config = config or OrchestratorConfig()
        super().__init__(config=config, signature=OrchestratorSignature())
        self.quality_threshold = config.quality_threshold

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

        PLAN: Route to appropriate specialist(s)
        DO: Execute specialist work with RAG context
        CHECK: QA review with adversarial challenge
        ACT: Return result or trigger rework (max 3 iterations)
        """
        # Redact PII before any LLM calls
        clean_request = redact_pii(request)

        # PLAN phase: classify and route
        plan = self.run(
            request=clean_request,
            case_context=case_context,
            conversation_history=conversation_history,
        )

        # Retrieve RAG context using PII-redacted request
        rag_result = retrieve_context(query=clean_request)

        # DO phase: execute specialist work based on routing decision
        analysis_result = self._execute_specialists(
            plan=plan,
            request=clean_request,
            case_context=case_context,
            rag_context=rag_result["context_text"],
        )

        # CHECK + ACT phase: iterate until quality gate passes or max iterations
        for iteration in range(MAX_PDCA_ITERATIONS):
            qa_result = self.qa_reviewer.review(
                analysis=json.dumps(analysis_result),
                original_query=clean_request,
                case_context=case_context,
            )

            if qa_result.get("quality_verdict") == "pass":
                return {
                    "response": analysis_result,
                    "qa_review": qa_result,
                    "iterations": iteration + 1,
                    "sources": rag_result["sources"],
                    "confidence": qa_result.get("confidence", 0),
                    "status": "complete",
                }

            if qa_result.get("quality_verdict") == "escalate":
                return {
                    "response": analysis_result,
                    "qa_review": qa_result,
                    "iterations": iteration + 1,
                    "sources": rag_result["sources"],
                    "confidence": qa_result.get("confidence", 0),
                    "status": "escalated",
                }

            # Rework: re-run with QA feedback via structured context, not string concat
            rework_instructions = qa_result.get("rework_instructions", "")
            rework_context = json.dumps(
                {
                    "original_request": clean_request,
                    "rework_instructions": rework_instructions,
                    "iteration": iteration + 1,
                }
            )
            analysis_result = self._execute_specialists(
                plan=plan,
                request=clean_request,
                case_context=rework_context,
                rag_context=rag_result["context_text"],
            )

        # Max iterations reached
        return {
            "response": analysis_result,
            "qa_review": qa_result,
            "iterations": MAX_PDCA_ITERATIONS,
            "sources": rag_result["sources"],
            "confidence": qa_result.get("confidence", 0),
            "status": "max_iterations_reached",
        }

    def _execute_specialists(
        self,
        plan: dict,
        request: str,
        case_context: str,
        rag_context: str,
    ) -> dict:
        """Execute specialist agents based on the orchestrator's routing decision.

        The LLM's structured output fields determine which agents run.
        """
        results = {}
        # Research is always useful for legal queries
        research_result = self.researcher.research(query=request)
        results["research"] = research_result

        # Associate analysis with RAG context
        associate_result = self.associate.analyze(
            facts=request,
            legal_issues=json.dumps([plan.get("case_type", "general")]),
            rag_context=rag_context,
        )
        results["analysis"] = associate_result

        # Drafting — invoked when the LLM's structured routing decision says so
        if plan.get("include_drafting", False):
            draft_result = self.drafting.draft(
                document_type=plan.get("case_type", "advice_note"),
                instructions=request,
                facts=request,
                legal_analysis=json.dumps(associate_result),
                rag_context=rag_context,
            )
            results["draft"] = draft_result

        return results
