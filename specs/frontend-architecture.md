# Frontend Architecture Specification

**Product:** LegalCoPilot v2 -- AI-Powered Legal Assistant for Singapore Law Firms
**Stack:** React 19 + TypeScript 6 + Vite 8 + Tailwind CSS v4 + Radix UI + React Query v5 + Zustand v5 + Lucide React + react-markdown + react-router-dom v6 + axios
**Root:** `src/frontend/`
**Proxy:** Vite dev server forwards `/api` to `http://localhost:8000`

---

## Table of Contents

1. [Route Structure](#1-route-structure)
2. [Component Architecture](#2-component-architecture)
3. [Type System](#3-type-system)
4. [State Management](#4-state-management)
5. [API Service Layer](#5-api-service-layer)
6. [Design System](#6-design-system)
7. [Key Interaction Patterns](#7-key-interaction-patterns)
8. [Performance and Loading](#8-performance-and-loading)
9. [Error Handling](#9-error-handling)
10. [Responsive Breakpoints](#10-responsive-breakpoints)
11. [File Structure](#11-file-structure)
12. [Implementation Status](#12-implementation-status)

---

## 1. Route Structure

### 1.1 Route Table

| Path | Page Component | Auth | Role Guard | Layout | Description |
|---|---|---|---|---|---|
| `/login` | `Login` | No (redirect if authed) | None | None (standalone) | Login page |
| `/` | redirect | Yes | None | -- | Redirects to `/dashboard` |
| `/dashboard` | `Dashboard` | Yes | None | `AppLayout` | Case list + quick stats + recent activity |
| `/cases/:id` | `CaseWorkspace` | Yes | None | `AppLayout` | The primary working view (tabs + chat panel) |
| `/cases/:id/chat/:conversationId` | `CaseWorkspace` | Yes | None | `AppLayout` | Deep-link into a specific conversation within a case |
| `/knowledge` | `Knowledge` | Yes | None | `AppLayout` | Knowledge base search + firm knowledge tabs |
| `/admin` | `AdminDashboard` | Yes | `admin` | `AppLayout` | Admin overview (usage stats, system health) |
| `/admin/users` | `AdminUsers` | Yes | `admin` | `AppLayout` | User management (invite, deactivate, change role) |
| `/admin/firm` | `AdminFirm` | Yes | `admin` | `AppLayout` | Firm settings (name, billing, API keys display) |
| `*` | `NotFound` | No | None | None (standalone) | 404 page |

### 1.2 Route Guards

**AuthGuard** -- wraps all authenticated routes. Reads `useAuthStore` state. If `user` is null and `token` is null, redirects to `/login`. If `token` exists but `user` is null, attempts silent re-auth via stored token before redirecting.

```
// Pseudocode -- not implementation
function AuthGuard({ children }) {
  const isAuthenticated = useIsAuthenticated();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}
```

**RoleGuard** -- wraps admin routes. Reads `user.role` from `useAuthStore`. If role is not `"admin"`, redirects to `/dashboard` and shows a toast ("You do not have permission to access this page").

```
function RoleGuard({ requiredRole, children }) {
  const user = useAuthStore(s => s.user);
  if (user?.role !== requiredRole) return <Navigate to="/dashboard" replace />;
  return children;
}
```

**LoginRedirectGuard** -- wraps the `/login` route. If user is already authenticated, redirects to `/dashboard`.

### 1.3 Router Configuration

The router uses `react-router-dom` v6 `createBrowserRouter` with the following nesting:

```
<BrowserRouter>
  <Routes>
    {/* Public */}
    <Route path="/login" element={<LoginRedirectGuard><Login /></LoginRedirectGuard>} />

    {/* Authenticated shell */}
    <Route element={<AuthGuard><AppLayout /></AuthGuard>}>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/cases/:id" element={<CaseWorkspace />} />
      <Route path="/cases/:id/chat/:conversationId" element={<CaseWorkspace />} />
      <Route path="/knowledge" element={<Knowledge />} />

      {/* Admin sub-shell */}
      <Route element={<RoleGuard requiredRole="admin" />}>
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/admin/users" element={<AdminUsers />} />
        <Route path="/admin/firm" element={<AdminFirm />} />
      </Route>
    </Route>

    {/* Catch-all */}
    <Route path="*" element={<NotFound />} />
  </Routes>
</BrowserRouter>
```

### 1.4 URL State

The `CaseWorkspace` page reads state from the URL:

- `useParams<{ id: string }>()` -- the active case ID.
- `useParams<{ conversationId?: string }>()` -- optional deep-link to a conversation.
- `useSearchParams` for the active tab: `?tab=documents|chronology|research|drafts|analysis|overview` (defaults to `overview`). Persisted in URL so that browser back/forward navigates between tabs.

---

## 2. Component Architecture

### 2.1 Existing Components (may need modification)

#### `components/common/`

| Component | File | Props | Status |
|---|---|---|---|
| `Button` | `Button.tsx` | `variant: "primary" \| "secondary" \| "danger" \| "ghost"`, `size: "sm" \| "md" \| "lg"`, `isLoading: boolean` | Built. No changes needed. |
| `Input` | `Input.tsx` | `label?: string`, `error?: string`, `icon?: ElementType` | Built. No changes needed. |
| `Badge` | `Badge.tsx` | `variant: "success" \| "warning" \| "danger" \| "info" \| "neutral"` | Built. Add `"accent"` variant (orange) for RevLaw branding on stage badges. |
| `Card` | `Card.tsx` | `title?: string`, `subtitle?: string`, `headerAction?: ReactNode` | Built. No changes needed. |
| `EmptyState` | `EmptyState.tsx` | `icon: ElementType`, `title: string`, `description: string`, `actionLabel?: string`, `onAction?: () => void` | Built. No changes needed. |
| `Loading` | `Loading.tsx` | `fullscreen?: boolean`, `size: "sm" \| "md" \| "lg"`, `text?: string` | Built. No changes needed. |

#### `components/layout/`

| Component | File | Status | Changes Needed |
|---|---|---|---|
| `Layout` | `Layout.tsx` | Built. Currently renders `<Outlet />` with padding. | Rename to `AppLayout`. Add `QueryClientProvider` wrapper. Remove padding for `CaseWorkspace` route (it manages its own full-bleed layout). |
| `Sidebar` | `Sidebar.tsx` | Built. Static navigation links. | Add "Admin" nav item (visible only when `user.role === "admin"`). Update routes to match new route table. Add active case indicator when on `/cases/:id`. |
| `Header` | `Header.tsx` | Built. Shows page title + user dropdown. | Add breadcrumb support for nested pages (e.g., Cases > Wong v Tan). Add notifications dropdown (future). |

#### `components/chat/`

| Component | File | Status | Changes Needed |
|---|---|---|---|
| `ChatView` | `ChatView.tsx` | Built. Standalone conversation list + chat area. | This stays as-is for the standalone `/dashboard` chat view. The `CaseWorkspace` uses `ChatPanel` (below) instead, which is a trimmed version without the conversation sidebar. |
| `ChatArea` | `ChatArea.tsx` | Built. Messages list + input. | Add `caseId` prop for case-scoped conversations. Add context indicator header. Add suggested prompts when empty. |
| `MessageBubble` | `MessageBubble.tsx` | Built. Renders user/assistant messages with markdown, confidence, sources, feedback. | Add agent badge styling (colored dot + agent name). Add copy-to-clipboard button on assistant messages. |
| `ChatInput` | `ChatInput.tsx` | Built. Textarea with send button. | Add suggested prompt chips above the input. Add attachment button (for referencing documents). |
| `SourcesList` | `SourcesList.tsx` | Built. Expandable source list with relevance bars. | No changes needed. |

#### `components/cases/`

| Component | File | Status | Changes Needed |
|---|---|---|---|
| `CaseList` | `CaseList.tsx` | Built. Filterable card grid. | Add priority indicator. Add stage progress badge. Add quick-stat counts (documents, conversations). |
| `CaseForm` | `CaseForm.tsx` | Built. Dialog for create/edit. | Add priority field. Add assigned user selector. |
| `DocumentUpload` | `DocumentUpload.tsx` | Built. Drag-drop upload with progress tracking. | Will be reused inside `CaseWorkspace` documents tab. No changes needed. |

#### `components/knowledge/`

| Component | File | Status | Changes Needed |
|---|---|---|---|
| `SearchPanel` | `SearchPanel.tsx` | Built. Legal research search with filters. | No changes needed. |
| `FirmKnowledgeList` | `FirmKnowledgeList.tsx` | Built. CRUD list with category tabs. | No changes needed. |
| `FirmKnowledgeForm` | `FirmKnowledgeForm.tsx` | Built. Dialog form for adding knowledge. | No changes needed. |

#### Pages

| Page | File | Status | Changes Needed |
|---|---|---|---|
| `Login` | `pages/Login.tsx` | Built. | No changes needed. |
| `Dashboard` | `pages/Dashboard.tsx` | Built. Currently just renders `ChatView`. | Replace with proper dashboard: case list (recent/active), quick stats (open cases, pending documents, recent conversations), and a "New Case" CTA. |
| `Cases` | `pages/Cases.tsx` | Built. Renders `CaseList`. | Remove (folded into `Dashboard`). The `/cases/:id` route goes directly to `CaseWorkspace`. |
| `CaseDetail` | `pages/CaseDetail.tsx` | Built. Tabs: overview, documents, conversations. | Replace entirely with `CaseWorkspace` -- the new primary working view described in section 2.2. |
| `Documents` | `pages/Documents.tsx` | Built. Cross-case document browser. | Keep as utility. Link from sidebar. May rename to "All Documents". |
| `NotFound` | `pages/NotFound.tsx` | Built. | No changes needed. |

### 2.2 New Components to Build

#### `pages/CaseWorkspace.tsx` -- The Core View

This is the most important page in the application. It is a split-pane layout: workspace tabs on the left, AI chat panel on the right. The chat panel is always visible (collapsible on mobile).

**Layout:**

```
+-------------------------------------------------------------------+
| CaseHeader (case title, status, stage bar, actions)               |
+-------------------------------------------------------------------+
| CaseStageBar (horizontal stepper showing litigation progress)     |
+----------------------------------------------+--------------------+
|                                              |                    |
|  Workspace Tabs                              |   Chat Panel       |
|  (Overview | Documents | Chronology |        |   (always visible) |
|   Research | Drafts | Analysis)              |                    |
|                                              |   Context bar:     |
|  [Active tab content fills this area]        |   "5 docs | 24     |
|                                              |    events | 3      |
|                                              |    citations"      |
|                                              |                    |
|                                              |   [Messages]       |
|                                              |                    |
|                                              |   [Suggested       |
|                                              |    prompts]        |
|                                              |                    |
|                                              |   [Chat input]     |
+----------------------------------------------+--------------------+
```

**Props:**

```typescript
// No props -- reads route params
// useParams<{ id: string; conversationId?: string }>()
// useSearchParams for ?tab=...
```

**Behavior:**
- Fetches case data via `useQuery(["case", id])`.
- Maintains active tab in URL search params.
- The chat panel width is stored in `useCaseStore.chatPanelWidth` and is resizable via `ResizablePanel`.
- On mobile (< 768px), the chat panel is a slide-over drawer triggered by a floating button.
- If `conversationId` param is present, auto-selects that conversation in the chat panel.

---

#### Case Header Components

**`components/case-workspace/CaseHeader.tsx`**

```typescript
interface CaseHeaderProps {
  caseData: Case;
  onEdit: () => void;
  onArchive: () => void;
}
```

Renders: case title, client name, status badge, practice area badge, priority badge, "Edit" and "Archive" action buttons. Back arrow navigates to `/dashboard`.

**`components/case-workspace/CaseStageBar.tsx`**

```typescript
interface CaseStageBarProps {
  currentStage: CaseStage;
  stages: StageDefinition[];
  onAdvanceStage?: () => void;
  canAdvance: boolean;
}

type CaseStage =
  | "intake"
  | "document_review"
  | "research"
  | "analysis"
  | "drafting"
  | "review"
  | "filing"
  | "hearing"
  | "resolution"
  | "closed";

interface StageDefinition {
  key: CaseStage;
  label: string;
  description: string;
}
```

Renders a horizontal stepper. Completed stages show a check icon. Current stage is highlighted with blue-600. Future stages are grayed out. On desktop, all stages are visible with labels. On mobile, shows current stage + progress fraction ("Step 4 of 10").

**`components/case-workspace/CaseWorkspaceTabs.tsx`**

```typescript
interface CaseWorkspaceTabsProps {
  activeTab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
  counts: {
    documents: number;
    chronologyEvents: number;
    researchItems: number;
    drafts: number;
  };
}

type WorkspaceTab =
  | "overview"
  | "documents"
  | "chronology"
  | "research"
  | "drafts"
  | "analysis";
```

Renders Radix `Tabs.List` with icons and count badges. Tabs:

| Tab | Icon | Badge |
|---|---|---|
| Overview | `Info` | -- |
| Documents | `FileText` | document count |
| Chronology | `Clock` | event count |
| Research | `Search` | pinned research count |
| Drafts | `PenTool` | draft count |
| Analysis | `BarChart3` | -- |

---

#### Document Components (for Documents tab inside CaseWorkspace)

**`components/case-workspace/documents/DocumentList.tsx`**

```typescript
interface DocumentListProps {
  caseId: string;
  firmId: string;
}
```

One API call: `useQuery(["case-documents", caseId])`. Renders a table/list of documents with sorting (by date, type, OCR status). Includes upload button that opens the existing `DocumentUpload` component. Shows skeleton loader while loading.

**`components/case-workspace/documents/DocumentRow.tsx`**

```typescript
interface DocumentRowProps {
  document: Document;
  caseName?: string;
  onSelect: (doc: Document) => void;
  onDelete: (doc: Document) => void;
}
```

Single row: file icon (by type), filename, file type badge, OCR status badge (with animated spinner for "processing"), upload date, size, actions dropdown (view, download, delete).

**`components/case-workspace/documents/DocumentDetail.tsx`**

```typescript
interface DocumentDetailProps {
  document: Document;
  onClose: () => void;
}
```

Slide-over panel (Radix `Dialog` or custom drawer) showing: document metadata, OCR-extracted text preview (scrollable), related chronology events extracted from this document, action buttons (download original, re-run OCR, delete).

**`components/case-workspace/documents/DocumentOcrStatus.tsx`**

```typescript
interface DocumentOcrStatusProps {
  status: "pending" | "processing" | "completed" | "failed";
  progress?: number;
}
```

Inline status indicator. `pending` = clock icon + "Queued". `processing` = animated spinner + "Processing" + optional progress bar. `completed` = green check + "Processed". `failed` = red X + "Failed" + retry button.

---

#### Chronology Components (for Chronology tab)

**`components/case-workspace/chronology/ChronologyTimeline.tsx`**

```typescript
interface ChronologyTimelineProps {
  caseId: string;
  firmId: string;
}
```

One API call: `useQuery(["case-timeline", caseId])`. Renders a vertical timeline of events. Each event is a `ChronologyEvent` card. Has filter controls (date range, event type, source). Includes "Add Event" button and "Auto-Extract" button.

**`components/case-workspace/chronology/ChronologyEvent.tsx`**

```typescript
interface TimelineEvent {
  id: string;
  case_id: string;
  date: string;
  title: string;
  description: string;
  event_type: "filing" | "hearing" | "correspondence" | "deadline" | "milestone" | "custom";
  source_document_id?: string;
  source_document_name?: string;
  is_auto_extracted: boolean;
  confidence?: number;
  created_at: string;
}

interface ChronologyEventProps {
  event: TimelineEvent;
  onEdit: (event: TimelineEvent) => void;
  onDelete: (eventId: string) => void;
}
```

Renders a single timeline event card. Shows date prominently, event type icon, title, description snippet, source document link (if extracted from a document), confidence badge (if auto-extracted), and edit/delete actions.

**`components/case-workspace/chronology/ChronologyEventForm.tsx`**

```typescript
interface ChronologyEventFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (event: Omit<TimelineEvent, "id" | "case_id" | "created_at" | "is_auto_extracted">) => void;
  initialValues?: TimelineEvent;
  isSubmitting: boolean;
}
```

Radix `Dialog` form. Fields: date (date picker), title, description (textarea), event type (select). Validates that date and title are provided.

**`components/case-workspace/chronology/ChronologyAutoExtract.tsx`**

```typescript
interface ChronologyAutoExtractProps {
  caseId: string;
  firmId: string;
  documentCount: number;
  onComplete: () => void;
}
```

Button + confirmation dialog. Triggers AI extraction of timeline events from all case documents. Shows progress: "Analyzing 12 documents..." with a progress bar. On completion, shows count of extracted events and prompts user to review.

---

#### Research Components (for Research tab)

**`components/case-workspace/research/ResearchSearchBar.tsx`**

```typescript
interface ResearchSearchBarProps {
  onSearch: (query: string, filters: ResearchFilters) => void;
  isSearching: boolean;
  initialQuery?: string;
}

interface ResearchFilters {
  jurisdiction: string;
  court: string;
  yearFrom?: number;
  yearTo?: number;
  includeStatutes: boolean;
  includeCases: boolean;
}
```

Search input with expandable filter row. Jurisdiction selector, court text input, year range, toggles for statutes/cases. Submit triggers the search.

**`components/case-workspace/research/ResearchResultCard.tsx`**

```typescript
interface ResearchResult {
  id: string;
  citation: string;
  case_name: string;
  court: string;
  year: number;
  jurisdiction: string;
  summary: string;
  relevance_score: number;
  is_pinned: boolean;
  treatment_status?: "followed" | "distinguished" | "overruled" | "considered";
}

interface ResearchResultCardProps {
  result: ResearchResult;
  onPin: (resultId: string) => void;
  onUnpin: (resultId: string) => void;
  onCite: (result: ResearchResult) => void;
}
```

Card showing: case name (bold), citation, court + year, relevance score bar, summary (truncated, expandable), treatment status badge (if any), pin button (toggle), "Cite in draft" button. Pinned items show a filled bookmark icon.

**`components/case-workspace/research/ResearchPinnedList.tsx`**

```typescript
interface ResearchPinnedListProps {
  caseId: string;
  firmId: string;
  onUnpin: (resultId: string) => void;
  onCite: (result: ResearchResult) => void;
}
```

One API call: `useQuery(["pinned-research", caseId])`. Renders compact list of pinned research items. Shown in a collapsible section above search results. Each item: citation, case name, relevance score, unpin button.

**`components/case-workspace/research/CitationBadge.tsx`**

```typescript
interface CitationBadgeProps {
  treatment: "followed" | "distinguished" | "overruled" | "considered" | "neutral";
  compact?: boolean;
}
```

Color-coded badge. `followed` = green. `distinguished` = yellow. `overruled` = red with strikethrough icon. `considered` = blue. `neutral` = gray. Compact mode shows only the icon without text.

---

#### Draft Components (for Drafts tab)

**`components/case-workspace/drafts/DraftList.tsx`**

```typescript
interface DraftListProps {
  caseId: string;
  firmId: string;
}
```

One API call: `useQuery(["case-drafts", caseId])`. Grid of `DraftCard` components. "Generate New Draft" button opens `DraftGenerateDialog`.

**`components/case-workspace/drafts/DraftCard.tsx`**

```typescript
interface Draft {
  id: string;
  case_id: string;
  title: string;
  document_type: string;
  template_name?: string;
  status: "generating" | "completed" | "failed";
  content?: string;
  word_count?: number;
  created_at: string;
  updated_at: string;
}

interface DraftCardProps {
  draft: Draft;
  onView: (draft: Draft) => void;
  onDelete: (draftId: string) => void;
  onRegenerate: (draftId: string) => void;
}
```

Card showing: title, document type badge, template name (if used), status (generating shows spinner, completed shows word count, failed shows retry), creation date, action buttons. Click opens `DraftViewer`.

**`components/case-workspace/drafts/DraftGenerateDialog.tsx`**

```typescript
interface DraftGenerateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  caseId: string;
  firmId: string;
  caseData: Case;
  onGenerated: (draft: Draft) => void;
}
```

Multi-step dialog:
1. Select document type (from `TemplateSelector`).
2. Enter instructions / additional context (textarea).
3. Select tone: "formal" | "persuasive" | "neutral".
4. Review and generate.

Shows progress indicator during generation. On success, navigates to the new draft in `DraftViewer`.

**`components/case-workspace/drafts/DraftViewer.tsx`**

```typescript
interface DraftViewerProps {
  draft: Draft;
  onClose: () => void;
  onRegenerate: () => void;
}
```

Full-screen overlay or large panel. Renders draft content as formatted markdown. Toolbar: copy, download as DOCX (future), regenerate, edit title. Read-only view of the AI-generated content.

**`components/case-workspace/drafts/TemplateSelector.tsx`**

```typescript
interface TemplateSelectorProps {
  caseType: string;
  practiceArea: PracticeArea;
  onSelect: (template: SOPTemplate) => void;
  selectedTemplate?: SOPTemplate;
}
```

Fetches templates via `useQuery(["templates", practiceArea])`. Renders a grid of template cards. Each shows: template name, description, usage stats (if available), practice area badge. Selecting a template auto-fills the document type in the generate dialog.

---

#### Analysis Components (for Analysis tab)

**`components/case-workspace/analysis/AnalysisPanel.tsx`**

```typescript
interface AnalysisPanelProps {
  caseId: string;
  firmId: string;
  caseData: Case;
}
```

Container that orchestrates the analysis tab. Has two sub-sections: IRAC Analysis and Risk Assessment. Each is a separate component with its own API call. "Run Analysis" button triggers both.

**`components/case-workspace/analysis/IracAnalysis.tsx`**

```typescript
interface IracData {
  issue: string;
  rule: string;
  application: string;
  conclusion: string;
  confidence: number;
  sources: Source[];
}

interface IracAnalysisProps {
  caseId: string;
  firmId: string;
}
```

One API call: `useQuery(["case-irac", caseId])`. Renders the IRAC framework in four clearly labeled sections (Issue, Rule, Application, Conclusion). Each section shows AI-generated content with confidence score and cited sources. Empty state prompts user to run analysis.

**`components/case-workspace/analysis/RiskAssessment.tsx`**

```typescript
interface RiskItem {
  id: string;
  category: "legal" | "procedural" | "factual" | "strategic";
  severity: "high" | "medium" | "low";
  title: string;
  description: string;
  mitigation: string;
  confidence: number;
}

interface RiskAssessmentProps {
  caseId: string;
  firmId: string;
}
```

One API call: `useQuery(["case-risks", caseId])`. Renders a categorized list of risk items. Each risk: severity badge (red/yellow/green), category tag, title, expandable description + mitigation strategy. Summary at top: "3 High, 5 Medium, 2 Low risks identified".

---

#### Chat Panel (for CaseWorkspace)

**`components/case-workspace/ChatPanel.tsx`**

```typescript
interface ChatPanelProps {
  caseId: string;
  firmId: string;
  conversationId?: string;
  caseData: Case;
  contextCounts: {
    documents: number;
    events: number;
    citations: number;
  };
}
```

Differs from the standalone `ChatView` in that:
1. It does NOT have a conversation sidebar -- it shows a single conversation scoped to the current case.
2. It has a context indicator bar at the top: "5 docs | 24 events | 3 citations".
3. It has stage-aware suggested prompts when the conversation is empty.
4. It passes `case_context` with every message (case ID, current stage, document count, etc.) so the backend can provide contextual responses.

**Context indicator format:**
```
[ FileText icon ] 5 docs  |  [ Clock icon ] 24 events  |  [ BookOpen icon ] 3 citations
```

---

#### Utility Components (new common components)

**`components/common/ResizablePanel.tsx`**

```typescript
interface ResizablePanelProps {
  direction: "horizontal" | "vertical";
  defaultSize: number;       // percentage (0-100)
  minSize: number;           // percentage
  maxSize: number;           // percentage
  onResize?: (size: number) => void;
  left: ReactNode;
  right: ReactNode;
  collapsible?: "left" | "right" | "none";
}
```

Implements a split-pane with a draggable divider. Used in `CaseWorkspace` to split the workspace tabs (left) from the chat panel (right). The divider is a 4px wide handle that shows a grip indicator on hover. Stores size in `useCaseStore.chatPanelWidth`.

Behavior:
- Default split: 60% workspace / 40% chat.
- Min workspace: 30%. Min chat: 25%.
- Double-click divider to reset to default.
- On mobile, collapses to full-width with a toggle.

**`components/common/ProgressStepper.tsx`**

```typescript
interface Step {
  key: string;
  label: string;
  description?: string;
}

interface ProgressStepperProps {
  steps: Step[];
  currentStep: string;
  completedSteps: string[];
  orientation: "horizontal" | "vertical";
  size?: "sm" | "md";
}
```

Reusable stepper component. Used by `CaseStageBar`. Each step shows: step number (or check icon if completed), label, optional description. Connected by lines. Current step is highlighted. Completed steps are green. Future steps are gray.

**`components/common/FileDropzone.tsx`**

```typescript
interface FileDropzoneProps {
  onFiles: (files: File[]) => void;
  accept?: string;                  // MIME types or extensions
  maxFiles?: number;
  maxSizeMB?: number;
  disabled?: boolean;
  children?: ReactNode;             // custom content inside the dropzone
}
```

Reusable drag-and-drop file zone. Renders a dashed border area. On drag-over, changes border color to blue and shows "Drop files here". Validates file count and size before calling `onFiles`. Used by `DocumentUpload` and potentially by other upload flows.

**`components/common/Skeleton.tsx`**

```typescript
interface SkeletonProps {
  className?: string;                // for sizing via Tailwind
  variant?: "text" | "circular" | "rectangular";
  lines?: number;                    // for text variant, how many lines
}
```

Animated placeholder. Uses `animate-pulse` with gray-200 background. Text variant renders multiple lines of varying width to simulate text. Used in every data-fetching component's loading state.

**`components/common/ConfirmDialog.tsx`**

```typescript
interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;             // default: "Confirm"
  cancelLabel?: string;              // default: "Cancel"
  variant?: "danger" | "default";    // danger = red confirm button
  onConfirm: () => void;
  isLoading?: boolean;
}
```

Radix `Dialog` for confirmation prompts. Used for delete operations, archive, and other destructive actions.

---

#### Admin Components

**`pages/AdminDashboard.tsx`**

Overview page. Cards showing: total users, active cases (this month), total documents processed, AI queries (this month). Line chart for daily query volume (future). Quick links to user management and firm settings.

**`pages/AdminUsers.tsx`**

Table of firm users. Columns: name, email, role, status (active/deactivated), last login, actions. Actions: change role (dropdown), deactivate/reactivate (confirm dialog), resend invite. "Invite User" button opens a form dialog (email + role).

**`pages/AdminFirm.tsx`**

Form page. Sections: Firm Name, Firm Domain, Contact Email, Billing Status (read-only display of plan tier), Knowledge Base Settings (quality threshold, max iterations), API Configuration (display obfuscated API key, regenerate button).

---

## 3. Type System

### 3.1 Existing Types (in `types/`)

These are already defined and match the backend schema:

- `types/auth.ts`: `User`, `LoginRequest`, `LoginResponse`, `AuthState`
- `types/case.ts`: `Case`, `Document`, `PracticeArea`, `CaseStatus`, `FileType`
- `types/chat.ts`: `Conversation`, `Message`, `Source`, `QualityWarning`, `RAGFeedback`
- `types/knowledge.ts`: `KnowledgeEntry`, `CitationEdge`, `Judge`, `LegislationRef`, `SOPTemplate`, `FirmKnowledge`
- `types/common.ts`: `PaginatedResponse<T>`, `ApiError`, re-exports

### 3.2 New Types to Add

**`types/case.ts` additions:**

```typescript
export type CaseStage =
  | "intake"
  | "document_review"
  | "research"
  | "analysis"
  | "drafting"
  | "review"
  | "filing"
  | "hearing"
  | "resolution"
  | "closed";

export type CasePriority = "low" | "normal" | "high" | "urgent";

// Extend the existing Case interface
export interface Case {
  // ... existing fields ...
  stage: CaseStage;
  priority: CasePriority;
}

export interface StageHistoryEntry {
  id: string;
  case_id: string;
  from_stage: CaseStage;
  to_stage: CaseStage;
  changed_by_id: string;
  reason?: string;
  created_at: string;
}
```

**`types/timeline.ts` (new file):**

```typescript
export type TimelineEventType =
  | "filing"
  | "hearing"
  | "correspondence"
  | "deadline"
  | "milestone"
  | "custom";

export interface TimelineEvent {
  id: string;
  case_id: string;
  firm_id: string;
  date: string;
  title: string;
  description: string;
  event_type: TimelineEventType;
  source_document_id?: string;
  source_document_name?: string;
  is_auto_extracted: boolean;
  confidence?: number;
  created_by_id: string;
  created_at: string;
  updated_at: string;
}

export interface TimelineExtractionResult {
  events_extracted: number;
  events: TimelineEvent[];
  documents_processed: number;
}
```

**`types/research.ts` (new file):**

```typescript
export type TreatmentStatus =
  | "followed"
  | "distinguished"
  | "overruled"
  | "considered"
  | "neutral";

export interface ResearchResult {
  id: string;
  citation: string;
  case_name: string;
  court: string;
  year: number;
  jurisdiction: string;
  summary: string;
  relevance_score: number;
  treatment_status?: TreatmentStatus;
}

export interface PinnedResearch {
  id: string;
  case_id: string;
  firm_id: string;
  research_result: ResearchResult;
  pinned_by_id: string;
  notes?: string;
  created_at: string;
}
```

**`types/draft.ts` (new file):**

```typescript
export type DraftStatus = "generating" | "completed" | "failed";

export interface Draft {
  id: string;
  case_id: string;
  firm_id: string;
  title: string;
  document_type: string;
  template_name?: string;
  status: DraftStatus;
  content?: string;
  word_count?: number;
  instructions: string;
  tone: "formal" | "persuasive" | "neutral";
  created_by_id: string;
  created_at: string;
  updated_at: string;
}

export interface DraftGenerateRequest {
  case_id: string;
  firm_id: string;
  document_type: string;
  template_name?: string;
  instructions: string;
  tone: "formal" | "persuasive" | "neutral";
}
```

**`types/analysis.ts` (new file):**

```typescript
export interface IracAnalysis {
  id: string;
  case_id: string;
  issue: string;
  rule: string;
  application: string;
  conclusion: string;
  confidence: number;
  sources: import("./chat").Source[];
  created_at: string;
}

export interface RiskItem {
  id: string;
  category: "legal" | "procedural" | "factual" | "strategic";
  severity: "high" | "medium" | "low";
  title: string;
  description: string;
  mitigation: string;
  confidence: number;
}

export interface CaseAnalysis {
  id: string;
  case_id: string;
  irac: IracAnalysis;
  risks: RiskItem[];
  overall_assessment: string;
  created_at: string;
  updated_at: string;
}
```

**`types/admin.ts` (new file):**

```typescript
export interface FirmSettings {
  id: string;
  name: string;
  domain: string;
  contact_email: string;
  plan_tier: "starter" | "professional" | "enterprise";
  quality_threshold: number;
  max_iterations: number;
  created_at: string;
}

export interface UserInvite {
  email: string;
  role: import("./auth").User["role"];
}

export interface UsageStats {
  total_users: number;
  active_cases: number;
  documents_processed: number;
  ai_queries_this_month: number;
  storage_used_mb: number;
}
```

---

## 4. State Management

### 4.1 State Management Decision Table

| Use Case | Solution | Rationale |
|---|---|---|
| Server data (cases, documents, messages, etc.) | React Query v5 | Handles caching, deduplication, background refetching, optimistic updates |
| Auth state (user, token) | Zustand `authStore` (persisted to sessionStorage) | Survives page refresh, needed synchronously by axios interceptor |
| Case workspace UI state | Zustand `caseStore` (not persisted) | Active tab, chat panel width, stage -- shared across sibling components |
| Chat transient state | Zustand `chatStore` (not persisted) | Active conversation, processing flag, optimistic messages |
| Global UI state | Zustand `uiStore` (not persisted) | Sidebar, theme, toasts |
| Form state | Component-local `useState` | Forms are ephemeral, no need for global state |
| URL state (active tab, filters) | `useSearchParams` | Back/forward navigation, shareable URLs |

### 4.2 Existing Stores

**`stores/authStore.ts`** (built, no changes needed)

```typescript
interface AuthStore {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  initializeAuth: () => void;
  clearError: () => void;
}
```

Persisted to `sessionStorage` via Zustand `persist` middleware (only `user` and `token` are persisted).

**`stores/chatStore.ts`** (built, minor additions needed)

```typescript
interface ChatStore {
  conversations: Map<string, Conversation>;
  activeConversationId: string | null;
  messages: Map<string, Message[]>;
  isProcessing: boolean;
  setActiveConversation: (id: string | null) => void;
  addConversation: (conversation: Conversation) => void;
  addMessage: (conversationId: string, message: Message) => void;
  setProcessing: (processing: boolean) => void;
  clearMessages: (conversationId: string) => void;
}
```

Additions needed:
- `addOptimisticMessage(conversationId: string, content: string): string` -- adds a temporary user message with a client-generated ID, returns the temp ID.
- `replaceOptimisticMessage(tempId: string, realMessage: Message): void` -- replaces the optimistic message with the server response.
- `removeOptimisticMessage(conversationId: string, tempId: string): void` -- removes a failed optimistic message.

**`stores/uiStore.ts`** (built, additions needed)

```typescript
interface UIStore {
  sidebarOpen: boolean;
  theme: "light" | "dark";
  toasts: Toast[];
  toggleSidebar: () => void;
  setTheme: (theme: "light" | "dark") => void;
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}
```

Additions needed:
- `isMobile: boolean` -- set by a resize observer in `AppLayout`, true when viewport < 768px.
- `setIsMobile: (isMobile: boolean) => void`.

### 4.3 New Stores

**`stores/caseStore.ts`** (new)

```typescript
interface CaseStore {
  // Active workspace state
  activeCaseId: string | null;
  activeTab: WorkspaceTab;
  chatPanelWidth: number;          // percentage (25-75), default 40
  chatPanelCollapsed: boolean;

  // Actions
  setActiveCaseId: (id: string | null) => void;
  setActiveTab: (tab: WorkspaceTab) => void;
  setChatPanelWidth: (width: number) => void;
  toggleChatPanel: () => void;
}

type WorkspaceTab =
  | "overview"
  | "documents"
  | "chronology"
  | "research"
  | "drafts"
  | "analysis";
```

Not persisted. Resets when navigating away from a case. The `activeTab` value is kept in sync with `?tab=` URL param (URL is the source of truth; the store mirrors it for convenience).

---

## 5. API Service Layer

### 5.1 Base Client (existing)

**`services/api.ts`** (built)

- `axios.create` with `baseURL` from `VITE_API_BASE_URL` (defaults to `/api`).
- Request interceptor: attaches `Authorization: Bearer <token>` from `sessionStorage`.
- Response interceptor: on 401, clears storage and redirects to `/login`. On 429, returns user-friendly error. Extracts server error messages.
- `nexusCall<T>(handler, params)` -- generic RPC-style call to the `/nexus` endpoint.
- `apiClient` export for direct REST calls (used by file upload).

### 5.2 Existing Services

**`services/auth.service.ts`** (built, no changes)

| Function | Signature | Description |
|---|---|---|
| `login` | `(email, password) => Promise<LoginResponse>` | POST `/auth/login` |
| `logout` | `() => void` | Clears sessionStorage, redirects to `/login` |
| `getStoredToken` | `() => string \| null` | Reads token from sessionStorage |
| `getStoredUser` | `() => User \| null` | Reads + parses user from sessionStorage |
| `storeAuth` | `(token, user) => void` | Writes token + user to sessionStorage |
| `refreshToken` | `() => Promise<string>` | POST `/auth/refresh` |

**`services/case.service.ts`** (built, additions needed)

| Function | Signature | Nexus Handler | Status |
|---|---|---|---|
| `createCase` | `(firm_id, created_by_id, title, ...) => Promise<Case>` | `create_case` | Built |
| `getCase` | `(case_id, firm_id) => Promise<Case>` | `get_case` | Built |
| `listCases` | `(firm_id, status?, practice_area?, ...) => Promise<PaginatedResponse<Case>>` | `list_cases` | Built |
| `updateCase` | `(case_id, firm_id, fields) => Promise<Case>` | `update_case` | Built |
| `uploadDocument` | `(case_id, firm_id, ...) => Promise<Document>` | `upload_document` | Built |
| `getDocument` | `(document_id, firm_id) => Promise<Document>` | `get_document` | Built |
| `listDocuments` | `(case_id, firm_id, ...) => Promise<PaginatedResponse<Document>>` | `list_documents` | Built |
| `advanceStage` | `(case_id, firm_id, to_stage, reason?) => Promise<Case>` | `advance_case_stage` | **NEW** |
| `getStageHistory` | `(case_id, firm_id) => Promise<StageHistoryEntry[]>` | `get_stage_history` | **NEW** |

**`services/chat.service.ts`** (built, no changes)

| Function | Nexus Handler | Status |
|---|---|---|
| `createConversation` | `create_conversation` | Built |
| `sendMessage` | `send_message` | Built |
| `getConversationHistory` | `get_conversation_history` | Built |
| `searchConversations` | `search_conversations` | Built |
| `submitFeedback` | `submit_feedback` | Built |
| `closeConversation` | `close_conversation` | Built |
| `draftDocument` | `draft_document` | Built |

**`services/knowledge.service.ts`** (built, no changes)

| Function | Nexus Handler | Status |
|---|---|---|
| `searchCases` | `search_cases` | Built |
| `getCitations` | `get_citations` | Built |
| `getJudgeProfile` | `get_judge_profile` | Built |
| `searchLegislation` | `search_legislation` | Built |
| `legalResearch` | `legal_research` | Built |
| `getSOPTemplate` | `get_sop_template` | Built |
| `listSOPTemplates` | `list_sop_templates` | Built |
| `getSOPUsageStats` | `get_sop_usage_stats` | Built |

**`services/firm-knowledge.service.ts`** (built, no changes)

| Function | Nexus Handler | Status |
|---|---|---|
| `createFirmKnowledge` | `create_firm_knowledge` | Built |
| `listFirmKnowledge` | `list_firm_knowledge` | Built |
| `getFirmKnowledge` | `get_firm_knowledge` | Built |
| `deleteFirmKnowledge` | `delete_firm_knowledge` | Built |

### 5.3 New Services

**`services/document.service.ts`** (new)

Handles presigned URL upload flow (for large files) and document management.

| Function | Signature | Nexus Handler | Description |
|---|---|---|---|
| `getUploadUrl` | `(case_id, firm_id, filename, content_type) => Promise<{ upload_url: string; document_id: string }>` | `get_upload_url` | Gets a presigned S3 URL for direct upload |
| `confirmUpload` | `(document_id, firm_id) => Promise<Document>` | `confirm_upload` | Confirms upload completed, triggers OCR |
| `getDownloadUrl` | `(document_id, firm_id) => Promise<{ download_url: string }>` | `get_download_url` | Gets a presigned URL for downloading |
| `deleteDocument` | `(document_id, firm_id) => Promise<{ success: boolean }>` | `delete_document` | Deletes a document |
| `rerunOcr` | `(document_id, firm_id) => Promise<Document>` | `rerun_ocr` | Re-triggers OCR processing |
| `getOcrStatus` | `(document_id, firm_id) => Promise<{ status: string; progress?: number }>` | `get_ocr_status` | Polls OCR progress |

**`services/timeline.service.ts`** (new)

| Function | Signature | Nexus Handler | Description |
|---|---|---|---|
| `getTimeline` | `(case_id, firm_id) => Promise<TimelineEvent[]>` | `get_timeline` | Fetches all timeline events for a case |
| `addEvent` | `(case_id, firm_id, event) => Promise<TimelineEvent>` | `add_timeline_event` | Manually adds a timeline event |
| `updateEvent` | `(event_id, firm_id, fields) => Promise<TimelineEvent>` | `update_timeline_event` | Updates a timeline event |
| `deleteEvent` | `(event_id, firm_id) => Promise<{ success: boolean }>` | `delete_timeline_event` | Deletes a timeline event |
| `extractTimeline` | `(case_id, firm_id) => Promise<TimelineExtractionResult>` | `extract_timeline` | Triggers AI extraction from documents |

**`services/research.service.ts`** (new)

| Function | Signature | Nexus Handler | Description |
|---|---|---|---|
| `searchCaseLaw` | `(query, filters) => Promise<PaginatedResponse<ResearchResult>>` | `search_case_law` | Searches case law with filters |
| `pinResearch` | `(case_id, firm_id, result_id) => Promise<PinnedResearch>` | `pin_research` | Pins a research result to a case |
| `unpinResearch` | `(pin_id, firm_id) => Promise<{ success: boolean }>` | `unpin_research` | Unpins a research result |
| `getPinnedResearch` | `(case_id, firm_id) => Promise<PinnedResearch[]>` | `get_pinned_research` | Gets all pinned research for a case |

**`services/draft.service.ts`** (new)

| Function | Signature | Nexus Handler | Description |
|---|---|---|---|
| `generateDraft` | `(request: DraftGenerateRequest) => Promise<Draft>` | `generate_draft` | Triggers AI draft generation |
| `getDrafts` | `(case_id, firm_id) => Promise<Draft[]>` | `get_drafts` | Lists all drafts for a case |
| `getDraft` | `(draft_id, firm_id) => Promise<Draft>` | `get_draft` | Gets a single draft with content |
| `deleteDraft` | `(draft_id, firm_id) => Promise<{ success: boolean }>` | `delete_draft` | Deletes a draft |
| `getStageTemplates` | `(case_type, practice_area) => Promise<SOPTemplate[]>` | `get_stage_templates` | Gets available templates for the case type |

**`services/analysis.service.ts`** (new)

| Function | Signature | Nexus Handler | Description |
|---|---|---|---|
| `runAnalysis` | `(case_id, firm_id) => Promise<CaseAnalysis>` | `run_analysis` | Triggers comprehensive case analysis |
| `getAnalysis` | `(case_id, firm_id) => Promise<CaseAnalysis \| null>` | `get_analysis` | Gets the latest analysis for a case |
| `runIrac` | `(case_id, firm_id) => Promise<IracAnalysis>` | `run_irac_analysis` | Triggers IRAC analysis only |
| `runRiskAssessment` | `(case_id, firm_id) => Promise<RiskItem[]>` | `run_risk_assessment` | Triggers risk assessment only |

**`services/admin.service.ts`** (new)

| Function | Signature | Nexus Handler | Description |
|---|---|---|---|
| `getUsageStats` | `(firm_id) => Promise<UsageStats>` | `get_usage_stats` | Firm usage statistics |
| `listUsers` | `(firm_id) => Promise<User[]>` | `list_users` | All users in the firm |
| `inviteUser` | `(firm_id, email, role) => Promise<User>` | `invite_user` | Sends an invite email |
| `updateUserRole` | `(user_id, firm_id, role) => Promise<User>` | `update_user_role` | Changes a user's role |
| `deactivateUser` | `(user_id, firm_id) => Promise<User>` | `deactivate_user` | Deactivates a user |
| `reactivateUser` | `(user_id, firm_id) => Promise<User>` | `reactivate_user` | Reactivates a user |
| `getFirmSettings` | `(firm_id) => Promise<FirmSettings>` | `get_firm_settings` | Gets firm configuration |
| `updateFirmSettings` | `(firm_id, settings) => Promise<FirmSettings>` | `update_firm_settings` | Updates firm configuration |

---

## 6. Design System

### 6.1 Color Palette

```
Brand / Accent:       #FF6B35 (RevLaw orange) -- used SPARINGLY: stage bar accent, logo mark, CTA hover states ONLY
Primary:              #2563EB (blue-600) -- buttons, links, active states, focus rings
Primary Hover:        #1D4ED8 (blue-700)
Primary Active:       #1E40AF (blue-800)

Sidebar Background:   #0F172A (slate-900)
Sidebar Border:       #1E293B (slate-800)
Sidebar Text:         #CBD5E1 (slate-300)
Sidebar Active:       #2563EB/20 background, #60A5FA text (blue-400)

Page Background:      #F9FAFB (gray-50)
Card Background:      #FFFFFF (white)
Card Border:          #E5E7EB (gray-200)

Text Primary:         #111827 (gray-900)
Text Secondary:       #6B7280 (gray-500)
Text Tertiary:        #9CA3AF (gray-400)

Success:              #059669 (green-600) / bg #ECFDF5 (green-50)
Warning:              #D97706 (yellow-600) / bg #FFFBEB (yellow-50)
Danger/Error:         #DC2626 (red-600) / bg #FEF2F2 (red-50)
Info:                 #2563EB (blue-600) / bg #EFF6FF (blue-50)
```

### 6.2 Typography

```
Font Family:          Inter (system fallback: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif)
Font Import:          Via Google Fonts in index.html or @fontsource/inter

Body Text:            14px / 1.5 line-height (text-sm leading-relaxed)
Caption:              12px / 1.4 (text-xs)
Small Label:          11px / 1.3 (text-[11px])
H1 (Page Title):      20px / 1.3 font-bold (text-xl)
H2 (Section Title):   16px / 1.4 font-semibold (text-base)
H3 (Card Title):      14px / 1.4 font-semibold (text-sm)

Monospace (code):     "JetBrains Mono", "Fira Code", ui-monospace, monospace
```

### 6.3 Spacing and Density

This is a professional legal-tech application. Density is higher than typical consumer apps, but not cramped.

```
Page padding:         px-4 py-6 sm:px-6 lg:px-8 (16/24/32px horizontal)
Card padding:         px-6 py-4 (24px horizontal, 16px vertical)
Card gap (grid):      gap-4 (16px) on desktop, gap-3 (12px) on mobile
Section gap:          space-y-6 (24px)
Form field gap:       space-y-4 (16px)
Inline element gap:   gap-2 (8px) or gap-3 (12px)
Button padding:       sm: px-3 py-1.5 | md: px-4 py-2 | lg: px-6 py-2.5
Badge padding:        px-2 py-0.5
```

### 6.4 Border Radius

```
Buttons:              rounded-lg (8px)
Cards:                rounded-xl (12px)
Dialogs:              rounded-2xl (16px)
Badges:               rounded-full
Inputs:               rounded-lg (8px)
Avatars:              rounded-full
Chat bubbles:         rounded-2xl with one corner rounded-md (message tail)
```

### 6.5 Shadows

```
Cards:                shadow-sm (subtle)
Dropdowns:            shadow-lg
Dialogs:              shadow-xl
Hover cards:          shadow-sm (added on hover via transition)
```

### 6.6 Animations

```
Transitions:          duration-150 (fast) for buttons, inputs
                      duration-200 (medium) for sidebars, panels
                      duration-300 (slow) for page transitions (if added)
Skeleton pulse:       animate-pulse
Spinner:              animate-spin on Loader2 icon
Dialog enter:         animate-in fade-in-0 zoom-in-95
Toast enter:          animate-in slide-in-from-top-full
```

### 6.7 Absolute Prohibitions

The following visual patterns are banned from this codebase:

- Purple or violet gradients
- Neon / glowing effects
- Glassmorphism (frosted glass / heavy backdrop-blur on cards)
- Gradient text
- Floating 3D elements or parallax
- Emoji in UI labels or headings
- Rounded-full buttons (except icon-only)
- Background patterns or textures
- Auto-playing animations (except spinners for loading states)

---

## 7. Key Interaction Patterns

### 7.1 Chat Panel Behavior (CaseWorkspace)

The chat panel is the AI interaction surface. It is always visible in the case workspace (except on mobile where it is a drawer).

**Context passing:** Every message sent from the chat panel includes a `case_context` object:

```typescript
interface CaseContext {
  case_id: string;
  firm_id: string;
  current_stage: CaseStage;
  practice_area: PracticeArea;
  document_count: number;
  timeline_event_count: number;
  pinned_research_count: number;
  active_tab: WorkspaceTab;       // so the AI knows what the user is looking at
}
```

**Suggested prompts:** When the conversation is empty, the chat panel shows stage-aware suggested prompts:

| Stage | Suggested Prompts |
|---|---|
| `intake` | "Summarise the key facts of this case", "What practice area does this case fall under?", "What are the immediate next steps?" |
| `document_review` | "What are the key documents I should review first?", "Extract a timeline from the uploaded documents", "Flag any missing documents" |
| `research` | "Find relevant Singapore case law for this matter", "What are the leading authorities on [topic]?", "Compare this case to [citation]" |
| `analysis` | "Run an IRAC analysis on this case", "What are the main legal risks?", "What are the strengths and weaknesses of our position?" |
| `drafting` | "Draft a letter of demand", "Prepare submissions for [court]", "Draft an affidavit based on the facts" |
| `review` | "Review this draft for legal accuracy", "Check all citations are current", "Suggest improvements to the argument structure" |
| `filing` | "Generate a filing checklist", "What are the court filing requirements?", "Calculate the filing deadline" |
| Default | "How can I help with this case?", "Summarise the current case status", "What should I work on next?" |

Prompts are rendered as clickable chips below the empty state icon. Clicking a chip populates the input and auto-sends.

### 7.2 AI Response Display

Every AI assistant message includes:

1. **Agent badge** -- a small colored dot + agent name (e.g., "Research Agent", "Drafting Agent"). Color is deterministic based on agent name hash.
2. **Confidence score** -- badge below the message. Green (>= 80%), Yellow (50-79%), Red (< 50%).
3. **Sources** -- expandable list (already built in `SourcesList`). Shows citation, case name, court, relevance bar, treatment warning.
4. **Feedback buttons** -- thumbs up / thumbs down (already built). After clicking, the selected thumb fills with color and both are disabled.
5. **Copy button** -- appears on hover. Copies the message content as plain text.
6. **Timestamp** -- relative time ("2m ago", "1h ago").

### 7.3 Optimistic Updates

**Messages:** When the user sends a message, immediately add a local "pending" user message to the message list (with a temporary ID). When the server responds, replace the temporary message with the real one and append the assistant response. If the send fails, mark the user message with an error state and show a retry button.

**Uploads:** When a file is dropped, immediately add it to the upload list with a progress bar. The upload progress is tracked via axios `onUploadProgress`. On success, invalidate the documents query. On failure, show an error badge with a retry button.

**Pins:** When the user pins a research result, immediately toggle the pin icon to filled. If the server call fails, revert the icon and show a toast.

### 7.4 Context Indicator

The context indicator bar at the top of the chat panel shows the current case context:

```
[ FileText ] 5 docs  |  [ Clock ] 24 events  |  [ BookOpen ] 3 citations
```

Each segment is clickable and navigates to the corresponding tab. The counts are fetched from the case data and related queries. When a count changes (e.g., a new document is uploaded), the count animates briefly (number scales up then settles).

### 7.5 Feedback Flow

1. User clicks thumbs up or thumbs down on an assistant message.
2. The button immediately fills with color (green for up, red for down). Both buttons become disabled.
3. A `submitFeedback` call fires in the background (fire-and-forget; failure is silent but logged).
4. If thumbs down: after a 500ms delay, a small inline form slides down asking "What went wrong?" with options: "Inaccurate", "Not relevant", "Too vague", "Other" + free text. Submitting this sends an additional feedback payload.

### 7.6 Stage Advancement

The stage bar shows a "Next Stage" button (only if `canAdvance` is true, which is determined by the backend based on completion criteria). Clicking it opens a confirmation dialog:

```
Advance to [Next Stage Name]?

Current stage: Document Review
Next stage: Research

Reason (optional): [text input]

[Cancel] [Advance]
```

On confirmation, calls `advanceStage`. On success, the stage bar animates the transition (current step fills green, next step becomes active with blue highlight), and the suggested prompts update to match the new stage.

---

## 8. Performance and Loading

### 8.1 Loading States

Every component that fetches data renders a Skeleton loader during `isPending`. Specific skeletons by component:

| Component | Skeleton Shape |
|---|---|
| Case list | 4 card-shaped rectangles (title line + 2 badge lines + date line) |
| Document list | 5 row-shaped rectangles (icon + filename + 2 badges) |
| Timeline | 3 timeline event cards (date circle + title line + description lines) |
| Chat messages | 3 alternating left/right bubble shapes |
| Research results | 4 card-shaped rectangles (title + citation + relevance bar) |
| Draft list | 3 card shapes (title + type badge + date) |
| Analysis | 4 section blocks (IRAC sections) |
| Admin stats | 4 stat cards (number + label) |

### 8.2 Lazy Loading

Heavy components are lazy-loaded to keep the initial bundle small:

```typescript
const CaseWorkspace = React.lazy(() => import("@/pages/CaseWorkspace"));
const Knowledge = React.lazy(() => import("@/pages/Knowledge"));
const AdminDashboard = React.lazy(() => import("@/pages/AdminDashboard"));
const AdminUsers = React.lazy(() => import("@/pages/AdminUsers"));
const AdminFirm = React.lazy(() => import("@/pages/AdminFirm"));
```

Each lazy route is wrapped in `<Suspense fallback={<Loading fullscreen />}>`.

### 8.3 React Query Configuration

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,         // 30 seconds -- data is "fresh" for 30s
      gcTime: 5 * 60_000,        // 5 minutes -- unused cache lives 5min
      retry: 2,                  // retry failed queries twice
      refetchOnWindowFocus: true, // refetch when user returns to tab
    },
    mutations: {
      retry: 0,                  // do not retry mutations
    },
  },
});
```

### 8.4 Query Key Convention

All query keys follow this pattern: `[entity, ...identifiers, ...filters]`

```
["cases", firmId]
["case", caseId, firmId]
["case-documents", caseId, firmId]
["case-timeline", caseId, firmId]
["case-drafts", caseId, firmId]
["case-analysis", caseId, firmId]
["case-irac", caseId, firmId]
["case-risks", caseId, firmId]
["pinned-research", caseId, firmId]
["conversations", firmId]
["messages", conversationId]
["firm-knowledge", firmId]
["templates", practiceArea]
["admin-users", firmId]
["admin-stats", firmId]
["admin-settings", firmId]
```

### 8.5 Prefetching

When the user hovers over a case card in the dashboard for more than 200ms, prefetch the case detail:

```typescript
queryClient.prefetchQuery({
  queryKey: ["case", caseId, firmId],
  queryFn: () => caseService.getCase(caseId, firmId),
});
```

Similarly, when the user navigates to a case workspace, prefetch the documents, timeline, and pinned research in parallel (these are likely to be needed regardless of which tab is active).

---

## 9. Error Handling

### 9.1 Error Levels

| Level | Display | Example |
|---|---|---|
| **Page-level** | Full-page error with retry button | Failed to load case (network down) |
| **Section-level** | Inline error message with retry | Failed to load documents within a working case page |
| **Action-level** | Toast notification | Failed to pin research result |
| **Field-level** | Inline below the field | "Case title is required" |

### 9.2 Error Boundary

A React error boundary wraps the `<Outlet />` in `AppLayout`. It catches rendering errors and shows a full-page error state with:
- "Something went wrong" message.
- "Try Again" button (reloads the page).
- "Go to Dashboard" link.

### 9.3 Network Error Handling

The axios interceptor in `api.ts` already handles:
- **401** -- clears auth, redirects to login.
- **429** -- returns "Too many requests. Please wait a moment and try again."
- **No response** -- returns "Unable to connect to the server."
- **Server error message** -- extracts and forwards.

Additional patterns for new services:
- **403** -- "You do not have permission to perform this action." (for admin routes)
- **404** -- "The requested resource was not found." (for deleted cases/documents)
- **500** -- "An unexpected error occurred. Please try again."

### 9.4 Toast Notifications

Toasts are used for ephemeral feedback. They auto-dismiss after 5 seconds (already implemented in `uiStore`).

| Variant | Color | Use Case |
|---|---|---|
| `success` | Green | "Document uploaded", "Case created", "Draft generated" |
| `error` | Red | "Failed to delete document", "Upload failed" |
| `warning` | Yellow | "OCR processing is taking longer than expected" |
| `default` | Gray | "Link copied to clipboard" |

---

## 10. Responsive Breakpoints

Following Tailwind's default breakpoints:

| Breakpoint | Width | Behavior |
|---|---|---|
| Mobile | < 640px (default) | Single-column layout. Sidebar is a drawer. Chat panel is a full-screen drawer. Tabs are scrollable. Stage bar shows compact view. |
| Small tablet | >= 640px (`sm:`) | Sidebar still drawer. Two-column grids where appropriate. |
| Tablet | >= 768px (`md:`) | Two-column grids. Chat panel visible as split pane (narrower). |
| Desktop | >= 1024px (`lg:`) | Sidebar always visible (static). Chat panel at full configured width. |
| Wide | >= 1280px (`xl:`) | Max content width applied. More spacing. |

### 10.1 CaseWorkspace Responsive Behavior

**Desktop (>= 1024px):**
- Split pane: workspace tabs (60%) + chat panel (40%), resizable.
- Stage bar shows all stages with labels.
- Tabs are horizontal with icons and labels.

**Tablet (768px - 1023px):**
- Split pane: workspace tabs (55%) + chat panel (45%), NOT resizable.
- Stage bar shows current stage + "4/10" progress.
- Tabs show icons only (labels on hover via tooltip).

**Mobile (< 768px):**
- Full-width workspace tabs.
- Chat panel is a slide-up drawer triggered by a floating action button (bottom-right, blue circle with `MessageSquare` icon).
- Stage bar shows current stage name + progress bar.
- Tabs are horizontally scrollable.

---

## 11. File Structure

```
src/frontend/src/
  main.tsx                              # App entry, React root
  App.tsx                               # Router configuration (to be rewritten)
  index.css                             # Tailwind imports, global styles

  components/
    common/
      Badge.tsx                         # EXISTING
      Button.tsx                        # EXISTING
      Card.tsx                          # EXISTING
      ConfirmDialog.tsx                 # NEW
      EmptyState.tsx                    # EXISTING
      FileDropzone.tsx                  # NEW
      Input.tsx                         # EXISTING
      Loading.tsx                       # EXISTING
      ProgressStepper.tsx               # NEW
      ResizablePanel.tsx                # NEW
      Skeleton.tsx                      # NEW

    layout/
      AppLayout.tsx                     # EXISTING (renamed from Layout.tsx)
      Header.tsx                        # EXISTING (add breadcrumbs)
      Sidebar.tsx                       # EXISTING (add admin nav, case indicator)

    chat/
      ChatArea.tsx                      # EXISTING (add case context)
      ChatInput.tsx                     # EXISTING (add suggested prompts)
      ChatView.tsx                      # EXISTING (standalone chat page)
      MessageBubble.tsx                 # EXISTING (add agent badge, copy)
      SourcesList.tsx                   # EXISTING

    cases/
      CaseForm.tsx                      # EXISTING (add priority, assignee)
      CaseList.tsx                      # EXISTING (add stage, priority)
      DocumentUpload.tsx                # EXISTING

    case-workspace/
      CaseHeader.tsx                    # NEW
      CaseStageBar.tsx                  # NEW
      CaseWorkspaceTabs.tsx             # NEW
      ChatPanel.tsx                     # NEW

      documents/
        DocumentList.tsx                # NEW
        DocumentRow.tsx                 # NEW
        DocumentDetail.tsx              # NEW
        DocumentOcrStatus.tsx           # NEW

      chronology/
        ChronologyTimeline.tsx          # NEW
        ChronologyEvent.tsx             # NEW
        ChronologyEventForm.tsx         # NEW
        ChronologyAutoExtract.tsx       # NEW

      research/
        ResearchSearchBar.tsx           # NEW
        ResearchResultCard.tsx          # NEW
        ResearchPinnedList.tsx          # NEW
        CitationBadge.tsx               # NEW

      drafts/
        DraftList.tsx                   # NEW
        DraftCard.tsx                   # NEW
        DraftGenerateDialog.tsx         # NEW
        DraftViewer.tsx                 # NEW
        TemplateSelector.tsx            # NEW

      analysis/
        AnalysisPanel.tsx               # NEW
        IracAnalysis.tsx                # NEW
        RiskAssessment.tsx              # NEW

    knowledge/
      FirmKnowledgeForm.tsx             # EXISTING
      FirmKnowledgeList.tsx             # EXISTING
      SearchPanel.tsx                   # EXISTING

    admin/
      AdminStatsCards.tsx               # NEW
      UserTable.tsx                     # NEW
      UserInviteForm.tsx                # NEW
      FirmSettingsForm.tsx              # NEW

  hooks/
    useDebounce.ts                      # EXISTING
    useMediaQuery.ts                    # NEW -- returns boolean for breakpoint matches
    useClickOutside.ts                  # NEW -- for closing dropdowns/drawers
    useCaseContext.ts                   # NEW -- builds CaseContext from current case data

  pages/
    Login.tsx                           # EXISTING
    Dashboard.tsx                       # EXISTING (rewrite: case list + stats)
    CaseWorkspace.tsx                   # NEW (replaces CaseDetail.tsx)
    Knowledge.tsx                       # NEW (wraps SearchPanel + FirmKnowledgeList in tabs)
    Documents.tsx                       # EXISTING
    AdminDashboard.tsx                  # NEW
    AdminUsers.tsx                      # NEW
    AdminFirm.tsx                       # NEW
    NotFound.tsx                        # EXISTING

  services/
    api.ts                              # EXISTING
    auth.service.ts                     # EXISTING
    case.service.ts                     # EXISTING (add advanceStage, getStageHistory)
    chat.service.ts                     # EXISTING
    knowledge.service.ts                # EXISTING
    firm-knowledge.service.ts           # EXISTING
    document.service.ts                 # NEW
    timeline.service.ts                 # NEW
    research.service.ts                 # NEW
    draft.service.ts                    # NEW
    analysis.service.ts                 # NEW
    admin.service.ts                    # NEW

  stores/
    authStore.ts                        # EXISTING
    chatStore.ts                        # EXISTING (add optimistic methods)
    uiStore.ts                          # EXISTING (add isMobile)
    caseStore.ts                        # NEW

  types/
    auth.ts                             # EXISTING
    case.ts                             # EXISTING (add CaseStage, CasePriority, StageHistoryEntry)
    chat.ts                             # EXISTING
    common.ts                           # EXISTING
    knowledge.ts                        # EXISTING
    timeline.ts                         # NEW
    research.ts                         # NEW
    draft.ts                            # NEW
    analysis.ts                         # NEW
    admin.ts                            # NEW

  utils/
    constants.ts                        # EXISTING (add ROUTES for new pages, CASE_STAGES)
    helpers.ts                          # EXISTING (add formatStage, getStageIndex)
```

---

## 12. Implementation Status

### 12.1 Built and Ready

- Login flow (auth store, login page, token management, 401 redirect)
- Base API client (axios instance, auth interceptor, nexus RPC helper)
- Common components (Button, Input, Badge, Card, EmptyState, Loading)
- Layout shell (Sidebar, Header, Layout with Outlet)
- Chat system (ChatView, ChatArea, MessageBubble, ChatInput, SourcesList)
- Case list with filters and create form
- Case detail with overview/documents/conversations tabs
- Document upload with drag-drop and progress
- Knowledge search with jurisdiction/practice area filters
- Firm knowledge CRUD with category tabs
- Cross-case document browser
- All type definitions for auth, case, chat, knowledge

### 12.2 Needs Modification

| Item | Change | Priority |
|---|---|---|
| `App.tsx` | Replace Vite boilerplate with router configuration | P0 |
| `main.tsx` | Add QueryClientProvider, BrowserRouter | P0 |
| `Dashboard` | Replace ChatView wrapper with proper dashboard | P1 |
| `Layout` -> `AppLayout` | Remove padding for CaseWorkspace, add QueryClientProvider | P1 |
| `Sidebar` | Add admin nav, update routes, add case indicator | P1 |
| `Header` | Add breadcrumb support | P2 |
| `ChatArea` | Add caseId prop, context indicator, suggested prompts | P1 |
| `ChatInput` | Add suggested prompt chips | P2 |
| `MessageBubble` | Add agent badge, copy button | P2 |
| `Badge` | Add "accent" variant (orange) | P2 |
| `CaseList` | Add stage badge, priority indicator | P2 |
| `CaseForm` | Add priority field, assignee selector | P2 |
| `chatStore` | Add optimistic message methods | P1 |
| `uiStore` | Add isMobile state | P1 |
| `constants.ts` | Add new routes, CASE_STAGES array | P0 |
| `case.ts` types | Add CaseStage, CasePriority, StageHistoryEntry | P0 |

### 12.3 Needs to Be Built

| Item | Priority | Estimated Components |
|---|---|---|
| Router configuration + guards | P0 | 3 (AuthGuard, RoleGuard, LoginRedirectGuard) |
| `CaseWorkspace` page | P0 | 1 page + 4 sub-components (header, stage bar, tabs, chat panel) |
| `ResizablePanel` | P0 | 1 |
| Case workspace document tab | P1 | 4 (DocumentList, DocumentRow, DocumentDetail, DocumentOcrStatus) |
| Chronology tab | P1 | 4 (Timeline, Event, EventForm, AutoExtract) |
| Research tab | P1 | 4 (SearchBar, ResultCard, PinnedList, CitationBadge) |
| Drafts tab | P2 | 5 (DraftList, DraftCard, GenerateDialog, Viewer, TemplateSelector) |
| Analysis tab | P2 | 3 (AnalysisPanel, IracAnalysis, RiskAssessment) |
| New service files | P1 | 6 (document, timeline, research, draft, analysis, admin) |
| New type files | P0 | 5 (timeline, research, draft, analysis, admin) |
| `caseStore` | P0 | 1 |
| Common utility components | P1 | 4 (ConfirmDialog, FileDropzone, ProgressStepper, Skeleton) |
| Admin pages | P3 | 3 pages + 4 sub-components |
| New hooks | P2 | 3 (useMediaQuery, useClickOutside, useCaseContext) |
| Dashboard rewrite | P1 | 1 page rewrite |

### 12.4 Implementation Order

**Phase 1 -- Foundation (P0):**
1. Rewrite `App.tsx` with router, guards, lazy loading.
2. Add new type files and update existing types.
3. Add `caseStore`.
4. Update `constants.ts` with new routes and stages.
5. Build `CaseWorkspace` page shell with `ResizablePanel`.
6. Build `CaseHeader`, `CaseStageBar`, `CaseWorkspaceTabs`.
7. Build `ChatPanel` (case-scoped chat).

**Phase 2 -- Core Tabs (P1):**
8. Build document tab components + `document.service.ts`.
9. Build chronology tab components + `timeline.service.ts`.
10. Build research tab components + `research.service.ts`.
11. Build common utility components (Skeleton, ConfirmDialog, ProgressStepper, FileDropzone).
12. Rewrite Dashboard page.
13. Update Sidebar and Header.

**Phase 3 -- Advanced Features (P2):**
14. Build drafts tab components + `draft.service.ts`.
15. Build analysis tab components + `analysis.service.ts`.
16. Add optimistic updates to chatStore.
17. Add suggested prompts to ChatInput.
18. Add agent badge and copy button to MessageBubble.
19. Build new hooks.

**Phase 4 -- Admin (P3):**
20. Build admin pages + components + `admin.service.ts`.
21. Add admin nav to Sidebar.
22. Build admin type file.
