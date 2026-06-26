"""Case and Document API endpoints via Nexus.

CRUD operations for legal cases and documents, firm-scoped via tenant isolation.
Document upload triggers the processing pipeline (OCR -> classify -> vectorize).

All handlers execute DataFlow auto-generated workflows via LocalRuntime.
"""

import datetime
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
        if not firm_id:
            return {"error": "firm_id is required"}
        if not title or not title.strip():
            return {"error": "title is required"}

        case_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
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
            "tags": [],
            "metadata": {},
            "created_at": now,
            "updated_at": now,
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
        # DataFlow list workflows may return a total count; fall back to page size
        total = results.get("total", len(records))
        return {
            "firm_id": firm_id,
            "cases": records,
            "total": total,
            "limit": effective_limit,
            "offset": effective_offset,
        }

    @app.handler("update_case", description="Update a case's fields")
    async def update_case(
        case_id: str,
        firm_id: str = "",
        title: str = "",
        status: str = "",
        assigned_user_id: str = "",
        priority: str = "",
        practice_area: str = "",
        case_type: str = "",
        client_name: str = "",
        opposing_party: str = "",
        court: str = "",
        description: str = "",
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}
        # Note: "stage" is deliberately excluded — stage transitions must go
        # through the transition_stage handler which validates the transition.
        fields = {
            k: v
            for k, v in {
                "title": title,
                "status": status,
                "assigned_user_id": assigned_user_id,
                "priority": priority,
                "practice_area": practice_area,
                "case_type": case_type,
                "client_name": client_name,
                "opposing_party": opposing_party,
                "court": court,
                "description": description,
            }.items()
            if v is not None and v != ""
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
        content_text: str = "",
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
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        data = {
            "id": doc_id,
            "case_id": case_id,
            "firm_id": firm_id,
            "uploaded_by_id": uploaded_by_id,
            "filename": filename,
            "file_type": file_type,
            "ocr_status": "pending",
            "storage_url": "",
            "file_size_bytes": 0,
            "classification": {},
            "metadata": {},
            "created_at": now,
            "updated_at": now,
        }

        doc_wf = workflows["document_create"]
        with LocalRuntime() as runtime:
            results, _run_id = runtime.execute(doc_wf.build(), inputs={"data": data})
        doc_record = results.get("result", data)

        # Trigger the document processing pipeline if real text content is provided.
        # Documents without content_text stay at ocr_status: "pending" until
        # real OCR is integrated (future MCP tool).
        if content_text:
            from legalcopilot.services.document_processor import process_document

            try:
                process_result = process_document(
                    document_id=doc_id,
                    case_id=case_id,
                    firm_id=firm_id,
                    text=content_text,
                )
                doc_record["processing"] = process_result
            except Exception:
                logger.exception("Document processing failed for %s", doc_id)
                doc_record["processing"] = {"status": "failed"}

        return doc_record

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
        total = results.get("total", len(records))
        return {
            "case_id": case_id,
            "documents": records,
            "total": total,
            "limit": effective_limit,
            "offset": effective_offset,
        }

    @app.handler("get_upload_url", description="Get a presigned URL for document upload")
    async def get_upload_url(
        case_id: str,
        firm_id: str,
        filename: str,
        content_type: str = "application/pdf",
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}

        # Verify case belongs to this firm
        workflows = _get_workflows()
        case_wf = workflows["case_read"]
        with LocalRuntime() as runtime:
            case_results, _ = runtime.execute(case_wf.build(), inputs={"id": case_id})
        case_record = case_results.get("result")
        if case_record is None or case_record.get("firm_id") != firm_id:
            return {"error": "Case not found", "case_id": case_id}

        from legalcopilot.services.storage import generate_presigned_upload_url, StorageError

        try:
            result = generate_presigned_upload_url(case_id, filename, firm_id, content_type)
            return result
        except StorageError:
            logger.exception("Upload URL generation failed for case %s", case_id)
            return {"error": "Failed to generate upload URL"}

    @app.handler("confirm_upload", description="Confirm a file upload and trigger processing")
    async def confirm_upload(
        case_id: str,
        firm_id: str,
        uploaded_by_id: str,
        filename: str,
        storage_key: str,
        file_type: str = "other",
        content_type: str = "application/pdf",
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}

        # Verify case belongs to this firm
        workflows = _get_workflows()
        case_wf = workflows["case_read"]
        with LocalRuntime() as runtime:
            case_results, _ = runtime.execute(case_wf.build(), inputs={"id": case_id})
        case_record = case_results.get("result")
        if case_record is None or case_record.get("firm_id") != firm_id:
            return {"error": "Case not found", "case_id": case_id}

        from legalcopilot.services.storage import download_file, StorageError, use_s3
        from legalcopilot.services.file_extractor import extract_text

        # Validate storage_key: must start with firm_id/case_id/ and contain no traversal
        expected_prefix = f"{firm_id}/{case_id}/"
        if not storage_key.startswith(expected_prefix) or ".." in storage_key:
            return {"error": "Invalid storage key"}

        # Determine storage URL
        if use_s3():
            from legalcopilot.config import settings as cfg

            storage_url = f"s3://{cfg.S3_BUCKET}/{storage_key}"
        else:
            storage_url = f"local://{storage_key}"

        # Create document record
        doc_id = str(uuid.uuid4())
        data = {
            "id": doc_id,
            "case_id": case_id,
            "firm_id": firm_id,
            "uploaded_by_id": uploaded_by_id,
            "filename": filename,
            "file_type": file_type,
            "storage_url": storage_url,
            "ocr_status": "processing",
        }

        doc_wf = workflows["document_create"]
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(doc_wf.build(), inputs={"data": data})
        doc_record = results.get("result", data)

        # Download file, extract text, and process
        try:
            file_bytes = download_file(storage_url)
            doc_record["file_size_bytes"] = len(file_bytes)

            # Update file size
            update_wf = workflows["document_update"]
            with LocalRuntime() as runtime:
                runtime.execute(
                    update_wf.build(),
                    inputs={
                        "filter": {"id": doc_id, "firm_id": firm_id},
                        "fields": {"file_size_bytes": len(file_bytes)},
                    },
                )

            text = extract_text(file_bytes, filename)

            if text:
                from legalcopilot.services.document_processor import process_document

                process_result = process_document(
                    document_id=doc_id,
                    case_id=case_id,
                    firm_id=firm_id,
                    text=text,
                )
                doc_record["processing"] = process_result
            else:
                # No text extracted — mark complete with no text
                with LocalRuntime() as runtime:
                    runtime.execute(
                        update_wf.build(),
                        inputs={
                            "filter": {"id": doc_id, "firm_id": firm_id},
                            "fields": {"ocr_status": "complete", "ocr_text": ""},
                        },
                    )
                doc_record["processing"] = {
                    "status": "complete",
                    "chunk_count": 0,
                    "vector_count": 0,
                }
        except StorageError:
            logger.exception("Failed to process upload %s", doc_id)
            doc_record["processing"] = {
                "status": "failed",
                "error": "Storage error during processing",
            }
            update_wf = workflows["document_update"]
            with LocalRuntime() as runtime:
                runtime.execute(
                    update_wf.build(),
                    inputs={
                        "filter": {"id": doc_id, "firm_id": firm_id},
                        "fields": {"ocr_status": "failed"},
                    },
                )
        except Exception:
            logger.exception("Failed to process upload %s", doc_id)
            doc_record["processing"] = {"status": "failed"}
            try:
                update_wf = workflows["document_update"]
                with LocalRuntime() as runtime:
                    runtime.execute(
                        update_wf.build(),
                        inputs={
                            "filter": {"id": doc_id, "firm_id": firm_id},
                            "fields": {"ocr_status": "failed"},
                        },
                    )
            except Exception:
                logger.exception("Failed to update ocr_status for %s", doc_id)

        return doc_record

    @app.handler("get_download_url", description="Get a download URL for a document")
    async def get_download_url(document_id: str, firm_id: str = "") -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}

        workflows = _get_workflows()
        workflow = workflows["document_read"]
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(workflow.build(), inputs={"id": document_id})
        record = results.get("result")
        if record is None or record.get("firm_id") != firm_id:
            return {"error": "Document not found", "id": document_id}

        storage_url = record.get("storage_url", "")
        if not storage_url:
            return {"error": "No file stored for this document", "id": document_id}

        from legalcopilot.services.storage import generate_presigned_download_url

        download_url = generate_presigned_download_url(storage_url)
        return {
            "document_id": document_id,
            "download_url": download_url,
            "filename": record.get("filename", ""),
        }

    @app.handler("retry_document_processing", description="Retry failed document processing")
    async def retry_document_processing(document_id: str, firm_id: str = "") -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}

        workflows = _get_workflows()
        workflow = workflows["document_read"]
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(workflow.build(), inputs={"id": document_id})
        record = results.get("result")
        if record is None or record.get("firm_id") != firm_id:
            return {"error": "Document not found", "id": document_id}

        if record.get("ocr_status") != "failed":
            return {
                "error": "Document is not in failed state",
                "id": document_id,
                "current_status": record.get("ocr_status"),
            }

        storage_url = record.get("storage_url", "")
        if not storage_url:
            return {"error": "No file stored — cannot retry processing", "id": document_id}

        from legalcopilot.services.storage import download_file, StorageError
        from legalcopilot.services.file_extractor import extract_text
        from legalcopilot.services.document_processor import process_document

        try:
            file_bytes = download_file(storage_url)
            text = extract_text(file_bytes, record.get("filename", ""))

            if not text:
                return {"error": "Could not extract text from file", "id": document_id}

            result = process_document(
                document_id=document_id,
                case_id=record["case_id"],
                firm_id=firm_id,
                text=text,
            )
            return {"document_id": document_id, "processing": result}
        except StorageError:
            logger.exception("Retry storage error for %s", document_id)
            return {"error": "Storage error during reprocessing", "id": document_id}
        except Exception:
            logger.exception("Retry processing failed for %s", document_id)
            return {"error": "Processing failed", "id": document_id}
