# Document Pipeline — Domain Specification

**Domain:** File upload, storage, text extraction, and processing pipeline for LegalCoPilot v2.
**Status:** Draft
**Last updated:** 2026-06-23

---

## 1. Current State (Baseline)

### 1.1 What Exists

| Component | Location | State |
|---|---|---|
| S3 settings | `src/legalcopilot/config/settings.py:72-73` | `S3_BUCKET`, `S3_REGION` defined; zero consumers |
| AWS credentials | `.env.example:49-50` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` templated; no code reads them |
| Document model | `src/legalcopilot/models/core.py:165-213` | Fields: `storage_url` (always empty string), `ocr_text`, `ocr_status`, `file_size_bytes`, `filename`, `file_type` |
| Upload handler | `src/legalcopilot/api/cases.py:177-229` | Accepts `content_text: str` only; no binary file upload; no S3 interaction |
| Document processor | `src/legalcopilot/services/document_processor.py` | Accepts `text: str` input; chunks (1000 chars, 200 overlap), embeds via `text-embedding-3-small` (1536-dim), upserts to Qdrant |
| Frontend upload | `src/frontend/src/components/cases/DocumentUpload.tsx` | Posts `multipart/form-data` to `/documents/upload`; drag-and-drop UI exists; accepts `.pdf,.docx,.doc,.txt,.png,.jpg,.jpeg` |
| Frontend types | `src/frontend/src/types/case.ts:45-55` | `Document` interface has `content_text`, no `storage_url` or `file_size_bytes` |
| Frontend service | `src/frontend/src/services/case.service.ts:63-79` | `uploadDocument()` sends via Nexus call with `content_text` string |
| Dependencies | `pyproject.toml` | Zero file-processing libraries (no boto3, pypdf, python-docx, openpyxl, python-pptx) |

### 1.2 What Is Missing

1. **No S3 client** -- boto3 is not installed; no code creates an S3 client or references credentials.
2. **No binary upload path** -- the backend only accepts a text string, not file bytes.
3. **No text extraction** -- no libraries to extract text from PDF, DOCX, XLSX, or PPTX.
4. **No presigned URL flow** -- the frontend sends files to the backend, not directly to S3.
5. **No download capability** -- no endpoint to retrieve uploaded files.
6. **`storage_url` is dead** -- the field exists on the Document model but is never populated.

---

## 2. Architecture Overview

```
Browser                      Backend (Python)               AWS S3
  |                              |                            |
  |-- POST /get-upload-url ----->|                            |
  |<-- {upload_url, fields} -----|                            |
  |                              |                            |
  |-- PUT (binary) ------------------------------------------>|
  |<-- 200 OK ------------------------------------------------|
  |                              |                            |
  |-- POST /confirm-upload ----->|                            |
  |                              |-- GET object ------------->|
  |                              |<-- file bytes -------------|
  |                              |                            |
  |                              |-- extract_text()           |
  |                              |-- process_document()       |
  |                              |   (chunk + embed + Qdrant) |
  |                              |-- update Document record   |
  |<-- {document} --------------|                            |
```

The upload uses a **two-phase presigned URL pattern**:
- Phase 1: Backend generates a presigned S3 upload URL.
- Phase 2: Browser uploads binary directly to S3 (no backend proxy for large files).
- Phase 3: Backend confirms, downloads from S3, extracts text, processes, updates the record.

---

## 3. S3 Storage Service

**File:** `src/legalcopilot/services/storage.py` (NEW)

### 3.1 Settings Consumed

All values from `.env` via `src/legalcopilot/config/settings.py`. New settings to add:

```python
# In settings.py — add below existing S3_REGION line
AWS_ACCESS_KEY_ID = get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = get("AWS_SECRET_ACCESS_KEY")
S3_PRESIGN_EXPIRY = get_int("S3_PRESIGN_EXPIRY", 3600)        # 1 hour default
S3_UPLOAD_EXPIRY = get_int("S3_UPLOAD_EXPIRY", 600)            # 10 min for upload URLs
STORAGE_BACKEND = get("STORAGE_BACKEND", "auto")               # "s3", "local", or "auto"
LOCAL_STORAGE_DIR = get("LOCAL_STORAGE_DIR", "data/uploads")    # dev-mode fallback
```

`STORAGE_BACKEND=auto` means: use S3 if `AWS_ACCESS_KEY_ID` is non-empty, otherwise fall back to local filesystem. Explicit `"s3"` or `"local"` forces the backend.

### 3.2 S3 Key Format

```
{firm_id}/{case_id}/{uuid}_{original_filename}
```

Example: `firm_abc123/case_def456/a1b2c3d4-e5f6-7890-abcd-ef1234567890_Contract_Draft.pdf`

Rules:
- `firm_id` is always the first path segment (enables per-firm S3 lifecycle policies and IAM scoping).
- `case_id` is the second segment (enables per-case listing via S3 prefix).
- The UUID prefix on the filename prevents collisions when the same filename is uploaded twice.
- Original filename is preserved after the UUID for human readability in S3 console.
- The original filename is sanitized: only `[a-zA-Z0-9._-]` retained; all other characters replaced with `_`; consecutive underscores collapsed; max 200 characters.

### 3.3 Functions

#### `get_s3_client() -> boto3.client`

Returns a configured boto3 S3 client. Uses `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from settings. Region set to `S3_REGION`.

Raises `StorageConfigError` if `STORAGE_BACKEND=s3` and credentials are missing.

#### `generate_presigned_upload_url(case_id, filename, firm_id, content_type) -> dict`

Generates a presigned POST URL for direct browser-to-S3 upload.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `case_id` | `str` | Yes | Parent case ID |
| `filename` | `str` | Yes | Original filename from the user |
| `firm_id` | `str` | Yes | Owning firm ID (tenant isolation) |
| `content_type` | `str` | Yes | MIME type (e.g., `application/pdf`) |

**Returns:**
```python
{
    "upload_url": "https://legalcopilot-documents.s3.ap-southeast-1.amazonaws.com",
    "fields": {
        "key": "firm_abc/case_def/uuid_filename.pdf",
        "Content-Type": "application/pdf",
        "AWSAccessKeyId": "...",
        "policy": "...",
        "signature": "..."
    },
    "key": "firm_abc/case_def/uuid_filename.pdf",
    "expires_in": 600
}
```

**Conditions:**
- `content_type` must be in the allowed set (see section 3.5).
- The presigned POST includes a condition limiting upload size to 50MB (`["content-length-range", 0, 52428800]`).
- Expiry: `S3_UPLOAD_EXPIRY` seconds (default 600 = 10 minutes).

#### `generate_presigned_download_url(storage_url, expires_in=3600) -> str`

Generates a presigned GET URL for downloading a file from S3.

**Parameters:**
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `storage_url` | `str` | Yes | -- | Full S3 URI (`s3://bucket/key`) or just the key |
| `expires_in` | `int` | No | `3600` | URL expiry in seconds |

**Returns:** A presigned HTTPS URL string.

**Validation:**
- The `storage_url` must reference the configured `S3_BUCKET`. Raises `StorageError` if it references a different bucket.

#### `upload_file(file_bytes, case_id, filename, firm_id, content_type="application/octet-stream") -> str`

Server-side upload for the confirm-upload flow (backend downloads from S3 after presigned upload) or for direct backend uploads.

**Returns:** `s3://legalcopilot-documents/firm_id/case_id/uuid_filename.ext`

#### `download_file(storage_url) -> bytes`

Downloads file bytes from S3 given a storage URL.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `storage_url` | `str` | Yes | `s3://bucket/key` or just the key |

**Returns:** Raw file bytes.

**Raises:** `StorageError` if the object does not exist or access is denied.

#### `delete_file(storage_url) -> bool`

Deletes a file from S3.

**Returns:** `True` if deleted (or already absent), `False` on error.

### 3.4 Local Filesystem Fallback (Dev Mode)

When `STORAGE_BACKEND=local` (or `auto` with empty AWS credentials), all storage operations use the local filesystem under `LOCAL_STORAGE_DIR` (default `data/uploads/`).

| S3 Operation | Local Equivalent |
|---|---|
| `generate_presigned_upload_url` | Returns `{"upload_url": "/api/documents/local-upload", "fields": {}, "key": "...", "expires_in": 600}` |
| `generate_presigned_download_url` | Returns `/api/documents/local-download?key=...` |
| `upload_file` | Writes to `LOCAL_STORAGE_DIR/{firm_id}/{case_id}/{uuid}_{filename}` |
| `download_file` | Reads from the local path |
| `delete_file` | Deletes the local file |

The key format is identical to S3. The returned `storage_url` uses the prefix `local://` instead of `s3://`.

Two additional Nexus handlers are registered only when `STORAGE_BACKEND=local`:
- `POST /api/documents/local-upload` -- accepts `multipart/form-data`, saves to disk.
- `GET /api/documents/local-download` -- serves the file by key.

### 3.5 Allowed Content Types

```python
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",        # .xlsx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation", # .pptx
    "text/plain",
}
```

Mapping from file extension to content type:

| Extension | Content Type |
|---|---|
| `.pdf` | `application/pdf` |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` |
| `.txt` | `text/plain` |

### 3.6 S3 Bucket CORS Configuration

Required for presigned POST uploads from the browser:

```json
{
    "CORSRules": [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["PUT", "POST", "GET"],
            "AllowedOrigins": ["http://localhost:3000", "https://*.legalcopilot.sg"],
            "ExposeHeaders": ["ETag", "x-amz-request-id"],
            "MaxAgeSeconds": 3600
        }
    ]
}
```

This must be applied to the `legalcopilot-documents` bucket in `ap-southeast-1` before browser uploads will work. A setup script or Terraform/CloudFormation template should be provided.

### 3.7 Error Types

```python
class StorageError(Exception):
    """Base exception for storage operations."""
    pass

class StorageConfigError(StorageError):
    """Raised when storage is misconfigured (missing credentials, wrong backend)."""
    pass

class StorageNotFoundError(StorageError):
    """Raised when the requested object does not exist."""
    pass
```

---

## 4. File Text Extraction Service

**File:** `src/legalcopilot/services/file_extractor.py` (NEW)

### 4.1 Public Interface

#### `extract_text(file_bytes: bytes, filename: str) -> str`

Dispatches to the appropriate extractor based on file extension. Returns extracted plain text.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `file_bytes` | `bytes` | Yes | Raw file content |
| `filename` | `str` | Yes | Original filename (used to determine extension) |

**Returns:** Extracted text as a string, truncated to `MAX_EXTRACTION_CHARS` (50,000 characters).

**Raises:**
| Exception | When |
|---|---|
| `ExtractionError` | General extraction failure |
| `UnsupportedFileTypeError` | Unrecognized file extension |
| `EncryptedFileError` | PDF is password-protected |
| `EmptyExtractionError` | File yielded zero text (likely a scanned-image PDF with no OCR layer) |

### 4.2 Extension Dispatch Table

| Extension | Library | Extractor Function |
|---|---|---|
| `.pdf` | `pypdf>=4.0.0` | `_extract_pdf(file_bytes) -> str` |
| `.docx` | `python-docx>=1.1.0` | `_extract_docx(file_bytes) -> str` |
| `.xlsx` | `openpyxl>=3.1.0` | `_extract_xlsx(file_bytes) -> str` |
| `.pptx` | `python-pptx>=0.6.23` | `_extract_pptx(file_bytes) -> str` |
| `.txt` | stdlib | `_extract_txt(file_bytes) -> str` |

Extension matching is case-insensitive.

### 4.3 Extractor Details

#### PDF (`_extract_pdf`)

```python
def _extract_pdf(file_bytes: bytes) -> str:
    """Extract text from all pages of a PDF."""
```

- Uses `pypdf.PdfReader` with a `BytesIO` wrapper.
- Iterates all pages; concatenates page text with `\n\n` separators.
- Detects encrypted PDFs via `reader.is_encrypted`; raises `EncryptedFileError`.
- If total extracted text (after stripping whitespace) is fewer than 10 characters, raises `EmptyExtractionError` with a message indicating the PDF may be scanned/image-only.
- Catches `pypdf.errors.PdfReadError` and wraps as `ExtractionError`.

#### Word (`_extract_docx`)

```python
def _extract_docx(file_bytes: bytes) -> str:
    """Extract text from all paragraphs and tables in a DOCX."""
```

- Uses `docx.Document` with a `BytesIO` wrapper.
- Extracts all `paragraph.text` values, joined by `\n`.
- Also extracts text from all tables: iterates `document.tables`, then each row and cell, joining cell text with `\t` (tab) and rows with `\n`.
- Tables are appended after paragraph text, separated by `\n\n--- Tables ---\n\n`.

#### Excel (`_extract_xlsx`)

```python
def _extract_xlsx(file_bytes: bytes) -> str:
    """Extract text from all sheets, preserving table structure."""
```

- Uses `openpyxl.load_workbook` with `data_only=True` and `read_only=True`.
- Iterates all worksheets.
- For each sheet, emits a header line: `=== Sheet: {sheet.title} ===`.
- For each row, joins cell values with `\t` (tab); rows joined with `\n`.
- `None` cell values are rendered as empty string.
- Sheets are separated by `\n\n`.

#### PowerPoint (`_extract_pptx`)

```python
def _extract_pptx(file_bytes: bytes) -> str:
    """Extract text from all slides."""
```

- Uses `pptx.Presentation` with a `BytesIO` wrapper.
- Iterates all slides.
- For each slide, emits a header: `--- Slide {n} ---`.
- Extracts text from all shapes that have a `text_frame`: iterates paragraphs, concatenates `paragraph.text` with `\n`.
- Slides separated by `\n\n`.

#### Plain Text (`_extract_txt`)

```python
def _extract_txt(file_bytes: bytes) -> str:
    """Decode plain text as UTF-8."""
```

- Decodes with `encoding="utf-8"`, `errors="replace"`.
- No further processing.

### 4.4 Constants

```python
MAX_EXTRACTION_CHARS = 50_000    # Matches document_processor.MAX_OCR_TEXT_CHARS
MIN_MEANINGFUL_TEXT = 10         # Below this, consider extraction empty
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".txt"}
```

### 4.5 Error Types

```python
class ExtractionError(Exception):
    """Base exception for file extraction failures."""
    pass

class UnsupportedFileTypeError(ExtractionError):
    """Raised when the file extension is not supported."""
    pass

class EncryptedFileError(ExtractionError):
    """Raised when a PDF is password-protected."""
    pass

class EmptyExtractionError(ExtractionError):
    """Raised when extraction yields zero meaningful text (e.g., scanned PDF)."""
    pass
```

---

## 5. API Endpoints

All endpoints are registered as Nexus handlers in `src/legalcopilot/api/cases.py` (extend existing `register_document_routes`).

### 5.1 Get Upload URL

**Handler:** `get_upload_url`
**Description:** Generate a presigned S3 URL for direct browser upload.

**Request Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `case_id` | `str` | Yes | Target case ID |
| `firm_id` | `str` | Yes | Owning firm (tenant isolation) |
| `filename` | `str` | Yes | Original filename |
| `content_type` | `str` | Yes | MIME type of the file |

**Validation:**
1. `firm_id` is required (non-empty).
2. Case must exist and belong to `firm_id` (read case, check `firm_id` match).
3. `content_type` must be in `ALLOWED_CONTENT_TYPES`.
4. `filename` extension must be in `SUPPORTED_EXTENSIONS`.

**Success Response:**
```json
{
    "upload_url": "https://legalcopilot-documents.s3.ap-southeast-1.amazonaws.com",
    "fields": {
        "key": "firm_abc/case_def/uuid_filename.pdf",
        "Content-Type": "application/pdf",
        "AWSAccessKeyId": "...",
        "policy": "...",
        "signature": "..."
    },
    "key": "firm_abc/case_def/uuid_filename.pdf",
    "expires_in": 600,
    "max_file_size": 52428800
}
```

**Error Responses:**
| Condition | Response |
|---|---|
| Missing `firm_id` | `{"error": "firm_id is required"}` |
| Case not found / wrong firm | `{"error": "Case not found", "case_id": "..."}` |
| Unsupported content type | `{"error": "Unsupported file type", "content_type": "...", "allowed": [...]}` |
| Storage misconfigured | `{"error": "Storage service unavailable"}` |

### 5.2 Confirm Upload

**Handler:** `confirm_upload`
**Description:** Confirm a file has been uploaded to S3, trigger text extraction and processing.

**Request Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `case_id` | `str` | Yes | Target case ID |
| `firm_id` | `str` | Yes | Owning firm |
| `uploaded_by_id` | `str` | Yes | User who uploaded |
| `filename` | `str` | Yes | Original filename |
| `file_type` | `str` | No | Legal document type (default `"other"`) |
| `s3_key` | `str` | Yes | The S3 key returned by `get_upload_url` |
| `file_size_bytes` | `int` | No | File size in bytes (from browser) |

**Processing Flow:**
1. Validate `firm_id` and case ownership.
2. Validate `s3_key` starts with `{firm_id}/` (tenant isolation -- a firm cannot reference another firm's files).
3. Create Document record with `ocr_status: "pending"`, `storage_url: "s3://{bucket}/{s3_key}"`.
4. Download file from S3 via `storage.download_file()`.
5. Update `ocr_status` to `"processing"`.
6. Extract text via `file_extractor.extract_text(file_bytes, filename)`.
7. Process via `document_processor.process_document(document_id, case_id, firm_id, text)`.
8. Update Document record: `ocr_status: "complete"`, `ocr_text: text[:50000]`, `file_size_bytes`.
9. Return the Document record with processing results.

**On Extraction/Processing Failure:**
- Catch `ExtractionError` subclasses.
- Update Document record: `ocr_status: "failed"`, `metadata: {"error": str(exception), "error_type": type(exception).__name__}`.
- Return the Document record with `ocr_status: "failed"`.
- Do NOT delete the S3 object (the user may retry or the file may be useful for manual review).

**Success Response:**
```json
{
    "id": "doc_uuid",
    "case_id": "case_def",
    "firm_id": "firm_abc",
    "filename": "Contract_Draft.pdf",
    "file_type": "contract",
    "storage_url": "s3://legalcopilot-documents/firm_abc/case_def/uuid_Contract_Draft.pdf",
    "file_size_bytes": 245000,
    "ocr_status": "complete",
    "ocr_text": "First 50K chars of extracted text...",
    "processing": {
        "document_id": "doc_uuid",
        "status": "complete",
        "chunk_count": 12,
        "vector_count": 12
    },
    "created_at": "2026-06-23T10:00:00Z"
}
```

**Error Responses:**
| Condition | Response |
|---|---|
| Missing `firm_id` | `{"error": "firm_id is required"}` |
| Case not found / wrong firm | `{"error": "Case not found", "case_id": "..."}` |
| `s3_key` does not start with `firm_id/` | `{"error": "Access denied: key does not belong to firm"}` |
| S3 object not found | `{"error": "File not found in storage", "s3_key": "..."}` |
| Encrypted PDF | Document created with `ocr_status: "failed"`, `metadata.error_type: "EncryptedFileError"` |
| Empty extraction (scanned PDF) | Document created with `ocr_status: "failed"`, `metadata.error_type: "EmptyExtractionError"` |

### 5.3 Get Download URL

**Handler:** `get_download_url`
**Description:** Generate a presigned S3 download URL for a document.

**Request Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `document_id` | `str` | Yes | Document ID |
| `firm_id` | `str` | Yes | Owning firm (tenant isolation) |

**Processing Flow:**
1. Read the Document record.
2. Verify `firm_id` matches (tenant isolation).
3. Verify `storage_url` is non-empty (file was actually uploaded).
4. Generate presigned download URL via `storage.generate_presigned_download_url()`.

**Success Response:**
```json
{
    "document_id": "doc_uuid",
    "download_url": "https://legalcopilot-documents.s3.ap-southeast-1.amazonaws.com/...",
    "filename": "Contract_Draft.pdf",
    "expires_in": 3600
}
```

**Error Responses:**
| Condition | Response |
|---|---|
| Missing `firm_id` | `{"error": "firm_id is required"}` |
| Document not found / wrong firm | `{"error": "Document not found", "document_id": "..."}` |
| No file stored (`storage_url` empty) | `{"error": "No file stored for this document", "document_id": "..."}` |

### 5.4 Retry Processing

**Handler:** `retry_document_processing`
**Description:** Retry text extraction and processing for a failed document.

**Request Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `document_id` | `str` | Yes | Document ID |
| `firm_id` | `str` | Yes | Owning firm |

**Processing Flow:**
1. Read Document record, verify `firm_id`.
2. Verify `ocr_status` is `"failed"` (only failed documents can be retried).
3. Verify `storage_url` is non-empty.
4. Re-run the same flow as confirm-upload steps 4-9.

**Success Response:** Same shape as confirm-upload success.

**Error Responses:**
| Condition | Response |
|---|---|
| Document not found / wrong firm | `{"error": "Document not found"}` |
| `ocr_status` is not `"failed"` | `{"error": "Document is not in failed state", "ocr_status": "..."}` |
| `storage_url` is empty | `{"error": "No file stored for this document"}` |

### 5.5 Backward Compatibility: Existing `upload_document` Handler

The existing `upload_document` handler (text-only) remains unchanged for backward compatibility. It continues to accept `content_text: str` and process documents without S3 involvement. This supports cases where text is provided directly (e.g., pasted content, API integrations).

---

## 6. Upload Flow (End-to-End)

### 6.1 Sequence

```
1. User drops a file onto the upload zone (or clicks to browse).
2. Frontend reads filename, file size, and content type from the File object.
3. Frontend validates:
   a. Extension is in {.pdf, .docx, .xlsx, .pptx, .txt}
   b. Size <= 50MB (52,428,800 bytes)
4. Frontend calls POST /nexus { handler: "get_upload_url", params: { case_id, firm_id, filename, content_type } }
5. Backend validates case ownership, generates presigned URL, returns { upload_url, fields, key }.
6. Frontend uploads binary to S3 via presigned POST:
   a. Constructs FormData with all `fields` from the response.
   b. Appends the file as the last field (required by S3).
   c. POSTs to `upload_url`.
   d. Tracks upload progress via XMLHttpRequest or axios onUploadProgress.
7. On S3 upload success (HTTP 204):
   a. Frontend calls POST /nexus { handler: "confirm_upload", params: { case_id, firm_id, uploaded_by_id, filename, file_type, s3_key: key, file_size_bytes } }
8. Backend downloads from S3, extracts text, processes (chunk + embed + Qdrant upsert), updates Document record.
9. Backend returns the Document record with processing results.
10. Frontend updates the document list (invalidates the query cache).
```

### 6.2 State Transitions (Per File)

```
[idle] --user drops file--> [validating]
[validating] --pass--> [requesting_url]
[validating] --fail (size/type)--> [error: "File type not supported" / "File too large"]
[requesting_url] --success--> [uploading_to_s3]
[requesting_url] --fail--> [error: "Could not prepare upload"]
[uploading_to_s3] --progress events--> [uploading_to_s3] (update progress %)
[uploading_to_s3] --success--> [confirming]
[uploading_to_s3] --fail--> [error: "Upload failed"]
[confirming] --success (ocr_status=complete)--> [completed]
[confirming] --success (ocr_status=failed)--> [processing_failed]
[confirming] --fail--> [error: "Processing failed"]
[processing_failed] --user clicks retry--> [retrying]
[retrying] --success--> [completed]
[retrying] --fail--> [processing_failed]
```

### 6.3 Error Recovery

| Failure Point | User Experience | Recovery |
|---|---|---|
| Presigned URL request fails | Error toast; file stays in queue | Retry button re-requests the URL |
| S3 upload fails (network) | Error toast with "Upload failed" | Retry button restarts from step 4 |
| S3 upload fails (expired URL) | Error toast | Retry restarts from step 4 (gets new URL) |
| Confirm-upload fails (network) | Error toast; S3 object is orphaned | Retry button re-calls confirm-upload with the same key |
| Text extraction fails | Document created with `ocr_status: "failed"` | Retry button calls `retry_document_processing` |
| Embedding/Qdrant fails | Document created with `ocr_status: "failed"` | Same retry flow |

---

## 7. Download Flow

### 7.1 Sequence

```
1. User clicks "Download" on a document in the document list.
2. Frontend calls POST /nexus { handler: "get_download_url", params: { document_id, firm_id } }
3. Backend validates ownership, generates presigned download URL (1 hour expiry).
4. Frontend receives the URL.
5. Frontend opens the URL in a new tab or triggers a download via an invisible anchor element:
   a. Create an <a> element with href=download_url and download=filename.
   b. Programmatically click it.
   c. Remove the element.
6. Browser downloads the file directly from S3.
```

### 7.2 Security

- Presigned download URLs expire after 1 hour (configurable via `S3_PRESIGN_EXPIRY`).
- The backend verifies `firm_id` matches the document's `firm_id` before generating the URL.
- S3 bucket policy should deny all public access; presigned URLs are the only access path.

---

## 8. Frontend Upload Component

**File:** `src/frontend/src/components/cases/DocumentUpload.tsx` (MODIFY existing)

### 8.1 Changes Required

The existing component already has drag-and-drop, file input, and progress tracking. It needs to be modified to use the presigned URL flow instead of posting `multipart/form-data` directly to the backend.

### 8.2 Updated Upload Flow

Replace the current `uploadMutation` that posts to `/documents/upload` with a three-step mutation:

```typescript
// Step 1: Get presigned URL
const { upload_url, fields, key } = await nexusCall<PresignedUploadResponse>(
    "get_upload_url",
    { case_id: caseId, firm_id: firmId, filename: file.name, content_type: file.type }
);

// Step 2: Upload to S3 via presigned POST
const formData = new FormData();
Object.entries(fields).forEach(([k, v]) => formData.append(k, v));
formData.append("file", file);  // file MUST be last

await axios.post(upload_url, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => { /* update progress */ },
});

// Step 3: Confirm upload
const document = await nexusCall<Document>("confirm_upload", {
    case_id: caseId,
    firm_id: firmId,
    uploaded_by_id: userId,
    filename: file.name,
    file_type: selectedFileType,
    s3_key: key,
    file_size_bytes: file.size,
});
```

### 8.3 Updated Status Indicators

| Status | Icon | Text | Color |
|---|---|---|---|
| Validating | Spinner | "Preparing..." | Blue |
| Uploading to S3 | Spinner + progress bar | "Uploading... {n}%" | Blue |
| Confirming/Processing | Spinner | "Processing..." | Blue |
| Completed | Checkmark | "Processed" | Green |
| Failed (upload) | X icon | "Upload failed" + Retry button | Red |
| Failed (processing) | Warning icon | "Processing failed" + Retry button | Orange |

### 8.4 Accepted File Types

Update the `accept` attribute and help text:

```tsx
<input
    accept=".pdf,.docx,.xlsx,.pptx,.txt"
    // ...
/>
<p className="text-xs text-gray-500 mt-1">
    PDF, Word, Excel, PowerPoint, or text files up to 50MB
</p>
```

### 8.5 Client-Side Validation

Before requesting a presigned URL:

```typescript
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const ACCEPTED_EXTENSIONS = new Set([".pdf", ".docx", ".xlsx", ".pptx", ".txt"]);

function validateFile(file: File): string | null {
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!ACCEPTED_EXTENSIONS.has(ext)) {
        return `File type "${ext}" is not supported. Accepted: PDF, Word, Excel, PowerPoint, Text.`;
    }
    if (file.size > MAX_FILE_SIZE) {
        return `File is too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Maximum is 50MB.`;
    }
    if (file.size === 0) {
        return "File is empty.";
    }
    return null; // valid
}
```

### 8.6 Updated TypeScript Types

Update `src/frontend/src/types/case.ts`:

```typescript
export interface Document {
    id: string;
    case_id: string;
    firm_id: string;
    filename: string;
    file_type: FileType;
    storage_url: string;
    file_size_bytes: number;
    ocr_text: string | null;
    ocr_status: "pending" | "processing" | "complete" | "failed";
    uploaded_by_id: string;
    metadata: Record<string, unknown>;
    created_at: string;
    updated_at: string;
}

export interface PresignedUploadResponse {
    upload_url: string;
    fields: Record<string, string>;
    key: string;
    expires_in: number;
    max_file_size: number;
}

export interface PresignedDownloadResponse {
    document_id: string;
    download_url: string;
    filename: string;
    expires_in: number;
}
```

### 8.7 New Frontend Service Functions

Add to `src/frontend/src/services/case.service.ts`:

```typescript
export async function getUploadUrl(
    case_id: string,
    firm_id: string,
    filename: string,
    content_type: string,
): Promise<PresignedUploadResponse> {
    return nexusCall<PresignedUploadResponse>("get_upload_url", {
        case_id, firm_id, filename, content_type,
    });
}

export async function confirmUpload(
    case_id: string,
    firm_id: string,
    uploaded_by_id: string,
    filename: string,
    file_type: FileType,
    s3_key: string,
    file_size_bytes: number,
): Promise<Document> {
    return nexusCall<Document>("confirm_upload", {
        case_id, firm_id, uploaded_by_id, filename, file_type, s3_key, file_size_bytes,
    });
}

export async function getDownloadUrl(
    document_id: string,
    firm_id: string,
): Promise<PresignedDownloadResponse> {
    return nexusCall<PresignedDownloadResponse>("get_download_url", {
        document_id, firm_id,
    });
}

export async function retryDocumentProcessing(
    document_id: string,
    firm_id: string,
): Promise<Document> {
    return nexusCall<Document>("retry_document_processing", {
        document_id, firm_id,
    });
}
```

---

## 9. Processing Pipeline (Existing + Integration)

### 9.1 Existing Pipeline (No Changes)

`src/legalcopilot/services/document_processor.py` remains unchanged. It continues to:
1. Accept `(document_id, case_id, firm_id, text)`.
2. Chunk text (1000 chars, 200 overlap, word-boundary aware).
3. Embed via `text-embedding-3-small` (1536-dim) in batches of 100.
4. Upsert to Qdrant with payload `{document_id, case_id, firm_id, chunk_index, type: "document", text}`.
5. Update Document record `ocr_status` to `"complete"` or `"failed"`.

### 9.2 Integration Point

The new `confirm_upload` handler calls the existing pipeline:

```python
# In confirm_upload handler (pseudo-code)
file_bytes = storage.download_file(s3_key)
text = file_extractor.extract_text(file_bytes, filename)
result = document_processor.process_document(doc_id, case_id, firm_id, text)
```

### 9.3 OCR Status Progression

```
pending        -- Document record created, file uploaded to S3
    |
processing     -- Backend has downloaded the file and started extraction
    |
    +-- complete   -- Text extracted, chunked, embedded, upserted to Qdrant
    |
    +-- failed     -- Extraction or processing error; error stored in metadata
                      User can retry via retry_document_processing
```

### 9.4 Failure Metadata

On failure, the Document record's `metadata` field is updated with error details:

```python
{
    "error": "PDF is password-protected",
    "error_type": "EncryptedFileError",
    "failed_at": "2026-06-23T10:05:00Z"
}
```

This enables the frontend to show a meaningful error message and helps debugging.

---

## 10. Dependencies

### 10.1 New Python Dependencies (add to `pyproject.toml` `dependencies`)

```toml
"boto3>=1.28.0",
"pypdf>=4.0.0",
"python-docx>=1.1.0",
"openpyxl>=3.1.0",
"python-pptx>=0.6.23",
```

### 10.2 New Environment Variables (add to `.env.example`)

The following already exist in `.env.example` and do not need to be added:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET`
- `S3_REGION`

New variables to add:

```bash
# S3_PRESIGN_EXPIRY=3600          # Download URL expiry (seconds)
# S3_UPLOAD_EXPIRY=600            # Upload URL expiry (seconds)
# STORAGE_BACKEND=auto            # "s3", "local", or "auto"
# LOCAL_STORAGE_DIR=data/uploads  # Dev-mode local storage path
```

### 10.3 New Settings (add to `settings.py`)

```python
# Storage (extended)
AWS_ACCESS_KEY_ID = get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = get("AWS_SECRET_ACCESS_KEY")
S3_PRESIGN_EXPIRY = get_int("S3_PRESIGN_EXPIRY", 3600)
S3_UPLOAD_EXPIRY = get_int("S3_UPLOAD_EXPIRY", 600)
STORAGE_BACKEND = get("STORAGE_BACKEND", "auto")
LOCAL_STORAGE_DIR = get("LOCAL_STORAGE_DIR", "data/uploads")
```

---

## 11. File Inventory

### 11.1 New Files

| File | Purpose |
|---|---|
| `src/legalcopilot/services/storage.py` | S3 client, presigned URLs, upload/download/delete, local fallback |
| `src/legalcopilot/services/file_extractor.py` | Text extraction from PDF, DOCX, XLSX, PPTX, TXT |

### 11.2 Modified Files

| File | Changes |
|---|---|
| `src/legalcopilot/config/settings.py` | Add `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_PRESIGN_EXPIRY`, `S3_UPLOAD_EXPIRY`, `STORAGE_BACKEND`, `LOCAL_STORAGE_DIR` |
| `src/legalcopilot/api/cases.py` | Add `get_upload_url`, `confirm_upload`, `get_download_url`, `retry_document_processing` handlers |
| `pyproject.toml` | Add `boto3`, `pypdf`, `python-docx`, `openpyxl`, `python-pptx` to `dependencies` |
| `.env.example` | Add `S3_PRESIGN_EXPIRY`, `S3_UPLOAD_EXPIRY`, `STORAGE_BACKEND`, `LOCAL_STORAGE_DIR` |
| `src/frontend/src/types/case.ts` | Update `Document` interface; add `PresignedUploadResponse`, `PresignedDownloadResponse` |
| `src/frontend/src/services/case.service.ts` | Add `getUploadUrl`, `confirmUpload`, `getDownloadUrl`, `retryDocumentProcessing` |
| `src/frontend/src/components/cases/DocumentUpload.tsx` | Replace direct upload with presigned URL flow; update accepted types; add retry |

### 11.3 Unchanged Files

| File | Reason |
|---|---|
| `src/legalcopilot/services/document_processor.py` | Existing pipeline is correct; new code calls into it |
| `src/legalcopilot/services/embedding.py` | No changes needed |
| `src/legalcopilot/services/vector_store.py` | No changes needed |
| `src/legalcopilot/models/core.py` | Document model already has all needed fields (`storage_url`, `ocr_text`, `ocr_status`, `file_size_bytes`, `metadata`) |

---

## 12. Security Considerations

### 12.1 Tenant Isolation

- S3 key format starts with `firm_id/`, ensuring firm-scoped storage.
- `confirm_upload` validates that `s3_key` starts with the caller's `firm_id`.
- `get_download_url` reads the Document record and verifies `firm_id` before generating a presigned URL.
- A firm cannot access another firm's documents even if they guess the S3 key, because the Nexus handler checks ownership.

### 12.2 Presigned URL Security

- Upload URLs expire after 10 minutes (configurable).
- Upload URLs include a `content-length-range` condition (0 to 50MB).
- Download URLs expire after 1 hour (configurable).
- The S3 bucket denies all public access; presigned URLs are the only path.

### 12.3 File Validation

- Content type is validated server-side against an allowlist before generating the presigned URL.
- File extension is validated both client-side and server-side.
- File size is enforced both client-side (50MB JS check) and server-side (S3 presigned POST condition).

### 12.4 Extraction Safety

- `pypdf` handles malformed PDFs gracefully (raises `PdfReadError`).
- Encrypted PDFs are detected and rejected with a clear error.
- Text output is truncated to 50K characters to prevent memory issues.
- No `eval()`, `exec()`, or shell commands are used in extraction.
- Extraction runs in the main process; for production scale, this should be moved to a background task queue (out of scope for this spec).

---

## 13. Constraints and Limits

| Constraint | Value | Enforced By |
|---|---|---|
| Max file size | 50 MB (52,428,800 bytes) | Frontend JS + S3 presigned POST condition |
| Max extracted text | 50,000 characters | `file_extractor.MAX_EXTRACTION_CHARS` |
| Max stored OCR text | 50,000 characters | `document_processor.MAX_OCR_TEXT_CHARS` |
| Chunk size | 1,000 characters | `document_processor.CHUNK_SIZE` |
| Chunk overlap | 200 characters | `document_processor.CHUNK_OVERLAP` |
| Embedding dimensions | 1,536 | `settings.EMBEDDING_DIMENSIONS` |
| Upload URL expiry | 10 minutes | `settings.S3_UPLOAD_EXPIRY` |
| Download URL expiry | 1 hour | `settings.S3_PRESIGN_EXPIRY` |
| Accepted extensions | .pdf, .docx, .xlsx, .pptx, .txt | `SUPPORTED_EXTENSIONS` |
| S3 region | ap-southeast-1 | `settings.S3_REGION` |
| S3 bucket | legalcopilot-documents | `settings.S3_BUCKET` |

---

## 14. Future Considerations (Out of Scope)

These items are explicitly out of scope for this spec but noted for awareness:

1. **Background task queue** -- Extraction and processing currently run synchronously in the confirm-upload handler. For production, this should be moved to a Celery/Redis task queue or equivalent to avoid blocking the API.
2. **OCR for scanned PDFs** -- The current pipeline cannot extract text from image-only PDFs. A future integration with an OCR service (AWS Textract, Google Vision, Tesseract) would address this.
3. **Virus scanning** -- Uploaded files are not scanned for malware. A production deployment should add a scanning step (e.g., ClamAV or AWS GuardDuty) before extraction.
4. **S3 lifecycle policies** -- Automatic deletion of orphaned S3 objects (uploaded but never confirmed) and soft-deleted documents.
5. **Multi-file upload atomicity** -- The current flow handles files individually. A batch-upload endpoint with transactional semantics could be added later.
6. **Real-time processing status** -- WebSocket or SSE notifications for processing progress, instead of polling.
