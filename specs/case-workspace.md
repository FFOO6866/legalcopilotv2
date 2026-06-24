# Case Workspace -- Domain Specification

**Domain:** LegalCoPilot v2 -- AI-powered legal assistant for Singapore law firms
**Scope:** The Case Workspace is the primary working surface where lawyers conduct all case-related activities. It replaces the current `CaseDetail` page (`src/frontend/src/pages/CaseDetail.tsx`) with a full-featured workspace that combines tabbed content with a persistent AI chat panel.
**Route:** `/cases/:id`

---

## 1. Data Model Alignment

All field names, enumerations, and constraints reference the source-of-truth backend model at `src/legalcopilot/models/core.py`. The frontend TypeScript types live at `src/frontend/src/types/case.ts` and `src/frontend/src/types/chat.ts`.

### 1.1 Case Fields (from `core.py` Case model)

| Field              | Type             | Default     | Notes                                                        |
| ------------------ | ---------------- | ----------- | ------------------------------------------------------------ |
| `id`               | `str`            | --          | UUID v4, primary key                                         |
| `firm_id`          | `str`            | --          | Multi-tenancy root, FK to Firm                               |
| `created_by_id`    | `str`            | --          | FK to User                                                   |
| `assigned_user_id` | `str | null`     | `null`      | FK to User, nullable                                         |
| `case_number`      | `str | null`     | `null`      | Unique per firm                                              |
| `title`            | `str`            | --          | 1-500 chars                                                  |
| `description`      | `str | null`     | `null`      | Free text                                                    |
| `practice_area`    | `PracticeArea`   | `"general"` | 12 values -- see section 1.2                                 |
| `case_type`        | `str`            | `"general"` | Free text, maps to SOP templates                             |
| `status`           | `CaseStatus`     | `"open"`    | 6 values -- see section 1.3                                  |
| `stage`            | `CaseStage`      | `"intake"`  | 8 values, ordered -- see section 1.4                         |
| `priority`         | `CasePriority`   | `"normal"`  | `low | normal | high | urgent`                               |
| `client_name`      | `str | null`     | `null`      | Display name                                                 |
| `client_reference` | `str | null`     | `null`      | Client's own reference number                                |
| `opposing_party`   | `str | null`     | `null`      | Free text                                                    |
| `court`            | `str | null`     | `null`      | Free text                                                    |
| `filing_date`      | `datetime | null` | `null`     | ISO 8601                                                     |
| `tags`             | `str[]`          | `[]`        | Freeform tags                                                |
| `metadata`         | `dict`           | `{}`        | Extensible JSON                                              |
| `created_at`       | `datetime`       | auto        | ISO 8601                                                     |
| `updated_at`       | `datetime`       | auto        | ISO 8601                                                     |

### 1.2 Practice Areas

Enumerated at `core.py` line 134 and mirrored in `src/frontend/src/utils/constants.ts` as `PRACTICE_AREAS`:

`general`, `contract`, `employment`, `family`, `criminal`, `property`, `arbitration`, `corporate`, `insolvency`, `ip`, `tort`, `probate`

Display labels are resolved via `classifyPracticeArea()` in `src/frontend/src/utils/helpers.ts`.

### 1.3 Case Status

Enumerated at `core.py` line 111:

`open`, `in_progress`, `pending_review`, `under_review`, `closed`, `archived`

**Note:** The current frontend type at `case.ts` line 15 defines `CaseStatus` as `"open" | "active" | "closed" | "archived"`, which is a MISMATCH with the backend. The backend has 6 values; the frontend has 4. This spec uses the backend as source of truth. The frontend type MUST be updated to match during implementation.

### 1.4 Case Stages (Ordered)

Enumerated at `core.py` line 122. The stage represents a linear progression through a case lifecycle:

| Index | Value             | Display Label    | Badge Color Class                                  |
| ----- | ----------------- | ---------------- | -------------------------------------------------- |
| 0     | `intake`          | Intake           | `bg-gray-100 text-gray-700 ring-gray-500/20`       |
| 1     | `fact_gathering`  | Fact Gathering   | `bg-blue-50 text-blue-700 ring-blue-600/20`        |
| 2     | `research`        | Research         | `bg-indigo-50 text-indigo-700 ring-indigo-600/20`  |
| 3     | `analysis`        | Analysis         | `bg-violet-50 text-violet-700 ring-violet-600/20`  |
| 4     | `drafting`        | Drafting         | `bg-amber-50 text-amber-700 ring-amber-600/20`     |
| 5     | `review`          | Review           | `bg-orange-50 text-orange-700 ring-orange-600/20`  |
| 6     | `submission`      | Submission       | `bg-emerald-50 text-emerald-700 ring-emerald-600/20` |
| 7     | `complete`        | Complete         | `bg-green-50 text-green-700 ring-green-600/20`     |

Stages are strictly ordered. A stage transition MUST validate that the target stage index is exactly `current_index + 1` (forward by one) OR any index less than `current_index` (backward to any prior stage). Jumping forward by more than one stage is blocked. The `complete` stage is terminal in the forward direction -- once complete, backward transitions are allowed only for reopening.

### 1.5 Document Fields (from `core.py` Document model)

| Field              | Type           | Notes                                              |
| ------------------ | -------------- | -------------------------------------------------- |
| `id`               | `str`          | UUID v4                                            |
| `case_id`          | `str`          | FK to Case                                         |
| `firm_id`          | `str`          | Multi-tenancy                                      |
| `uploaded_by_id`   | `str`          | FK to User                                         |
| `filename`         | `str`          | 1-500 chars                                        |
| `file_type`        | `FileType`     | 9 values: pleading, affidavit, exhibit, correspondence, submission, judgment, contract, memo, other |
| `storage_url`      | `str`          | Object storage path                                |
| `file_size_bytes`  | `int`          | 0 until real file upload                           |
| `classification`   | `dict`         | AI-generated document classification               |
| `ocr_text`         | `str | null`   | Extracted text                                     |
| `ocr_status`       | `OcrStatus`    | `pending | processing | complete | failed`         |
| `metadata`         | `dict`         | Extensible                                         |
| `created_at`       | `datetime`     | ISO 8601                                           |
| `updated_at`       | `datetime`     | ISO 8601                                           |

### 1.6 Conversation Fields (from `chat.ts`)

| Field               | Type     | Notes                                  |
| ------------------- | -------- | -------------------------------------- |
| `id`                | `str`    | UUID v4                                |
| `firm_id`           | `str`    | Multi-tenancy                          |
| `user_id`           | `str`    | FK to User                             |
| `case_id`           | `str?`   | Optional FK to Case (scoped when set)  |
| `title`             | `str?`   | Auto-generated or user-set             |
| `conversation_type` | `str`    | `legal_research | document_drafting | case_analysis | general` |
| `status`            | `str`    | `active | closed`                      |
| `created_at`        | `str`    | ISO 8601                               |
| `updated_at`        | `str`    | ISO 8601                               |

---

## 2. Route Structure

### 2.1 Application Routes

| Route                              | Page Component      | Auth | Layout   |
| ---------------------------------- | ------------------- | ---- | -------- |
| `/login`                           | `Login`             | No   | None     |
| `/dashboard`                       | `Dashboard`         | Yes  | `Layout` |
| `/cases`                           | `Cases`             | Yes  | `Layout` |
| `/cases/:id`                       | `CaseWorkspace`     | Yes  | `Layout` |
| `/cases/:id/chat/:conversationId`  | `CaseWorkspace`     | Yes  | `Layout` |
| `/knowledge`                       | `Knowledge`         | Yes  | `Layout` |
| `/admin`                           | `Admin`             | Yes  | `Layout` |
| `/admin/users`                     | `AdminUsers`        | Yes  | `Layout` |
| `/admin/firm`                      | `AdminFirm`         | Yes  | `Layout` |
| `*`                                | `NotFound`          | No   | None     |

### 2.2 Route Parameters

- `:id` -- Case UUID. Validated on load; 404 if not found or not in user's firm.
- `:conversationId` -- Optional. When present, the chat panel opens with this conversation active and scrolled to bottom. Deep-linking into a specific case conversation.

### 2.3 Constants Update

`ROUTES` in `src/frontend/src/utils/constants.ts` MUST be extended:

```typescript
export const ROUTES = {
  LOGIN: "/login",
  DASHBOARD: "/dashboard",
  CASES: "/cases",
  CASE_DETAIL: "/cases/:id",       // new
  CASE_CHAT: "/cases/:id/chat/:conversationId",  // new
  KNOWLEDGE: "/knowledge",
  ADMIN: "/admin",
  ADMIN_USERS: "/admin/users",
  ADMIN_FIRM: "/admin/firm",
} as const;
```

---

## 3. Page Layout -- Case Workspace

The Case Workspace is a full-height split-pane layout. The left pane holds the case header, stage progress bar, and tabbed content. The right pane holds the AI chat panel. The two panes share the available horizontal space within the main content area (inside the existing `Layout` component which provides the sidebar navigation and header).

### 3.1 Layout Anatomy (ASCII)

```
+-- Layout shell (sidebar 280px + main) ----------------------------------+
|                                                                          |
| +-- CaseWorkspace (fills main area, no outer padding) ----------------+ |
| |                                                                      | |
| | +-- Case Header (full width, h-auto) ----------------------------+  | |
| | | [<-]  Case Title                  [Stage] [Status]  [Actions v]|  | |
| | +----------------------------------------------------------------+  | |
| |                                                                      | |
| | +-- Stage Progress Bar (full width, h-12) -----------------------+  | |
| | | (o)---(o)---(o)---(*)---( )---( )---( )---( )                  |  | |
| | | Intake  Fact   Research Analysis Drafting Review Submit Complete|  | |
| | +----------------------------------------------------------------+  | |
| |                                                                      | |
| | +-- Split Pane Container (flex, flex-1) -------------------------+  | |
| | |                                                                  | | |
| | | +-- Tab Content (flex-1, min-w-0) --+ +-- Chat Panel --------+ | | |
| | | |                                    | |  w: 320px-50%        | | | |
| | | | [Overview][Docs][Chrono][Research]  | |  resizable via drag  | | | |
| | | | [Drafts][Analysis]                 | |                      | | | |
| | | |                                    | | +-- Messages ------+ | | | |
| | | | +--- Active Tab Content --------+  | | |                  | | | | |
| | | | |                               |  | | |                  | | | | |
| | | | |  (scrollable, flex-1)         |  | | |                  | | | | |
| | | | |                               |  | | |                  | | | | |
| | | | |                               |  | | +------------------+ | | | |
| | | | |                               |  | |                      | | | |
| | | | +-------------------------------+  | | +-- Input ---------+ | | | |
| | | |                                    | | | [Type message...] | | | | |
| | | +------------------------------------+ | +------------------+ | | | |
| | |                                        +----------------------+ | | |
| | +----------------------------------------------------------------+ | |
| +--------------------------------------------------------------------+ |
+------------------------------------------------------------------------+
```

### 3.2 Dimensions and Spacing

| Element                   | Measurement                                        |
| ------------------------- | -------------------------------------------------- |
| Case Header height        | Auto (content-driven), min-height 56px             |
| Case Header padding       | `px-6 py-3`                                        |
| Stage Progress Bar height | 48px (`h-12`)                                      |
| Stage Progress Bar padding| `px-6 py-2`                                        |
| Tab bar height            | 44px                                                |
| Tab bar padding           | `px-6`, each trigger `px-4 py-2.5`                 |
| Split Pane gap            | 0 (divider is the drag handle, 4px wide)           |
| Chat Panel min-width      | 320px                                               |
| Chat Panel max-width      | 50% of split pane container                         |
| Chat Panel default width  | 380px                                               |
| Tab content padding       | `px-6 py-4`                                         |
| Page outer padding        | 0 (workspace fills the Layout main area edge-to-edge)|

### 3.3 Full-Height Behavior

The CaseWorkspace component MUST fill the entire available main area height. The existing `Layout` component wraps content in `<main className="flex-1 overflow-y-auto"><div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">`. The CaseWorkspace page MUST use negative margins to break out of the `max-w-7xl` and padding containers, similar to how `ChatView` does at `src/frontend/src/components/chat/ChatView.tsx` line 69:

```
className="flex h-[calc(100dvh-theme(spacing.16)-theme(spacing.12))] -mx-4 -my-6 sm:-mx-6 lg:-mx-8"
```

The exact height calculation accounts for:
- Header bar: 64px (`spacing.16`)
- Main padding: 48px (`spacing.12`)

All internal scrolling happens within the tab content area and the chat messages area. The outer page does NOT scroll.

---

## 4. Case Header

### 4.1 Layout

The Case Header is a horizontal bar at the top of the workspace.

```
+--------------------------------------------------------------------+
| [<-]  Title of the Case (truncated if long)                        |
|        Practice Area Badge   Stage Badge   Status Badge             |
|                                               [Edit] [Actions v]   |
+--------------------------------------------------------------------+
```

### 4.2 Elements

| Element            | Position      | Component / Behavior                                                                  |
| ------------------ | ------------- | ------------------------------------------------------------------------------------- |
| Back arrow         | Far left      | `ArrowLeft` icon (lucide), 18px. Navigates to `/cases`. `p-1.5 rounded-lg hover:bg-gray-100` |
| Title              | Left of center| `<h1>`, `text-xl font-bold text-gray-900 truncate`. Max 1 line.                       |
| Case Number        | Below title   | `text-sm text-gray-500` if `case_number` is not null. Format: `Case #ABC-2024-001`.  |
| Practice Area badge| Below title   | Uses `Badge` component, variant `"info"`. Label from `classifyPracticeArea()`.        |
| Stage badge        | Below title   | Uses stage-specific color -- see section 1.4 badge colors.                             |
| Status badge       | Below title   | Uses status variant map: `open=info`, `in_progress=success`, `pending_review=warning`, `under_review=warning`, `closed=neutral`, `archived=neutral`. |
| Client name        | Below title   | `text-sm text-gray-500` if not null. Prefixed with client icon.                        |
| Edit button        | Far right     | `Button` variant `"secondary"` size `"sm"`. Opens `CaseForm` dialog for editing.      |
| Actions dropdown   | Far right     | Radix `DropdownMenu`. Items: Assign User, Change Priority, Change Status, Export Case, Archive Case. |

### 4.3 Actions Dropdown Menu Items

| Action           | Icon             | Condition                          | Behavior                                          |
| ---------------- | ---------------- | ---------------------------------- | ------------------------------------------------- |
| Assign User      | `UserPlus`       | Always                             | Opens user-selection dialog                        |
| Change Priority  | `AlertTriangle`  | Always                             | Sub-menu: Low, Normal, High, Urgent                |
| Change Status    | `RefreshCw`      | Always                             | Sub-menu: all 6 status values                      |
| Export Case      | `Download`       | Always                             | Exports case metadata + document list as JSON      |
| Archive Case     | `Archive`        | `status !== "archived"`            | Confirmation dialog, then sets status to archived  |
| Reopen Case      | `RotateCcw`      | `status === "closed" or "archived"`| Sets status to `open`, confirms via dialog         |

---

## 5. Stage Progress Bar

The Stage Progress Bar is a horizontal stepper showing all 8 case stages with visual indicators for completed, current, and future stages.

### 5.1 Layout

```
(*)------(*)------(*)------[*]------( )------( )------( )------( )
Intake   Fact     Research  Analysis Drafting  Review  Submit  Complete
         Gathering
```

### 5.2 Visual States

| State     | Circle Style                                       | Connector Style                         | Label Style                    |
| --------- | -------------------------------------------------- | --------------------------------------- | ------------------------------ |
| Completed | Filled circle with checkmark icon, stage color bg  | Solid line, stage color                  | `text-sm font-medium` in stage color |
| Current   | Filled circle with pulse ring animation, stage color bg | Left: solid stage color, Right: `bg-gray-200` | `text-sm font-semibold` in stage color |
| Future    | Hollow circle, `border-gray-300 bg-white`          | Dashed line, `bg-gray-200`              | `text-sm text-gray-400`       |

### 5.3 Dimensions

| Measurement         | Value                                 |
| ------------------- | ------------------------------------- |
| Circle diameter     | 28px (7 in Tailwind, `w-7 h-7`)      |
| Checkmark icon size | 14px                                  |
| Connector height    | 2px                                   |
| Connector gap       | 0 (connects edge-to-edge of circles) |
| Label font size     | 12px (`text-xs`)                      |
| Label gap below     | 4px (`mt-1`)                          |
| Overall bar height  | 48px                                  |
| Horizontal padding  | `px-6`                                |

### 5.4 Interaction

- **Completed stages:** Clickable. Navigating to a completed stage scrolls the Drafts tab to that stage's section (accordion opens).
- **Current stage:** Not clickable. Shows pulse animation ring.
- **Future stages:** Not clickable. Hover shows tooltip: "Complete [current stage] to proceed."
- **Stage advancement:** Clicking "Advance Stage" in the Actions dropdown opens a confirmation dialog showing the current and next stage names, plus a checklist of stage-completion criteria (e.g., "At least 1 document uploaded" for fact_gathering).

### 5.5 Stage Transition Validation

Transitions are validated client-side before sending to the `update_case` API:

| From Stage        | Valid Forward Target   | Validation Criteria                                    |
| ----------------- | ---------------------- | ------------------------------------------------------ |
| `intake`          | `fact_gathering`       | Title and description are non-empty                    |
| `fact_gathering`  | `research`             | At least 1 document uploaded                           |
| `research`        | `analysis`             | At least 1 research item pinned to case                |
| `analysis`        | `drafting`             | At least 1 analysis run completed                      |
| `drafting`        | `review`               | At least 1 draft created                               |
| `review`          | `submission`           | At least 1 draft in "approved" status                  |
| `submission`      | `complete`             | User confirms submission is filed                      |
| `complete`        | (terminal)             | Backward transitions only                              |

Backward transitions to any prior stage are always allowed. The confirmation dialog shows: "Move case back to [stage]? This will reopen the case for further work."

---

## 6. Tab Bar

### 6.1 Tab Definitions

| Index | Value        | Icon           | Label       | Badge Content                    |
| ----- | ------------ | -------------- | ----------- | -------------------------------- |
| 0     | `overview`   | `Info`         | Overview    | --                               |
| 1     | `documents`  | `FileText`     | Documents   | Document count (e.g., `12`)      |
| 2     | `chronology` | `Clock`        | Chronology  | Event count if > 0               |
| 3     | `research`   | `Search`       | Research    | Pinned research count if > 0     |
| 4     | `drafts`     | `PenTool`      | Drafts      | Draft count if > 0               |
| 5     | `analysis`   | `BarChart3`    | Analysis    | Analysis count if > 0            |

### 6.2 Tab Bar Styling

Uses `@radix-ui/react-tabs` (already installed). Follows the existing pattern from `CaseDetail.tsx`:

- Container: `flex border-b border-gray-200`
- Each trigger: `flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors`
- Active: `border-blue-600 text-blue-600`
- Inactive: `border-transparent text-gray-500 hover:text-gray-700`
- Badge next to label: small count badge using existing `Badge` component, variant `"neutral"`, only shown when count > 0.

### 6.3 Tab Persistence

The active tab is persisted to the `caseStore` Zustand store keyed by case ID, so returning to the case workspace restores the last-viewed tab. Default tab on first visit is `overview`.

---

## 7. Tab Content -- Overview

### 7.1 Layout

The Overview tab displays case metadata in a card grid with quick statistics.

```
+--------------------------------------------------------------------+
| +--- Quick Stats Row (grid-cols-4) --------------------------------+|
| | Docs: 12     | Conversations: 5 | Drafts: 3    | Days Open: 42  ||
| +------------------------------------------------------------------+|
|                                                                      |
| +--- Case Info Card ---+ +--- Description Card --------------------+|
| | Client: ABC Pte Ltd  | | Lorem ipsum dolor sit amet, consectetur ||
| | Practice: Contract    | | adipiscing elit. Sed do eiusmod tempor  ||
| | Type: Dispute         | | incididunt ut labore et dolore magna    ||
| | Priority: High        | | aliqua...                               ||
| | Stage: Research       | |                                         ||
| | Court: SIAC           | |                                         ||
| | Opposing: XYZ Corp    | |                                         ||
| +-----------------------+ +-----------------------------------------+|
|                                                                      |
| +--- Timeline Card --------+ +--- Assigned To Card ----------------+|
| | Created: 15 Jan 2025     | | [Avatar] Jane Doe                   ||
| | Updated: 23 Jun 2026     | | Senior Associate                     ||
| | Filing: 20 Feb 2025      | | Created by: John Smith               ||
| +---------------------------+ +-------------------------------------+|
|                                                                      |
| +--- Tags Card (full width) ----------------------------------------+|
| | [contract] [dispute] [SIAC] [urgent]                              ||
| +--------------------------------------------------------------------+|
+----------------------------------------------------------------------+
```

### 7.2 Quick Stats Row

A row of 4 metric cards across the top of the Overview tab. Each card is a compact stat display.

| Stat             | Icon          | Source                                                   |
| ---------------- | ------------- | -------------------------------------------------------- |
| Documents        | `FileText`    | Count from `list_documents` query                        |
| Conversations    | `MessageSquare` | Count from case-scoped conversation query              |
| Drafts           | `PenTool`     | Count of documents with `file_type` in draft-related types |
| Days Open        | `Calendar`    | `Math.ceil((now - created_at) / 86400000)`               |

Each card: `rounded-xl border border-gray-200 bg-white shadow-sm px-4 py-3`. Metric value in `text-2xl font-bold text-gray-900`. Label in `text-xs text-gray-500 uppercase tracking-wide`.

### 7.3 Case Information Card

Uses existing `Card` component. Displays all non-null metadata fields in a definition list (`<dl>`) with `<dt>` as label and `<dd>` as value. Same pattern as current `OverviewTab` in `CaseDetail.tsx`.

Fields displayed (in order): Client, Practice Area, Case Type, Priority (with colored badge), Stage (with colored badge), Court, Opposing Party, Client Reference, Filing Date (formatted via `formatDate()`).

### 7.4 Description Card

Uses `Card` component with title "Description". Body is `whitespace-pre-wrap text-sm text-gray-700 leading-relaxed`. If description is null/empty, shows `EmptyState` with message "No description provided. Edit the case to add one."

---

## 8. Tab Content -- Documents

### 8.1 Layout

```
+--------------------------------------------------------------------+
| +-- Toolbar -------------------------------------------------------+|
| | [Search docs...      ]  [Filter: Type v] [Sort: Date v]  [Upload]||
| +------------------------------------------------------------------+|
|                                                                      |
| +-- Drag-Drop Upload Zone (when no docs OR always as a strip) -----+|
| |   +----------------------------------------------------+         ||
| |   | [Upload icon]                                       |         ||
| |   | Drag and drop files here, or click to browse        |         ||
| |   | Supports PDF, DOCX, TXT, images (max 50MB)          |         ||
| |   +----------------------------------------------------+         ||
| +------------------------------------------------------------------+|
|                                                                      |
| +-- Document List --------------------------------------------------+|
| | +--- Row -------------------------------------------------------+||
| | | [PDF icon]  Affidavit_of_Evidence.pdf        Affidavit         |||
| | |             23 Jun 2025  2.4 MB              OCR: Complete     |||
| | +---------------------------------------------------------------+||
| | +--- Row -------------------------------------------------------+||
| | | [DOC icon]  Defence_Submission.docx          Submission         |||
| | |             15 Jun 2025  1.1 MB              OCR: Processing   |||
| | +---------------------------------------------------------------+||
| +------------------------------------------------------------------+|
```

### 8.2 Toolbar

| Element       | Position | Component                                               |
| ------------- | -------- | ------------------------------------------------------- |
| Search        | Left     | `Input` with `Search` icon, debounced 300ms, filters document list by filename |
| Type filter   | Center   | Radix `Select`, options from `FILE_TYPES` constant + "All Types" |
| Sort          | Center   | Radix `Select`, options: "Newest First", "Oldest First", "Name A-Z", "Name Z-A", "Type" |
| Upload button | Right    | `Button` variant `"primary"` size `"sm"`, `Upload` icon |

### 8.3 Drag-Drop Upload Zone

Visible when there are 0 documents (fills content area) OR as a collapsed strip at the top (when documents exist, 60px height). On drag-over, expands to full height with a blue dashed border (`border-2 border-dashed border-blue-400 bg-blue-50`).

| State        | Appearance                                                  |
| ------------ | ----------------------------------------------------------- |
| Default      | Dashed border `border-gray-300`, gray icon, gray text       |
| Drag-over    | Dashed border `border-blue-400`, blue bg, blue text         |
| Uploading    | Shows progress bar per file, filename, percentage           |
| Error        | Red border, error message per file                          |

Accepted MIME types: `application/pdf`, `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/plain`, `image/png`, `image/jpeg`.

Max file size: 50MB per file. Multiple files accepted simultaneously.

### 8.4 Document List Item

Each document row is a card-like element (same pattern as current `DocumentsTab` in `CaseDetail.tsx` line 206):

```
+---------------------------------------------------------------+
| [FileIcon]  Filename.pdf                    [Type Badge]       |
|             23 Jun 2025  |  2.4 MB          [OCR Status Badge] |
+---------------------------------------------------------------+
```

- File icon: `FileText` (lucide), 18px, `text-gray-400`
- Filename: `text-sm font-medium text-gray-900 truncate`
- Date: `text-xs text-gray-500`, formatted via `formatDate()`
- Size: `text-xs text-gray-500`, formatted as KB/MB
- Type badge: `Badge` variant `"neutral"`
- OCR status badge: `complete=success`, `processing=warning`, `pending=warning`, `failed=danger`

Clicking a document row opens the Document Detail Drawer (section 8.5).

### 8.5 Document Detail Drawer

A slide-in drawer from the right side (Radix `Dialog` with custom positioning), 480px wide. Contains:

| Section          | Content                                                           |
| ---------------- | ----------------------------------------------------------------- |
| Header           | Filename, file type badge, close button                           |
| Metadata         | Upload date, uploader, file size, OCR status                      |
| Classification   | AI-generated classification tags (from `classification` dict)     |
| Preview          | If OCR text available: scrollable text preview with search-in-doc |
| Actions          | Download, Re-run OCR, Delete (with confirmation), Reclassify      |

---

## 9. Tab Content -- Chronology

### 9.1 Layout

A vertical timeline of case events, with date markers and event cards.

```
+--------------------------------------------------------------------+
| +-- Toolbar -------------------------------------------------------+|
| | [Auto-Extract from Docs]              [+ Add Event]  [Filter v]  ||
| +------------------------------------------------------------------+|
|                                                                      |
| --- 23 Jun 2025 --------------------------------------------------- |
|  o  Filed Statement of Claim                                        |
|     Source: Statement_of_Claim.pdf  |  Significance: High           |
|     Filed at the State Courts of Singapore                          |
|                                                                      |
| --- 15 Jun 2025 --------------------------------------------------- |
|  o  Received Defence and Counterclaim                               |
|     Source: Defence_Counterclaim.pdf  |  Significance: High         |
|     Opposing party filed counterclaim for $50,000                   |
|                                                                      |
| --- 10 Jun 2025 --------------------------------------------------- |
|  o  Client meeting - initial consultation                           |
|     Source: Manual entry  |  Significance: Medium                   |
|     Discussed case merits and strategy with client                  |
+--------------------------------------------------------------------+
```

### 9.2 Timeline Data Model

Each chronology event is stored in `case.metadata.chronology` as an array (until a dedicated Chronology model is created):

```typescript
interface ChronologyEvent {
  id: string;                    // UUID v4
  date: string;                  // ISO 8601 date
  title: string;                 // Short description
  description: string;           // Detailed description
  source_document_id: string | null;  // FK to Document
  source_type: "manual" | "auto_extracted";
  significance: "low" | "medium" | "high" | "critical";
  created_by_id: string;         // FK to User
  created_at: string;            // ISO 8601
}
```

### 9.3 Date Markers

Events are grouped by date. Each date group has a horizontal line with the date displayed in `text-sm font-semibold text-gray-500`. Format: `DD MMM YYYY`.

### 9.4 Event Cards

| Element              | Style                                                           |
| -------------------- | --------------------------------------------------------------- |
| Timeline dot         | `w-3 h-3 rounded-full`, color by significance (low=gray, medium=blue, high=amber, critical=red) |
| Timeline line        | `w-0.5 bg-gray-200`, connects dots vertically                  |
| Title                | `text-sm font-medium text-gray-900`                            |
| Source               | `text-xs text-gray-500`, links to document if `source_document_id` is set |
| Significance badge   | `Badge`, variant by level                                       |
| Description          | `text-sm text-gray-600`, 2-line clamp, expandable on click     |

### 9.5 Auto-Extract Button

The "Auto-Extract from Docs" button triggers an AI analysis of all uploaded documents to extract a timeline of events. It calls `send_message` with a system prompt instructing the AI to parse documents and return structured timeline data. During processing, shows a loading indicator with "Analyzing documents..." text.

### 9.6 Add Event Dialog

Opens a Radix `Dialog` with:
- Date picker (native `<input type="date">`)
- Title input (required, max 200 chars)
- Description textarea (optional, max 2000 chars)
- Source document select (optional, populated from case documents)
- Significance select (low/medium/high/critical)

---

## 10. Tab Content -- Research

### 10.1 Layout

```
+--------------------------------------------------------------------+
| +-- Search Bar (full width) ---------------------------------------+|
| | [Search case law, legislation, or legal topics...      ] [Search]||
| | Jurisdiction: [SG v]  Practice Area: [auto-filled]               ||
| +------------------------------------------------------------------+|
|                                                                      |
| +-- Split: Results (left 60%) -----+ +-- Pinned (right 40%) ------+|
| |                                   | |                            ||
| | +-- Result Card -----------------+| | Pinned Research (3)        ||
| | | [2024] SGCA 45                  || |                            ||
| | | Tan v Lee [2024] SGCA 45       || | +-- Pinned Card ----------+||
| | | Court of Appeal, Singapore     || | | Tan v Lee [2024] SGCA 45|||
| | | Relevance: 92%                 || | | Positive treatment       |||
| | | "The court held that..."       || | | [Unpin] [Open]           |||
| | | [Add to Case]                  || | +-------------------------+||
| | +--------------------------------+| |                            ||
| |                                   | | +-- Pinned Card ----------+||
| | +-- Result Card -----------------+| | | Lim v MAS [2023] SGHC 12|||
| | | [2023] SGHC 12                  || | | Negative treatment (!)  |||
| | | Lim v MAS [2023] SGHC 12      || | | [Unpin] [Open]           |||
| | | High Court, Singapore          || | +-------------------------+||
| | | Relevance: 87%                 || |                            ||
| | | "It was established that..."   || |                            ||
| | | [Add to Case]                  || |                            ||
| | +--------------------------------+| |                            ||
| +-----------------------------------+ +----------------------------+|
+--------------------------------------------------------------------+
```

### 10.2 Search Controls

| Element           | Component                                                     |
| ----------------- | ------------------------------------------------------------- |
| Search input      | Full-width `Input` with `Search` icon                         |
| Jurisdiction      | Radix `Select`, values from `JURISDICTIONS` constant, default "SG" |
| Practice area     | Auto-filled from case's `practice_area`, editable via `Select` |
| Search button     | `Button` variant `"primary"`, triggers `legalResearch()` API call |

### 10.3 Search Result Card

Each result card displays:

| Element           | Style / Source                                                   |
| ----------------- | ---------------------------------------------------------------- |
| Year              | `text-xs font-mono text-gray-500`, extracted from citation       |
| Citation          | `text-sm font-semibold text-gray-900`                            |
| Case name         | `text-sm text-gray-700`                                          |
| Court             | `text-xs text-gray-500`                                          |
| Relevance score   | Percentage badge, color-coded: >=80% green, 60-79% amber, <60% gray |
| Summary snippet   | `text-sm text-gray-600`, 3-line clamp                            |
| Treatment warning | If `treatment_warning` is set: red banner with warning text      |
| "Add to Case"     | `Button` variant `"secondary"` size `"sm"`, pins research to case |

### 10.4 Pinned Research Sidebar

Shows research items that have been pinned to this case. Pinned items are stored in `case.metadata.pinned_research` as an array:

```typescript
interface PinnedResearch {
  id: string;
  citation: string;
  case_name: string;
  court: string;
  relevance_score: number;
  summary: string;
  treatment_warning: string | null;
  pinned_by_id: string;
  pinned_at: string;
}
```

Each pinned card shows citation, treatment status, and actions (Unpin, Open full details).

### 10.5 Citation Treatment Warnings

Treatment warnings surface when a cited case has been overruled, distinguished, or otherwise treated negatively by subsequent decisions. The warning is sourced from the `Source.treatment_warning` field in the chat types.

| Treatment      | Badge Variant | Icon          | Display Text                           |
| -------------- | ------------- | ------------- | -------------------------------------- |
| Overruled      | `danger`      | `AlertCircle` | "Overruled by [citation]"              |
| Distinguished  | `warning`     | `AlertTriangle` | "Distinguished in [citation]"        |
| Followed       | `success`     | `CheckCircle` | "Followed in [citation]"              |
| Considered     | `info`        | `Info`        | "Considered in [citation]"             |
| Not followed   | `warning`     | `XCircle`     | "Not followed in [citation]"           |

---

## 11. Tab Content -- Drafts

### 11.1 Layout

Drafts are organized by case stage in an accordion layout.

```
+--------------------------------------------------------------------+
| [Generate Draft v]                                                  |
|                                                                      |
| v  Research (2 drafts) --------------------------------------------- |
| | +-- Draft Card ------------------------------------------------+ ||
| | | Legal Memo - Preliminary Analysis       v1.2    In Progress  | ||
| | | Template: Legal Memorandum  |  23 Jun 2025                   | ||
| | | [Edit] [Preview] [Export]                                    | ||
| | +--------------------------------------------------------------+ ||
| | +-- Draft Card ------------------------------------------------+ ||
| | | Case Brief - Background Facts           v1.0    Complete     | ||
| | | Template: Case Brief  |  20 Jun 2025                        | ||
| | | [Edit] [Preview] [Export]                                    | ||
| | +--------------------------------------------------------------+ ||
|                                                                      |
| >  Drafting (0 drafts) -------------------------------------------- |
|                                                                      |
| >  Submission (0 drafts) ------------------------------------------ |
+--------------------------------------------------------------------+
```

### 11.2 Stage Accordion

Each stage that has applicable templates appears as an accordion section. Uses Radix `Collapsible` or custom accordion. The current stage's section is expanded by default. Empty stages show "No drafts for this stage" with a "Generate Draft" button.

### 11.3 Draft Card

| Element         | Style                                                             |
| --------------- | ----------------------------------------------------------------- |
| Title           | `text-sm font-medium text-gray-900`                              |
| Version         | `text-xs font-mono text-gray-500`, format: `v1.0`, `v1.1`, etc. |
| Status badge    | `draft=neutral`, `in_progress=info`, `review=warning`, `approved=success`, `rejected=danger` |
| Template name   | `text-xs text-gray-500`                                          |
| Date            | `text-xs text-gray-500`, formatted via `formatDate()`            |
| Actions         | Edit (opens draft viewer), Preview (read-only viewer), Export (downloads as DOCX/PDF) |

### 11.4 Generate Draft Button

Opens a template selector modal (Radix `Dialog`):

1. **Template selection:** Grid of template cards filtered by the case's `practice_area` and current `stage`. Each card shows template name, description, and the stage it applies to. Templates are sourced from the `listSOPTemplates()` API.

2. **Configuration:** After selecting a template, shows:
   - Instructions textarea (optional additional instructions for the AI)
   - Tone selector: Formal, Neutral, Persuasive, Conversational
   - "Include case documents" toggle
   - "Include pinned research" toggle

3. **Generation:** Calls `draftDocument()` from `chat.service.ts`. Shows a progress indicator ("Generating draft..."). On completion, the new draft appears in the appropriate stage accordion.

### 11.5 Draft Viewer

Opens as a full-width overlay panel (replaces tab content temporarily, with a back button to return to the drafts list). Contains:

| Section    | Content                                                             |
| ---------- | ------------------------------------------------------------------- |
| Header     | Draft title, version, status badge, back button                     |
| Toolbar    | Edit, Save, Export as DOCX, Export as PDF, Version History, Submit for Review |
| Content    | Rich text content area (rendered markdown via `react-markdown`)      |
| Metadata   | Template used, generation date, word count, last editor             |

---

## 12. Tab Content -- Analysis

### 12.1 Layout

```
+--------------------------------------------------------------------+
| [Run Analysis v]                              [Analysis History]    |
|                                                                      |
| +-- IRAC Analysis Card -------------------------------------------+|
| | Issue                                                            ||
| |   Whether the defendant breached the implied warranty...        ||
| |                                                                  ||
| | Rule                                                             ||
| |   Under Section 14 of the Sale of Goods Act (Cap 393)...       ||
| |                                                                  ||
| | Application                                                      ||
| |   In the present case, the goods delivered were...              ||
| |                                                                  ||
| | Conclusion                                                       ||
| |   On balance, the defendant likely breached...                  ||
| +------------------------------------------------------------------+|
|                                                                      |
| +-- Risk Assessment Card --+ +-- Strengths & Weaknesses Card -----+|
| | Overall Risk: Medium      | | Strengths:                        ||
| | [======----] 60%          | |  + Strong documentary evidence    ||
| |                           | |  + Favorable precedent             ||
| | Key Risks:                | |                                    ||
| |  - Limitation period      | | Weaknesses:                       ||
| |  - Witness availability   | |  - Delayed filing                 ||
| |  - Costs exposure         | |  - Key witness unavailable        ||
| +---------------------------+ +------------------------------------+|
+--------------------------------------------------------------------+
```

### 12.2 Run Analysis Button

Dropdown with analysis types:

| Analysis Type    | Description                                    | Prompt Strategy               |
| ---------------- | ---------------------------------------------- | ----------------------------- |
| IRAC Analysis    | Issue, Rule, Application, Conclusion           | Structured legal analysis     |
| Risk Assessment  | Identify and score case risks                  | Risk matrix generation        |
| SWOT Analysis    | Strengths, Weaknesses, Opportunities, Threats  | Case position evaluation      |
| Costs Estimate   | Estimate legal costs and disbursements         | Financial projection          |
| Timeline Review  | Identify limitation periods and deadlines      | Critical dates extraction     |

Each analysis type calls `send_message()` with a structured system prompt and the case context (documents, chronology, pinned research). The response is parsed and displayed in structured cards.

### 12.3 IRAC Analysis Card

A single `Card` component with four labeled sections. Each section:
- Label: `text-xs font-semibold uppercase tracking-wide text-gray-500`
- Content: `text-sm text-gray-700 leading-relaxed` rendered via `react-markdown`

### 12.4 Risk Assessment Card

| Element          | Style                                                    |
| ---------------- | -------------------------------------------------------- |
| Overall risk     | Large text label + colored progress bar (green/amber/red)|
| Risk percentage  | `text-2xl font-bold`                                     |
| Risk items       | Bulleted list with severity badges                       |

### 12.5 Strengths and Weaknesses Card

Two-column layout within a `Card`. Strengths prefixed with `+` in green, Weaknesses prefixed with `-` in red.

### 12.6 Analysis History

A collapsible sidebar or dropdown that shows previously run analyses for this case, with timestamps and types. Clicking a historical analysis loads it into the analysis view.

Analysis data is stored in `case.metadata.analyses` as an array:

```typescript
interface CaseAnalysis {
  id: string;
  type: "irac" | "risk" | "swot" | "costs" | "timeline";
  content: Record<string, unknown>;  // Structured per type
  generated_by_conversation_id: string;
  created_at: string;
}
```

---

## 13. Chat Panel

### 13.1 Layout

The Chat Panel is the right pane of the split layout. It provides always-available AI assistance scoped to the current case.

```
+-------------------------------------------+
| Chat  [Conversations v]  [New] [Collapse] |
+-------------------------------------------+
|                                           |
| +-- Messages (scrollable) ---------------+|
| |                                         ||
| | [User] What are the key issues in      ||
| |         this case?                      ||
| |                                         ||
| | [AI] Based on the documents uploaded,  ||
| |      the key issues are:               ||
| |      1. Whether the defendant...       ||
| |      2. The applicable limitation...   ||
| |                                         ||
| |      Sources:                          ||
| |      - Tan v Lee [2024] SGCA 45       ||
| |      - Sale of Goods Act s14          ||
| |                                         ||
| +-----------------------------------------+|
|                                           |
| +-- Input --------------------------------+|
| | [Type a message...              ] [Send]||
| | [Attach] [@ Mention doc]               ||
| +-----------------------------------------+|
+-------------------------------------------+
```

### 13.2 Panel Header

| Element              | Position | Behavior                                                  |
| -------------------- | -------- | --------------------------------------------------------- |
| "Chat" label         | Left     | `text-sm font-semibold text-gray-900`                     |
| Conversations select | Center   | Dropdown listing case-scoped conversations                 |
| New button           | Right    | Creates a new conversation scoped to this case             |
| Collapse button      | Right    | Collapses panel to a 48px-wide strip with expand arrow     |

### 13.3 Resize Handle

A 4px-wide vertical drag handle between the tab content and chat panel. Implemented with `pointer-events` and `mousemove`/`touchmove` handlers.

| Measurement        | Value                             |
| ------------------ | --------------------------------- |
| Handle width       | 4px                               |
| Handle hover width | 4px (cursor changes to `col-resize`) |
| Handle color       | `transparent` default, `bg-blue-400` on hover/drag |
| Min panel width    | 320px                             |
| Max panel width    | 50% of split pane container       |

### 13.4 Message Display

Uses existing `MessageBubble` component from `src/frontend/src/components/chat/MessageBubble.tsx`. Messages are fetched via `getConversationHistory()` and displayed in chronological order.

| Message Role | Alignment | Style                                           |
| ------------ | --------- | ----------------------------------------------- |
| `user`       | Right     | Blue background (`bg-blue-600 text-white`)      |
| `assistant`  | Left      | White background, gray border                   |
| `system`     | Center    | Gray background, italic text                    |

Assistant messages render markdown content via `react-markdown` and display sources using the existing `SourcesList` component.

### 13.5 Chat Input

Uses existing `ChatInput` component from `src/frontend/src/components/chat/ChatInput.tsx`. Additional context buttons:

| Button       | Icon        | Behavior                                                      |
| ------------ | ----------- | ------------------------------------------------------------- |
| Attach       | `Paperclip` | Opens file picker for inline document reference               |
| Mention doc  | `AtSign`    | Opens document selector to reference a case document in the message |
| Send         | `Send`      | Sends message via `sendMessage()` with case context           |

The `case_context` parameter passed to `sendMessage()` includes:

```typescript
{
  case_id: string;
  practice_area: string;
  case_type: string;
  stage: string;
  client_name: string;
  document_ids: string[];     // IDs of documents in the case
  pinned_research: string[];  // Citations of pinned research
}
```

### 13.6 Collapsed State

When collapsed, the chat panel shows a 48px-wide strip:

```
+------+
| [>>] |
|      |
| Chat |
| (3)  |
|      |
+------+
```

The `>>` icon expands the panel. The `(3)` badge shows unread message count.

---

## 14. Responsive Behavior

### 14.1 Breakpoint Definitions

| Breakpoint    | Width Range    | Layout Behavior                                         |
| ------------- | -------------- | ------------------------------------------------------- |
| `xl` (large)  | >= 1280px      | Full split pane. Chat panel visible at default 380px.   |
| `lg` (medium) | 1024-1279px    | Split pane. Chat collapsed by default (48px strip).     |
| `md` (tablet) | 768-1023px     | Full-width tabs. Chat as bottom sheet (40% viewport h). |
| `sm` (mobile) | < 768px        | Single column. Chat as full-screen overlay.             |

### 14.2 Large Desktop (>= 1280px)

- Standard layout per section 3.1
- Chat panel visible, default width 380px
- Tab content and chat panel side-by-side
- Stage progress bar shows all 8 labels
- All 6 tabs visible in single row

### 14.3 Medium Desktop (1024-1279px)

- Split pane layout maintained
- Chat panel collapsed to 48px strip by default
- User can expand chat panel; when expanded, it overlays the tab content partially
- Stage progress bar shows abbreviated labels (e.g., "Intake", "Facts", "Res.", "Ana.", "Draft", "Rev.", "Sub.", "Done")
- All 6 tabs visible, possibly scrollable horizontally

### 14.4 Tablet (768-1023px)

- No split pane -- tab content takes full width
- Chat available as a bottom sheet:
  - Collapsed: 60px handle strip at bottom with "Chat" label and drag handle
  - Half-expanded: 40% viewport height
  - Full-expanded: 80% viewport height
- Stage progress bar: circles only (no labels), tooltip on tap
- Tabs may scroll horizontally if they overflow

### 14.5 Mobile (< 768px)

- Single column layout
- Case header stacks vertically: title on one line, badges on next line, actions on third line
- Stage progress bar: minimal -- shows only current stage name with left/right arrows
- Tabs rendered as horizontal scrollable pills
- Chat opens as full-screen overlay modal:
  - Triggered by a floating action button (FAB) at bottom-right, 56px diameter
  - FAB shows `MessageSquare` icon with unread badge
  - Overlay has close button at top-right

### 14.6 Tab Content Responsive Adjustments

| Tab         | >= 768px                        | < 768px                          |
| ----------- | ------------------------------- | -------------------------------- |
| Overview    | 2-column grid                   | Single column stack              |
| Documents   | Toolbar inline                  | Toolbar stacked, search full-width |
| Chronology  | Timeline with full descriptions | Compact timeline, descriptions truncated |
| Research    | Split results/pinned            | Stacked: results then pinned     |
| Drafts      | Accordion with full cards       | Accordion with compact cards     |
| Analysis    | Multi-column cards              | Single column stack              |

---

## 15. State Management

### 15.1 Zustand Store -- `caseStore`

New store at `src/frontend/src/stores/caseStore.ts`:

```typescript
interface CaseStore {
  // Active workspace state
  activeCaseId: string | null;
  activeTab: Record<string, string>;       // keyed by caseId -> tab value
  chatPanelWidth: number;                  // persisted resize width
  chatPanelCollapsed: boolean;
  chatPanelConversationId: string | null;  // active conversation in chat panel

  // Actions
  setActiveCaseId: (id: string | null) => void;
  setActiveTab: (caseId: string, tab: string) => void;
  setChatPanelWidth: (width: number) => void;
  setChatPanelCollapsed: (collapsed: boolean) => void;
  setChatPanelConversationId: (id: string | null) => void;
}
```

This store uses `zustand/middleware` `persist` with `sessionStorage` (same pattern as `authStore`).

### 15.2 React Query Keys

All queries use a structured key convention for cache management and invalidation.

| Query Key                                     | Fetcher                                          | Stale Time |
| --------------------------------------------- | ------------------------------------------------ | ---------- |
| `["cases"]`                                   | `listCases(firmId)`                              | 30s        |
| `["cases", caseId]`                           | `getCase(caseId, firmId)`                        | 60s        |
| `["case-documents", caseId]`                  | `listDocuments(caseId, firmId)`                  | 30s        |
| `["case-documents", caseId, docId]`           | `getDocument(docId, firmId)`                     | 60s        |
| `["case-conversations", caseId]`              | `searchConversations(firmId, caseId, ...)`       | 15s        |
| `["case-conversation-messages", convId]`      | `getConversationHistory(convId, firmId)`          | 10s        |
| `["case-chronology", caseId]`                 | Derived from case metadata                       | 60s        |
| `["case-research", caseId]`                   | Derived from case metadata                       | 60s        |
| `["case-drafts", caseId]`                     | Filtered documents by draft types                | 30s        |
| `["case-analyses", caseId]`                   | Derived from case metadata                       | 60s        |
| `["sop-templates", practiceArea]`             | `listSOPTemplates(practiceArea)`                 | 300s       |
| `["legal-research", searchParams]`            | `legalResearch(query, ...)`                      | 120s       |

### 15.3 Optimistic Updates

| Operation          | Optimistic Behavior                                             | Rollback                       |
| ------------------ | --------------------------------------------------------------- | ------------------------------ |
| Upload document    | Add placeholder row with `ocr_status: "processing"` immediately | Remove row on error            |
| Send message       | Add message with `role: "user"` immediately, show typing indicator | Remove message on error       |
| Pin research       | Add to pinned sidebar immediately                               | Remove from sidebar on error   |
| Add chronology     | Add event to timeline immediately                               | Remove event on error          |
| Stage transition   | Update stage badge and progress bar immediately                 | Revert to previous stage       |

### 15.4 Query Key Invalidation Map

When a mutation succeeds, the following query keys are invalidated:

| Mutation                  | Invalidated Keys                                               |
| ------------------------- | -------------------------------------------------------------- |
| `update_case`             | `["cases", caseId]`, `["cases"]`                               |
| `upload_document`         | `["case-documents", caseId]`, `["cases", caseId]`             |
| `send_message`            | `["case-conversation-messages", convId]`, `["case-conversations", caseId]` |
| `create_conversation`     | `["case-conversations", caseId]`                               |
| Pin/unpin research        | `["cases", caseId]`, `["case-research", caseId]`              |
| Add/remove chronology     | `["cases", caseId]`, `["case-chronology", caseId]`            |
| Run analysis              | `["cases", caseId]`, `["case-analyses", caseId]`              |
| Generate draft            | `["case-documents", caseId]`, `["case-drafts", caseId]`       |

---

## 16. Component File Structure

New and modified files for the Case Workspace implementation:

```
src/frontend/src/
  pages/
    CaseWorkspace.tsx              # Main page component (replaces CaseDetail.tsx)

  components/
    case-workspace/
      CaseHeader.tsx               # Header bar with title, badges, actions
      StageProgressBar.tsx         # 8-stage horizontal stepper
      CaseTabs.tsx                 # Tab bar + content switching
      ChatPanel.tsx                # Right-side chat panel with resize
      ResizeHandle.tsx             # Drag handle for split pane

      tabs/
        OverviewTab.tsx            # Case metadata cards and stats
        DocumentsTab.tsx           # Document list, upload, detail drawer
        ChronologyTab.tsx          # Timeline with events
        ResearchTab.tsx            # Case law search and pinned research
        DraftsTab.tsx              # Stage-organized drafts
        AnalysisTab.tsx            # IRAC, risk, SWOT analysis

      dialogs/
        StageTransitionDialog.tsx  # Confirmation for stage changes
        GenerateDraftDialog.tsx    # Template selector and configuration
        AddEventDialog.tsx         # Manual chronology event creation
        DocumentDetailDrawer.tsx   # Slide-in document details

  stores/
    caseStore.ts                   # New Zustand store

  types/
    case.ts                        # Updated with CaseStage, missing backend statuses
    workspace.ts                   # New types: ChronologyEvent, PinnedResearch, CaseAnalysis

  utils/
    constants.ts                   # Updated ROUTES, added CASE_STAGES constant
    stage-utils.ts                 # Stage color map, validation, display helpers
```

---

## 17. Existing Component Reuse

These existing components are used directly without modification:

| Component      | Path                                         | Usage                          |
| -------------- | -------------------------------------------- | ------------------------------ |
| `Badge`        | `components/common/Badge.tsx`                | Status, stage, type badges     |
| `Button`       | `components/common/Button.tsx`               | All action buttons             |
| `Card`         | `components/common/Card.tsx`                 | All content cards              |
| `Loading`      | `components/common/Loading.tsx`              | All loading states             |
| `EmptyState`   | `components/common/EmptyState.tsx`           | Empty tab content              |
| `Input`        | `components/common/Input.tsx`                | Search inputs                  |
| `MessageBubble`| `components/chat/MessageBubble.tsx`          | Chat panel messages            |
| `ChatInput`    | `components/chat/ChatInput.tsx`              | Chat panel input               |
| `ChatArea`     | `components/chat/ChatArea.tsx`               | Chat panel message area        |
| `SourcesList`  | `components/chat/SourcesList.tsx`            | Research source citations       |
| `CaseForm`     | `components/cases/CaseForm.tsx`              | Case editing dialog            |

---

## 18. API Dependencies

### 18.1 Existing API Endpoints (from `case.service.ts` and `chat.service.ts`)

| Endpoint              | Service Function          | Used By                          |
| --------------------- | ------------------------- | -------------------------------- |
| `create_case`         | `createCase()`            | CaseForm                        |
| `get_case`            | `getCase()`               | CaseWorkspace (main query)       |
| `list_cases`          | `listCases()`             | Cases page                       |
| `update_case`         | `updateCase()`            | Header actions, stage transition |
| `upload_document`     | `uploadDocument()`        | DocumentsTab                     |
| `get_document`        | `getDocument()`           | DocumentDetailDrawer             |
| `list_documents`      | `listDocuments()`         | DocumentsTab, stats              |
| `create_conversation` | `createConversation()`    | ChatPanel                        |
| `send_message`        | `sendMessage()`           | ChatPanel, auto-extract, analysis |
| `get_conversation_history` | `getConversationHistory()` | ChatPanel                   |
| `search_conversations`| `searchConversations()`   | ChatPanel, stats                 |
| `draft_document`      | `draftDocument()`         | DraftsTab                        |
| `legal_research`      | `legalResearch()`         | ResearchTab                      |
| `list_sop_templates`  | `listSOPTemplates()`      | GenerateDraftDialog              |

### 18.2 New API Endpoints Required

These endpoints do not exist yet and MUST be implemented before or alongside the frontend workspace:

| Endpoint                    | Purpose                                     | Parameters                                        |
| --------------------------- | ------------------------------------------- | ------------------------------------------------- |
| `get_case_stats`            | Quick stats for case overview               | `case_id, firm_id` -> `{ doc_count, conv_count, draft_count }` |
| `search_case_conversations` | List conversations scoped to a case         | `case_id, firm_id, limit, offset` -> paginated conversations  |
| `update_case_metadata`      | Patch case metadata JSON (chronology, research, analyses) | `case_id, firm_id, metadata_patch` -> updated case |

**Note:** The `search_conversations` function in `chat.service.ts` currently accepts `(firm_id, query, status, limit, offset)` but the `CaseDetail.tsx` calls it as `searchConversations(firmId, caseId, undefined, 50)` where `caseId` is passed as the `query` parameter. This is a semantic mismatch -- the backend `search_conversations` handler does text search, not case-scoped filtering. A dedicated `search_case_conversations` endpoint MUST filter by `case_id` FK.

---

## 19. Error States

### 19.1 Page-Level Errors

| Error Condition                | Display                                                     |
| ------------------------------ | ----------------------------------------------------------- |
| Case not found (404)           | Full-page `EmptyState`: "Case not found", "Back to Cases" button |
| Unauthorized (403 / wrong firm)| Full-page error: "You don't have access to this case"       |
| Network error                  | Full-page error with retry button                           |
| Case loading                   | Full-page `Loading` spinner                                 |

### 19.2 Tab-Level Errors

Each tab handles its own error state independently:

| Error Condition           | Display                                                   |
| ------------------------- | --------------------------------------------------------- |
| Documents failed to load  | Inline error banner with retry button                     |
| Search failed             | Inline error with "Try a different search" suggestion     |
| Analysis generation failed| Error toast + inline error in analysis section             |
| Draft generation failed   | Error toast + error state in draft card                    |

### 19.3 Chat Panel Errors

| Error Condition           | Display                                                   |
| ------------------------- | --------------------------------------------------------- |
| Message send failed       | Red error below failed message, "Retry" button            |
| Conversation load failed  | Inline error with retry                                   |
| Rate limited              | Yellow banner: "Slow down. Try again in X seconds."       |

---

## 20. Loading States

| Component              | Loading Indicator                                              |
| ---------------------- | -------------------------------------------------------------- |
| Case data              | Full-page `Loading` with "Loading case..."                     |
| Documents list         | `Loading` component with "Loading documents..."                |
| Chat messages          | `Loading` component inside chat panel                          |
| AI message response    | Typing indicator (three animated dots) in assistant bubble     |
| Document upload        | Progress bar per file with percentage                          |
| Analysis generation    | Pulsing card skeleton with "Running analysis..."               |
| Draft generation       | Pulsing card skeleton with "Generating draft..."               |
| Search results         | Skeleton cards (3 placeholder rows)                            |
| Stage transition       | Stage badge shows spinner during API call                      |

---

## 21. Keyboard Shortcuts

| Shortcut         | Action                                     | Scope            |
| ---------------- | ------------------------------------------ | ---------------- |
| `Ctrl+1` ... `Ctrl+6` | Switch to tab 1-6                    | Case Workspace   |
| `Ctrl+/`         | Focus chat input                           | Case Workspace   |
| `Ctrl+U`         | Open upload dialog                         | Documents tab    |
| `Ctrl+Enter`     | Send chat message                          | Chat panel       |
| `Escape`         | Close active dialog/drawer                 | Global           |
| `Ctrl+B`         | Toggle chat panel collapsed/expanded       | Case Workspace   |

---

## 22. Accessibility

| Requirement                    | Implementation                                          |
| ------------------------------ | ------------------------------------------------------- |
| Tab navigation                 | Radix Tabs handles keyboard nav (arrow keys)            |
| Screen reader stage progress   | `aria-label="Case stage: Research (step 3 of 8)"`       |
| Chat panel landmark            | `<aside role="complementary" aria-label="Case chat">`   |
| Document list                  | `role="list"` with `role="listitem"` per row            |
| Drag-drop upload               | Accessible file input fallback always available          |
| Resize handle                  | `role="separator" aria-orientation="vertical" aria-valuenow={width}` |
| Stage progress bar             | `role="progressbar" aria-valuenow={currentIndex} aria-valuemin={0} aria-valuemax={7}` |
| Focus management               | Dialogs trap focus; closing returns focus to trigger     |
| Color contrast                 | All text meets WCAG 2.1 AA (4.5:1 for normal, 3:1 for large) |

---

## 23. Performance Considerations

| Concern                    | Strategy                                                       |
| -------------------------- | -------------------------------------------------------------- |
| Large document lists       | Paginate at 50 per page; virtual scrolling if > 200 documents  |
| Chat history               | Load last 50 messages; infinite scroll backward for history    |
| Research results            | Paginate at 20 per page                                       |
| Stage progress bar          | Static render; no re-render on tab change                     |
| Chat panel resize           | `requestAnimationFrame` throttle on drag                      |
| Tab content                 | Lazy-mount tabs (Radix `forceMount` NOT used); unmounted tabs do not retain query subscriptions |
| Prefetching                 | On case load, prefetch `["case-documents", caseId]` and `["case-conversations", caseId]` |
| Image previews              | Lazy-load document thumbnails with `loading="lazy"`           |

---

## 24. Design Token Alignment

The workspace uses the existing design tokens established in the codebase. No new colors or typography scales are introduced. All visual patterns match existing components.

| Token Category | Values Used                                                           |
| -------------- | --------------------------------------------------------------------- |
| Border radius  | `rounded-xl` (cards), `rounded-lg` (inputs, buttons), `rounded-full` (badges, avatars) |
| Shadows        | `shadow-sm` (cards) -- single level only                              |
| Font sizes     | `text-xs` (labels), `text-sm` (body), `text-base` (card titles), `text-xl` (page title), `text-2xl` (stat numbers) |
| Font weights   | `font-medium` (labels, links), `font-semibold` (section titles, card headers), `font-bold` (page title, stat numbers) |
| Colors         | Gray scale (50-900), Blue (primary actions), Green (success), Red (danger), Amber (warning) |
| Transitions    | `transition-colors duration-150` (links, buttons), `transition-transform duration-200 ease-in-out` (panels) |

---

## 25. Migration Notes

### 25.1 Replacing CaseDetail.tsx

The current `CaseDetail.tsx` at `src/frontend/src/pages/CaseDetail.tsx` (425 lines) is replaced entirely by `CaseWorkspace.tsx`. The existing code contains three inline tab components (`OverviewTab`, `DocumentsTab`, `ConversationsTab`) that MUST be migrated to the new component structure:

- `OverviewTab` -> `components/case-workspace/tabs/OverviewTab.tsx` (expanded with quick stats)
- `DocumentsTab` -> `components/case-workspace/tabs/DocumentsTab.tsx` (expanded with drag-drop, drawer)
- `ConversationsTab` -> Functionality absorbed into `ChatPanel.tsx`

### 25.2 Frontend Type Fixes

The `CaseStatus` type at `src/frontend/src/types/case.ts` line 15 currently has 4 values (`open | active | closed | archived`) but the backend at `core.py` line 111 has 6 values (`open | in_progress | pending_review | under_review | closed | archived`). The frontend type MUST be updated to match the backend:

```typescript
export type CaseStatus =
  | "open"
  | "in_progress"
  | "pending_review"
  | "under_review"
  | "closed"
  | "archived";
```

Additionally, a new `CaseStage` type MUST be added:

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
```

### 25.3 Constants Updates

`CASE_STATUSES` in `constants.ts` MUST be updated to include all 6 backend status values. A new `CASE_STAGES` constant MUST be added:

```typescript
export const CASE_STAGES = [
  { value: "intake", label: "Intake", color: "gray" },
  { value: "fact_gathering", label: "Fact Gathering", color: "blue" },
  { value: "research", label: "Research", color: "indigo" },
  { value: "analysis", label: "Analysis", color: "violet" },
  { value: "drafting", label: "Drafting", color: "amber" },
  { value: "review", label: "Review", color: "orange" },
  { value: "submission", label: "Submission", color: "emerald" },
  { value: "complete", label: "Complete", color: "green" },
] as const;
```

### 25.4 Route Registration

The router configuration (presumably in `App.tsx` or a dedicated router file) MUST add:

```typescript
<Route path="/cases/:id" element={<CaseWorkspace />} />
<Route path="/cases/:id/chat/:conversationId" element={<CaseWorkspace />} />
```

The existing `/cases/:id` route pointing to `CaseDetail` is replaced.
