"""Paralegal agent — document intake, classification, OCR, metadata extraction.

Kaizen BaseAgent with ParalegalSignature. Uses PII filter before all LLM calls.
"""

from dataclasses import dataclass, field

from kaizen.core.base_agent import BaseAgent

from legalcopilot.agents.signatures import ParalegalSignature
from legalcopilot.config import settings
from legalcopilot.services.pii_filter import redact_pii


@dataclass
class ParalegalConfig:
    llm_provider: str = field(default_factory=lambda: settings.get("LLM_PROVIDER", "openai"))
    model: str = field(default_factory=lambda: settings.DEFAULT_LLM_MODEL)
    temperature: float = 0.2
    max_tokens: int = 3000
    confidence_threshold: float = 0.85


class ParalegalAgent(BaseAgent):
    """Document classification, metadata extraction, entity identification."""

    def __init__(self, config: ParalegalConfig | None = None):
        config = config or ParalegalConfig()
        super().__init__(config=config, signature=ParalegalSignature())
        self.confidence_threshold = config.confidence_threshold

    def classify_document(
        self, document_text: str, document_type: str = "pdf", case_context: str = "{}"
    ) -> dict:
        """Classify a legal document and extract metadata.

        PII is redacted before sending to the LLM.
        """
        clean_text = redact_pii(document_text)
        result = self.run(
            document_text=clean_text,
            document_type=document_type,
            case_context=case_context,
        )
        return result
