# Specs Index — LegalCoPilot v2

## Domain Specification Files

| File | Domain | Description |
|------|--------|-------------|
| `authentication.md` | Auth | JWT login/logout, bcrypt passwords, pre-seeded users, token refresh, route protection |
| `case-workspace.md` | UI/UX | Case-centric workspace layout, 6 tabs, split pane with chat, stage bar, responsive behavior |
| `document-pipeline.md` | Storage | S3 presigned upload/download, text extraction (PDF/Word/Excel/PPT), OCR processing pipeline |
| `chronology.md` | Timeline | CaseEvent model, AI timeline extraction, manual event CRUD, chronology tab UI |
| `case-context.md` | AI Core | Case-level context assembly, cross-conversation memory, case-scoped RAG, draft persistence |
| `drafting-pipeline.md` | AI Drafting | Stage-to-template mapping, draft generation flow, draft persistence, version history |
| `stage-transitions.md` | Lifecycle | Stage validation rules, StageTransition model, stage history, stage-aware template filtering |
| `data-model.md` | Data | All DataFlow models, new models (CaseEvent, StageTransition, CaseResearch), indexes, seed data |
| `frontend-architecture.md` | Frontend | Route structure, component hierarchy, state management, API services, design system |

## Brief Traceability

Every requirement from `workspaces/legalcopilot-rebuild/briefs/02-frontend-e2e-rebuild.md` maps to specs:

| Brief Requirement | Spec File(s) |
|-------------------|--------------|
| 1. Real Authentication (3 users, JWT, bcrypt) | `authentication.md` |
| 2a. Upload case files and prepare submission | `document-pipeline.md`, `case-context.md`, `drafting-pipeline.md` |
| 2b. Develop chronological timeline with analysis | `chronology.md`, `case-workspace.md` (Chronology tab) |
| 2c. Stage-based document generation | `stage-transitions.md`, `drafting-pipeline.md` |
| 3. Case Continuity (cross-conversation memory) | `case-context.md` |
| 4. File Support (PDF, Word, Excel, PPT, S3) | `document-pipeline.md` |
| 5. Case Lifecycle Stages (Singapore ROC 2021) | `stage-transitions.md`, `data-model.md` |
| 6. Frontend Design (case-centric, professional) | `case-workspace.md`, `frontend-architecture.md` |

## Cross-Cutting Concerns

- **Tenant isolation**: Every model has `firm_id` + `multi_tenant: True` → `data-model.md`
- **Token budgeting**: Case context assembly respects LLM token limits → `case-context.md`
- **Security**: bcrypt, JWT, no secrets in frontend → `authentication.md`
- **Responsive design**: 4 breakpoints (sm/md/lg/xl) → `case-workspace.md`, `frontend-architecture.md`

## Dependency Order (Implementation Critical Path)

```
authentication.md          → Frontend can start (login gate)
document-pipeline.md       → File upload works
chronology.md              → Timeline extraction works (depends on document-pipeline)
case-context.md            → AI has full case memory (depends on chronology + document-pipeline)
stage-transitions.md       → Stage lifecycle enforced (independent)
drafting-pipeline.md       → Draft generation works (depends on case-context + stage-transitions)
data-model.md              → Schema changes (parallel with all above)
frontend-architecture.md   → UI implementation (depends on all backend specs)
case-workspace.md          → Core UI view (depends on frontend-architecture)
```
