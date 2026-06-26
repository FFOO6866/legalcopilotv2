# Stage Transitions Specification

## Status

Draft — pending implementation.

## Overview

The `Case` model (at `src/legalcopilot/models/core.py:82-162`) has a `stage` field with 8 valid values: `intake`, `fact_gathering`, `research`, `analysis`, `drafting`, `review`, `submission`, `complete`. Today, the `update_case` handler (at `src/legalcopilot/api/cases.py:124-171`) accepts any valid stage value and applies it without transition validation — a case can jump from `intake` directly to `complete` with no guard. There is no stage history tracking and no mechanism for querying which templates are available at a given stage.

This spec defines:

1. Transition rules that enforce forward progression with one-step-back flexibility.
2. A `StageTransition` model for tracking the full stage history. **(removed — simplified)**
3. A `StageManager` service for validation, transition execution, and template lookup.
4. API endpoints for stage advancement and history queries.
5. Frontend components for a horizontal stage stepper bar.

---

## 1. Stage Transition Rules

**Simplified for small firm**: Stage transitions are ADVISORY, not enforced. The `update_case` endpoint allows any stage change. The frontend shows a suggested order but does not block backward or skip transitions. The StageTransition audit model has been removed — stage history is not tracked separately.

### 1.1 Valid Transitions

The case lifecycle is a directed graph. Each stage permits forward transitions to the next stage and backward transitions to the immediately preceding stage (with the exception of `intake`, which has no predecessor, and `complete`, which is terminal).

```
intake --> fact_gathering --> research --> analysis --> drafting --> review --> submission --> complete
       <--               <--          <--           <--          <--        <--
```

Expressed as an adjacency list:

| Current Stage | Valid Next Stages |
|--------------|-------------------|
| `intake` | `fact_gathering` |
| `fact_gathering` | `research`, `intake` |
| `research` | `analysis`, `fact_gathering` |
| `analysis` | `drafting`, `research` |
| `drafting` | `review`, `analysis` |
| `review` | `submission`, `drafting` |
| `submission` | `complete`, `review` |
| `complete` | _(none — terminal)_ |

### 1.2 Transition Direction

Every transition is classified as one of:

- **Forward**: Moving to the next stage in the lifecycle (e.g., `intake` -> `fact_gathering`). This is the normal progression.
- **Backward**: Moving to the immediately preceding stage (e.g., `research` -> `fact_gathering`). This requires a confirmation reason.
- **Invalid**: Any transition not in the adjacency list above (e.g., `intake` -> `complete`, or `analysis` -> `intake`). Rejected with a `400` error.

### 1.3 Data Representation

```python
STAGE_ORDER: list[str] = [
    "intake",
    "fact_gathering",
    "research",
    "analysis",
    "drafting",
    "review",
    "submission",
    "complete",
]

VALID_TRANSITIONS: dict[str, list[str]] = {
    "intake":          ["fact_gathering"],
    "fact_gathering":  ["research", "intake"],
    "research":        ["analysis", "fact_gathering"],
    "analysis":        ["drafting", "research"],
    "drafting":        ["review", "analysis"],
    "review":          ["submission", "drafting"],
    "submission":      ["complete", "review"],
    "complete":        [],
}
```

### 1.4 Fast-Track Override

An admin user (with `role == "partner"` or `role == "admin"` on the `User` model) can bypass transition validation to jump to any stage. This covers cases like:

- Urgent matters that skip research and go straight to drafting.
- Administrative corrections where a case was created at the wrong stage.
- Reopening a case from `complete` back to an earlier stage.

Fast-track transitions:

- Require `is_admin_override: true` in the request body.
- Require a `reason` string (mandatory, min 10 characters).
- Are logged in `StageTransition` (removed — simplified) with `metadata.admin_override: true`.
- Are audited in `AuditEntry` with `action: "update"` and `details.admin_override: true`.

---

## 2. StageTransition Model (removed — simplified)

~~A new DataFlow model added to `src/legalcopilot/models/core.py` to track every stage change.~~ The StageTransition model has been removed. Stage changes are tracked directly on the Case model's `stage` field and `updated_at` timestamp. For a 3-user firm, a separate audit trail model is unnecessary.

### 2.1 Model Definition

```python
@db.model
class StageTransition:
    """Audit trail for case stage changes."""

    id: str
    case_id: str
    firm_id: str
    from_stage: str
    to_stage: str
    direction: str = "forward"
    transitioned_by_id: str
    reason: Optional[str] = None
    metadata: dict = {}
    created_at: datetime = None

    __validation__ = {
        "from_stage": {
            "one_of": [
                "intake", "fact_gathering", "research", "analysis",
                "drafting", "review", "submission", "complete",
            ]
        },
        "to_stage": {
            "one_of": [
                "intake", "fact_gathering", "research", "analysis",
                "drafting", "review", "submission", "complete",
            ]
        },
        "direction": {
            "one_of": ["forward", "backward", "admin_override"]
        },
    }
    __dataflow__ = {
        "multi_tenant": True,
        "audit_log": True,
    }
    __indexes__ = [
        {"fields": ["case_id"]},
        {"fields": ["case_id", "created_at"]},
        {"fields": ["firm_id"]},
        {"fields": ["firm_id", "case_id"]},
        {"fields": ["transitioned_by_id"]},
    ]
```

### 2.2 Registration

The model must be:

1. Added to `src/legalcopilot/models/core.py` after the `Document` class.
2. Imported and re-exported in `src/legalcopilot/models/__init__.py`:
   ```python
   from legalcopilot.models.core import Case, Document, Firm, User, StageTransition
   ```
   Added to `__all__`:
   ```python
   "StageTransition",
   ```

DataFlow auto-generates CRUD workflows: `stagetransition_create`, `stagetransition_read`, `stagetransition_list`, etc.

### 2.3 Example Records

**Forward transition:**

```json
{
  "id": "uuid",
  "case_id": "case-uuid",
  "firm_id": "firm-uuid",
  "from_stage": "intake",
  "to_stage": "fact_gathering",
  "direction": "forward",
  "transitioned_by_id": "user-uuid",
  "reason": null,
  "metadata": {},
  "created_at": "2026-06-23T10:00:00Z"
}
```

**Backward transition:**

```json
{
  "id": "uuid",
  "case_id": "case-uuid",
  "firm_id": "firm-uuid",
  "from_stage": "research",
  "to_stage": "fact_gathering",
  "direction": "backward",
  "transitioned_by_id": "user-uuid",
  "reason": "Additional witness statements received; need to re-gather facts.",
  "metadata": {},
  "created_at": "2026-06-23T11:00:00Z"
}
```

**Admin override:**

```json
{
  "id": "uuid",
  "case_id": "case-uuid",
  "firm_id": "firm-uuid",
  "from_stage": "intake",
  "to_stage": "drafting",
  "direction": "admin_override",
  "transitioned_by_id": "admin-uuid",
  "reason": "Urgent matter — client needs letter of demand by EOD. Skipping research phase per partner instruction.",
  "metadata": {
    "admin_override": true,
    "skipped_stages": ["fact_gathering", "research", "analysis"]
  },
  "created_at": "2026-06-23T09:00:00Z"
}
```

---

## 3. StageManager Service

A new service at `src/legalcopilot/services/stage_manager.py` encapsulates all stage transition logic.

### 3.1 Public Interface

```python
class StageManager:
    """Manages case stage transitions with validation and history tracking."""

    def validate_transition(
        self,
        current_stage: str,
        new_stage: str,
    ) -> bool:
        """Check if a transition is valid per the adjacency list.

        Returns True if valid, False if not. Does NOT check admin override.
        """

    def advance_stage(
        self,
        case_id: str,
        firm_id: str,
        new_stage: str,
        user_id: str,
        reason: str | None = None,
        is_admin_override: bool = False,
    ) -> dict:
        """Execute a stage transition.

        Steps:
        1. Read the current case record.
        2. Validate the transition (unless admin override).
        3. Determine direction (forward, backward, admin_override).
        4. Update the case's stage field via case_update workflow.
        5. Create a StageTransition record via stagetransition_create workflow.
        6. Create an AuditEntry record.
        7. Return a dict with the updated case and the transition record.

        Raises ValueError for invalid transitions.
        Raises PermissionError for admin overrides by non-admin users.
        """

    def get_stage_history(
        self,
        case_id: str,
        firm_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Get the transition history for a case, ordered by created_at desc."""

    def get_available_templates(
        self,
        stage: str,
        practice_area: str = "",
    ) -> list[str]:
        """Return template names available for a stage + practice area.

        Uses the STAGE_TEMPLATES mapping from the drafting-pipeline spec.
        """

    def get_current_stage_info(
        self,
        case_id: str,
        firm_id: str,
    ) -> dict:
        """Return current stage, available forward/backward transitions,
        available templates, and time spent at current stage."""

    @staticmethod
    def get_stage_index(stage: str) -> int:
        """Return the 0-based index of a stage in STAGE_ORDER."""

    @staticmethod
    def get_direction(from_stage: str, to_stage: str) -> str:
        """Classify a transition as 'forward', 'backward', or raise for invalid."""
```

### 3.2 Validation Logic

```python
def validate_transition(self, current_stage: str, new_stage: str) -> bool:
    if current_stage not in VALID_TRANSITIONS:
        return False
    return new_stage in VALID_TRANSITIONS[current_stage]
```

### 3.3 Advance Stage Logic

```python
def advance_stage(self, case_id, firm_id, new_stage, user_id, reason=None, is_admin_override=False):
    # 1. Read current case
    case = _execute_workflow("case_read", {"id": case_id})["result"]
    if case is None or case.get("firm_id") != firm_id:
        raise ValueError("Case not found")

    current_stage = case["stage"]

    # 2. Same-stage check
    if current_stage == new_stage:
        raise ValueError(f"Case is already at stage '{current_stage}'")

    # 3. Terminal check
    if current_stage == "complete":
        if not is_admin_override:
            raise ValueError("Case is at terminal stage 'complete' and cannot be transitioned")

    # 4. Validate transition (unless admin override)
    if is_admin_override:
        # Verify user has admin/partner role
        user = _execute_workflow("user_read", {"id": user_id})["result"]
        if user.get("role") not in ("partner", "admin"):
            raise PermissionError("Only partners and admins can perform fast-track transitions")
        if not reason or len(reason) < 10:
            raise ValueError("Admin override requires a reason of at least 10 characters")
        direction = "admin_override"
    else:
        if not self.validate_transition(current_stage, new_stage):
            valid = VALID_TRANSITIONS.get(current_stage, [])
            raise ValueError(
                f"Invalid transition from '{current_stage}' to '{new_stage}'. "
                f"Valid transitions: {valid}"
            )
        from_idx = self.get_stage_index(current_stage)
        to_idx = self.get_stage_index(new_stage)
        direction = "forward" if to_idx > from_idx else "backward"

    # 5. Require reason for backward transitions
    if direction == "backward" and not reason:
        raise ValueError("Backward transitions require a reason")

    # 6. Update case stage
    _execute_workflow("case_update", {
        "filter": {"id": case_id},
        "fields": {"stage": new_stage},
    })

    # 7. Create StageTransition record
    transition_id = str(uuid.uuid4())
    metadata = {}
    if is_admin_override:
        metadata["admin_override"] = True
        # Record skipped stages for audit
        from_idx = self.get_stage_index(current_stage)
        to_idx = self.get_stage_index(new_stage)
        if to_idx > from_idx:
            skipped = STAGE_ORDER[from_idx + 1 : to_idx]
            if skipped:
                metadata["skipped_stages"] = skipped

    transition_data = {
        "id": transition_id,
        "case_id": case_id,
        "firm_id": firm_id,
        "from_stage": current_stage,
        "to_stage": new_stage,
        "direction": direction,
        "transitioned_by_id": user_id,
        "reason": reason,
        "metadata": metadata,
    }
    _execute_workflow("stagetransition_create", {"data": transition_data})

    # 8. Create audit entry
    audit_id = str(uuid.uuid4())
    _execute_workflow("auditentry_create", {"data": {
        "id": audit_id,
        "firm_id": firm_id,
        "user_id": user_id,
        "action": "update",
        "entity_type": "case",
        "entity_id": case_id,
        "details": {
            "field": "stage",
            "from": current_stage,
            "to": new_stage,
            "direction": direction,
            "reason": reason,
            "admin_override": is_admin_override,
        },
        "clearance_level": "internal",
    }})

    # 9. Return result
    return {
        "case_id": case_id,
        "from_stage": current_stage,
        "to_stage": new_stage,
        "direction": direction,
        "transition_id": transition_id,
        "reason": reason,
    }
```

---

## 4. API Endpoints

New endpoints registered in `src/legalcopilot/api/stages.py`:

### 4.1 `POST /api/cases/:id/stage` — Advance Stage

**Simplified**: This endpoint is OPTIONAL. The existing `update_case` endpoint can change the stage directly. This dedicated endpoint exists for frontend convenience (validates transition + returns updated case).

**Handler name:** `advance_case_stage`

**Request body:**

```json
{
  "new_stage": "fact_gathering",
  "reason": "All intake documents collected.",
  "is_admin_override": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `new_stage` | string | yes | — | Target stage. Must be one of the 8 valid stage values. |
| `reason` | string | conditional | `null` | Required for backward transitions and admin overrides. |
| `is_admin_override` | bool | no | `false` | If `true`, bypasses adjacency validation. Requires admin/partner role. |

**Success response (200):**

```json
{
  "case_id": "uuid",
  "from_stage": "intake",
  "to_stage": "fact_gathering",
  "direction": "forward",
  "transition_id": "uuid",
  "reason": "All intake documents collected."
}
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| `400` | Invalid transition, missing reason for backward/override, same-stage, terminal stage. |
| `403` | Non-admin user attempting admin override. |
| `404` | Case not found or firm mismatch. |

### 4.2 `GET /api/cases/:id/stage/history` — Get Transition History

**Handler name:** `get_stage_history`

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | `50` | Max records. |
| `offset` | int | `0` | Pagination offset. |

**Response:**

```json
{
  "case_id": "uuid",
  "current_stage": "research",
  "transitions": [
    {
      "id": "uuid",
      "from_stage": "fact_gathering",
      "to_stage": "research",
      "direction": "forward",
      "transitioned_by_id": "user-uuid",
      "reason": null,
      "metadata": {},
      "created_at": "2026-06-23T11:00:00Z"
    },
    {
      "id": "uuid",
      "from_stage": "intake",
      "to_stage": "fact_gathering",
      "direction": "forward",
      "transitioned_by_id": "user-uuid",
      "reason": null,
      "metadata": {},
      "created_at": "2026-06-22T09:00:00Z"
    }
  ],
  "total": 2,
  "limit": 50,
  "offset": 0
}
```

### 4.3 `GET /api/stages/:stage/templates` — Get Available Templates

**Handler name:** `get_stage_templates`

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `practice_area` | string | `""` | Filter templates by practice area. |

**Response:**

```json
{
  "stage": "analysis",
  "practice_area": "contract",
  "templates": [
    "legal_opinion",
    "risk_assessment",
    "letter_of_demand",
    "advice_note"
  ]
}
```

### 4.4 `GET /api/cases/:id/stage/info` — Get Current Stage Info

**Handler name:** `get_stage_info`

**Response:**

```json
{
  "case_id": "uuid",
  "current_stage": "analysis",
  "stage_index": 3,
  "total_stages": 8,
  "available_transitions": {
    "forward": ["drafting"],
    "backward": ["research"]
  },
  "available_templates": [
    "legal_opinion",
    "risk_assessment",
    "letter_of_demand",
    "advice_note"
  ],
  "time_at_current_stage_hours": 48.5,
  "transition_count": 3
}
```

### 4.5 Route Registration

```python
def register_stage_routes(app: Nexus) -> None:
    """Register stage transition and history endpoints."""

    @app.handler("advance_case_stage", description="Advance a case to a new stage")
    async def advance_case_stage(
        case_id: str,
        firm_id: str,
        user_id: str,
        new_stage: str,
        reason: str = "",
        is_admin_override: bool = False,
    ) -> dict: ...

    @app.handler("get_stage_history", description="Get stage transition history for a case")
    async def get_stage_history(
        case_id: str,
        firm_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict: ...

    @app.handler("get_stage_templates", description="Get available templates for a stage")
    async def get_stage_templates(
        stage: str,
        practice_area: str = "",
    ) -> dict: ...

    @app.handler("get_stage_info", description="Get current stage info for a case")
    async def get_stage_info(
        case_id: str,
        firm_id: str,
    ) -> dict: ...
```

Registered in `src/legalcopilot/api/app.py` alongside existing route registrations.

---

## 5. Existing `update_case` Handler Changes

**Simplified**: Since transitions are advisory (not enforced), the `update_case` handler KEEPS `stage` as a directly-updatable field. No changes needed to the existing handler. The `advance_case_stage` endpoint is an optional convenience that validates the transition and returns the updated case, but `update_case` can change the stage directly for simplicity.

```python
# NO CHANGE — stage stays as a direct-update field for simplicity
fields = {
    k: v
    for k, v in {
        "title": title,
        "status": status,
        "stage": stage,          # kept — transitions are advisory
        "assigned_user_id": assigned_user_id,
        "priority": priority,
    }.items()
    if v
}
```

---

## 6. Frontend: Stage Bar Component

### 6.1 New Components

| Component | Path | Purpose |
|-----------|------|---------|
| `StageBar` | `src/frontend/src/components/cases/StageBar.tsx` | Horizontal stepper showing all 8 stages. |
| `AdvanceStageDialog` | `src/frontend/src/components/cases/AdvanceStageDialog.tsx` | Confirmation dialog for stage transitions. |

### 6.2 StageBar Design

A horizontal stepper rendered at the top of the `CaseDetail` page, above the tabs.

```
  (1)-------(2)-------(3)-------(4)-------(5)-------(6)-------(7)-------(8)
 Intake   Fact      Research  Analysis  Drafting  Review   Submission Complete
          Gathering
```

**Visual states per stage:**

| State | Circle | Line | Label |
|-------|--------|------|-------|
| Completed | Filled circle with check icon | Filled (colored) | Muted text |
| Current | Filled circle with pulse animation | Half-filled | Bold text |
| Future | Outlined circle (empty) | Gray | Gray text |

### 6.3 Stage Colors

Each stage has a designated color used for the filled circle and connecting line:

| Stage | Tailwind Class | Hex |
|-------|---------------|-----|
| `intake` | `gray-500` | `#6B7280` |
| `fact_gathering` | `blue-500` | `#3B82F6` |
| `research` | `indigo-500` | `#6366F1` |
| `analysis` | `violet-500` | `#8B5CF6` |
| `drafting` | `amber-500` | `#F59E0B` |
| `review` | `orange-500` | `#F97316` |
| `submission` | `emerald-500` | `#10B981` |
| `complete` | `green-600` | `#16A34A` |

### 6.4 StageBar Interactions

- **Click a completed stage**: Scrolls the Drafts tab to that stage's section (if the Drafts tab is visible) or switches to the Drafts tab and scrolls.
- **Click the current stage**: No action (or shows stage info tooltip with time spent).
- **Click a future stage**: No action (future stages are not clickable).
- **Hover any stage**: Tooltip showing stage name, transition date (if completed), and available templates count.

### 6.5 AdvanceStageDialog

Triggered by an "Advance Stage" button in the case actions dropdown (alongside "Edit Case").

```
+----------------------------------------------+
|  Advance Stage                          [X]  |
+----------------------------------------------+
|                                              |
|  Current stage: Analysis                     |
|                                              |
|  Move to:                                    |
|  (*) Drafting  (next stage)                  |
|  ( ) Research  (go back one step)            |
|                                              |
|  Reason (required for going back):           |
|  +------------------------------------------+|
|  |                                          ||
|  +------------------------------------------+|
|                                              |
|  [Cancel]                [Advance to Stage]  |
+----------------------------------------------+
```

**Behavior:**

- Shows available transitions based on the current stage (from `VALID_TRANSITIONS`).
- Forward transitions have a "(next stage)" label.
- Backward transitions have a "(go back one step)" label and require the reason field to be filled.
- The reason field is hidden for forward transitions and visible for backward transitions.
- On confirm, calls `advance_case_stage` and refreshes the case data.
- Shows a success toast: "Case advanced to {stage_label}".
- Shows an error toast on failure with the server's error message.

### 6.6 Admin Override UI

For users with `role === "partner"` or `role === "admin"`, the dialog shows an additional section:

```
  [ ] Fast-track (skip stages)

  [If checked, a dropdown of ALL stages appears]
  Jump to: [dropdown of all stages]

  Reason (required):
  +------------------------------------------+
  |                                          |
  +------------------------------------------+
```

When "Fast-track" is checked, the normal radio buttons are replaced with a dropdown of all stages (excluding the current one and `complete` if already at `complete`). The reason field becomes mandatory (min 10 characters).

### 6.7 StageBar Placement in CaseDetail

The `StageBar` is placed between the case header and the tabs:

```tsx
// In CaseDetail (src/frontend/src/pages/CaseDetail.tsx)
return (
  <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
    {/* Case header with title, badges, Edit button */}
    <div className="flex items-start justify-between gap-4 mb-6">
      ...
    </div>

    {/* Stage bar */}
    <StageBar
      currentStage={caseData.stage}
      caseId={caseData.id}
      firmId={firmId}
      onStageClick={(stage) => {
        // Switch to Drafts tab and scroll to stage section
      }}
    />

    {/* Tabs */}
    <Tabs.Root defaultValue="overview">
      ...
    </Tabs.Root>
  </div>
);
```

### 6.8 Stage History Timeline

The Overview tab gains a "Stage History" card that shows the transition history as a vertical timeline:

```
+--------------------------------------------+
|  Stage History                             |
+--------------------------------------------+
|                                            |
|  o  Research                               |
|  |  Jun 23, 2026 at 11:00 AM              |
|  |  Advanced by John Doe                   |
|  |                                         |
|  o  Fact Gathering                         |
|  |  Jun 22, 2026 at 9:00 AM               |
|  |  Advanced by John Doe                   |
|  |                                         |
|  o  Intake (initial)                       |
|     Jun 21, 2026 at 3:00 PM               |
|     Case created by John Doe               |
|                                            |
+--------------------------------------------+
```

Each entry shows:

- Stage name with the stage's color dot.
- Timestamp.
- Who triggered the transition.
- Reason (if provided, shown in italic below the user name).
- Admin override badge (if applicable).

---

## 7. Frontend Services and Types

### 7.1 Service Functions

New file `src/frontend/src/services/stage.service.ts`:

```typescript
import { nexusCall } from "./api";

export async function advanceStage(
  case_id: string,
  firm_id: string,
  user_id: string,
  new_stage: string,
  reason?: string,
  is_admin_override?: boolean,
): Promise<StageTransitionResult> {
  return nexusCall<StageTransitionResult>("advance_case_stage", {
    case_id,
    firm_id,
    user_id,
    new_stage,
    reason,
    is_admin_override,
  });
}

export async function getStageHistory(
  case_id: string,
  firm_id: string,
  limit?: number,
  offset?: number,
): Promise<StageHistoryResponse> {
  return nexusCall<StageHistoryResponse>("get_stage_history", {
    case_id,
    firm_id,
    limit,
    offset,
  });
}

export async function getStageTemplates(
  stage: string,
  practice_area?: string,
): Promise<StageTemplatesResponse> {
  return nexusCall<StageTemplatesResponse>("get_stage_templates", {
    stage,
    practice_area,
  });
}

export async function getStageInfo(
  case_id: string,
  firm_id: string,
): Promise<StageInfoResponse> {
  return nexusCall<StageInfoResponse>("get_stage_info", {
    case_id,
    firm_id,
  });
}
```

### 7.2 TypeScript Types

Added to `src/frontend/src/types/case.ts`:

```typescript
export type CaseStage =
  | "intake"
  | "fact_gathering"
  | "research"
  | "analysis"
  | "drafting"
  | "review"
  | "submission"
  | "complete";

export interface StageTransition {
  id: string;
  case_id: string;
  firm_id: string;
  from_stage: CaseStage;
  to_stage: CaseStage;
  direction: "forward" | "backward" | "admin_override";
  transitioned_by_id: string;
  reason: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface StageTransitionResult {
  case_id: string;
  from_stage: CaseStage;
  to_stage: CaseStage;
  direction: string;
  transition_id: string;
  reason: string | null;
}

export interface StageHistoryResponse {
  case_id: string;
  current_stage: CaseStage;
  transitions: StageTransition[];
  total: number;
  limit: number;
  offset: number;
}

export interface StageTemplatesResponse {
  stage: CaseStage;
  practice_area: string;
  templates: string[];
}

export interface StageInfoResponse {
  case_id: string;
  current_stage: CaseStage;
  stage_index: number;
  total_stages: number;
  available_transitions: {
    forward: CaseStage[];
    backward: CaseStage[];
  };
  available_templates: string[];
  time_at_current_stage_hours: number;
  transition_count: number;
}

export const STAGE_ORDER: CaseStage[] = [
  "intake",
  "fact_gathering",
  "research",
  "analysis",
  "drafting",
  "review",
  "submission",
  "complete",
];

export const STAGE_LABELS: Record<CaseStage, string> = {
  intake: "Intake",
  fact_gathering: "Fact Gathering",
  research: "Research",
  analysis: "Analysis",
  drafting: "Drafting",
  review: "Review",
  submission: "Submission",
  complete: "Complete",
};

export const STAGE_COLORS: Record<CaseStage, string> = {
  intake: "gray-500",
  fact_gathering: "blue-500",
  research: "indigo-500",
  analysis: "violet-500",
  drafting: "amber-500",
  review: "orange-500",
  submission: "emerald-500",
  complete: "green-600",
};
```

---

## 8. Edge Cases

### 8.1 Concurrent Stage Updates

If two users attempt to advance the same case simultaneously, the second request will see the updated stage from the first request and may fail validation (e.g., both try to advance from `analysis` to `drafting`, but the second request finds the case already at `drafting`). The `advance_stage` method handles this via the "same-stage check" — if `current_stage == new_stage`, it returns an error: "Case is already at stage 'drafting'."

### 8.2 Stage at Complete

Once a case reaches `complete`:

- No forward transitions exist (empty `VALID_TRANSITIONS["complete"]`).
- The "Advance Stage" button is disabled with a tooltip: "Case is complete."
- Only admin fast-track can reopen the case to an earlier stage.
- The `StageBar` shows all stages as completed with check icons.

### 8.3 Backward Transition Confirmation

Backward transitions always require a `reason` string. The frontend enforces this by:

1. Showing the reason text field only when a backward transition is selected.
2. Disabling the "Advance" button until the reason has at least 1 character.
3. The backend also validates: if `direction == "backward"` and `reason` is empty, return a `400` error.

### 8.4 Template Availability vs. Practice Area

Some templates are practice-area-specific (see `drafting-pipeline.md` Section 1.1). When a user requests templates for a stage, the response is filtered by the case's `practice_area`. For example:

- `GET /api/stages/drafting/templates?practice_area=criminal` returns `mitigation_plea` and `representations_to_agc` in addition to the generic templates.
- `GET /api/stages/drafting/templates?practice_area=contract` does NOT return `mitigation_plea` or `writ_for_divorce`.

### 8.5 Case Creation Default

New cases always start at `intake` (enforced by the `create_case` handler at `cases.py:58`: `"stage": "intake"`). An initial `StageTransition` record is NOT created for the starting stage — the first transition record is created when the case moves from `intake` to `fact_gathering`. The case's `created_at` timestamp serves as the start-of-`intake` marker.

### 8.6 Backward from intake

The `intake` stage has no predecessor. `VALID_TRANSITIONS["intake"]` only contains `["fact_gathering"]` — there is no backward path. Attempting to go backward from `intake` returns: "No backward transition available from 'intake'."

### 8.7 Stage Duration Tracking

The `get_stage_info` endpoint computes `time_at_current_stage_hours` by finding the most recent `StageTransition` record for the case (whose `to_stage` matches the current stage) and computing the difference from `now`. If no transition record exists (i.e., the case is still at `intake` with no transitions), the case's `created_at` is used instead.

---

## 9. Cross-Reference: Drafting Pipeline

This spec and `specs/drafting-pipeline.md` share the `get_available_templates` function. The canonical stage-to-template mapping lives in the `StageManager` service (this spec), and the `DraftManager` (drafting-pipeline spec) delegates to `StageManager.get_available_templates()` to avoid duplicating the mapping.

Both the `get_stage_templates` endpoint defined here and the `get_stage_templates` endpoint defined in the drafting-pipeline spec are the SAME endpoint — implemented once in `src/legalcopilot/api/stages.py` and referenced by both specs.

---

## 10. Security Considerations

- **Tenant isolation**: All stage queries and transitions filter by `firm_id`. A user in one firm cannot view or modify another firm's case stages.
- **Role-based access**: Admin override is restricted to users with `role` of `partner` or `admin`. The backend verifies this by reading the `User` record, not by trusting a client-provided flag.
- **Audit trail**: Every stage transition (including admin overrides) is recorded in both `StageTransition` and `AuditEntry` tables. Admin overrides are explicitly flagged in both records.
- **Input validation**: `new_stage` is validated against the `STAGE_ORDER` list before any transition logic runs. Invalid stage values (e.g., typos, injection attempts) are rejected with a `400`.
- **Reason logging**: Reasons for backward transitions and admin overrides are stored verbatim after PII redaction.

---

## 11. Files to Create or Modify

| Action | File Path | Description |
|--------|-----------|-------------|
| **Create** | `src/legalcopilot/services/stage_manager.py` | Stage validation, transition execution, history, template lookup. |
| **Create** | `src/legalcopilot/api/stages.py` | Nexus route handlers for stage endpoints. |
| **Create** | `src/frontend/src/services/stage.service.ts` | Frontend API client for stage endpoints. |
| **Create** | `src/frontend/src/components/cases/StageBar.tsx` | Horizontal stepper component. |
| **Create** | `src/frontend/src/components/cases/AdvanceStageDialog.tsx` | Confirmation dialog for stage transitions. |
| ~~**Modify**~~ | ~~`src/legalcopilot/models/core.py`~~ | ~~Add `StageTransition` model after `Document`.~~ (REMOVED — simplified) |
| ~~**Modify**~~ | ~~`src/legalcopilot/models/__init__.py`~~ | ~~Import and export `StageTransition`.~~ (REMOVED — simplified) |
| **Modify** | `src/legalcopilot/api/app.py` | Register `register_stage_routes`. |
| **Modify** | `src/legalcopilot/api/cases.py` | Remove `stage` from direct `update_case` fields; redirect to stage endpoint. |
| **Modify** | `src/frontend/src/types/case.ts` | Add `CaseStage`, `StageTransition`, `StageTransitionResult`, `StageHistoryResponse`, `StageTemplatesResponse`, `StageInfoResponse` types plus `STAGE_ORDER`, `STAGE_LABELS`, `STAGE_COLORS` constants. |
| **Modify** | `src/frontend/src/pages/CaseDetail.tsx` | Add `StageBar` above tabs; add "Advance Stage" to actions; add stage history to Overview tab. |
| **Modify** | `src/frontend/src/utils/constants.ts` | Add `STAGE_LABELS`, `STAGE_COLORS`, `VALID_TRANSITIONS` constants (shared between components). |
