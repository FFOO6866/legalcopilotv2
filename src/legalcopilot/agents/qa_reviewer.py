"""QA reviewer agent — adversarial challenge, quality validation, compliance check.

Kaizen BaseAgent with QASignature. Reviews analyses for completeness, accuracy,
counter-arguments, and Singapore regulatory compliance.
"""

from dataclasses import dataclass, field

from kaizen.core.base_agent import BaseAgent

from legalcopilot.agents.signatures import QASignature
from legalcopilot.config import settings


@dataclass
class QAConfig:
    llm_provider: str = field(default_factory=lambda: settings.get("LLM_PROVIDER", "openai"))
    model: str = field(default_factory=lambda: settings.DEFAULT_LLM_MODEL)
    temperature: float = 0.4
    max_tokens: int = 3000
    confidence_threshold: float = 0.85


class QAReviewerAgent(BaseAgent):
    """Quality gate validation with adversarial challenge."""

    def __init__(self, config: QAConfig | None = None):
        config = config or QAConfig()
        super().__init__(config=config, signature=QASignature())
        self.confidence_threshold = config.confidence_threshold

    def review(
        self,
        analysis: str,
        original_query: str,
        case_context: str = "{}",
        quality_threshold: float = 0.0,
    ) -> dict:
        """Review a legal analysis for quality, accuracy, and compliance.

        When quality_threshold is provided (from SOP), it overrides the
        default confidence_threshold for this review cycle.
        Returns verdict: 'pass', 'rework', or 'escalate'.
        """
        effective_threshold = (
            quality_threshold if quality_threshold > 0 else self.confidence_threshold
        )
        result = self.run(
            analysis=analysis,
            original_query=original_query,
            case_context=case_context,
            quality_threshold=str(effective_threshold),
        )
        return result
