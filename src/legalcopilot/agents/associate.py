"""Associate agent — legal analysis, IRAC methodology, citation research.

Kaizen BaseAgent with AssociateSignature. Performs fact extraction,
legal issue identification, and risk assessment using RAG context.
"""

from dataclasses import dataclass, field

from kaizen.core.base_agent import BaseAgent

from legalcopilot.agents.signatures import AssociateSignature
from legalcopilot.config import settings
from legalcopilot.services.pii_filter import redact_pii


@dataclass
class AssociateConfig:
    llm_provider: str = field(default_factory=lambda: settings.get("LLM_PROVIDER", "openai"))
    model: str = field(default_factory=lambda: settings.DEFAULT_LLM_MODEL)
    temperature: float = 0.3
    max_tokens: int = 4000
    confidence_threshold: float = 0.90


class AssociateAgent(BaseAgent):
    """IRAC legal analysis, citation research, risk assessment."""

    def __init__(self, config: AssociateConfig | None = None):
        config = config or AssociateConfig()
        super().__init__(config=config, signature=AssociateSignature())
        self.confidence_threshold = config.confidence_threshold

    def analyze(
        self,
        facts: str,
        legal_issues: str,
        jurisdiction: str = "SG",
        rag_context: str = "",
    ) -> dict:
        """Perform IRAC analysis on the given facts and legal issues.

        PII is redacted from facts before sending to the LLM.
        RAG context is pre-retrieved and passed through.
        """
        clean_facts = redact_pii(facts)
        result = self.run(
            facts=clean_facts,
            legal_issues=legal_issues,
            jurisdiction=jurisdiction,
            rag_context=rag_context,
        )
        return result
