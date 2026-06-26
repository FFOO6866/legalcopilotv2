"""RAG pipeline — retrieval-augmented generation for legal conversations.

Pipeline: query -> embed -> search Qdrant -> enrich from KG -> budget tokens -> assemble context.

Token budget defaults to 6000 (env-configurable). Legal authorities (case law)
are never truncated before supporting materials.
"""

import logging
from typing import Optional

from legalcopilot.config import settings
from legalcopilot.models.database import db
from legalcopilot.services.embedding import embed_text
from legalcopilot.services.vector_store import search as vector_search

logger = logging.getLogger(__name__)

# Priority classes for token budget allocation (higher = kept first)
PRIORITY_AUTHORITY = 3  # Case law authorities — never truncated first
PRIORITY_STATUTE = 2  # Legislation references
PRIORITY_CONTEXT = 1  # Supporting context, firm knowledge

# Citation treatments that indicate a case may no longer be good law
_ADVERSE_TREATMENTS = frozenset({"overruled", "not_followed", "distinguished"})


def retrieve_context(
    query: str,
    top_k: int = 10,
    token_budget: Optional[int] = None,
    filter_conditions: Optional[dict] = None,
    include_kg: bool = True,
    firm_id: Optional[str] = None,
) -> dict:
    """Full RAG pipeline: query -> relevant legal context for LLM injection.

    Args:
        query: User's question or search text.
        top_k: Number of vector search results.
        token_budget: Max tokens for assembled context (default from env).
        filter_conditions: Optional filters (court, jurisdiction, year).
        include_kg: Whether to enrich results with knowledge graph data
            (citation treatment annotations — flags overruled cases).
        firm_id: Optional firm ID — when provided, also searches firm-specific
            knowledge vectors and merges them with public results.

    Returns:
        Dict with 'context_text', 'sources', 'token_count', 'truncated'.
    """
    token_budget = token_budget or int(settings.get("RAG_TOKEN_BUDGET", "6000"))

    # Step 1: Embed the query
    try:
        query_vector = embed_text(query)
    except Exception:
        logger.warning("Embedding service unavailable, returning empty context")
        return {
            "context_text": "",
            "sources": [],
            "token_count": 0,
            "truncated": False,
        }

    # Step 2: Semantic search (public knowledge base)
    try:
        results = vector_search(
            query_vector=query_vector,
            limit=top_k,
            score_threshold=0.3,
            filter_conditions=filter_conditions,
        )
    except Exception:
        logger.warning("Vector search unavailable (Qdrant down?), returning empty context")
        return {
            "context_text": "",
            "sources": [],
            "token_count": 0,
            "truncated": False,
        }

    # Exclude firm-private vectors from public results (tenant isolation)
    if not firm_id:
        results = [r for r in results if r.get("payload", {}).get("type") != "firm_knowledge"]

    # Step 2b: Merge firm-specific knowledge if firm_id provided
    if firm_id:
        firm_limit = max(3, top_k // 3)
        firm_results = vector_search(
            query_vector=query_vector,
            limit=firm_limit,
            score_threshold=0.3,
            filter_conditions={"firm_id": firm_id, "type": "firm_knowledge"},
        )
        results = _merge_results(results, firm_results, top_k)

    if not results:
        return {
            "context_text": "",
            "sources": [],
            "token_count": 0,
            "truncated": False,
        }

    # Step 3: Enrich with knowledge graph data (citation treatment)
    if include_kg:
        results = _enrich_with_kg(results)

    # Step 4: Classify and prioritize results
    prioritized = _prioritize_results(results)

    # Step 5: Token budget allocation with priority-based truncation
    context_chunks, sources, was_truncated = _allocate_token_budget(prioritized, token_budget)

    # Step 6: Assemble final context
    context_text = _assemble_context(context_chunks)
    token_count = _estimate_tokens(context_text)

    return {
        "context_text": context_text,
        "sources": sources,
        "token_count": token_count,
        "truncated": was_truncated,
    }


def _merge_results(
    public_results: list[dict], firm_results: list[dict], max_total: int
) -> list[dict]:
    """Merge public and firm-specific results, deduplicated and sorted by score."""
    seen_ids = set()
    merged = []

    # Combine both lists sorted by score descending
    all_results = sorted(
        public_results + firm_results, key=lambda r: r.get("score", 0), reverse=True
    )
    for result in all_results:
        rid = result.get("id", "")
        if rid and rid in seen_ids:
            continue
        seen_ids.add(rid)
        merged.append(result)
        if len(merged) >= max_total:
            break

    return merged


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

        # Budget is calculated on original text so treatment warnings
        # don't penalize adversely-treated authorities in priority ranking
        chunk_tokens = _estimate_tokens(text)

        # Prepend treatment warning so the LLM sees adverse citation status
        treatment_warning = result.get("treatment_warning", "")
        if treatment_warning:
            text = f"[{treatment_warning}]\n\n{text}"

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


def _enrich_with_kg(results: list[dict]) -> list[dict]:
    """Enrich vector search results with citation treatment data from KG.

    Queries the KGCitationEdge model to check if any retrieved case has been
    overruled, not followed, or distinguished by later decisions. Annotates
    results with treatment warnings so the LLM and user are informed.
    """
    try:
        workflows = db.get_workflows()
        list_wf = workflows.get("kgcitationedge_list")
        if list_wf is None:
            logger.debug("kgcitationedge_list workflow not available, skipping KG enrichment")
            return results
    except Exception:
        logger.debug("Could not load KG workflows, skipping enrichment")
        return results

    from kailash import LocalRuntime

    try:
        with LocalRuntime() as runtime:
            for result in results:
                payload = result.get("payload", {})
                entry_id = payload.get("entry_id", "")
                if not entry_id:
                    continue

                try:
                    edge_results, _ = runtime.execute(
                        list_wf.build(),
                        inputs={
                            "filter": {"cited_id": entry_id},
                            "limit": 50,
                            "offset": 0,
                        },
                    )
                    edges = edge_results.get("result", [])
                    if not edges:
                        continue

                    treatments = [e.get("treatment", "cited") for e in edges]
                    adverse = [t for t in treatments if t in _ADVERSE_TREATMENTS]

                    if adverse:
                        result["treatment_warning"] = (
                            f"WARNING: This authority has been {', '.join(set(adverse))} "
                            f"by later decisions ({len(adverse)} adverse treatment(s) found)."
                        )
                    result["citation_treatments"] = treatments
                except Exception:
                    logger.debug("KG enrichment failed for entry %s, continuing", entry_id)
    except Exception:
        logger.debug("LocalRuntime init failed for KG enrichment, skipping")

    return results


def _extract_source(result: dict) -> dict:
    """Extract citation metadata from a search result."""
    payload = result.get("payload", {})
    source = {
        "citation": payload.get("citation", ""),
        "case_name": payload.get("case_name", ""),
        "court": payload.get("court", ""),
        "score": result.get("score", 0),
        "type": payload.get("type", "context"),
    }
    if result.get("treatment_warning"):
        source["treatment_warning"] = result["treatment_warning"]
    if result.get("citation_treatments"):
        source["citation_treatments"] = result["citation_treatments"]
    return source


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
