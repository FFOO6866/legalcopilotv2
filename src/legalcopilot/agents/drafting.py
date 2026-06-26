"""Drafting agent — legal document generation with Singapore conventions.

Kaizen BaseAgent with DraftingSignature. Produces formal legal documents
(letters, submissions, contracts, memos) using analysis context and RAG.
"""

from dataclasses import dataclass, field

from kaizen.core.base_agent import BaseAgent

from legalcopilot.agents.signatures import DraftingSignature
from legalcopilot.config import settings
from legalcopilot.services.pii_filter import redact_pii


@dataclass
class DraftingConfig:
    llm_provider: str = field(default_factory=lambda: settings.get("LLM_PROVIDER", "openai"))
    model: str = field(default_factory=lambda: settings.DEFAULT_LLM_MODEL)
    temperature: float = 0.15
    max_tokens: int = 8000
    confidence_threshold: float = 0.85


class DraftingAgent(BaseAgent):
    """Legal document drafting with Singapore conventions."""

    def __init__(self, config: DraftingConfig | None = None):
        config = config or DraftingConfig()
        super().__init__(config=config, signature=DraftingSignature())
        self.confidence_threshold = config.confidence_threshold

    def draft(
        self,
        document_type: str,
        instructions: str,
        facts: str = "",
        legal_analysis: str = "",
        rag_context: str = "",
        tone: str = "formal",
    ) -> dict:
        """Draft a legal document based on instructions and analysis.

        PII is redacted from facts and instructions before sending
        to the LLM. Legal analysis and RAG context are passed through
        as-is (already sanitized by upstream agents).
        """
        clean_facts = redact_pii(facts) if facts else ""
        clean_instructions = redact_pii(instructions) if instructions else ""
        result = self.run(
            document_type=document_type,
            instructions=clean_instructions,
            facts=clean_facts,
            legal_analysis=legal_analysis,
            rag_context=rag_context,
            tone=tone,
        )
        return result
