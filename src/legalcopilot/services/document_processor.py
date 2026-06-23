"""Document processing pipeline — chunk, embed, and vectorize uploaded documents.

Implements the missing pipeline that moves documents from ocr_status: "pending"
to "complete" by chunking text, generating embeddings, and upserting to Qdrant.

Invariants:
  - Chunk size 1000 chars with 200 overlap (word-boundary aware)
  - 1536-dim embeddings (text-embedding-3-small)
  - Status transitions: pending -> processing -> complete | failed
  - Qdrant payload: {document_id, case_id, firm_id, chunk_index, type: "document"}
"""

import logging
import uuid

from kailash import LocalRuntime

from legalcopilot.models.database import db
from legalcopilot.services.embedding import embed_batch
from legalcopilot.services.vector_store import (
    delete_by_payload,
    ensure_collection,
    upsert_vectors,
)

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBED_BATCH_SIZE = 100
MIN_TEXT_LENGTH = 50
MAX_OCR_TEXT_CHARS = 50_000

_workflows = None


def _get_workflows() -> dict:
    global _workflows
    if _workflows is None:
        _workflows = db.get_workflows()
    return _workflows


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, breaking at word boundaries."""
    if not text or not text.strip():
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size

        # Break at word boundary if not at the end of text
        if end < text_len:
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary + 1  # include the space

        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        if end >= text_len:
            break
        start = end - overlap

    return chunks


def _delete_document_vectors(document_id: str) -> None:
    """Delete all existing vectors for a document (idempotency cleanup)."""
    try:
        delete_by_payload("document_id", document_id)
    except Exception:
        logger.warning("Failed to delete existing vectors for document %s", document_id)


def _embed_and_upsert(
    chunks: list[str],
    document_id: str,
    case_id: str,
    firm_id: str,
) -> int:
    """Batch embed chunks and upsert to Qdrant with metadata payload.

    Processes in batches of EMBED_BATCH_SIZE to respect API limits.
    Returns the number of vectors upserted.
    """
    if not chunks:
        return 0

    ensure_collection()

    # Delete existing vectors for this document (idempotency)
    _delete_document_vectors(document_id)

    total_upserted = 0

    for batch_start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch_chunks = chunks[batch_start : batch_start + EMBED_BATCH_SIZE]
        vectors_list = embed_batch(batch_chunks)

        points = []
        for i, (chunk_text, vector) in enumerate(zip(batch_chunks, vectors_list)):
            points.append(
                {
                    "id": str(uuid.uuid4()),
                    "vector": vector,
                    "payload": {
                        "document_id": document_id,
                        "case_id": case_id,
                        "firm_id": firm_id,
                        "chunk_index": batch_start + i,
                        "type": "document",
                        "text": chunk_text,
                    },
                }
            )

        upsert_vectors(points)
        total_upserted += len(points)

    return total_upserted


def _update_document_status(
    document_id: str, firm_id: str, status: str, ocr_text: str = ""
) -> None:
    """Update document record with processing status and OCR text via DataFlow.

    Uses both document_id and firm_id in the filter for tenant isolation.
    """
    workflows = _get_workflows()
    update_wf = workflows["document_update"]

    fields = {"ocr_status": status}
    if ocr_text:
        fields["ocr_text"] = ocr_text

    with LocalRuntime() as runtime:
        runtime.execute(
            update_wf.build(),
            inputs={
                "filter": {"id": document_id, "firm_id": firm_id},
                "fields": fields,
            },
        )


def process_document(document_id: str, case_id: str, firm_id: str, text: str) -> dict:
    """Main entry point — process a document through the embedding pipeline.

    Args:
        document_id: The document's ID.
        case_id: The parent case ID.
        firm_id: The owning firm ID.
        text: The document text content to process.

    Returns:
        Dict with processing results (status, chunk_count, vector_count).
    """
    if len(text) < MIN_TEXT_LENGTH:
        logger.info(
            "Skipping document %s: text too short (%d chars, minimum %d)",
            document_id,
            len(text),
            MIN_TEXT_LENGTH,
        )
        return {
            "document_id": document_id,
            "status": "skipped",
            "chunk_count": 0,
            "vector_count": 0,
        }

    logger.info(
        "Processing document %s (case=%s, firm=%s, text_len=%d)",
        document_id,
        case_id,
        firm_id,
        len(text),
    )

    _update_document_status(document_id, firm_id, "processing")

    try:
        chunks = _chunk_text(text)

        if not chunks:
            _update_document_status(document_id, firm_id, "complete", ocr_text="")
            return {
                "document_id": document_id,
                "status": "complete",
                "chunk_count": 0,
                "vector_count": 0,
            }

        vector_count = _embed_and_upsert(chunks, document_id, case_id, firm_id)

        stored_text = text[:MAX_OCR_TEXT_CHARS]
        if len(text) > MAX_OCR_TEXT_CHARS:
            logger.info(
                "Document %s text truncated from %d to %d chars for storage",
                document_id,
                len(text),
                MAX_OCR_TEXT_CHARS,
            )

        _update_document_status(document_id, firm_id, "complete", ocr_text=stored_text)

        logger.info(
            "Document %s processed: %d chunks, %d vectors",
            document_id,
            len(chunks),
            vector_count,
        )

        return {
            "document_id": document_id,
            "status": "complete",
            "chunk_count": len(chunks),
            "vector_count": vector_count,
        }

    except Exception:
        logger.exception("Document processing failed for %s", document_id)
        # Clean up any orphaned vectors
        _delete_document_vectors(document_id)
        _update_document_status(document_id, firm_id, "failed")
        return {
            "document_id": document_id,
            "status": "failed",
            "chunk_count": 0,
            "vector_count": 0,
        }
