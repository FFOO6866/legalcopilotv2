"""Research agent — legal research, precedent search, authority scoring.

Kaizen BaseAgent with ResearchSignature. Combines RAG (vector search)
with knowledge graph traversal for comprehensive legal research.
"""

from dataclasses import dataclass, field

from kaizen.core.base_agent import BaseAgent

from legalcopilot.agents.signatures import ResearchSignature
from legalcopilot.config import settings
from legalcopilot.services.pii_filter import redact_pii
from legalcopilot.services.rag_pipeline import retrieve_context


@dataclass
class ResearchConfig:
    llm_provider: str = field(default_factory=lambda: settings.get("LLM_PROVIDER", "openai"))
    model: str = field(default_factory=lambda: settings.DEFAULT_LLM_MODEL)
    temperature: float = 0.2
    max_tokens: int = 4000
    top_k: int = 10


class ResearchAgent(BaseAgent):
    """Legal research combining semantic search and knowledge graph."""

    def __init__(self, config: ResearchConfig | None = None):
        config = config or ResearchConfig()
        super().__init__(config=config, signature=ResearchSignature())
        self.top_k = config.top_k

    def research(
        self,
        query: str,
        jurisdiction: str = "SG",
        practice_area: str = "general",
    ) -> dict:
        """Perform legal research — retrieves RAG context then analyzes.

        Automatically calls the RAG pipeline to retrieve relevant case law
        before invoking the LLM for analysis.
        """
        clean_query = redact_pii(query)

        # Use PII-redacted query for both RAG search and LLM
        rag_result = retrieve_context(
            query=clean_query,
            top_k=self.top_k,
            filter_conditions={"jurisdiction": jurisdiction} if jurisdiction != "all" else None,
        )
        result = self.run(
            query=clean_query,
            jurisdiction=jurisdiction,
            practice_area=practice_area,
            rag_context=rag_result["context_text"],
        )
        result["rag_sources"] = rag_result["sources"]
        return result
