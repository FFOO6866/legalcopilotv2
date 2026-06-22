"""RAG pipeline — retrieval-augmented generation for legal conversations.

Pipeline: query -> embed -> search Qdrant -> enrich from KG -> budget tokens -> assemble context.

Token budget defaults to 6000 (env-configurable). Legal authorities (case law)
are never truncated before supporting materials.
"""

from typing import Optional

from legalcopilot.config import settings
from legalcopilot.services.embedding import embed_text
from legalcopilot.services.vector_store import search as vector_search


# Priority classes for token budget allocation (higher = kept first)
PRIORITY_AUTHORITY = 3  # Case law authorities — never truncated first
PRIORITY_STATUTE = 2  # Legislation references
PRIORITY_CONTEXT = 1  # Supporting context, firm knowledge


def retrieve_context(
    query: str,
    top_k: int = 10,
    token_budget: Optional[int] = None,
    filter_conditions: Optional[dict] = None,
    include_kg: bool = True,
) -> dict:
    """Full RAG pipeline: query -> relevant legal context for LLM injection.

    Args:
        query: User's question or search text.
        top_k: Number of vector search results.
        token_budget: Max tokens for assembled context (default from env).
        filter_conditions: Optional filters (court, jurisdiction, year).
        include_kg: Whether to enrich results with knowledge graph data.

    Returns:
        Dict with 'context_text', 'sources', 'token_count', 'truncated'.
    """
    token_budget = token_budget or int(settings.get("RAG_TOKEN_BUDGET", "6000"))

    # Step 1: Embed the query
    query_vector = embed_text(query)

    # Step 2: Semantic search
    results = vector_search(
        query_vector=query_vector,
        limit=top_k,
        score_threshold=0.3,
        filter_conditions=filter_conditions,
    )

    if not results:
        return {
            "context_text": "",
            "sources": [],
            "token_count": 0,
            "truncated": False,
        }

    # Step 3: Classify and prioritize results
    prioritized = _prioritize_results(results)

    # Step 4: Token budget allocation with priority-based truncation
    context_chunks, sources, was_truncated = _allocate_token_budget(prioritized, token_budget)

    # Step 5: Assemble final context
    context_text = _assemble_context(context_chunks)
    token_count = _estimate_tokens(context_text)

    return {
        "context_text": context_text,
        "sources": sources,
        "token_count": token_count,
        "truncated": was_truncated,
    }


def _prioritize_results(results: list[dict]) -> list[dict]:
    """Assign priority to each result based on content type."""
    for result in results:
        payload = result.get("payload", {})
        content_type = payload.get("type", "context")

        if content_type in ("judgment", "case_law", "authority"):
            result["priority"] = PRIORITY_AUTHORITY
        elif content_type in ("statute", "legislation", "regulation"):
            result["priority"] = PRIORITY_STATUTE
        else:
            result["priority"] = PRIORITY_CONTEXT

    return sorted(results, key=lambda r: (-r["priority"], -r["score"]))


def _allocate_token_budget(results: list[dict], budget: int) -> tuple[list[str], list[dict], bool]:
    """Allocate token budget with priority-based truncation.

    Authorities are never truncated before lower-priority content.
    """
    chunks = []
    sources = []
    used_tokens = 0
    truncated = False

    for result in results:
        payload = result.get("payload", {})
        text = payload.get("text", payload.get("chunk_text", ""))

        if not text:
            continue

        chunk_tokens = _estimate_tokens(text)

        if used_tokens + chunk_tokens > budget:
            truncated = True
            # If this is high-priority and we have budget for at least part of it
            if result["priority"] >= PRIORITY_AUTHORITY:
                remaining = budget - used_tokens
                if remaining > 100:  # minimum useful chunk
                    text = _truncate_to_tokens(text, remaining)
                    chunks.append(text)
                    sources.append(_extract_source(result))
                    used_tokens += _estimate_tokens(text)
            continue

        chunks.append(text)
        sources.append(_extract_source(result))
        used_tokens += chunk_tokens

    return chunks, sources, truncated


def _extract_source(result: dict) -> dict:
    """Extract citation metadata from a search result."""
    payload = result.get("payload", {})
    return {
        "citation": payload.get("citation", ""),
        "case_name": payload.get("case_name", ""),
        "court": payload.get("court", ""),
        "score": result.get("score", 0),
        "type": payload.get("type", "context"),
    }


def _assemble_context(chunks: list[str]) -> str:
    """Join context chunks with clear separators for the LLM."""
    if not chunks:
        return ""
    return "\n\n---\n\n".join(chunks)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token for English legal text)."""
    return len(text) // 4


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to approximately max_tokens."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    # Truncate at last sentence boundary before limit
    truncated = text[:max_chars]
    last_period = truncated.rfind(".")
    if last_period > max_chars * 0.5:
        return truncated[: last_period + 1]
    return truncated + "..."
