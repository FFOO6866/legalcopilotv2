"""FirmKnowledge API endpoints via Nexus.

CRUD operations for firm-specific knowledge (precedents, playbooks, templates).
All operations are firm-scoped for tenant isolation. Creating knowledge
automatically embeds and upserts to Qdrant for RAG integration.
"""

import logging
import uuid

from kailash import LocalRuntime
from nexus import Nexus

from legalcopilot.models.database import db
from legalcopilot.services.embedding import embed_text
from legalcopilot.services.vector_store import (
    delete_by_payload,
    ensure_collection,
    upsert_vectors,
)

logger = logging.getLogger(__name__)

_MAX_LIMIT = 200
_MAX_CONTENT_LENGTH = 100_000
_MAX_TITLE_LENGTH = 500
_VALID_CATEGORIES = frozenset(
    {
        "precedent",
        "playbook",
        "template",
        "policy",
        "training",
        "other",
    }
)
_workflows = None


def _get_workflows() -> dict:
    global _workflows
    if _workflows is None:
        _workflows = db.get_workflows()
    return _workflows


def _embed_and_upsert_firm_knowledge(
    knowledge_id: str, firm_id: str, title: str, content: str
) -> str:
    """Embed firm knowledge content and upsert to Qdrant.

    Returns the Qdrant point ID.
    """
    ensure_collection()

    # Combine title and content for richer embedding
    text_to_embed = f"{title}\n\n{content}"
    vector = embed_text(text_to_embed)

    point_id = str(uuid.uuid4())
    upsert_vectors(
        [
            {
                "id": point_id,
                "vector": vector,
                "payload": {
                    "knowledge_id": knowledge_id,
                    "firm_id": firm_id,
                    "type": "firm_knowledge",
                    "text": text_to_embed[:5000],  # cap payload text
                },
            }
        ]
    )
    return point_id


def register_firm_knowledge_routes(app: Nexus) -> None:
    """Register firm knowledge CRUD endpoints on the Nexus app."""

    @app.handler(
        "create_firm_knowledge",
        description="Create firm-specific knowledge entry with auto-embedding",
    )
    async def create_firm_knowledge(
        firm_id: str,
        title: str,
        category: str,
        content: str = "",
    ) -> dict:
        if len(title) > _MAX_TITLE_LENGTH:
            return {"error": f"Title exceeds maximum length ({_MAX_TITLE_LENGTH} characters)"}
        if content and len(content) > _MAX_CONTENT_LENGTH:
            return {"error": f"Content exceeds maximum length ({_MAX_CONTENT_LENGTH} characters)"}
        if category not in _VALID_CATEGORIES:
            return {
                "error": f"Invalid category. Must be one of: {', '.join(sorted(_VALID_CATEGORIES))}"
            }

        knowledge_id = str(uuid.uuid4())

        # Embed and upsert to Qdrant if there is meaningful content
        qdrant_point_id = ""
        warnings = []
        if content and len(content) >= 50:
            try:
                qdrant_point_id = _embed_and_upsert_firm_knowledge(
                    knowledge_id, firm_id, title, content
                )
            except Exception:
                logger.exception("Failed to embed firm knowledge %s", knowledge_id)
                warnings.append(
                    "Embedding failed — content saved but will not appear "
                    "in search results until re-indexed"
                )

        data = {
            "id": knowledge_id,
            "firm_id": firm_id,
            "title": title,
            "category": category,
            "content": content,
            "qdrant_point_id": qdrant_point_id,
            "is_active": True,
        }

        workflows = _get_workflows()
        wf = workflows["firmknowledge_create"]
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(wf.build(), inputs={"data": data})
        record = results.get("result", data)
        if warnings:
            record["warnings"] = warnings
        return record

    @app.handler(
        "list_firm_knowledge",
        description="List firm-specific knowledge entries (firm-scoped)",
    )
    async def list_firm_knowledge(
        firm_id: str,
        category: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        effective_limit = max(1, min(limit, _MAX_LIMIT))
        effective_offset = max(0, offset)

        filter_conditions = {"firm_id": firm_id, "is_active": True}
        if category:
            filter_conditions["category"] = category

        workflows = _get_workflows()
        wf = workflows["firmknowledge_list"]
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(
                wf.build(),
                inputs={
                    "filter": filter_conditions,
                    "limit": effective_limit,
                    "offset": effective_offset,
                },
            )
        records = results.get("result", [])
        return {
            "firm_id": firm_id,
            "knowledge": records,
            "total": len(records),
            "limit": effective_limit,
            "offset": effective_offset,
        }

    @app.handler(
        "get_firm_knowledge",
        description="Get a firm knowledge entry by ID (firm-scoped)",
    )
    async def get_firm_knowledge(knowledge_id: str, firm_id: str) -> dict:
        workflows = _get_workflows()
        wf = workflows["firmknowledge_read"]
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(wf.build(), inputs={"id": knowledge_id})
        record = results.get("result")
        if record is None or record.get("firm_id") != firm_id:
            return {"error": "Knowledge entry not found", "id": knowledge_id}
        return record

    @app.handler(
        "delete_firm_knowledge",
        description="Delete a firm knowledge entry and remove from Qdrant",
    )
    async def delete_firm_knowledge(knowledge_id: str, firm_id: str) -> dict:
        # Verify ownership
        workflows = _get_workflows()
        read_wf = workflows["firmknowledge_read"]
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(read_wf.build(), inputs={"id": knowledge_id})
        record = results.get("result")
        if record is None or record.get("firm_id") != firm_id:
            return {"error": "Knowledge entry not found", "id": knowledge_id}

        # Remove from Qdrant
        vector_cleanup_ok = True
        try:
            delete_by_payload("knowledge_id", knowledge_id)
        except Exception:
            logger.warning("Failed to delete vectors for knowledge %s", knowledge_id)
            vector_cleanup_ok = False

        # Soft-delete via DataFlow (is_active = False)
        update_wf = workflows["firmknowledge_update"]
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(
                update_wf.build(),
                inputs={
                    "filter": {"id": knowledge_id, "firm_id": firm_id},
                    "fields": {"is_active": False},
                },
            )
        result = {"deleted": True, "id": knowledge_id}
        if not vector_cleanup_ok:
            result["warnings"] = [
                "Vector cleanup failed — content may still appear in search " "results temporarily"
            ]
        return result
