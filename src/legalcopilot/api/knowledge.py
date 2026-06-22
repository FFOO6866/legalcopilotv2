"""Knowledge graph and legal research API endpoints via Nexus.

Provides citation network traversal, judge queries, statute lookup,
and research endpoints combining RAG with knowledge graph data.
"""

import logging

from kailash import LocalRuntime
from nexus import Nexus

from legalcopilot.models.database import db
from legalcopilot.services.pii_filter import redact_pii
from legalcopilot.services.rag_pipeline import retrieve_context
from legalcopilot.services.sop_service import get_sop_template, list_sop_templates

logger = logging.getLogger(__name__)

# Maximum citation traversal depth to prevent runaway queries on the 215K-edge graph.
_MAX_CITATION_DEPTH = 3
_MAX_LIMIT = 200
_VALID_DIRECTIONS = {"citing", "cited_by", "both"}


def _run_workflow(workflow_name: str, inputs: dict) -> dict:
    """Execute a DataFlow workflow by name and return results.

    Returns an empty dict when the workflow is unavailable or execution fails,
    so callers degrade gracefully instead of raising to the user.
    """
    try:
        workflows = db.get_workflows()
        wf = workflows.get(workflow_name)
        if wf is None:
            logger.warning("Workflow %s not found in DataFlow registry", workflow_name)
            return {}
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(wf.build(), inputs=inputs)
        return results or {}
    except Exception:
        logger.exception("Workflow %s execution failed", workflow_name)
        return {}


def _collect_citations_at_depth(
    entry_ids: set[str],
    direction: str,
    remaining_depth: int,
    seen_citing: set[str],
    seen_cited_by: set[str],
    all_citing: list[dict],
    all_cited_by: list[dict],
) -> None:
    """Recursively collect citation edges up to *remaining_depth* hops.

    *entry_ids* is the frontier of IDs to expand on this hop.
    *seen_citing* / *seen_cited_by* track already-visited edge IDs to avoid
    duplicates when the same case appears at multiple depths.
    """
    if remaining_depth <= 0 or not entry_ids:
        return

    next_frontier: set[str] = set()

    for entry_id in entry_ids:
        if direction in ("citing", "both"):
            results = _run_workflow(
                "kgcitationedge_list",
                {"filters": {"citing_id": entry_id}, "limit": 200},
            )
            for edge in results.get("items", results.get("result", [])):
                eid = edge.get("id", "")
                if eid and eid not in seen_citing:
                    seen_citing.add(eid)
                    all_citing.append(edge)
                    cited = edge.get("cited_id")
                    if cited:
                        next_frontier.add(cited)

        if direction in ("cited_by", "both"):
            results = _run_workflow(
                "kgcitationedge_list",
                {"filters": {"cited_id": entry_id}, "limit": 200},
            )
            for edge in results.get("items", results.get("result", [])):
                eid = edge.get("id", "")
                if eid and eid not in seen_cited_by:
                    seen_cited_by.add(eid)
                    all_cited_by.append(edge)
                    citing = edge.get("citing_id")
                    if citing:
                        next_frontier.add(citing)

    _collect_citations_at_depth(
        next_frontier,
        direction,
        remaining_depth - 1,
        seen_citing,
        seen_cited_by,
        all_citing,
        all_cited_by,
    )


def register_knowledge_routes(app: Nexus) -> None:
    """Register knowledge graph and research endpoints on the Nexus app."""

    @app.handler("search_cases", description="Semantic search over the legal knowledge base")
    async def search_cases(
        query: str,
        jurisdiction: str = "SG",
        court: str = "",
        year_from: int = 0,
        year_to: int = 0,
        limit: int = 10,
    ) -> dict:
        limit = max(1, min(limit, _MAX_LIMIT))
        filter_conditions = {}
        if jurisdiction:
            filter_conditions["jurisdiction"] = jurisdiction
        if court:
            filter_conditions["court"] = court
        if year_from:
            filter_conditions["year_from"] = year_from
        if year_to:
            filter_conditions["year_to"] = year_to

        clean_query = redact_pii(query)
        result = retrieve_context(
            query=clean_query,
            top_k=limit,
            filter_conditions=filter_conditions if filter_conditions else None,
        )
        return {
            "query": query,
            "results": result["sources"],
            "context": result["context_text"][:500] if result["context_text"] else "",
            "total": len(result["sources"]),
            "truncated": result["truncated"],
        }

    @app.handler("get_citations", description="Get citation network for a case")
    async def get_citations(
        entry_id: str,
        direction: str = "both",
        depth: int = 1,
    ) -> dict:
        if direction not in _VALID_DIRECTIONS:
            return {
                "error": f"Invalid direction. Must be one of: {', '.join(sorted(_VALID_DIRECTIONS))}"
            }
        effective_depth = max(1, min(depth, _MAX_CITATION_DEPTH))

        all_citing: list[dict] = []
        all_cited_by: list[dict] = []

        _collect_citations_at_depth(
            entry_ids={entry_id},
            direction=direction,
            remaining_depth=effective_depth,
            seen_citing=set(),
            seen_cited_by=set(),
            all_citing=all_citing,
            all_cited_by=all_cited_by,
        )

        return {
            "entry_id": entry_id,
            "direction": direction,
            "depth": effective_depth,
            "citing": all_citing,
            "cited_by": all_cited_by,
        }

    @app.handler("get_judge_profile", description="Get judge profile and case history")
    async def get_judge_profile(judge_id: str) -> dict:
        # Fetch the judge record
        judge_result = _run_workflow("kgjudge_read", {"id": judge_id})
        judge = judge_result.get("result", judge_result) if judge_result else {}

        # Fetch the cases this judge presided over
        cases_result = _run_workflow(
            "kgcasejudge_list",
            {"filters": {"judge_id": judge_id}, "limit": 500},
        )
        cases = cases_result.get("items", cases_result.get("result", []))
        if not isinstance(cases, list):
            cases = []

        return {
            "judge_id": judge_id,
            "name": judge.get("name", ""),
            "court": judge.get("court", ""),
            "title": judge.get("title", ""),
            "cases": cases,
            "total_cases": len(cases),
        }

    @app.handler("search_legislation", description="Search legislation references")
    async def search_legislation(
        statute_name: str = "",
        section: str = "",
        query: str = "",
    ) -> dict:
        filters: dict = {}
        if statute_name:
            filters["statute_name"] = statute_name
        if section:
            filters["section"] = section

        inputs: dict = {"limit": 100}
        if filters:
            inputs["filters"] = filters
        if query:
            inputs["search"] = query

        results = _run_workflow("kglegislationref_list", inputs)
        references = results.get("items", results.get("result", []))
        if not isinstance(references, list):
            references = []

        return {
            "statute_name": statute_name,
            "section": section,
            "references": references,
            "total": len(references),
        }

    @app.handler("legal_research", description="Full legal research combining RAG and KG")
    async def legal_research(
        query: str,
        jurisdiction: str = "SG",
        practice_area: str = "general",
        include_statutes: bool = True,
        include_cases: bool = True,
    ) -> dict:
        clean_query = redact_pii(query)
        result = retrieve_context(query=clean_query, top_k=15)

        statutes: list = []
        if include_statutes:
            statute_results = _run_workflow(
                "kglegislationref_list",
                {"search": query, "limit": 20},
            )
            refs = statute_results.get("items", statute_results.get("result", []))
            if isinstance(refs, list):
                statutes = refs

        return {
            "query": query,
            "jurisdiction": jurisdiction,
            "practice_area": practice_area,
            "cases": result["sources"] if include_cases else [],
            "statutes": statutes,
            "context": result["context_text"],
            "token_count": result["token_count"],
        }

    @app.handler("get_sop_template", description="Get SOP template for a case type")
    async def get_sop(case_type: str) -> dict:
        return get_sop_template(case_type)

    @app.handler("list_sop_templates", description="List available SOP templates")
    async def list_sops(practice_area: str = "") -> dict:
        templates = list_sop_templates(practice_area)
        return {
            "templates": templates,
            "total": len(templates),
            "practice_area": practice_area or "all",
        }
