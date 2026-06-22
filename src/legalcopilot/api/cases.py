"""Case and Document API endpoints via Nexus.

CRUD operations for legal cases and documents, firm-scoped via tenant isolation.
Document upload triggers the processing pipeline (OCR -> classify -> vectorize).

All handlers execute DataFlow auto-generated workflows via LocalRuntime.
"""

import logging
import uuid

from kailash import LocalRuntime
from nexus import Nexus

from legalcopilot.models.database import db

logger = logging.getLogger(__name__)

MAX_LIMIT = 200

# Cache the workflow dict at module level so db.get_workflows() is called once,
# not per-request.  The dict is populated after DataFlow model registration
# (i.e. after legalcopilot.models.core is imported).
_workflows = None


def _get_workflows() -> dict:
    """Lazily fetch and cache the DataFlow workflow dict."""
    global _workflows
    if _workflows is None:
        _workflows = db.get_workflows()
    return _workflows


def register_case_routes(app: Nexus) -> None:
    """Register case management endpoints on the Nexus app."""

    @app.handler("create_case", description="Create a new legal case")
    async def create_case(
        firm_id: str,
        created_by_id: str,
        title: str,
        practice_area: str = "general",
        case_type: str = "general",
        client_name: str = "",
        description: str = "",
    ) -> dict:
        case_id = str(uuid.uuid4())
        data = {
            "id": case_id,
            "firm_id": firm_id,
            "created_by_id": created_by_id,
            "title": title,
            "practice_area": practice_area,
            "case_type": case_type,
            "status": "open",
            "stage": "intake",
            "priority": "normal",
        }
        if client_name:
            data["client_name"] = client_name
        if description:
            data["description"] = description

        workflows = _get_workflows()
        workflow = workflows["case_create"]
        with LocalRuntime() as runtime:
            results, _run_id = runtime.execute(workflow.build(), inputs={"data": data})
        return results.get("result", data)

    @app.handler("get_case", description="Get a case by ID")
    async def get_case(case_id: str, firm_id: str = "") -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}
        workflows = _get_workflows()
        workflow = workflows["case_read"]
        with LocalRuntime() as runtime:
            results, _run_id = runtime.execute(workflow.build(), inputs={"id": case_id})
        record = results.get("result")
        if record is None or record.get("firm_id") != firm_id:
            return {"error": "Case not found", "id": case_id}
        return record

    @app.handler("list_cases", description="List cases for a firm with filters")
    async def list_cases(
        firm_id: str,
        status: str = "",
        practice_area: str = "",
        assigned_user_id: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        effective_limit = max(1, min(limit, MAX_LIMIT))
        effective_offset = max(0, offset)

        filter_conditions = {"firm_id": firm_id}
        if status:
            filter_conditions["status"] = status
        if practice_area:
            filter_conditions["practice_area"] = practice_area
        if assigned_user_id:
            filter_conditions["assigned_user_id"] = assigned_user_id

        workflows = _get_workflows()
        workflow = workflows["case_list"]
        with LocalRuntime() as runtime:
            results, _run_id = runtime.execute(
                workflow.build(),
                inputs={
                    "filter": filter_conditions,
                    "limit": effective_limit,
                    "offset": effective_offset,
                },
            )
        records = results.get("result", [])
        return {
            "firm_id": firm_id,
            "cases": records,
            "total": len(records),
            "limit": effective_limit,
            "offset": effective_offset,
        }

    @app.handler("update_case", description="Update a case's fields")
    async def update_case(
        case_id: str,
        firm_id: str = "",
        title: str = "",
        status: str = "",
        stage: str = "",
        assigned_user_id: str = "",
        priority: str = "",
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}
        fields = {
            k: v
            for k, v in {
                "title": title,
                "status": status,
                "stage": stage,
                "assigned_user_id": assigned_user_id,
                "priority": priority,
            }.items()
            if v
        }
        if not fields:
            return {"id": case_id, "updated_fields": []}

        # Verify case exists and belongs to this firm before updating
        workflows = _get_workflows()
        read_wf = workflows["case_read"]
        with LocalRuntime() as runtime:
            read_results, _ = runtime.execute(read_wf.build(), inputs={"id": case_id})
        existing = read_results.get("result")
        if existing is None or existing.get("firm_id") != firm_id:
            return {"error": "Case not found", "id": case_id}

        update_wf = workflows["case_update"]
        with LocalRuntime() as runtime:
            results, _run_id = runtime.execute(
                update_wf.build(),
                inputs={
                    "filter": {"id": case_id},
                    "fields": fields,
                },
            )
        record = results.get("result")
        if record is None:
            return {"error": "Case not found", "id": case_id}
        return record


def register_document_routes(app: Nexus) -> None:
    """Register document management endpoints on the Nexus app."""

    @app.handler("upload_document", description="Upload a document to a case")
    async def upload_document(
        case_id: str,
        firm_id: str,
        uploaded_by_id: str,
        filename: str,
        file_type: str = "other",
    ) -> dict:
        # Verify case exists and belongs to this firm before attaching document
        workflows = _get_workflows()
        case_wf = workflows["case_read"]
        with LocalRuntime() as runtime:
            case_results, _ = runtime.execute(case_wf.build(), inputs={"id": case_id})
        case_record = case_results.get("result")
        if case_record is None or case_record.get("firm_id") != firm_id:
            return {"error": "Case not found", "case_id": case_id}

        doc_id = str(uuid.uuid4())
        data = {
            "id": doc_id,
            "case_id": case_id,
            "firm_id": firm_id,
            "uploaded_by_id": uploaded_by_id,
            "filename": filename,
            "file_type": file_type,
            "ocr_status": "pending",
        }

        doc_wf = workflows["document_create"]
        with LocalRuntime() as runtime:
            results, _run_id = runtime.execute(doc_wf.build(), inputs={"data": data})
        return results.get("result", data)

    @app.handler("get_document", description="Get a document by ID")
    async def get_document(document_id: str, firm_id: str = "") -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}
        workflows = _get_workflows()
        workflow = workflows["document_read"]
        with LocalRuntime() as runtime:
            results, _run_id = runtime.execute(workflow.build(), inputs={"id": document_id})
        record = results.get("result")
        if record is None or record.get("firm_id") != firm_id:
            return {"error": "Document not found", "id": document_id}
        return record

    @app.handler("list_documents", description="List documents for a case")
    async def list_documents(
        case_id: str,
        firm_id: str = "",
        file_type: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}
        effective_limit = max(1, min(limit, MAX_LIMIT))
        effective_offset = max(0, offset)

        filter_conditions = {"case_id": case_id, "firm_id": firm_id}
        if file_type:
            filter_conditions["file_type"] = file_type

        workflows = _get_workflows()
        workflow = workflows["document_list"]
        with LocalRuntime() as runtime:
            results, _run_id = runtime.execute(
                workflow.build(),
                inputs={
                    "filter": filter_conditions,
                    "limit": effective_limit,
                    "offset": effective_offset,
                },
            )
        records = results.get("result", [])
        return {
            "case_id": case_id,
            "documents": records,
            "total": len(records),
            "limit": effective_limit,
            "offset": effective_offset,
        }
