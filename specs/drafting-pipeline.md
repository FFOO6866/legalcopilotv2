# Drafting Pipeline Specification

## Status

Draft — pending implementation.

## Overview

The drafting pipeline governs how legal documents are generated, persisted, versioned, and surfaced in LegalCoPilot v2. Today, the `draft_document` endpoint (at `src/legalcopilot/api/chat.py:494-553`) accepts an opaque `case_context` string, invokes `DraftingAgent.draft()`, and returns the result inline. Drafts exist only as chat message content — they are never saved as `Document` records and are not retrievable outside the conversation that produced them.

This spec closes that gap by defining:

1. A stage-to-template mapping grounded in Singapore Rules of Court 2021.
2. A draft generation flow with context auto-assembly.
3. Draft persistence as first-class `Document` records.
4. A "draft from chat" pathway that saves the result automatically.
5. Frontend components for a dedicated Drafts tab inside `CaseDetail`.

## Terminology

| Term | Definition |
|------|-----------|
| **Template** | A named document type (e.g., `statement_of_claim`) available for generation at a given stage. |
| **Stage** | One of the 8 lifecycle values on `Case.stage`: `intake`, `fact_gathering`, `research`, `analysis`, `drafting`, `review`, `submission`, `complete`. |
| **Draft version** | An auto-incrementing integer scoped to `(case_id, template, stage)`. |
| **Draft status** | Lifecycle of a single draft: `draft` -> `review` -> `final`. |
| **Context summary** | A pre-generation digest showing the user how much case material will feed the draft (document count, event count, citation count, prior draft count). |

---

## 1. Stage-to-Template Mapping

Templates are scoped to stages per the Singapore Rules of Court 2021 and the 8-stage case lifecycle. The mapping below is the canonical source. Templates marked with a practice-area qualifier are available only when `Case.practice_area` matches.

| Stage | Available Templates |
|-------|-------------------|
| `intake` | `legal_opinion`, `chronology_summary` |
| `fact_gathering` | `fact_summary`, `chronology_summary` |
| `research` | `research_memo`, `case_analysis` |
| `analysis` | `legal_opinion`, `risk_assessment`, `letter_of_demand`, `advisory_letter` |
| `drafting` | `statement_of_claim`, `defence`, `reply`, `counterclaim`, `affidavit`, `notice`, `application`, `writ_for_divorce` (family), `statement_of_particulars` (family), `parenting_plan` (family), `matrimonial_property_plan` (family), `mitigation_plea` (criminal), `representations_to_agc` (criminal), `bail_application` (criminal) |
| `review` | `aeic`, `opening_statement`, `bundle_of_authorities`, `submission`, `affidavit_of_assets_and_means` (family) |
| `submission` | `closing_submissions`, `bill_of_costs`, `appeal_petition` |
| `complete` | _(none — no drafting at terminal stage)_ |

### 1.1 Practice-Area Filtering

When the user requests templates for a stage, the returned list is the union of:

- All templates for that stage with no practice-area qualifier.
- Templates whose practice-area qualifier matches `Case.practice_area`.

For example, at the `drafting` stage on a `criminal` case, the user sees `statement_of_claim`, `defence`, `reply`, `counterclaim`, `affidavit`, `notice`, `application`, `mitigation_plea`, `representations_to_agc`, and `bail_application`. The `writ_for_divorce` and other family-specific templates are excluded because the case is not `family`.

**Practice-area-specific vs general templates:**

- **General** (available in all practice areas): `statement_of_claim`, `defence`, `reply`, `counterclaim`, `affidavit`, `notice`, `application`, `aeic`, `opening_statement`, `bundle_of_authorities`, `submission`, `closing_submissions`, `bill_of_costs`, `appeal_petition`, `legal_opinion`, `chronology_summary`, `fact_summary`, `research_memo`, `case_analysis`, `risk_assessment`, `letter_of_demand`, `advisory_letter`.
- **Family only**: `writ_for_divorce`, `statement_of_particulars`, `parenting_plan`, `matrimonial_property_plan`, `affidavit_of_assets_and_means`.
- **Criminal only**: `mitigation_plea`, `representations_to_agc`, `bail_application`.

### 1.2 SOP Template Cross-Reference

The existing SOP templates (in `src/legalcopilot/services/sop_service.py`) define `skills.drafting.types` per `case_type`. Those lists govern which document types the `DraftingAgent` can produce for a given SOP. The stage-to-template mapping in this spec is additive: it controls which templates the frontend offers at each stage, while the SOP `drafting.types` list controls what the agent is instructed to produce. If a template is not in the SOP's `drafting.types`, the agent can still attempt it, but a warning is logged (existing behavior at `chat.py:519-525`).

### 1.3 Data Representation

The mapping is stored as a Python dict in the `StageManager` service (see Section 5) so it can be queried at runtime without a database round-trip:

```python
STAGE_TEMPLATES: dict[str, list[dict]] = {
    "intake": [
        {"template": "legal_opinion", "practice_areas": None},
        {"template": "chronology_summary", "practice_areas": None},
    ],
    "fact_gathering": [
        {"template": "fact_summary", "practice_areas": None},
        {"template": "chronology_summary", "practice_areas": None},
    ],
    "research": [
        {"template": "research_memo", "practice_areas": None},
        {"template": "case_analysis", "practice_areas": None},
    ],
    "analysis": [
        {"template": "legal_opinion", "practice_areas": None},
        {"template": "risk_assessment", "practice_areas": None},
        {"template": "letter_of_demand", "practice_areas": None},
        {"template": "advisory_letter", "practice_areas": None},
    ],
    "drafting": [
        {"template": "statement_of_claim", "practice_areas": None},
        {"template": "defence", "practice_areas": None},
        {"template": "reply", "practice_areas": None},
        {"template": "counterclaim", "practice_areas": None},
        {"template": "affidavit", "practice_areas": None},
        {"template": "notice", "practice_areas": None},
        {"template": "application", "practice_areas": None},
        {"template": "writ_for_divorce", "practice_areas": ["family"]},
        {"template": "statement_of_particulars", "practice_areas": ["family"]},
        {"template": "parenting_plan", "practice_areas": ["family"]},
        {"template": "matrimonial_property_plan", "practice_areas": ["family"]},
        {"template": "mitigation_plea", "practice_areas": ["criminal"]},
        {"template": "representations_to_agc", "practice_areas": ["criminal"]},
        {"template": "bail_application", "practice_areas": ["criminal"]},
    ],
    "review": [
        {"template": "aeic", "practice_areas": None},
        {"template": "opening_statement", "practice_areas": None},
        {"template": "bundle_of_authorities", "practice_areas": None},
        {"template": "submission", "practice_areas": None},
        {"template": "affidavit_of_assets_and_means", "practice_areas": ["family"]},
    ],
    "submission": [
        {"template": "closing_submissions", "practice_areas": None},
        {"template": "bill_of_costs", "practice_areas": None},
        {"template": "appeal_petition", "practice_areas": None},
    ],
    "complete": [],
}
```

`practice_areas: None` means available in all practice areas.

---

## 2. Draft Generation Flow

### 2.1 User-Initiated (Drafts Tab)

The happy path, step by step:

1. User navigates to `CaseDetail` and clicks the **Drafts** tab.
2. User clicks **"Generate Draft"** button.
3. A modal opens showing templates available for the case's CURRENT `stage` (filtered by `practice_area` per Section 1.1). If the current stage has no templates (i.e., `complete`), the button is disabled with a tooltip: "No templates available at the current stage."
4. User selects a template from the list.
5. User optionally types free-text drafting instructions (max 5,000 characters).
6. Before confirming, the modal displays a **context summary** computed from the case's existing data:
   - `{N} documents` — count of `Document` records for this case.
   - `{N} events` — count of timeline events from case metadata (if tracked).
   - `{N} citations` — count of citations from prior research messages.
   - `{N} prior drafts` — count of existing `Document` records with `file_type="draft"` for this case.
7. User clicks **"Generate"**.
8. Frontend sends: `POST /api/cases/:id/drafts/generate`
9. Backend auto-assembles `case_context` (see Section 2.2), invokes the Kaizen `DraftingAgent` via the PDCA orchestrator, and saves the result as a `Document` record.
10. Response includes the new `Document` record.
11. Frontend refreshes the Drafts tab — the new draft appears under the current stage's section.

### 2.2 Case Context Auto-Assembly

Today, `case_context` is an opaque string passed by the caller. For draft generation, the backend assembles it automatically from the case's data:

```python
def assemble_draft_context(case_id: str, firm_id: str) -> dict:
    """Build a structured context dict from all case data."""
    # 1. Case record
    case = _execute_workflow("case_read", {"id": case_id})["result"]

    # 2. All documents for the case (text content for RAG)
    docs = _execute_workflow("document_list", {
        "filter": {"case_id": case_id, "firm_id": firm_id},
        "limit": 100,
        "offset": 0,
    })["result"]

    # 3. Prior drafts for this case
    prior_drafts = [d for d in docs if d.get("file_type") == "draft"]

    # 4. Recent conversation messages linked to this case
    conversations = _execute_workflow("conversation_list", {
        "filter": {"case_id": case_id, "firm_id": firm_id},
        "limit": 10,
        "offset": 0,
    })["result"]

    # 5. RAG context from case documents
    rag_context = retrieve_context(
        query=case.get("description", case.get("title", "")),
        filter_conditions={"case_id": case_id},
        top_k=15,
    )

    return {
        "case": case,
        "documents": docs,
        "prior_drafts": prior_drafts,
        "conversations": conversations,
        "rag_context": rag_context,
        "document_count": len(docs),
        "citation_count": len(rag_context.get("sources", [])),
        "prior_draft_count": len(prior_drafts),
    }
```

The assembled context is serialized to JSON and passed to the orchestrator's `process_request` as `case_context`.

### 2.3 API Contract

#### `POST /api/cases/:id/drafts/generate`

**Request body:**

```json
{
  "template": "letter_of_demand",
  "stage": "analysis",
  "instructions": "Focus on breach of warranty clause. Demand $50,000.",
  "tone": "firm"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `template` | string | yes | — | One of the template names from Section 1. |
| `stage` | string | yes | — | Must match `Case.stage` at time of request. |
| `instructions` | string | no | `""` | Free-text drafting instructions. Max 5,000 chars. |
| `tone` | string | no | `"formal"` | One of: `formal`, `firm`, `conciliatory`, `neutral`. |

**Validation rules:**

- `template` must be in the stage-to-template mapping for the given `stage`.
- `stage` must match the case's current `Case.stage` value. If mismatched, return `400` with `"Case is currently at stage '{actual}', not '{requested}'."`.
- `template` must pass the practice-area filter for the case's `practice_area`.

**Success response (201):**

```json
{
  "draft": {
    "id": "uuid",
    "case_id": "uuid",
    "firm_id": "uuid",
    "filename": "letter_of_demand_v1.md",
    "file_type": "draft",
    "content_text": "...(full markdown draft)...",
    "metadata": {
      "template": "letter_of_demand",
      "stage": "analysis",
      "version": 1,
      "instructions": "Focus on breach of warranty clause.",
      "tone": "firm",
      "draft_status": "draft",
      "agent": "DraftingAgent",
      "sop_template": "Contract Dispute Analysis",
      "confidence": 0.87,
      "citations_used": ["[2024] SGHC 123", "Civil Law Act s 6"],
      "generated_at": "2026-06-23T10:30:00Z"
    },
    "created_at": "2026-06-23T10:30:00Z"
  },
  "context_summary": {
    "document_count": 5,
    "citation_count": 12,
    "prior_draft_count": 1
  },
  "sources": [...]
}
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| `400` | Invalid template for stage, stage mismatch, practice-area mismatch, instructions too long. |
| `404` | Case not found or firm mismatch. |
| `500` | Agent generation failure. |

#### `GET /api/cases/:id/drafts`

List all drafts for a case, grouped by stage.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `stage` | string | `""` | Filter to a specific stage. |
| `template` | string | `""` | Filter to a specific template. |
| `draft_status` | string | `""` | Filter by draft status (`draft`, `review`, `final`). |
| `limit` | int | `50` | Max records. |
| `offset` | int | `0` | Pagination offset. |

**Response:**

```json
{
  "case_id": "uuid",
  "drafts": [...],
  "total": 7,
  "limit": 50,
  "offset": 0
}
```

#### `PATCH /api/cases/:id/drafts/:draft_id/status`

Update a draft's status.

**Request body:**

```json
{
  "draft_status": "review"
}
```

Valid transitions: `draft` -> `review` -> `final`. No backward transitions. Returns the updated `Document` record.

---

## 3. Draft Persistence

### 3.1 Storage Model

Every generated draft is saved as a `Document` record (defined at `src/legalcopilot/models/core.py:165-213`). The existing `Document` model is reused without schema changes, leveraging its `metadata` dict for draft-specific fields.

**Document record fields for drafts:**

| Field | Value for Drafts |
|-------|-----------------|
| `id` | UUID, auto-generated. |
| `case_id` | The case this draft belongs to. |
| `firm_id` | Tenant isolation. |
| `uploaded_by_id` | The user who triggered generation. |
| `filename` | `"{template}_v{version}.md"` — e.g., `letter_of_demand_v1.md`. |
| `file_type` | `"draft"` — **requires adding `"draft"` to the `file_type` validation `one_of` list** on the `Document` model. |
| `storage_url` | Empty string (content stored inline via `ocr_text` or `metadata`). |
| `file_size_bytes` | Byte length of `content_text`. |
| `ocr_text` | The full markdown draft content. Reused since this field holds extracted text and is already indexed for search. |
| `ocr_status` | `"complete"` (the draft is the "extracted" content). |
| `classification` | `{}` |
| `metadata` | Draft-specific metadata (see below). |

**`metadata` dict structure for drafts:**

```python
{
    "template": "letter_of_demand",      # template name
    "stage": "analysis",                 # stage at time of generation
    "version": 1,                        # auto-incremented per (case_id, template, stage)
    "instructions": "...",               # user's free-text instructions
    "tone": "firm",                      # tone parameter
    "draft_status": "draft",             # draft | review | final
    "agent": "DraftingAgent",            # agent that produced it
    "sop_template": "Contract Dispute",  # SOP template name used
    "confidence": 0.87,                  # agent confidence score
    "citations_used": [...],             # list of citations from the draft
    "review_notes": "...",               # agent's review notes
    "generated_at": "2026-06-23T10:30:00Z"
}
```

### 3.2 Model Change Required

The `Document` model's `file_type` validation must be extended:

```python
# Current (src/legalcopilot/models/core.py:187-198)
"file_type": {
    "one_of": [
        "pleading", "affidavit", "exhibit", "correspondence",
        "submission", "judgment", "contract", "memo", "other",
    ]
}

# Updated — add "draft"
"file_type": {
    "one_of": [
        "pleading", "affidavit", "exhibit", "correspondence",
        "submission", "judgment", "contract", "memo", "draft", "other",
    ]
}
```

The frontend `FileType` type (at `src/frontend/src/types/case.ts:17-26`) must also be extended to include `"draft"`.

### 3.3 Version Numbering

Version numbers auto-increment per `(case_id, template, stage)` tuple:

1. Before saving a new draft, query existing drafts:
   ```python
   existing = _execute_workflow("document_list", {
       "filter": {
           "case_id": case_id,
           "firm_id": firm_id,
           "file_type": "draft",
       },
       "limit": 200,
       "offset": 0,
   })["result"]
   ```
2. Filter to matching `(template, stage)` by inspecting each record's `metadata.template` and `metadata.stage`.
3. Find the max `metadata.version` among matches.
4. New version = max + 1 (or 1 if none exist).

### 3.4 Draft Status Lifecycle

```
draft  -->  review  -->  final
```

- **draft**: Initial state after generation. Editable (regeneration creates a new version).
- **review**: Marked for lawyer review. No further AI regeneration at this version.
- **final**: Approved by the lawyer. Locked — the definitive version.

Status transitions are forward-only. Transitioning backward (e.g., `final` -> `review`) is not permitted. To revise a finalized draft, the user generates a new version.

---

## 4. Draft from Chat

### 4.1 Detection

When a user types a message like "Draft a letter of demand for breach of contract" in a case-bound conversation, the orchestrator's PDCA cycle already routes to the `DraftingAgent` via the `routing_decision` (see `src/legalcopilot/agents/orchestrator.py:285`). This pathway needs enhancement to also persist the draft.

### 4.2 Enhanced Flow

1. User sends a message in a case-bound conversation (`conversation.case_id` is set).
2. Orchestrator runs the PDCA cycle as normal.
3. If the result includes a `draft` key in the response (i.e., `routing.drafting == True` or `plan.include_drafting == True`), the `send_message` handler:
   a. Extracts the draft content from `result["response"]["draft"]`.
   b. Infers the template from the draft result's `document_type` field.
   c. Saves a `Document` record using the same persistence logic as Section 3.
   d. Includes a link in the assistant message metadata:
      ```python
      assistant_msg_data["metadata"]["saved_draft"] = {
          "document_id": doc_id,
          "template": template,
          "stage": case_stage,
          "version": version,
          "link_text": f"Saved to Drafts tab -> {stage_label} -> {template_label} v{version}",
      }
      ```
4. Frontend renders the `saved_draft` metadata as a clickable link in the message bubble that navigates to the Drafts tab and highlights the saved draft.

### 4.3 Chat Message Rendering

When a message's `metadata.saved_draft` is present, the `MessageBubble` component renders an additional element below the message content:

```
+-------------------------------------------------------+
|  [Draft icon] Saved to Drafts tab                     |
|  Analysis stage -> Letter of Demand v1                 |
|  [View Draft]                                         |
+-------------------------------------------------------+
```

Clicking "View Draft" switches to the Drafts tab and scrolls to the relevant stage section.

---

## 5. Backend Service: Draft Manager

A new service at `src/legalcopilot/services/draft_manager.py` encapsulates all draft-related logic.

### 5.1 Public Interface

```python
class DraftManager:
    def generate_draft(
        self,
        case_id: str,
        firm_id: str,
        user_id: str,
        template: str,
        stage: str,
        instructions: str = "",
        tone: str = "formal",
    ) -> dict:
        """Generate a draft and persist it as a Document record.

        Returns the saved Document record with draft content.
        Raises ValueError for validation failures.
        """

    def list_drafts(
        self,
        case_id: str,
        firm_id: str,
        stage: str = "",
        template: str = "",
        draft_status: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List drafts for a case, optionally filtered."""

    def update_draft_status(
        self,
        draft_id: str,
        firm_id: str,
        new_status: str,
    ) -> dict:
        """Transition a draft's status. Returns updated record."""

    def get_available_templates(
        self,
        stage: str,
        practice_area: str = "",
    ) -> list[str]:
        """Return template names available for a stage + practice area."""

    def get_context_summary(
        self,
        case_id: str,
        firm_id: str,
    ) -> dict:
        """Return a context summary for the pre-generation modal."""

    def save_chat_draft(
        self,
        case_id: str,
        firm_id: str,
        user_id: str,
        draft_content: dict,
        stage: str,
    ) -> dict:
        """Save a draft produced by the chat pathway."""
```

### 5.2 Orchestrator Integration

The `DraftManager.generate_draft` method:

1. Validates the template against the stage-to-template mapping and practice-area filter.
2. Calls `assemble_draft_context(case_id, firm_id)` to build the context.
3. Loads the SOP template for the case's `case_type`.
4. Invokes the PDCA orchestrator with `include_drafting=True` and the assembled context.
5. Extracts the draft from the orchestrator result.
6. Computes the next version number.
7. Saves the `Document` record via the `document_create` DataFlow workflow.
8. Returns the saved record.

---

## 6. API Route Registration

New endpoints registered in a new file `src/legalcopilot/api/drafts.py`:

```python
def register_draft_routes(app: Nexus) -> None:
    """Register draft generation and management endpoints."""

    @app.handler("generate_draft", description="Generate a draft document for a case")
    async def generate_draft(
        case_id: str,
        firm_id: str,
        user_id: str,
        template: str,
        stage: str,
        instructions: str = "",
        tone: str = "formal",
    ) -> dict: ...

    @app.handler("list_drafts", description="List drafts for a case")
    async def list_drafts(
        case_id: str,
        firm_id: str,
        stage: str = "",
        template: str = "",
        draft_status: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict: ...

    @app.handler("update_draft_status", description="Update a draft's status")
    async def update_draft_status(
        draft_id: str,
        firm_id: str,
        draft_status: str,
    ) -> dict: ...

    # NOTE: `get_stage_templates` is registered in `src/legalcopilot/api/stages.py`
    # (see stage-transitions.md Section 4.3). The drafts module imports it; do NOT
    # re-register it here. The DraftManager delegates to StageManager.get_available_templates().

    @app.handler("get_draft_context_summary", description="Get context summary for draft generation")
    async def get_draft_context_summary(
        case_id: str,
        firm_id: str,
    ) -> dict: ...
```

These handlers are registered in `src/legalcopilot/api/app.py` alongside the existing `register_case_routes` and `register_chat_routes` calls.

---

## 7. Frontend: Drafts Tab

### 7.1 New Components

| Component | Path | Purpose |
|-----------|------|---------|
| `DraftsTab` | `src/frontend/src/components/cases/DraftsTab.tsx` | Top-level tab content for CaseDetail. |
| `DraftStageSection` | `src/frontend/src/components/cases/DraftStageSection.tsx` | Accordion section for one stage. |
| `DraftCard` | `src/frontend/src/components/cases/DraftCard.tsx` | Individual draft display card. |
| `DraftGenerateModal` | `src/frontend/src/components/cases/DraftGenerateModal.tsx` | Template selector + instructions modal. |
| `DraftViewer` | `src/frontend/src/components/cases/DraftViewer.tsx` | Markdown-rendered draft viewer panel. |

### 7.2 DraftsTab Layout

```
+----------------------------------------------------------+
|  [Generate Draft]                           [Filter: All] |
+----------------------------------------------------------+
|                                                          |
|  v Analysis (2 drafts)                                   |
|  +------------------------------------------------------+|
|  | Letter of Demand v2    |  Jun 23  | [draft]  [View]  ||
|  | Letter of Demand v1    |  Jun 22  | [final]  [View]  ||
|  +------------------------------------------------------+|
|                                                          |
|  v Drafting (1 draft)                                    |
|  +------------------------------------------------------+|
|  | Statement of Claim v1  |  Jun 21  | [review] [View]  ||
|  +------------------------------------------------------+|
|                                                          |
|  > Research (0 drafts)  [collapsed]                      |
|                                                          |
+----------------------------------------------------------+
```

**Behavior:**

- Stage sections are rendered as accordions. Stages with drafts are expanded by default; empty stages are collapsed.
- Only stages that have at least one draft OR are the current stage are shown. The `complete` stage is never shown.
- Each `DraftCard` displays:
  - Template name (human-readable label, e.g., "Letter of Demand").
  - Version number (e.g., "v2").
  - Date generated.
  - Status badge: `draft` (gray), `review` (amber), `final` (green).
  - "View" button to open the `DraftViewer`.
- The "Generate Draft" button opens `DraftGenerateModal`.

### 7.3 DraftGenerateModal

```
+------------------------------------------+
|  Generate Draft                     [X]  |
+------------------------------------------+
|                                          |
|  Template:                               |
|  [v] Letter of Demand                    |
|      Advisory Letter                     |
|      Legal Opinion                       |
|      Risk Assessment                     |
|                                          |
|  Instructions (optional):                |
|  +--------------------------------------+|
|  | Focus on breach of warranty clause.  ||
|  | Demand $50,000 in damages.           ||
|  +--------------------------------------+|
|                                          |
|  Tone:                                   |
|  ( ) Formal  (*) Firm                    |
|  ( ) Conciliatory  ( ) Neutral           |
|                                          |
|  Context Summary:                        |
|  5 documents | 12 citations              |
|  3 prior drafts                          |
|                                          |
|  [Cancel]              [Generate Draft]  |
+------------------------------------------+
```

**Behavior:**

- Template list is populated by calling `get_stage_templates` with the case's current stage and practice area.
- Context summary is populated by calling `get_draft_context_summary`.
- On "Generate Draft" click, calls `generate_draft` and shows a loading spinner.
- On success, closes the modal and refreshes the drafts list.

### 7.4 DraftViewer

A slide-over panel or full-width view that renders the draft markdown content.

**Features:**

- Markdown rendering (using the existing `react-markdown` dependency).
- Header showing: template name, version, stage, date, status badge.
- Action buttons:
  - "Mark for Review" (transitions `draft` -> `review`).
  - "Approve as Final" (transitions `review` -> `final`).
  - "Regenerate" (opens `DraftGenerateModal` pre-filled with the same template and instructions, creating a new version).
  - "Copy to Clipboard" (copies raw markdown).
- Version history sidebar: lists all versions of the same `(template, stage)` with click to view any version.

### 7.5 CaseDetail Integration

The `CaseDetail` page (at `src/frontend/src/pages/CaseDetail.tsx`) gains a fourth tab: **Drafts**.

```tsx
<Tabs.Trigger value="drafts">
  <PenTool size={16} />
  Drafts
</Tabs.Trigger>

<Tabs.Content value="drafts">
  <DraftsTab caseId={caseData.id} firmId={firmId} userId={userId} stage={caseData.stage} practiceArea={caseData.practice_area} />
</Tabs.Content>
```

### 7.6 Frontend Service

New functions in `src/frontend/src/services/draft.service.ts`:

```typescript
export async function generateDraft(
  case_id: string, firm_id: string, user_id: string,
  template: string, stage: string,
  instructions?: string, tone?: string,
): Promise<DraftResponse>;

export async function listDrafts(
  case_id: string, firm_id: string,
  stage?: string, template?: string, draft_status?: string,
  limit?: number, offset?: number,
): Promise<PaginatedResponse<DraftDocument>>;

export async function updateDraftStatus(
  draft_id: string, firm_id: string, draft_status: string,
): Promise<DraftDocument>;

export async function getStageTemplates(
  stage: string, practice_area?: string,
): Promise<TemplateListResponse>;

export async function getDraftContextSummary(
  case_id: string, firm_id: string,
): Promise<ContextSummary>;
```

### 7.7 TypeScript Types

New types in `src/frontend/src/types/case.ts`:

```typescript
export type DraftStatus = "draft" | "review" | "final";

export interface DraftMetadata {
  template: string;
  stage: string;
  version: number;
  instructions: string;
  tone: string;
  draft_status: DraftStatus;
  agent: string;
  sop_template: string;
  confidence: number;
  citations_used: string[];
  review_notes: string;
  generated_at: string;
}

export interface DraftDocument extends Document {
  metadata: DraftMetadata;
}

export interface ContextSummary {
  document_count: number;
  citation_count: number;
  prior_draft_count: number;
}

export interface TemplateListResponse {
  stage: string;
  templates: string[];
}

export interface DraftResponse {
  draft: DraftDocument;
  context_summary: ContextSummary;
  sources: Array<{ citation: string; relevance: number }>;
}
```

---

## 8. Migration Path from Existing `draft_document` Endpoint

The existing `draft_document` handler at `chat.py:494-553` continues to function as-is for backward compatibility. It is not removed. Instead:

1. The new `generate_draft` handler is the primary pathway for case-bound draft generation (with persistence).
2. The existing `draft_document` handler remains for standalone drafting (no case binding, no persistence) — useful for quick one-off drafts from the chat interface.
3. The `send_message` handler is enhanced per Section 4.2 to detect and persist drafts produced during case-bound conversations.

---

## 9. Document Export

Drafts are stored as markdown content in the `ocr_text` field of the `Document` record. For lawyer review, court filing, and client delivery, drafts must be exportable as `.docx` (Microsoft Word) files.

### 9.1 Export Flow

1. User views a draft in the `DraftViewer` component.
2. User clicks **"Export as Word"** button.
3. Frontend calls: `POST /api/cases/:id/drafts/:draft_id/export`
4. Backend converts the markdown draft content to `.docx` format using `python-docx`.
5. The generated `.docx` is uploaded to S3 (or local storage in dev) and a presigned download URL is returned.
6. Frontend triggers a browser download from the presigned URL.

### 9.2 API Contract

#### `POST /api/cases/:id/drafts/:draft_id/export`

**Handler name:** `export_draft`

**Request body:**

```json
{
  "format": "docx"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `format` | string | no | `"docx"` | Export format. Currently only `docx` is supported. |

**Success response (200):**

```json
{
  "document_id": "uuid",
  "firm_id": "uuid",
  "export_format": "docx",
  "filename": "letter_of_demand_v1.docx",
  "download_url": "https://storage.example.com/presigned/...",
  "expires_at": "2026-06-23T11:30:00Z"
}
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| `400` | Unsupported format. |
| `404` | Draft not found, case not found, or firm mismatch. |
| `500` | Conversion failure. |

### 9.3 Conversion Logic

```python
def export_draft(document_id: str, firm_id: str, format: str = "docx") -> dict:
    """Convert a markdown draft to the requested format and return a download URL.

    Args:
        document_id: The Document record ID of the draft.
        firm_id: Tenant isolation.
        format: Export format (currently only "docx").

    Returns:
        Dict with download_url and metadata.
    """
    from docx import Document as DocxDocument
    import markdown
    import io

    # 1. Fetch the draft Document record
    draft = _execute_workflow("document_read", {"id": document_id})["result"]
    if not draft or draft.get("firm_id") != firm_id:
        raise ValueError("Draft not found")
    if draft.get("file_type") != "draft":
        raise ValueError("Document is not a draft")

    # 2. Get the markdown content
    md_content = draft.get("ocr_text", "")

    # 3. Convert markdown to docx
    doc = DocxDocument()
    doc.add_heading(draft.get("metadata", {}).get("template", "Draft"), level=1)

    # Set page format: A4, 2.54cm all sides (Singapore court standard)
    from docx.shared import Cm
    for section in doc.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(2.54)
        section.right_margin = Cm(2.54)

    # Parse markdown sections and add to docx with appropriate styles
    # Conversion rules:
    #   - Markdown headings (#, ##, ###) -> Word heading styles (Heading 1, 2, 3)
    #   - Bold/italic -> Word character formatting
    #   - Bullet lists -> Word list formatting
    #   - Legal citation formatting preserved
    _markdown_to_docx(doc, md_content)

    # 4. Save to buffer and upload
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    # 5. Upload and generate presigned URL
    template = draft.get("metadata", {}).get("template", "draft")
    version = draft.get("metadata", {}).get("version", 1)
    filename = f"{template}_v{version}.docx"
    download_url = _upload_and_presign(buffer, filename, firm_id)

    return {
        "document_id": document_id,
        "firm_id": firm_id,
        "export_format": format,
        "filename": filename,
        "download_url": download_url,
        "expires_at": _presign_expiry(),
    }
```

### 9.4 Dependencies

Add `python-docx` to the project dependencies:

```
python-docx>=1.1.0
```

### 9.5 Frontend: Export Button

The `DraftViewer` component gains an **"Export as Word"** button alongside the existing action buttons:

```tsx
<Button
  variant="outline"
  onClick={() => handleExport(draft.id, "docx")}
  disabled={isExporting}
>
  <FileDown size={16} />
  {isExporting ? "Exporting..." : "Export as Word"}
</Button>
```

The `handleExport` function calls `exportDraft()` from `draft.service.ts` and triggers a browser download on success.

Add to `src/frontend/src/services/draft.service.ts`:

```typescript
export async function exportDraft(
  case_id: string,
  draft_id: string,
  firm_id: string,
  format: string = "docx",
): Promise<ExportDraftResponse>;
```

---

## 10. Security Considerations

- **Tenant isolation**: All draft queries filter by `firm_id`. A draft's `firm_id` must match the requesting user's firm.
- **PII redaction**: All user instructions and case context are passed through `redact_pii()` before reaching the LLM, consistent with existing behavior.
- **Input validation**: Template names are validated against the hardcoded stage-to-template mapping — no user-supplied template names reach the agent without validation.
- **Content size**: Draft content stored in `ocr_text` has no explicit column size limit in the DataFlow model, but the LLM's `max_tokens` (8,000 for `DraftingAgent`) provides a practical ceiling.
- **Export security**: Presigned download URLs expire after 15 minutes. The export endpoint validates firm_id ownership before generating the file.

---

## 11. Files to Create or Modify

| Action | File Path | Description |
|--------|-----------|-------------|
| **Create** | `src/legalcopilot/services/draft_manager.py` | Draft generation, persistence, and version management service. |
| **Create** | `src/legalcopilot/api/drafts.py` | Nexus route handlers for draft endpoints. |
| **Create** | `src/frontend/src/services/draft.service.ts` | Frontend API client for draft endpoints. |
| **Create** | `src/frontend/src/components/cases/DraftsTab.tsx` | Drafts tab container. |
| **Create** | `src/frontend/src/components/cases/DraftStageSection.tsx` | Per-stage accordion section. |
| **Create** | `src/frontend/src/components/cases/DraftCard.tsx` | Individual draft card. |
| **Create** | `src/frontend/src/components/cases/DraftGenerateModal.tsx` | Template selection and generation modal. |
| **Create** | `src/frontend/src/components/cases/DraftViewer.tsx` | Markdown-rendered draft viewer. |
| **Modify** | `src/legalcopilot/models/core.py` | Add `"draft"` to `Document.file_type` validation. |
| **Modify** | `src/legalcopilot/api/app.py` | Register `register_draft_routes`. |
| **Modify** | `src/legalcopilot/api/chat.py` | Enhance `send_message` to persist chat-originated drafts. |
| **Modify** | `src/frontend/src/types/case.ts` | Add `DraftStatus`, `DraftMetadata`, `DraftDocument`, `ContextSummary`, `TemplateListResponse`, `DraftResponse` types. Add `"draft"` to `FileType`. |
| **Modify** | `src/frontend/src/pages/CaseDetail.tsx` | Add Drafts tab. |
| **Modify** | `src/frontend/src/components/chat/MessageBubble.tsx` | Render `saved_draft` link in chat messages. |
| **Modify** | `src/frontend/src/utils/constants.ts` | Add `DRAFT_STATUS_LABELS`, `TEMPLATE_LABELS`, `STAGE_LABELS` constants. |
