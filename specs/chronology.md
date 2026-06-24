# Chronology & Timeline Extraction

Domain specification for structured timeline extraction from legal documents, manual event management, and case chronology visualization.

## Status

- **Current state**: No CaseEvent model exists. No timeline extraction service. No chronology API endpoints. No frontend chronology tab. Zero hits for "timeline", "chronology", or "CaseEvent" in the backend codebase.
- **Orchestrator output**: `OrchestratorAgent.process_request()` returns unstructured analysis dicts via `_execute_specialists()`. The `ParalegalSignature` extracts `key_dates` as an untyped list, but these are embedded in the analysis response and never persisted as discrete events.
- **Document processor**: `process_document()` in `services/document_processor.py` chunks text, embeds, and upserts to Qdrant -- but performs no date/event extraction. The pipeline ends at vectorization.

## Data Model

### CaseEvent (NEW: add to `src/legalcopilot/models/core.py`)

A discrete event on a case's factual timeline, extracted by AI or entered manually.

```python
@db.model
class CaseEvent:
    """A discrete event on a case timeline -- AI-extracted or manually created."""

    id: str
    case_id: str
    firm_id: str
    document_id: Optional[str] = None          # source document (null for manual events)
    event_date: Optional[datetime] = None       # parsed datetime (best-effort)
    event_date_text: str = ""                   # raw date string from source ("on or about March 2024", "Q1 2024")
    description: str = ""                       # human-readable event description
    significance: str = "neutral"               # AI-assessed: critical, high, medium, low, neutral
    parties_involved: List[str] = []            # party names involved in this event
    event_type: str = "other"                   # see validation below
    source_text: str = ""                       # verbatim excerpt from source document
    confidence: float = 1.0                     # extraction confidence 0.0-1.0 (1.0 for manual)
    is_manual: bool = False                     # True if human-created, False if AI-extracted
    metadata: dict = {}                         # extensible: extraction_model, extraction_run_id, etc.
    created_at: datetime = None
    updated_at: datetime = None

    __validation__ = {
        "description": {"min_length": 1, "max_length": 2000},
        "significance": {"one_of": ["critical", "high", "medium", "low", "neutral"]},
        "event_type": {
            "one_of": [
                "contract_signed",
                "contract_terminated",
                "breach",
                "notice_served",
                "notice_received",
                "filing",
                "hearing",
                "judgment",
                "appeal",
                "payment",
                "default",
                "meeting",
                "communication",
                "regulatory_action",
                "corporate_action",
                "injury_incident",
                "property_transfer",
                "will_executed",
                "death",
                "marriage",
                "divorce",
                "arrest",
                "charge",
                "sentencing",
                "mediation",
                "arbitration_commenced",
                "award_issued",
                "other",
            ]
        },
        "confidence": {"range": {"min": 0.0, "max": 1.0}},
        "source_text": {"max_length": 5000},
        "event_date_text": {"max_length": 500},
    }
    __dataflow__ = {
        "soft_delete": True,
        "audit_log": True,
        "multi_tenant": True,
    }
    __indexes__ = [
        {"fields": ["case_id"]},
        {"fields": ["firm_id"]},
        {"fields": ["firm_id", "case_id"]},
        {"fields": ["case_id", "event_date"]},
        {"fields": ["document_id"]},
        {"fields": ["event_type"]},
        {"fields": ["significance"]},
        {"fields": ["is_manual"]},
    ]
```

**DataFlow auto-generates**: CaseEventCreate, CaseEventRead, CaseEventUpdate, CaseEventDelete, CaseEventList, CaseEventCount, CaseEventBulkCreate, CaseEventBulkUpdate, CaseEventBulkDelete, CaseEventSearch, CaseEventExists workflows.

### Field semantics

| Field | Purpose | Invariants |
|-------|---------|------------|
| `event_date` | Parsed `datetime` -- best-effort from `event_date_text`. `None` when unparseable. | Never fabricated. If the LLM cannot resolve to a date, leave `None`. |
| `event_date_text` | Raw string exactly as it appears in the source. Examples: `"on or about 15 March 2024"`, `"Q1 2024"`, `"recently"`, `"before the contract was signed"`. | Preserved verbatim from extraction. For manual events, user-provided. |
| `source_text` | Verbatim excerpt from the source document containing the event mention. | Max 5000 chars. Truncated at sentence boundary if longer. |
| `document_id` | FK to Document. `None` for manual events. Present for AI-extracted events. | If the source document is deleted, events remain (soft-delete orphan tolerance). |
| `significance` | AI-assessed legal significance in the context of the case. | LLM decides based on case_type + practice_area + event_type. Manual events default to `"neutral"` unless user overrides. |
| `parties_involved` | JSON array of party name strings. | De-duplicated. Normalized to consistent casing by the LLM. |
| `confidence` | Extraction confidence from the LLM. `1.0` for manual events. | Range `[0.0, 1.0]`. Below `0.5` triggers a review flag in the frontend. |
| `is_manual` | Distinguishes human-entered from AI-extracted. | Immutable after creation. |
| `metadata` | Extensible dict for extraction provenance. | Keys: `extraction_model`, `extraction_run_id`, `extraction_timestamp`, `dedup_group_id`. |

### Document.file_type extension

Add `"draft"` to the existing `file_type` validation `one_of` list in the Document model:

```python
"file_type": {
    "one_of": [
        "pleading", "affidavit", "exhibit", "correspondence",
        "submission", "judgment", "contract", "memo", "other",
        "draft",  # AI-generated drafts persisted back as documents
    ]
},
```

This supports the draft persistence requirement from the case-context spec.

---

## Timeline Extraction Service

**New file**: `src/legalcopilot/services/timeline_extractor.py`

### Kaizen signature

```python
class TimelineExtractionSignature(Signature):
    """You are a legal chronology specialist extracting structured timeline events
    from legal documents.

    For each event you identify:
    1. The exact date or date expression as written in the text
    2. Your best-effort parsing of that date to a standard datetime
    3. A concise description of what happened
    4. The legal significance in the context of this case type
    5. Which parties were involved
    6. The event type classification
    7. The verbatim source text (the sentence or passage containing the event)
    8. Your confidence in the extraction accuracy

    Rules:
    - Extract EVERY chronologically significant event, not just dates
    - Preserve ambiguous dates exactly as written ("on or about", "sometime in Q1")
    - Do not fabricate dates -- if unsure, set parsed_date to null
    - Include events that lack explicit dates but have temporal markers ("before the meeting", "subsequently")
    - Rank significance relative to the case type (a breach event is critical in a contract dispute, neutral in a family matter)
    """

    document_text: str = InputField(description="Full text of the document to extract events from")
    case_type: str = InputField(description="Case type for significance assessment", default="general")
    practice_area: str = InputField(description="Practice area for context", default="general")
    existing_parties: str = InputField(
        description="JSON array of known party names for normalization", default="[]"
    )
    existing_events_summary: str = InputField(
        description="Summary of already-extracted events to help with dedup", default=""
    )

    events: list = OutputField(
        description="JSON array of extracted events, each with: "
        "event_date_text (raw string), parsed_date (ISO 8601 or null), "
        "description, significance (critical/high/medium/low/neutral), "
        "parties_involved (array), event_type, source_text, confidence (0-1)"
    )
    extraction_notes: str = OutputField(
        description="Any notes about ambiguities, conflicting dates, or extraction caveats"
    )
```

### Service functions

```python
def extract_timeline_from_document(
    document_id: str,
    case_id: str,
    firm_id: str,
    text: str,
    case_type: str = "general",
    practice_area: str = "general",
) -> list[dict]:
    """Extract structured timeline events from a single document's text.

    Args:
        document_id: Source document ID (linked to each CaseEvent).
        case_id: Parent case ID.
        firm_id: Owning firm ID (tenant isolation).
        text: Document text content.
        case_type: For significance assessment.
        practice_area: For context.

    Returns:
        List of CaseEvent dicts (persisted to DB via DataFlow).

    Flow:
        1. Fetch existing events for dedup context
        2. Fetch known parties from Case record
        3. Run TimelineExtractionSignature via Kaizen BaseAgent
        4. Parse LLM response into CaseEvent records
        5. Deduplicate against existing events
        6. Persist via caseevent_bulkcreate workflow
        7. Return created events
    """
```

```python
def extract_timeline_from_all_documents(
    case_id: str,
    firm_id: str,
) -> dict:
    """Extract timeline events from ALL documents attached to a case.

    Args:
        case_id: Case to extract from.
        firm_id: Owning firm.

    Returns:
        Dict with total_events, new_events, skipped_documents, errors.

    Flow:
        1. List all documents for case (document_list workflow, filter ocr_status=complete)
        2. Fetch case metadata for case_type and practice_area
        3. For each document with ocr_text:
           a. Call extract_timeline_from_document()
           b. Accumulate results
        4. Return summary
    """
```

```python
def build_case_timeline(
    case_id: str,
    firm_id: str,
    include_manual: bool = True,
    significance_filter: Optional[list[str]] = None,
    event_type_filter: Optional[list[str]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """Build a complete timeline for a case, sorted by date.

    Args:
        case_id: Case ID.
        firm_id: Owning firm.
        include_manual: Include manually-created events.
        significance_filter: e.g. ["critical", "high"]
        event_type_filter: e.g. ["breach", "filing"]
        date_from: Only events on or after this date.
        date_to: Only events on or before this date.
        limit: Pagination limit.
        offset: Pagination offset.

    Returns:
        Dict with events (sorted by event_date ASC, nulls last),
        total count, filter metadata.

    Sort order:
        1. Events with event_date: ascending by event_date
        2. Events without event_date: grouped at end, sorted by created_at
    """
```

### Date parsing strategy

The LLM produces `parsed_date` as ISO 8601 or null. Post-processing applies a fallback parser:

```
Input text                        -> event_date           event_date_text
"15 March 2024"                   -> 2024-03-15T00:00:00  "15 March 2024"
"on or about 15 March 2024"       -> 2024-03-15T00:00:00  "on or about 15 March 2024"
"March 2024"                      -> 2024-03-01T00:00:00  "March 2024"
"Q1 2024"                         -> 2024-01-01T00:00:00  "Q1 2024"
"2024"                            -> 2024-01-01T00:00:00  "2024"
"recently"                        -> None                 "recently"
"before the contract was signed"  -> None                 "before the contract was signed"
"sometime in late 2023"           -> 2023-10-01T00:00:00  "sometime in late 2023"
```

For approximate dates (quarters, months, years, "late/early"), the `event_date` is set to the start of the period. The `event_date_text` always preserves the original expression. The `metadata` dict records `{"date_precision": "day"|"month"|"quarter"|"year"|"approximate"|"unparseable"}`.

### Deduplication strategy

When extracting from multiple documents that reference overlapping facts, duplicates are expected. The dedup algorithm:

1. **Candidate matching**: For each new event, find existing events where:
   - `event_date` matches (within 1-day tolerance) OR both are `None`
   - AND text similarity between `description` fields exceeds 0.85 (cosine similarity on embedded descriptions) OR Jaccard token overlap exceeds 0.70

2. **Resolution**: When a duplicate is detected:
   - Keep the event with higher `confidence`
   - Merge `parties_involved` (union)
   - Merge `source_text` (append with separator if from different documents)
   - Record the duplicate's `document_id` in `metadata.additional_source_documents`

3. **Group ID**: Dedup-merged events share a `metadata.dedup_group_id` (UUID) so the frontend can show "this event was found in 3 documents."

### Auto-extraction trigger

After `process_document()` completes successfully in `services/document_processor.py`, trigger timeline extraction:

```python
# In process_document(), after _update_document_status(... "complete" ...):
try:
    from legalcopilot.services.timeline_extractor import extract_timeline_from_document
    # Fetch case metadata for case_type
    case_results = _execute_workflow("case_read", {"id": case_id})
    case_record = case_results.get("result", {})
    extract_timeline_from_document(
        document_id=document_id,
        case_id=case_id,
        firm_id=firm_id,
        text=stored_text,
        case_type=case_record.get("case_type", "general"),
        practice_area=case_record.get("practice_area", "general"),
    )
except Exception:
    logger.warning("Timeline extraction failed for document %s, continuing", document_id)
```

This is best-effort: extraction failure does not block document processing.

---

## API Endpoints

**Add to**: `src/legalcopilot/api/cases.py` inside `register_case_routes()`, or create a new `register_timeline_routes()` function.

### GET /api/cases/:id/timeline

List all timeline events for a case, sorted by date.

**Handler**: `get_case_timeline`

```
Parameters:
    case_id: str          (path)
    firm_id: str          (required)
    significance: str     (optional, comma-separated: "critical,high")
    event_type: str       (optional, comma-separated: "breach,filing")
    date_from: str        (optional, ISO 8601)
    date_to: str          (optional, ISO 8601)
    include_manual: bool  (optional, default True)
    sort: str             (optional, "asc" or "desc", default "asc")
    limit: int            (optional, default 50, max 200)
    offset: int           (optional, default 0)

Response 200:
{
    "case_id": "...",
    "events": [
        {
            "id": "uuid",
            "case_id": "...",
            "firm_id": "...",
            "document_id": "uuid | null",
            "event_date": "2024-03-15T00:00:00Z | null",
            "event_date_text": "on or about 15 March 2024",
            "description": "Defendant served notice of termination",
            "significance": "critical",
            "parties_involved": ["Plaintiff Pte Ltd", "Defendant Corp"],
            "event_type": "notice_served",
            "source_text": "By letter dated on or about 15 March 2024, the Defendant served...",
            "confidence": 0.92,
            "is_manual": false,
            "metadata": {
                "date_precision": "day",
                "extraction_model": "gpt-4o",
                "dedup_group_id": "uuid"
            },
            "created_at": "2024-06-01T10:00:00Z",
            "updated_at": "2024-06-01T10:00:00Z"
        }
    ],
    "total": 47,
    "limit": 50,
    "offset": 0,
    "filters_applied": {
        "significance": null,
        "event_type": null,
        "date_from": null,
        "date_to": null,
        "include_manual": true
    }
}

Response 404:
    {"error": "Case not found", "case_id": "..."}
```

**Tenant isolation**: Verify `case.firm_id == firm_id` before returning events.

### POST /api/cases/:id/timeline/extract

Trigger AI extraction from all case documents. Long-running -- returns immediately with a job status.

**Handler**: `extract_case_timeline`

```
Parameters:
    case_id: str          (path)
    firm_id: str          (required)
    force_reextract: bool (optional, default False -- re-extract from already-processed docs)

Response 200 (extraction complete, synchronous for now):
{
    "case_id": "...",
    "status": "complete",
    "total_events_extracted": 23,
    "new_events": 18,
    "duplicate_events_merged": 5,
    "documents_processed": 7,
    "documents_skipped": 2,
    "errors": []
}

Response 200 (partial failure):
{
    "case_id": "...",
    "status": "partial",
    "total_events_extracted": 15,
    "new_events": 12,
    "duplicate_events_merged": 3,
    "documents_processed": 5,
    "documents_skipped": 1,
    "errors": [
        {"document_id": "uuid", "filename": "exhibit_A.pdf", "error": "extraction failed"}
    ]
}
```

**Design note**: This runs synchronously in v1. If extraction takes >30s per document and a case has many documents, move to an async job model (return 202 with a job_id, poll for completion). For v1, set a per-case timeout of 120s and process documents sequentially.

### POST /api/cases/:id/timeline

Add a manual event.

**Handler**: `add_timeline_event`

```
Parameters:
    case_id: str              (path)
    firm_id: str              (required)
    user_id: str              (required)
    event_date: str           (optional, ISO 8601)
    event_date_text: str      (required)
    description: str          (required)
    significance: str         (optional, default "neutral")
    parties_involved: list    (optional, default [])
    event_type: str           (optional, default "other")

Response 201:
{
    "id": "uuid",
    "case_id": "...",
    "firm_id": "...",
    "document_id": null,
    "event_date": "2024-03-15T00:00:00Z | null",
    "event_date_text": "15 March 2024",
    "description": "Initial client meeting",
    "significance": "neutral",
    "parties_involved": ["Client Name"],
    "event_type": "meeting",
    "source_text": "",
    "confidence": 1.0,
    "is_manual": true,
    "metadata": {"created_by": "user_id"},
    "created_at": "...",
    "updated_at": "..."
}

Validation errors 400:
    {"error": "description is required"}
    {"error": "event_date_text is required"}
    {"error": "Invalid event_type: xyz. Valid types: contract_signed, ..."}
```

**Manual event invariants**: `is_manual=True`, `confidence=1.0`, `document_id=None`, `source_text=""`.

### PUT /api/cases/:id/timeline/:eventId

Update an existing event.

**Handler**: `update_timeline_event`

```
Parameters:
    case_id: str              (path)
    event_id: str             (path, named eventId in URL)
    firm_id: str              (required)
    event_date: str           (optional)
    event_date_text: str      (optional)
    description: str          (optional)
    significance: str         (optional)
    parties_involved: list    (optional)
    event_type: str           (optional)

Response 200:
    { ...updated CaseEvent record... }

Response 404:
    {"error": "Event not found", "event_id": "..."}
```

**Constraint**: Both manual and AI-extracted events can be edited. Editing an AI-extracted event sets `metadata.manually_edited=True` and `metadata.edited_at=<timestamp>`.

### DELETE /api/cases/:id/timeline/:eventId

Delete an event (soft-delete via DataFlow).

**Handler**: `delete_timeline_event`

```
Parameters:
    case_id: str    (path)
    event_id: str   (path)
    firm_id: str    (required)

Response 200:
    {"deleted": true, "event_id": "..."}

Response 404:
    {"error": "Event not found", "event_id": "..."}
```

---

## Frontend: Chronology Tab

### Location

Add a "Chronology" or "Timeline" tab to the case detail view. This sits alongside existing tabs (Documents, Conversations, etc.).

### Components

#### TimelineView (main container)

```
+---------------------------------------------------------------+
|  [Case Title]                                                  |
|  Tabs: [Details] [Documents] [Conversations] [Chronology] ... |
+---------------------------------------------------------------+
|                                                                |
|  Filters: [Significance v] [Event Type v] [Date Range]        |
|  Sort: [Ascending v]    [+ Add Event]   [Auto-Extract Events] |
|                                                                |
|  --- Timeline ---                                              |
|                                                                |
|  o  15 Mar 2024                                                |
|  |  +----------------------------------------------------+    |
|  |  | Contract signed between parties                     |    |
|  |  | Type: contract_signed  Significance: [HIGH]         |    |
|  |  | Source: Agreement_v2.pdf (p.3)                       |    |
|  |  | Confidence: 0.95  Parties: Alpha Pte, Beta Corp     |    |
|  |  | "...the parties hereby execute this Agreement..."   |    |
|  |  +----------------------------------------------------+    |
|  |                                                             |
|  o  Q1 2024 (approximate)                                     |
|  |  +----------------------------------------------------+    |
|  |  | Performance issues reported by Alpha                |    |
|  |  | Type: breach  Significance: [CRITICAL]              |    |
|  |  | Source: Email_chain.pdf                              |    |
|  |  | Confidence: 0.78                                    |    |
|  |  +----------------------------------------------------+    |
|  |                                                             |
|  o  No date                                                    |
|  |  +----------------------------------------------------+    |
|  |  | Prior negotiations referenced in clause 14.2        |    |
|  |  | Type: communication  Significance: [LOW]            |    |
|  |  | Confidence: 0.65  [Review flag]                     |    |
|  |  +----------------------------------------------------+    |
|                                                                |
|  Showing 47 events  [Load more]                                |
+---------------------------------------------------------------+
```

#### EventCard

Each event on the timeline displays:
- **Date marker**: Rendered date (formatted) or "No date" or "Approximate: Q1 2024"
- **Description**: Primary text
- **Badges**: Event type pill, significance badge (color-coded: critical=red, high=orange, medium=yellow, low=blue, neutral=gray)
- **Source link**: If `document_id` is set, clickable link to the source document
- **Source excerpt**: Collapsed by default, expandable `source_text` showing the verbatim passage
- **Confidence indicator**: Visual bar or percentage. Below 0.5 shows a yellow "Review" flag
- **Parties**: Comma-separated party names
- **Actions**: Edit (pencil icon), Delete (trash icon with confirmation)
- **Dedup badge**: If `metadata.dedup_group_id` exists and multiple documents contributed, show "Found in N documents"

#### ManualEventForm

Modal or slide-out form for adding/editing events:
- Date picker (optional) + free text date field (required)
- Description textarea
- Significance dropdown
- Event type dropdown
- Parties involved (tag input, comma-separated)
- Save / Cancel buttons

#### AutoExtractButton

- Button text: "Auto-Extract Events"
- Loading state: spinner + "Extracting events from N documents..."
- Progress: Show per-document progress if extraction is sequential
- Completion: Toast notification "Extracted 18 new events from 7 documents"
- Error: Toast with "Extraction partially failed. 2 documents had errors."
- Disabled state: When no documents are attached to the case, or all documents have `ocr_status != "complete"`

### Filter behavior

| Filter | UI | Behavior |
|--------|-----|----------|
| Significance | Multi-select dropdown | Filter events by significance level(s). Default: all. |
| Event type | Multi-select dropdown | Filter by event_type(s). Default: all. |
| Date range | Two date pickers (from/to) | Filter events with event_date within range. Events with no event_date are always shown when "Include undated" checkbox is on. |
| Sort | Toggle button | Ascending (oldest first, default) or Descending (newest first). |
| Include manual | Checkbox | Show/hide manually-created events. Default: on. |

### Empty states

- **No events, no documents**: "No timeline events yet. Upload documents to auto-extract events, or add events manually."
- **No events, has documents**: "No timeline events extracted yet. Click 'Auto-Extract Events' to analyze your documents."
- **No events match filter**: "No events match your filters. Try adjusting your criteria."

---

## Edge Cases

### Ambiguous and unparseable dates

- **"Q1 2024"**: `event_date = 2024-01-01`, `metadata.date_precision = "quarter"`. Frontend renders as "Q1 2024" using `event_date_text`, not the parsed date.
- **"recently"**: `event_date = None`, `event_date_text = "recently"`. Sorted to end of timeline.
- **"before the contract was signed"**: `event_date = None`, `event_date_text = "before the contract was signed"`. If the contract signing date is known (from another event), `metadata.relative_anchor_event_id` can link to it for potential future resolution.
- **Conflicting dates**: Same event referenced with different dates in different documents. The dedup algorithm picks the higher-confidence extraction. Both dates stored in `metadata.conflicting_dates`.

### Duplicate events across documents

- A breach event described in the Statement of Claim, the Defence, and an email exhibit will match as duplicates.
- The dedup algorithm merges them into one event with `metadata.additional_source_documents = ["doc_id_2", "doc_id_3"]` and `metadata.dedup_group_id`.
- The `source_text` is the excerpt from the highest-confidence extraction. Additional excerpts available via the source documents.

### Large cases (100+ events)

- **Pagination**: Default page size 50. Frontend uses "Load more" infinite scroll rather than page numbers (timelines are inherently continuous).
- **API limit**: Max 200 events per request. For cases with 200+ events, require filters or date range narrowing.
- **Extraction cost**: A case with 50 documents at ~5000 tokens each = ~250K input tokens per extraction run. Cost guard: warn the user before extraction if `document_count > 20`, and require confirmation.
- **Token budget**: Each document extraction call budgets max 8000 output tokens. For very long documents (>50K chars), chunk the document and extract per-chunk, then dedup across chunks.

### Document deletion

- When a document is deleted (soft-delete), its CaseEvents remain. The `document_id` still references the soft-deleted document.
- If the document is hard-deleted (rare), events with that `document_id` get `metadata.source_document_deleted = True` and the source document link in the frontend shows "(document removed)".

### Concurrent extraction

- If two users trigger extraction simultaneously, the dedup algorithm handles it -- both runs extract events, and the second run's events dedup against the first run's persisted events.
- Guard: The extract endpoint should check for a recent extraction run (within last 60s) and return a message: "Extraction already in progress or recently completed. Use force_reextract=True to re-run."

### Re-extraction

- `force_reextract=True` does NOT delete existing AI-extracted events. It runs extraction again and dedup merges new findings.
- To start fresh, user must manually delete unwanted events first.
- Rationale: Users may have edited AI-extracted events. Re-extraction should add missing events, not destroy user edits.

---

## Audit Trail

Every CaseEvent mutation generates an AuditEntry:

| Action | entity_type | Details |
|--------|-------------|---------|
| Create (manual) | `case_event` | `{"source": "manual", "user_id": "..."}` |
| Create (AI) | `case_event` | `{"source": "ai_extraction", "document_id": "...", "model": "gpt-4o"}` |
| Update | `case_event` | `{"changed_fields": ["description", "significance"], "previous_values": {...}}` |
| Delete | `case_event` | `{"deleted_by": "user_id"}` |
| Bulk extract | `case_event` | `{"source": "bulk_extraction", "documents_processed": 7, "events_created": 18}` |

---

## Integration with Case Context

The timeline feeds into the case context assembly service (see `specs/case-context.md`). Specifically:

- `build_case_context()` includes a `timeline` key with all CaseEvents sorted by date.
- `build_case_context_text()` allocates a token budget slice to timeline events, prioritizing `critical` and `high` significance events.
- When the orchestrator processes a chat message for a case, the case context automatically includes the timeline -- the LLM can reference and reason about the chronology.

---

## Implementation Order

1. **CaseEvent model** -- add to `models/core.py`, run DataFlow migration
2. **TimelineExtractionSignature** -- add to `agents/signatures.py`
3. **Timeline extraction service** -- `services/timeline_extractor.py`
4. **API endpoints** -- add to `api/cases.py`
5. **Document processor hook** -- add auto-extraction trigger to `services/document_processor.py`
6. **Frontend Chronology tab** -- React components
7. **Integration with case context** -- wire into `services/case_context.py` (from case-context spec)
