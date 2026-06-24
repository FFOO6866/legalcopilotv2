# Data Model Specification -- LegalCoPilot v2

> Domain: All DataFlow models, relationships, indexes, constraints, tenant isolation, and seed data.
>
> Source of truth: `src/legalcopilot/models/` (core.py, conversation.py, knowledge.py, governance.py)
>
> Database: Kailash DataFlow with `auto_migrate=True` (SQLite dev, PostgreSQL production)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Existing Models -- Core](#2-existing-models----core)
3. [Existing Models -- Conversation](#3-existing-models----conversation)
4. [Existing Models -- Knowledge](#4-existing-models----knowledge)
5. [Existing Models -- Governance](#5-existing-models----governance)
6. [Model Additions (Existing Models)](#6-model-additions-existing-models)
7. [New Models](#7-new-models)
8. [Handler Parameter Gaps](#8-handler-parameter-gaps)
9. [Relationships](#9-relationships)
10. [Indexes (Complete Registry)](#10-indexes-complete-registry)
11. [Tenant Isolation](#11-tenant-isolation)
12. [Seed Data](#12-seed-data)
13. [Migration Notes](#13-migration-notes)

---

## 1. Overview

LegalCoPilot v2 is a legal assistant for Singapore law firms. The data model supports:

- **Multi-tenant architecture**: every model that holds firm-specific data carries `firm_id` with `multi_tenant: True`
- **Soft delete with audit trail**: core entities use `soft_delete: True` + `audit_log: True`
- **Singapore legal domain**: practice areas, court systems, and case lifecycle stages aligned with the Singapore Rules of Court 2021

### Database Instance

```python
# src/legalcopilot/models/database.py
from dataflow import DataFlow
from legalcopilot.config import settings

db = DataFlow(
    settings.DATABASE_URL,   # sqlite:///legalcopilot_dev.db (dev) | postgresql://... (prod)
    auto_migrate=True,
)
```

### Model Registration

All models are registered in `src/legalcopilot/models/__init__.py` and exported via `__all__`. Any new model MUST be added to both the import list and `__all__`.

### DataFlow Conventions

- Primary key MUST be named `id` (DataFlow requirement)
- `created_at` and `updated_at` are managed automatically by DataFlow -- never set manually (causes DF-104)
- Models are decorated with `@db.model`
- CreateNode uses flat fields; UpdateNode uses nested `filter` + `fields`

---

## 2. Existing Models -- Core

Source: `src/legalcopilot/models/core.py`

### 2.1 Firm

The multi-tenancy root entity. Every other tenant-scoped model references a Firm via `firm_id`.

| Field               | Type            | Default        | Constraint / Validation                            |
|---------------------|-----------------|----------------|-----------------------------------------------------|
| `id`                | `str`           | --             | Primary key                                         |
| `name`              | `str`           | --             | `min_length: 1`, `max_length: 200`                  |
| `domain`            | `Optional[str]` | `None`         | Unique index                                        |
| `subscription_plan` | `str`           | `"free"`       | One of: `free`, `professional`, `enterprise`        |
| `settings`          | `dict`          | `{}`           | Firm-level configuration (JSON)                     |
| `active`            | `bool`          | `True`         | Soft-active flag                                    |
| `created_at`        | `datetime`      | `None`         | Auto-managed by DataFlow                            |
| `updated_at`        | `datetime`      | `None`         | Auto-managed by DataFlow                            |

**DataFlow config**: `soft_delete: True`, `audit_log: True`

**Indexes**:
- `(domain)` -- unique
- `(name)`

**NOTE**: The brief described fields `subscription_tier`, `subscription_status`, `max_users`, and `metadata` on Firm. The actual codebase uses `subscription_plan`, `active`, and `settings` instead. This spec documents the codebase as-is. If additional fields are needed, they should be added via a migration.

---

### 2.2 User

A lawyer or staff member belonging to a firm. Multi-tenant scoped.

| Field            | Type                | Default        | Constraint / Validation                                                                  |
|------------------|---------------------|----------------|------------------------------------------------------------------------------------------|
| `id`             | `str`               | --             | Primary key                                                                              |
| `firm_id`        | `str`               | --             | Tenant key (foreign key to Firm)                                                         |
| `email`          | `str`               | --             | Email validator                                                                          |
| `name`           | `str`               | --             | `min_length: 1`, `max_length: 150`                                                       |
| `role`           | `str`               | `"associate"`  | One of: `partner`, `senior_associate`, `associate`, `paralegal`, `admin`, `viewer`        |
| `permissions`    | `dict`              | `{}`           | Granular permission overrides (JSON)                                                     |
| `active`         | `bool`              | `True`         | Soft-active flag                                                                         |
| `last_login_at`  | `Optional[datetime]`| `None`         | Timestamp of last successful login                                                       |
| `created_at`     | `datetime`          | `None`         | Auto-managed by DataFlow                                                                 |
| `updated_at`     | `datetime`          | `None`         | Auto-managed by DataFlow                                                                 |

**DataFlow config**: `soft_delete: True`, `audit_log: True`, `multi_tenant: True`

**Indexes**:
- `(firm_id, email)` -- unique
- `(firm_id)`
- `(firm_id, role)`

**NOTE on `role` values**: The codebase uses `partner`, `senior_associate`, `associate`, `paralegal`, `admin`, `viewer`. The brief mentioned `intern` -- that role is NOT present in the codebase and is intentionally excluded.

**NOTE on `permissions`**: The codebase stores permissions as a `dict` (JSON object), not a `list`. This allows key-value permission overrides per user rather than a flat list of permission strings.

---

### 2.3 Case

The primary work unit for lawyers. Represents a legal case or matter.

| Field              | Type                | Default        | Constraint / Validation                                                                                           |
|--------------------|---------------------|----------------|-------------------------------------------------------------------------------------------------------------------|
| `id`               | `str`               | --             | Primary key                                                                                                       |
| `firm_id`          | `str`               | --             | Tenant key (foreign key to Firm)                                                                                  |
| `created_by_id`    | `str`               | --             | Foreign key to User (who created the case)                                                                        |
| `assigned_user_id` | `Optional[str]`     | `None`         | Foreign key to User (currently assigned lawyer)                                                                   |
| `case_number`      | `Optional[str]`     | `None`         | Court-assigned case number; unique index                                                                          |
| `title`            | `str`               | --             | `min_length: 1`, `max_length: 500`                                                                                |
| `description`      | `Optional[str]`     | `None`         | Free-text case description                                                                                        |
| `practice_area`    | `str`               | `"general"`    | One of: `general`, `contract`, `employment`, `family`, `criminal`, `property`, `arbitration`, `corporate`, `insolvency`, `ip`, `tort`, `probate` |
| `case_type`        | `str`               | `"general"`    | Free-form case type string                                                                                        |
| `status`           | `str`               | `"open"`       | One of: `open`, `in_progress`, `pending_review`, `under_review`, `closed`, `archived`                             |
| `stage`            | `str`               | `"intake"`     | One of: `intake`, `fact_gathering`, `research`, `analysis`, `drafting`, `review`, `submission`, `complete`         |
| `priority`         | `str`               | `"normal"`     | One of: `low`, `normal`, `high`, `urgent`                                                                         |
| `client_name`      | `Optional[str]`     | `None`         | Name of the client                                                                                                |
| `client_reference` | `Optional[str]`     | `None`         | Client's internal reference number                                                                                |
| `opposing_party`   | `Optional[str]`     | `None`         | Name of opposing party                                                                                            |
| `court`            | `Optional[str]`     | `None`         | Court name (e.g. "Singapore High Court")                                                                          |
| `filing_date`      | `Optional[datetime]`| `None`         | Court filing date                                                                                                 |
| `tags`             | `List[str]`         | `[]`           | Free-form tags for categorization                                                                                 |
| `metadata`         | `dict`              | `{}`           | Arbitrary metadata (JSON)                                                                                         |
| `created_at`       | `datetime`          | `None`         | Auto-managed by DataFlow                                                                                          |
| `updated_at`       | `datetime`          | `None`         | Auto-managed by DataFlow                                                                                          |

**DataFlow config**: `soft_delete: True`, `audit_log: True`, `multi_tenant: True`

**Indexes**:
- `(firm_id)`
- `(firm_id, status)`
- `(firm_id, practice_area)`
- `(firm_id, created_at)`
- `(assigned_user_id)`
- `(case_number)` -- unique

**NOTE on `status` values**: The codebase uses `open`, `in_progress`, `pending_review`, `under_review`, `closed`, `archived`. The brief mentioned `active` instead of `in_progress` -- this spec follows the codebase. **Simplified for frontend**: The frontend only surfaces 4 statuses: `open`, `in_progress`, `closed`, `archived`. The backend keeps all 6 for flexibility, but `pending_review` and `under_review` are not exposed in the UI.

**NOTE on `stage` values**: The 8 stages map to the Singapore Rules of Court 2021 litigation lifecycle: `intake` -> `fact_gathering` -> `research` -> `analysis` -> `drafting` -> `review` -> `submission` -> `complete`.

---

### 2.4 Document

A file attached to a case (pleadings, evidence, correspondence, contracts, etc.).

| Field              | Type            | Default      | Constraint / Validation                                                                                    |
|--------------------|-----------------|--------------|------------------------------------------------------------------------------------------------------------|
| `id`               | `str`           | --           | Primary key                                                                                                |
| `case_id`          | `str`           | --           | Foreign key to Case                                                                                        |
| `firm_id`          | `str`           | --           | Tenant key (foreign key to Firm)                                                                           |
| `uploaded_by_id`   | `str`           | --           | Foreign key to User (uploader)                                                                             |
| `filename`         | `str`           | --           | `min_length: 1`, `max_length: 500`                                                                         |
| `file_type`        | `str`           | `"other"`    | One of: `pleading`, `affidavit`, `exhibit`, `correspondence`, `submission`, `judgment`, `contract`, `memo`, `other` |
| `storage_url`      | `str`           | `""`         | S3 presigned URL or storage path                                                                           |
| `file_size_bytes`  | `int`           | `0`          | File size in bytes                                                                                         |
| `classification`   | `dict`          | `{}`         | AI-generated document classification (JSON)                                                                |
| `ocr_text`         | `Optional[str]` | `None`       | Extracted OCR text (for scanned documents)                                                                 |
| `ocr_status`       | `str`           | `"pending"`  | One of: `pending`, `processing`, `complete`, `failed`                                                      |
| `metadata`         | `dict`          | `{}`         | Arbitrary metadata (JSON)                                                                                  |
| `created_at`       | `datetime`      | `None`       | Auto-managed by DataFlow                                                                                   |
| `updated_at`       | `datetime`      | `None`       | Auto-managed by DataFlow                                                                                   |

**DataFlow config**: `soft_delete: True`, `audit_log: True`, `multi_tenant: True`

**Indexes**:
- `(case_id)`
- `(firm_id)`
- `(firm_id, case_id)`
- `(firm_id, created_at)`
- `(uploaded_by_id)`
- `(file_type)`

**NOTE on `file_type`**: The codebase currently supports 9 types. The brief listed `opinion` and `draft` as additional types. `opinion` maps to `memo` in the current schema. `draft` is a required addition -- see [Section 8](#8-handler-parameter-gaps).

**NOTE**: The brief described `content_text` and `source_url` fields. The codebase uses `ocr_text` (for extracted text) and `storage_url` (for file location) instead. This spec follows the codebase.

---

## 3. Existing Models -- Conversation

Source: `src/legalcopilot/models/conversation.py`

### 3.1 Conversation

A structured conversation, optionally bound to a legal case.

| Field               | Type            | Default      | Constraint / Validation                                                   |
|---------------------|-----------------|--------------|---------------------------------------------------------------------------|
| `id`                | `str`           | --           | Primary key                                                               |
| `firm_id`           | `str`           | --           | Tenant key                                                                |
| `user_id`           | `str`           | --           | Foreign key to User (conversation owner)                                  |
| `case_id`           | `Optional[str]` | `None`       | Foreign key to Case (optional case binding)                               |
| `title`             | `Optional[str]` | `None`       | Conversation title (auto-generated or user-provided)                      |
| `conversation_type` | `str`           | `"general"`  | One of: `consultation`, `research`, `drafting`, `analysis`, `general`     |
| `status`            | `str`           | `"active"`   | One of: `active`, `paused`, `closed`, `archived`                          |
| `metadata`          | `dict`          | `{}`         | Arbitrary metadata (JSON)                                                 |
| `created_at`        | `datetime`      | `None`       | Auto-managed by DataFlow                                                  |
| `updated_at`        | `datetime`      | `None`       | Auto-managed by DataFlow                                                  |

**DataFlow config**: `soft_delete: True`, `audit_log: True`, `multi_tenant: True`

**Indexes**:
- `(firm_id)`
- `(user_id)`
- `(case_id)`
- `(firm_id, status)`
- `(firm_id, user_id)`
- `(firm_id, created_at)`

**NOTE on `conversation_type`**: The codebase uses `consultation`, `research`, `drafting`, `analysis`, `general`. The brief mentioned `chat` -- that maps to `general` in the current schema.

---

### 3.2 Message

A single message within a conversation (user, assistant, or system).

| Field                | Type             | Default   | Constraint / Validation                   |
|----------------------|------------------|-----------|-------------------------------------------|
| `id`                 | `str`            | --        | Primary key                               |
| `conversation_id`    | `str`            | --        | Foreign key to Conversation               |
| `firm_id`            | `str`            | --        | Tenant key                                |
| `role`               | `str`            | --        | One of: `user`, `assistant`, `system`     |
| `content`            | `str`            | --        | `min_length: 1`                           |
| `agent_name`         | `Optional[str]`  | `None`    | Name of the AI agent that generated this  |
| `confidence`         | `Optional[float]`| `None`    | Range: `0.0` to `1.0`                    |
| `rag_context`        | `Optional[dict]` | `None`    | Retrieved context used for this message   |
| `tokens_used`        | `int`            | `0`       | LLM tokens consumed                       |
| `processing_time_ms` | `int`            | `0`       | Processing time in milliseconds           |
| `metadata`           | `dict`           | `{}`      | Arbitrary metadata (JSON)                 |
| `created_at`         | `datetime`       | `None`    | Auto-managed by DataFlow                  |

**DataFlow config**: `multi_tenant: True` (no soft_delete, no audit_log -- messages are append-only)

**Indexes**:
- `(conversation_id)`
- `(conversation_id, created_at)`
- `(firm_id)`
- `(firm_id, conversation_id)`
- `(role)`

**NOTE**: Message has no `updated_at` field -- messages are immutable once created.

---

### 3.3 RAGFeedback

User feedback on RAG-augmented responses for quality tracking.

| Field           | Type            | Default  | Constraint / Validation       |
|-----------------|-----------------|----------|-------------------------------|
| `id`            | `str`           | --       | Primary key                   |
| `firm_id`       | `str`           | --       | Tenant key                    |
| `message_id`    | `str`           | --       | Foreign key to Message        |
| `was_helpful`   | `bool`          | `True`   | Thumbs up/down                |
| `feedback_text` | `Optional[str]` | `None`   | Free-text feedback            |
| `created_at`    | `datetime`      | `None`   | Auto-managed by DataFlow      |

**DataFlow config**: `multi_tenant: True`

**Indexes**:
- `(firm_id)`
- `(message_id)`
- `(firm_id, message_id)`

---

### 3.4 EngagementMetrics

Quality metrics for a conversation, tracking engagement quality for analytics.

| Field                  | Type             | Default  | Constraint / Validation                 |
|------------------------|------------------|----------|-----------------------------------------|
| `id`                   | `str`            | --       | Primary key                             |
| `firm_id`              | `str`            | --       | Tenant key                              |
| `conversation_id`      | `str`            | --       | Foreign key to Conversation; unique     |
| `turn_count`           | `int`            | `0`      | Number of message turns                 |
| `avg_response_time_ms` | `int`            | `0`      | Average AI response time (ms)           |
| `quality_score`        | `Optional[float]`| `None`   | Range: `0.0` to `1.0`                  |
| `practice_area`        | `Optional[str]`  | `None`   | Denormalized from Case for analytics    |
| `resolved`             | `bool`           | `False`  | Whether conversation reached resolution |
| `metadata`             | `dict`           | `{}`     | Arbitrary metadata (JSON)               |
| `created_at`           | `datetime`       | `None`   | Auto-managed by DataFlow                |
| `updated_at`           | `datetime`       | `None`   | Auto-managed by DataFlow                |

**DataFlow config**: `multi_tenant: True`

**Indexes**:
- `(firm_id)`
- `(conversation_id)` -- unique
- `(firm_id, practice_area)`
- `(resolved)`

---

## 4. Existing Models -- Knowledge

Source: `src/legalcopilot/models/knowledge.py`

These models represent the Singapore case law knowledge base (25K+ entries, 215K+ citation edges), legal metadata (judges, topics, legislation), SOP templates, and firm-specific knowledge. They are NOT tenant-scoped (except FirmKnowledge) -- the knowledge base is shared infrastructure.

### 4.1 KnowledgeEntry

Ingested case law entry from eLitigation, LexisNexis, or manual upload.

| Field              | Type                | Default          | Constraint / Validation                                                                 |
|--------------------|---------------------|------------------|-----------------------------------------------------------------------------------------|
| `id`               | `str`               | --               | Primary key                                                                             |
| `citation`         | `str`               | --               | `min_length: 1`, `max_length: 500`; unique index                                       |
| `case_name`        | `str`               | --               | `min_length: 1`, `max_length: 1000`                                                    |
| `court`            | `str`               | --               | `min_length: 1`, `max_length: 200`                                                     |
| `jurisdiction`     | `str`               | `"SG"`           | One of: `SG`, `UK`, `AU`, `MY`, `HK`, `IN`, `NZ`, `CA`, `INTL`                        |
| `decision_date`    | `Optional[datetime]`| `None`           | Date of judgment                                                                        |
| `year`             | `Optional[int]`     | `None`           | Year of judgment (denormalized for queries)                                             |
| `coram`            | `Optional[str]`     | `None`           | Judges who heard the case (comma-separated)                                             |
| `full_text`        | `Optional[str]`     | `None`           | Full judgment text                                                                      |
| `summary`          | `Optional[str]`     | `None`           | AI-generated or editorial summary                                                       |
| `headnotes`        | `Optional[str]`     | `None`           | Editorial headnotes                                                                     |
| `source`           | `str`               | `"elitigation"`  | One of: `elitigation`, `lexisnexis`, `lawnet`, `manual`, `subscription`                 |
| `source_url`       | `Optional[str]`     | `None`           | URL to the original source                                                              |
| `has_full_judgment` | `bool`             | `False`          | Whether full judgment text is available                                                 |
| `metadata`         | `dict`              | `{}`             | Arbitrary metadata (JSON)                                                               |
| `created_at`       | `datetime`          | `None`           | Auto-managed by DataFlow                                                                |
| `updated_at`       | `datetime`          | `None`           | Auto-managed by DataFlow                                                                |

**DataFlow config**: `soft_delete: True`, `audit_log: True` (NOT multi-tenant -- shared knowledge base)

**Indexes**:
- `(citation)` -- unique
- `(court)`
- `(jurisdiction)`
- `(year)`
- `(court, year)`

---

### 4.2 KnowledgeVector

Vector embedding chunk for a KnowledgeEntry (actual vectors stored in Qdrant; metadata stored here).

| Field             | Type            | Default                    | Constraint / Validation                                                                |
|-------------------|-----------------|----------------------------|----------------------------------------------------------------------------------------|
| `id`              | `str`           | --                         | Primary key                                                                            |
| `entry_id`        | `str`           | --                         | Foreign key to KnowledgeEntry                                                          |
| `chunk_text`      | `str`           | --                         | The text chunk that was embedded                                                       |
| `chunk_index`     | `int`           | `0`                        | Chunk position within the entry                                                        |
| `embedding_model` | `str`           | `"text-embedding-3-small"` | One of: `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002`   |
| `dimensions`      | `int`           | `1536`                     | Embedding dimension count                                                              |
| `qdrant_point_id` | `Optional[str]` | `None`                     | Reference to Qdrant point ID                                                           |
| `created_at`      | `datetime`      | `None`                     | Auto-managed by DataFlow                                                               |

**DataFlow config**: `audit_log: True`

**Indexes**:
- `(entry_id)`
- `(entry_id, chunk_index)`
- `(qdrant_point_id)`

---

### 4.3 KGCitationEdge

Citation relationship between two KnowledgeEntry records (215K+ edges in the knowledge graph).

| Field           | Type            | Default    | Constraint / Validation                                                                                           |
|-----------------|-----------------|------------|-------------------------------------------------------------------------------------------------------------------|
| `id`            | `str`           | --         | Primary key                                                                                                       |
| `citing_id`     | `str`           | --         | Foreign key to KnowledgeEntry (the case that cites)                                                               |
| `cited_id`      | `str`           | --         | Foreign key to KnowledgeEntry (the case being cited)                                                              |
| `treatment`     | `str`           | `"cited"`  | One of: `cited`, `followed`, `applied`, `distinguished`, `overruled`, `referred`, `considered`, `approved`, `not_followed` |
| `context_text`  | `Optional[str]` | `None`     | Text surrounding the citation                                                                                     |
| `paragraph_num` | `Optional[int]` | `None`     | Paragraph number where citation appears                                                                           |
| `created_at`    | `datetime`      | `None`     | Auto-managed by DataFlow                                                                                          |

**DataFlow config**: `audit_log: True`

**Indexes**:
- `(citing_id)`
- `(cited_id)`
- `(citing_id, cited_id)` -- unique
- `(treatment)`

---

### 4.4 KGJudge

Judge entity in the knowledge graph (499+ judges).

| Field               | Type                | Default | Constraint / Validation            |
|---------------------|---------------------|---------|------------------------------------|
| `id`                | `str`               | --      | Primary key                        |
| `name`              | `str`               | --      | `min_length: 1`, `max_length: 300` |
| `court`             | `Optional[str]`     | `None`  | Court affiliation                  |
| `title`             | `Optional[str]`     | `None`  | Judicial title                     |
| `appointment_start` | `Optional[datetime]`| `None`  | Start of appointment               |
| `appointment_end`   | `Optional[datetime]`| `None`  | End of appointment (None = current)|
| `metadata`          | `dict`              | `{}`   | Arbitrary metadata (JSON)          |
| `created_at`        | `datetime`          | `None`  | Auto-managed by DataFlow           |

**Indexes**:
- `(name)`
- `(court)`

---

### 4.5 KGCaseJudge

Many-to-many join: which judges presided over which cases.

| Field      | Type       | Default    | Constraint / Validation                                                   |
|------------|------------|------------|---------------------------------------------------------------------------|
| `id`       | `str`      | --         | Primary key                                                               |
| `entry_id` | `str`      | --         | Foreign key to KnowledgeEntry                                             |
| `judge_id` | `str`      | --         | Foreign key to KGJudge                                                    |
| `role`     | `str`      | `"judge"`  | One of: `judge`, `chief_justice`, `justice_of_appeal`, `registrar`        |
| `created_at`| `datetime`| `None`     | Auto-managed by DataFlow                                                  |

**Indexes**:
- `(entry_id)`
- `(judge_id)`
- `(entry_id, judge_id)` -- unique

---

### 4.6 KGCaseTopic

Topic classification for a KnowledgeEntry (9,977+ entries).

| Field       | Type       | Default | Constraint / Validation                     |
|-------------|------------|---------|---------------------------------------------|
| `id`        | `str`      | --      | Primary key                                 |
| `entry_id`  | `str`      | --      | Foreign key to KnowledgeEntry               |
| `topic`     | `str`      | --      | `min_length: 1`, `max_length: 300`          |
| `confidence`| `float`    | `1.0`   | Range: `0.0` to `1.0`                      |
| `created_at`| `datetime` | `None`  | Auto-managed by DataFlow                    |

**Indexes**:
- `(entry_id)`
- `(topic)`
- `(entry_id, topic)` -- unique

---

### 4.7 KGLegislationRef

Legislation reference from a KnowledgeEntry (43K+ references).

| Field          | Type            | Default | Constraint / Validation            |
|----------------|-----------------|---------|------------------------------------|
| `id`           | `str`           | --      | Primary key                        |
| `entry_id`     | `str`           | --      | Foreign key to KnowledgeEntry      |
| `statute_name` | `str`           | --      | `min_length: 1`, `max_length: 500` |
| `section`      | `Optional[str]` | `None`  | Section number                     |
| `subsection`   | `Optional[str]` | `None`  | Subsection                         |
| `chapter`      | `Optional[str]` | `None`  | Chapter (e.g. Cap. 50)             |
| `created_at`   | `datetime`      | `None`  | Auto-managed by DataFlow           |

**Indexes**:
- `(entry_id)`
- `(statute_name)`
- `(statute_name, section)`

---

### 4.8 SOPTemplate

Data-driven SOP (Standard Operating Procedure) template for a case type.

| Field               | Type            | Default          | Constraint / Validation                     |
|---------------------|-----------------|------------------|---------------------------------------------|
| `id`                | `str`           | --               | Primary key                                 |
| `name`              | `str`           | --               | `min_length: 1`, `max_length: 200`          |
| `practice_area`     | `str`           | --               | Practice area this SOP applies to           |
| `case_type`         | `str`           | --               | Case type; unique index                     |
| `description`       | `Optional[str]` | `None`           | SOP description                             |
| `skills`            | `dict`          | `{}`             | Required skills configuration (JSON)        |
| `knowledge_sources` | `dict`          | `{}`             | Knowledge source configuration (JSON)       |
| `tools`             | `dict`          | `{}`             | Tool configuration (JSON)                   |
| `quality_threshold` | `float`         | `0.8`            | Range: `0.0` to `1.0`                      |
| `adversarial_review`| `bool`          | `True`           | Whether adversarial review is enabled       |
| `max_iterations`    | `int`           | `3`              | Range: `1` to `10`                          |
| `is_active`         | `bool`          | `True`           | Whether template is active                  |
| `metadata`          | `dict`          | `{}`             | Arbitrary metadata (JSON)                   |
| `created_at`        | `datetime`      | `None`           | Auto-managed by DataFlow                    |
| `updated_at`        | `datetime`      | `None`           | Auto-managed by DataFlow                    |

**DataFlow config**: `soft_delete: True`, `audit_log: True`

**Indexes**:
- `(case_type)` -- unique
- `(practice_area)`
- `(is_active)`

---

### 4.9 SOPUsageRecord

Tracks SOP template usage and quality outcomes for auto-refinement.

| Field               | Type            | Default   | Constraint / Validation                                               |
|---------------------|-----------------|-----------|-----------------------------------------------------------------------|
| `id`                | `str`           | --        | Primary key                                                           |
| `case_type`         | `str`           | --        | The case type that was processed                                      |
| `quality_verdict`   | `str`           | `"pass"`  | One of: `pass`, `rework`, `escalate`, `max_iterations_reached`        |
| `confidence`        | `float`         | `0.0`     | Range: `0.0` to `1.0`                                                |
| `iterations`        | `int`           | `1`       | Range: `1` to `10`                                                   |
| `sop_template_name` | `Optional[str]` | `None`    | Name of SOP template used                                             |
| `metadata`          | `dict`          | `{}`      | Arbitrary metadata (JSON)                                             |
| `created_at`        | `datetime`      | `None`    | Auto-managed by DataFlow                                              |

**DataFlow config**: none (no soft_delete, no audit_log, NOT multi-tenant)

**Indexes**:
- `(case_type)`
- `(case_type, created_at)`
- `(quality_verdict)`

---

### 4.10 FirmKnowledge

Firm-specific knowledge (private precedents, internal playbooks, custom templates). Multi-tenant scoped.

| Field             | Type            | Default                    | Constraint / Validation                                                         |
|-------------------|-----------------|----------------------------|---------------------------------------------------------------------------------|
| `id`              | `str`           | --                         | Primary key                                                                     |
| `firm_id`         | `str`           | --                         | Tenant key                                                                      |
| `category`        | `str`           | --                         | One of: `precedent`, `playbook`, `template`, `policy`, `training`, `other`      |
| `title`           | `str`           | --                         | `min_length: 1`, `max_length: 500`                                              |
| `content`         | `Optional[str]` | `None`                     | Full content text                                                               |
| `embedding_model` | `str`           | `"text-embedding-3-small"` | Embedding model used                                                            |
| `qdrant_point_id` | `Optional[str]` | `None`                     | Reference to Qdrant point ID                                                    |
| `is_active`       | `bool`          | `True`                     | Whether entry is active                                                         |
| `metadata`        | `dict`          | `{}`                       | Arbitrary metadata (JSON)                                                       |
| `created_at`      | `datetime`      | `None`                     | Auto-managed by DataFlow                                                        |
| `updated_at`      | `datetime`      | `None`                     | Auto-managed by DataFlow                                                        |

**DataFlow config**: `soft_delete: True`, `audit_log: True`, `multi_tenant: True`

**Indexes**:
- `(firm_id)`
- `(firm_id, category)`
- `(is_active)`

---

## 5. Existing Models -- Governance

Source: `src/legalcopilot/models/governance.py`

### 5.1 AuditEntry

Immutable audit trail. Every AI action, data access, and state change gets an audit entry.

| Field             | Type            | Default        | Constraint / Validation                                                                       |
|-------------------|-----------------|----------------|-----------------------------------------------------------------------------------------------|
| `id`              | `str`           | --             | Primary key                                                                                   |
| `firm_id`         | `str`           | --             | Tenant key                                                                                    |
| `user_id`         | `Optional[str]` | `None`         | Foreign key to User (may be null for system actions)                                          |
| `agent_name`      | `Optional[str]` | `None`         | AI agent that performed the action                                                            |
| `action`          | `str`           | --             | One of: `create`, `read`, `update`, `delete`, `analyze`, `generate`, `search`, `export`, `login`, `logout` |
| `entity_type`     | `str`           | --             | Model name of the affected entity                                                             |
| `entity_id`       | `Optional[str]` | `None`         | ID of the affected entity                                                                     |
| `details`         | `dict`          | `{}`           | Action details (JSON)                                                                         |
| `pact_envelope`   | `dict`          | `{}`           | PACT governance envelope (JSON)                                                               |
| `clearance_level` | `str`           | `"internal"`   | One of: `public`, `internal`, `confidential`, `privileged`                                    |
| `ip_address`      | `Optional[str]` | `None`         | Requester IP address                                                                          |
| `created_at`      | `datetime`      | `None`         | Auto-managed by DataFlow                                                                      |

**DataFlow config**: `audit_log: False` (audit entries do NOT audit themselves), `multi_tenant: True`

**Indexes**:
- `(firm_id)`
- `(firm_id, created_at)`
- `(user_id)`
- `(entity_type, entity_id)`
- `(action)`
- `(agent_name)`

**NOTE**: AuditEntry has no `updated_at` -- entries are immutable once created.

---

## 6. Model Additions (Existing Models)

### 6.1 User.password_hash

**Add to User model** in `src/legalcopilot/models/core.py`:

| Field           | Type            | Default | Purpose                             |
|-----------------|-----------------|---------|-------------------------------------|
| `password_hash` | `Optional[str]` | `None`  | bcrypt-hashed password for auth     |

**Rationale**: Required for the authentication spec (`specs/authentication.md`). Passwords are hashed with bcrypt before storage. A `None` default means "no password set" (used during seed to detect first-login scenarios or API-key-only users). `Optional[str]` is preferred over `str = ""` because `None` is semantically distinct from an empty string -- `None` means "never set", whereas an empty string could be confused with a failed hash operation.

**Constraints**:
- MUST NOT be returned in any API response
- MUST NOT appear in audit log details
- MUST be hashed with bcrypt (cost factor 12) before storage
- MUST NOT be set manually via DataFlow `created_at`/`updated_at` -- only the hash is stored

**Implementation**:

```python
@db.model
class User:
    # ... existing fields ...
    password_hash: Optional[str] = None
    # ... rest of model ...
```

---

## 7. New Models

All new models go in `src/legalcopilot/models/core.py` (domain models) and MUST be registered in `src/legalcopilot/models/__init__.py`.

### 7.1 CaseEvent

A significant event on a case timeline. Events can be AI-extracted from documents or manually entered by users. Used by the chronology tab to build a case timeline.

| Field              | Type                | Default  | Constraint / Validation                                |
|--------------------|---------------------|----------|--------------------------------------------------------|
| `id`               | `str`               | --       | Primary key                                            |
| `case_id`          | `str`               | --       | Foreign key to Case                                    |
| `firm_id`          | `str`               | --       | Tenant key                                             |
| `document_id`      | `Optional[str]`     | `None`   | Foreign key to Document (source document, if any)      |
| `event_date`       | `Optional[datetime]`| `None`   | Parsed date of the event (for sorting/filtering)       |
| `event_date_text`  | `str`               | `""`     | Human-readable date text (e.g. "early March 2024")     |
| `description`      | `str`               | --       | Description of the event                               |
| `significance`     | `Optional[str]`     | `None`   | Why this event matters to the case                     |
| `parties_involved` | `list`              | `[]`     | List of party names involved                           |
| `event_type`       | `str`               | `"other"`| Type of event (e.g. `filing`, `hearing`, `correspondence`, `deadline`, `settlement`, `judgment`, `other`) |
| `source_text`      | `Optional[str]`     | `None`   | Original text from which this event was extracted       |
| `confidence`       | `float`             | `1.0`    | AI confidence score (1.0 for manual entries)           |
| `is_manual`        | `bool`              | `False`  | Whether manually entered (True) or AI-extracted (False)|
| `metadata`         | `dict`              | `{}`     | Arbitrary metadata (JSON)                              |
| `created_at`       | `datetime`          | `None`   | Auto-managed by DataFlow                               |
| `updated_at`       | `datetime`          | `None`   | Auto-managed by DataFlow                               |

**DataFlow config**: `soft_delete: True`, `audit_log: True`, `multi_tenant: True`

**Validation**:

```python
__validation__ = {
    "description": {"min_length": 1, "max_length": 2000},
    "event_type": {
        "one_of": [
            "filing",
            "hearing",
            "correspondence",
            "deadline",
            "settlement",
            "judgment",
            "other",
        ]
    },
    "confidence": {"range": {"min": 0.0, "max": 1.0}},
}
```

**Indexes**:

```python
__indexes__ = [
    {"fields": ["case_id", "event_date"]},
    {"fields": ["case_id", "firm_id"]},
    {"fields": ["firm_id"]},
    {"fields": ["document_id"]},
    {"fields": ["case_id", "event_type"]},
]
```

---

### 7.2 StageTransition — REMOVED (Simplified)

Stage changes are tracked directly on the Case model's `stage` field. For a small firm with 3 users, a full audit trail model is unnecessary. The `updated_at` timestamp on Case provides sufficient tracking.

---

### 7.3 CaseResearch

A pinned research finding for a case -- a citation that a lawyer has found relevant and wants to track.

| Field            | Type            | Default  | Constraint / Validation                                                                                         |
|------------------|-----------------|----------|-----------------------------------------------------------------------------------------------------------------|
| `id`             | `str`           | --       | Primary key                                                                                                     |
| `case_id`        | `str`           | --       | Foreign key to Case                                                                                             |
| `firm_id`        | `str`           | --       | Tenant key                                                                                                      |
| `citation`       | `str`           | --       | Legal citation string (e.g. "[2024] SGHC 123")                                                                 |
| `case_name`      | `str`           | --       | Name of the cited case                                                                                          |
| `court`          | `str`           | --       | Court that decided the cited case                                                                               |
| `date`           | `Optional[str]` | `None`   | Date string of the cited decision (free-form, e.g. "2024", "15 March 2024")                                    |
| `relevance_score`| `float`         | `0.0`    | AI-computed relevance to the current case; range `0.0` to `1.0`                                                |
| `snippet`        | `str`           | `""`     | Key excerpt or summary of the relevant holding                                                                  |
| `treatment`      | `str`           | `"cited"`| How this authority is being used; one of: `followed`, `applied`, `distinguished`, `overruled`, `cited`, `referred` |
| `pinned_by_id`   | `Optional[str]` | `None`   | Foreign key to User (who pinned this research item)                                                             |
| `metadata`       | `dict`          | `{}`     | Arbitrary metadata (JSON)                                                                                       |
| `created_at`     | `datetime`      | `None`   | Auto-managed by DataFlow                                                                                        |

**DataFlow config**: `soft_delete: True`, `audit_log: True`, `multi_tenant: True`

**Validation**:

```python
__validation__ = {
    "citation": {"min_length": 1, "max_length": 500},
    "case_name": {"min_length": 1, "max_length": 1000},
    "court": {"min_length": 1, "max_length": 200},
    "relevance_score": {"range": {"min": 0.0, "max": 1.0}},
    "treatment": {
        "one_of": [
            "followed",
            "applied",
            "distinguished",
            "overruled",
            "cited",
            "referred",
        ]
    },
}
```

**Indexes**:

```python
__indexes__ = [
    {"fields": ["case_id", "firm_id"]},
    {"fields": ["firm_id"]},
    {"fields": ["case_id"]},
    {"fields": ["pinned_by_id"]},
    {"fields": ["case_id", "relevance_score"]},
]
```

**NOTE**: CaseResearch has no `updated_at` -- research entries are created and optionally soft-deleted, not updated in place. If a lawyer wants to change the treatment, they delete and re-pin.

---

## 8. Handler Parameter Gaps

These are changes needed in the handler/service layer to align with the data model.

### 8.1 create_case handler

The `create_case` handler MUST accept the following parameters that already exist on the Case model but may not be wired into the handler:

| Parameter        | Type            | Notes                                            |
|------------------|-----------------|--------------------------------------------------|
| `opposing_party` | `Optional[str]` | Already on Case model; wire through to CreateNode |
| `court`          | `Optional[str]` | Already on Case model; wire through to CreateNode |

These fields exist on the Case model (section 2.3) but the handler may not be passing them to the DataFlow CreateNode. The handler MUST include them in the flat fields dict:

```python
# CreateNode uses flat fields
workflow.add_node("CaseCreateNode", "create", {
    "id": case_id,
    "firm_id": firm_id,
    "created_by_id": user_id,
    "title": title,
    "opposing_party": opposing_party,  # <-- wire this
    "court": court,                     # <-- wire this
    # ... other fields
})
```

### 8.2 update_case handler -- remove stage from directly-updatable fields

Remove `stage` from the directly-updatable fields in `update_case`. Stage changes MUST go through the `advance_case_stage` endpoint (see stage-transitions.md Section 5) for proper validation, history tracking, and audit logging.

If a caller passes `stage` to `update_case`, the handler MUST return an error directing them to the stage endpoint:

```python
# "stage" is removed from the fields dict — use advance_case_stage instead
fields = {
    k: v
    for k, v in {
        "title": title,
        "status": status,
        # "stage" removed — use advance_case_stage instead
        "assigned_user_id": assigned_user_id,
        "priority": priority,
    }.items()
    if v
}

# If caller passed stage, return an error directing them to the stage endpoint
if stage:
    return {
        "error": "Stage changes must use the advance_case_stage endpoint "
                 "for proper validation and history tracking.",
        "hint": "POST /api/cases/:id/stage with {new_stage, reason}",
    }
```

The `stage` parameter remains in the function signature for backward compatibility but is no longer applied directly. This ensures all stage changes produce a `StageTransition` audit record (see Section 7.2) and enforce the transition rules defined in `stage-transitions.md`.

### 8.3 Document file_type -- add "draft"

The Document model's `file_type` validation MUST be updated to include `draft` as a valid type. This supports AI-generated draft documents that are stored alongside uploaded documents.

**Current valid types**: `pleading`, `affidavit`, `exhibit`, `correspondence`, `submission`, `judgment`, `contract`, `memo`, `other`

**Updated valid types**: `pleading`, `affidavit`, `exhibit`, `correspondence`, `submission`, `judgment`, `contract`, `memo`, `draft`, `other`

Implementation in `src/legalcopilot/models/core.py`:

```python
"file_type": {
    "one_of": [
        "pleading",
        "affidavit",
        "exhibit",
        "correspondence",
        "submission",
        "judgment",
        "contract",
        "memo",
        "draft",      # <-- add this
        "other",
    ]
},
```

---

## 9. Relationships

### 9.1 Entity Relationship Diagram (Text)

```
Firm (1) ──────< User (N)
Firm (1) ──────< Case (N)
Firm (1) ──────< Document (N)
Firm (1) ──────< Conversation (N)
Firm (1) ──────< FirmKnowledge (N)
Firm (1) ──────< AuditEntry (N)

User (1) ──────< Case.created_by_id (N)
User (1) ──────< Case.assigned_user_id (N)
User (1) ──────< Document.uploaded_by_id (N)
User (1) ──────< Conversation.user_id (N)
User (1) ──────< StageTransition.transitioned_by_id (N)   [REMOVED — simplified]
User (1) ──────< CaseResearch.pinned_by_id (N)

Case (1) ──────< Document (N)           via document.case_id
Case (1) ──────< CaseEvent (N)          via case_event.case_id
Case (1) ──────< StageTransition (N)    via stage_transition.case_id  [REMOVED — simplified]
Case (1) ──────< Conversation (N)       via conversation.case_id
Case (1) ──────< CaseResearch (N)       via case_research.case_id

Document (1) ──< CaseEvent (N)          via case_event.document_id

Conversation (1) ──< Message (N)        via message.conversation_id
Conversation (1) ──< EngagementMetrics (1)  via engagement_metrics.conversation_id

Message (1) ──────< RAGFeedback (N)     via rag_feedback.message_id

KnowledgeEntry (1) ──< KnowledgeVector (N)     via knowledge_vector.entry_id
KnowledgeEntry (1) ──< KGCitationEdge (N)      via citing_id OR cited_id
KnowledgeEntry (1) ──< KGCaseJudge (N)         via kg_case_judge.entry_id
KnowledgeEntry (1) ──< KGCaseTopic (N)         via kg_case_topic.entry_id
KnowledgeEntry (1) ──< KGLegislationRef (N)    via kg_legislation_ref.entry_id

KGJudge (1) ───────< KGCaseJudge (N)           via kg_case_judge.judge_id
```

### 9.2 Relationship Detail

| Parent           | Child            | FK Field              | Cardinality | Notes                                       |
|------------------|------------------|-----------------------|-------------|----------------------------------------------|
| Firm             | User             | `user.firm_id`        | 1:N         | Tenant root                                  |
| Firm             | Case             | `case.firm_id`        | 1:N         | Tenant scoped                                |
| Firm             | Document         | `document.firm_id`    | 1:N         | Tenant scoped                                |
| Firm             | Conversation     | `conversation.firm_id`| 1:N         | Tenant scoped                                |
| Firm             | Message          | `message.firm_id`     | 1:N         | Tenant scoped (denormalized)                 |
| Firm             | CaseEvent        | `case_event.firm_id`  | 1:N         | Tenant scoped                                |
| ~~Firm~~         | ~~StageTransition~~ | ~~`stage_transition.firm_id`~~ | ~~1:N~~ | ~~Tenant scoped~~ (REMOVED — simplified)  |
| Firm             | CaseResearch     | `case_research.firm_id` | 1:N      | Tenant scoped                                |
| Firm             | FirmKnowledge    | `firm_knowledge.firm_id` | 1:N     | Tenant scoped                                |
| Firm             | AuditEntry       | `audit_entry.firm_id` | 1:N        | Tenant scoped                                |
| User             | Case             | `case.created_by_id`  | 1:N         | Case creator                                 |
| User             | Case             | `case.assigned_user_id`| 1:N        | Assigned lawyer (nullable)                   |
| User             | Document         | `document.uploaded_by_id` | 1:N     | Document uploader                            |
| User             | Conversation     | `conversation.user_id`| 1:N         | Conversation owner                           |
| ~~User~~         | ~~StageTransition~~ | ~~`stage_transition.transitioned_by_id`~~ | ~~1:N~~ | ~~Who triggered the transition~~ (REMOVED — simplified) |
| User             | CaseResearch     | `case_research.pinned_by_id` | 1:N  | Who pinned the research (nullable)           |
| Case             | Document         | `document.case_id`    | 1:N         | Documents attached to a case                 |
| Case             | CaseEvent        | `case_event.case_id`  | 1:N         | Timeline events for a case                   |
| ~~Case~~         | ~~StageTransition~~ | ~~`stage_transition.case_id`~~ | ~~1:N~~ | ~~Stage history for a case~~ (REMOVED — simplified) |
| Case             | Conversation     | `conversation.case_id`| 1:N         | Conversations bound to a case (nullable FK)  |
| Case             | CaseResearch     | `case_research.case_id` | 1:N      | Research findings for a case                 |
| Document         | CaseEvent        | `case_event.document_id` | 1:N     | Events extracted from a document (nullable)  |
| Conversation     | Message          | `message.conversation_id` | 1:N    | Messages in a conversation                   |
| Conversation     | EngagementMetrics| `engagement_metrics.conversation_id` | 1:1 | One metrics record per conversation |
| Message          | RAGFeedback      | `rag_feedback.message_id` | 1:N    | Feedback on a message                        |
| KnowledgeEntry   | KnowledgeVector  | `knowledge_vector.entry_id` | 1:N  | Embedding chunks                             |
| KnowledgeEntry   | KGCitationEdge   | `citing_id` / `cited_id` | N:N     | Citation graph (directed)                    |
| KnowledgeEntry   | KGCaseJudge      | `kg_case_judge.entry_id` | 1:N     | Join table to judges                         |
| KnowledgeEntry   | KGCaseTopic      | `kg_case_topic.entry_id` | 1:N     | Topic classifications                        |
| KnowledgeEntry   | KGLegislationRef | `kg_legislation_ref.entry_id` | 1:N| Legislation references                       |
| KGJudge          | KGCaseJudge      | `kg_case_judge.judge_id` | 1:N     | Join table from judges                       |

---

## 10. Indexes (Complete Registry)

### 10.1 Core Models

**Firm**:
| Fields       | Unique | Purpose                    |
|--------------|--------|----------------------------|
| `(domain)`   | Yes    | Lookup firm by domain      |
| `(name)`     | No     | Search firms by name       |

**User**:
| Fields              | Unique | Purpose                                |
|---------------------|--------|----------------------------------------|
| `(firm_id, email)`  | Yes    | Unique email per firm (login lookup)   |
| `(firm_id)`         | No     | List users in a firm                   |
| `(firm_id, role)`   | No     | List users by role within a firm       |

**Case**:
| Fields                   | Unique | Purpose                                   |
|--------------------------|--------|-------------------------------------------|
| `(firm_id)`              | No     | List cases in a firm                      |
| `(firm_id, status)`      | No     | Filter cases by status within a firm      |
| `(firm_id, practice_area)`| No    | Filter cases by practice area             |
| `(firm_id, created_at)`  | No     | Sort cases by creation date               |
| `(assigned_user_id)`     | No     | Find cases assigned to a user             |
| `(case_number)`          | Yes    | Lookup by court-assigned case number      |

**Document**:
| Fields                  | Unique | Purpose                                    |
|-------------------------|--------|--------------------------------------------|
| `(case_id)`             | No     | List documents for a case                  |
| `(firm_id)`             | No     | List all firm documents                    |
| `(firm_id, case_id)`    | No     | List firm documents for a specific case    |
| `(firm_id, created_at)` | No     | Sort firm documents by date                |
| `(uploaded_by_id)`      | No     | Find documents uploaded by a user          |
| `(file_type)`           | No     | Filter documents by type                   |

### 10.2 Conversation Models

**Conversation**:
| Fields                  | Unique | Purpose                                      |
|-------------------------|--------|----------------------------------------------|
| `(firm_id)`             | No     | List all firm conversations                  |
| `(user_id)`             | No     | List conversations by user                   |
| `(case_id)`             | No     | List conversations bound to a case           |
| `(firm_id, status)`     | No     | Filter by status within a firm               |
| `(firm_id, user_id)`    | No     | Filter by user within a firm                 |
| `(firm_id, created_at)` | No     | Sort firm conversations by date              |

**Message**:
| Fields                           | Unique | Purpose                                    |
|----------------------------------|--------|--------------------------------------------|
| `(conversation_id)`             | No     | List messages in a conversation            |
| `(conversation_id, created_at)` | No     | List messages in chronological order       |
| `(firm_id)`                     | No     | List all firm messages                     |
| `(firm_id, conversation_id)`    | No     | Tenant-scoped conversation messages        |
| `(role)`                        | No     | Filter messages by role                    |

**RAGFeedback**:
| Fields                    | Unique | Purpose                              |
|---------------------------|--------|--------------------------------------|
| `(firm_id)`               | No     | List all firm feedback               |
| `(message_id)`            | No     | Find feedback for a message          |
| `(firm_id, message_id)`   | No     | Tenant-scoped message feedback       |

**EngagementMetrics**:
| Fields                       | Unique | Purpose                                  |
|------------------------------|--------|------------------------------------------|
| `(firm_id)`                  | No     | List all firm metrics                    |
| `(conversation_id)`         | Yes    | One metrics record per conversation      |
| `(firm_id, practice_area)`  | No     | Analytics by practice area               |
| `(resolved)`                | No     | Filter resolved/unresolved               |

### 10.3 Knowledge Models

**KnowledgeEntry**:
| Fields            | Unique | Purpose                           |
|-------------------|--------|-----------------------------------|
| `(citation)`      | Yes    | Unique citation lookup            |
| `(court)`         | No     | Filter by court                   |
| `(jurisdiction)`  | No     | Filter by jurisdiction            |
| `(year)`          | No     | Filter by year                    |
| `(court, year)`   | No     | Filter by court and year          |

**KnowledgeVector**:
| Fields                      | Unique | Purpose                           |
|-----------------------------|--------|-----------------------------------|
| `(entry_id)`                | No     | List chunks for an entry          |
| `(entry_id, chunk_index)`   | No     | Ordered chunks for an entry       |
| `(qdrant_point_id)`         | No     | Lookup by Qdrant point            |

**KGCitationEdge**:
| Fields                    | Unique | Purpose                              |
|---------------------------|--------|--------------------------------------|
| `(citing_id)`             | No     | Find what a case cites               |
| `(cited_id)`              | No     | Find what cites a case               |
| `(citing_id, cited_id)`   | Yes    | One edge per citation pair           |
| `(treatment)`             | No     | Filter by treatment type             |

**KGJudge**:
| Fields    | Unique | Purpose            |
|-----------|--------|--------------------|
| `(name)`  | No     | Search by name     |
| `(court)` | No     | Filter by court    |

**KGCaseJudge**:
| Fields                  | Unique | Purpose                              |
|-------------------------|--------|--------------------------------------|
| `(entry_id)`            | No     | Find judges for a case               |
| `(judge_id)`            | No     | Find cases for a judge               |
| `(entry_id, judge_id)`  | Yes    | One record per case-judge pair       |

**KGCaseTopic**:
| Fields                 | Unique | Purpose                              |
|------------------------|--------|--------------------------------------|
| `(entry_id)`           | No     | Find topics for a case               |
| `(topic)`              | No     | Find cases by topic                  |
| `(entry_id, topic)`    | Yes    | One record per case-topic pair       |

**KGLegislationRef**:
| Fields                      | Unique | Purpose                              |
|-----------------------------|--------|--------------------------------------|
| `(entry_id)`                | No     | Find legislation for a case          |
| `(statute_name)`            | No     | Find cases referencing a statute     |
| `(statute_name, section)`   | No     | Find cases referencing a section     |

**SOPTemplate**:
| Fields           | Unique | Purpose                          |
|------------------|--------|----------------------------------|
| `(case_type)`    | Yes    | One template per case type       |
| `(practice_area)`| No     | Filter by practice area          |
| `(is_active)`    | No     | Filter active templates          |

**SOPUsageRecord**:
| Fields                    | Unique | Purpose                              |
|---------------------------|--------|--------------------------------------|
| `(case_type)`             | No     | Usage records by case type           |
| `(case_type, created_at)` | No    | Usage records sorted by date         |
| `(quality_verdict)`       | No     | Filter by verdict                    |

**FirmKnowledge**:
| Fields                  | Unique | Purpose                              |
|-------------------------|--------|--------------------------------------|
| `(firm_id)`             | No     | List all firm knowledge              |
| `(firm_id, category)`   | No     | Filter by category within a firm     |
| `(is_active)`           | No     | Filter active knowledge entries      |

**AuditEntry**:
| Fields                       | Unique | Purpose                              |
|------------------------------|--------|--------------------------------------|
| `(firm_id)`                  | No     | List all firm audit entries          |
| `(firm_id, created_at)`     | No     | Audit entries sorted by date         |
| `(user_id)`                 | No     | Find actions by a user               |
| `(entity_type, entity_id)`  | No     | Find audit trail for an entity       |
| `(action)`                  | No     | Filter by action type                |
| `(agent_name)`              | No     | Filter by AI agent                   |

### 10.4 New Model Indexes

**CaseEvent**:
| Fields                       | Unique | Purpose                                      |
|------------------------------|--------|----------------------------------------------|
| `(case_id, event_date)`     | No     | Timeline: events for a case sorted by date   |
| `(case_id, firm_id)`        | No     | Tenant-scoped case events                    |
| `(firm_id)`                 | No     | List all firm events                         |
| `(document_id)`             | No     | Find events extracted from a document        |
| `(case_id, event_type)`     | No     | Filter events by type within a case          |

**StageTransition**: *(REMOVED — simplified, see section 7.2)*

**CaseResearch**:
| Fields                           | Unique | Purpose                                       |
|----------------------------------|--------|-----------------------------------------------|
| `(case_id, firm_id)`            | No     | Tenant-scoped research for a case             |
| `(firm_id)`                     | No     | List all firm research                        |
| `(case_id)`                     | No     | List research for a case                      |
| `(pinned_by_id)`                | No     | Find research pinned by a user                |
| `(case_id, relevance_score)`    | No     | Research sorted by relevance                  |

---

## 11. Tenant Isolation

### 11.1 Principle

Every model that holds firm-specific data MUST have:
1. A `firm_id: str` field
2. `__dataflow__ = { "multi_tenant": True }` (at minimum)

This ensures DataFlow's tenant isolation layer automatically filters all queries by `firm_id`.

### 11.2 Tenant-Scoped Models (MUST filter by firm_id)

| Model               | `multi_tenant` | Notes                                         |
|----------------------|:--------------:|-----------------------------------------------|
| User                 | Yes            | Users belong to exactly one firm              |
| Case                 | Yes            | Cases belong to exactly one firm              |
| Document             | Yes            | Documents belong to exactly one firm          |
| Conversation         | Yes            | Conversations belong to exactly one firm      |
| Message              | Yes            | Denormalized firm_id from Conversation        |
| RAGFeedback          | Yes            | Denormalized firm_id                          |
| EngagementMetrics    | Yes            | Denormalized firm_id                          |
| FirmKnowledge        | Yes            | Firm-specific knowledge                       |
| AuditEntry           | Yes            | Firm-scoped audit trail                       |
| **CaseEvent**        | Yes            | (NEW) Firm-scoped timeline events             |
| ~~**StageTransition**~~ | ~~Yes~~     | ~~(NEW) Firm-scoped stage history~~ (REMOVED — simplified) |
| **CaseResearch**     | Yes            | (NEW) Firm-scoped research findings           |

### 11.3 Shared Models (NOT tenant-scoped)

| Model             | `multi_tenant` | Notes                                           |
|-------------------|:--------------:|-------------------------------------------------|
| Firm              | No             | IS the tenant root entity                       |
| KnowledgeEntry    | No             | Shared case law knowledge base                  |
| KnowledgeVector   | No             | Shared embedding metadata                       |
| KGCitationEdge    | No             | Shared citation graph                           |
| KGJudge           | No             | Shared judge directory                          |
| KGCaseJudge       | No             | Shared judge-case join                          |
| KGCaseTopic       | No             | Shared topic classification                     |
| KGLegislationRef  | No             | Shared legislation references                   |
| SOPTemplate       | No             | Shared SOP templates                            |
| SOPUsageRecord    | No             | Shared usage metrics                            |

### 11.4 Isolation Rules

1. **Every Express query** on a multi-tenant model MUST include `firm_id` as a filter parameter. DataFlow enforces this via `TenantRequiredError` when `multi_tenant: True`.
2. **Cross-firm data access is never permitted**. There is no admin endpoint that bypasses tenant isolation.
3. **Denormalized firm_id**: Models like Message carry `firm_id` even though it could be derived from `Conversation.firm_id`. This is intentional -- it allows DataFlow to enforce tenant isolation without a join.
4. **Seed data** (section 12) is scoped to a single firm for development.

---

## 12. Seed Data

### 12.1 Seed Firm

| Field               | Value                                |
|---------------------|--------------------------------------|
| `id`                | `"firm-revlaw"`                      |
| `name`              | `"RevLaw LLC"`                       |
| `domain`            | `"revlaw.sg"`                        |
| `subscription_plan` | `"enterprise"`                       |
| `settings`          | `{}`                                 |
| `active`            | `True`                               |

### 12.2 Seed Users

All users belong to firm `"firm-revlaw"`. Passwords are bcrypt-hashed (cost factor 12).

| `id`            | `name`          | `email`                    | `role`     | Password (plaintext, for dev only) |
|-----------------|-----------------|----------------------------|------------|------------------------------------|
| `"user-suitong"`| `"Sui Tong"`    | `"suitong@revlaw.sg"`      | `"partner"`| `"password123"`                    |
| `"user-yikwee"` | `"Yik Wee"`     | `"yikwee@revlaw.sg"`       | `"partner"`| `"password123"`                    |
| `"user-admin"`  | `"Tech Admin"`  | `"admin@revlaw.sg"`        | `"admin"`  | `"password123"`                    |

**NOTE**: The plaintext passwords above are for development seed data only. In production, passwords MUST come from a secure onboarding flow.

### 12.3 Seed Script

Location: `src/legalcopilot/scripts/seed_users.py`

The seed script MUST be:

1. **Idempotent**: Running it multiple times produces the same result. It checks for existing records before creating.
2. **bcrypt-hashed**: Passwords are hashed with bcrypt (cost factor 12) before storage.
3. **Express API**: Uses `db.express.create()` for single-record operations.
4. **Tenant-aware**: All user operations include `firm_id`.

Pseudocode:

```python
import bcrypt
from legalcopilot.models import db

FIRM_ID = "firm-revlaw"

async def seed():
    # 1. Create firm (idempotent)
    existing_firm = await db.express.find_one("Firm", {"id": FIRM_ID})
    if not existing_firm:
        await db.express.create("Firm", {
            "id": FIRM_ID,
            "name": "RevLaw LLC",
            "domain": "revlaw.sg",
            "subscription_plan": "enterprise",
        })

    # 2. Create users (idempotent)
    users = [
        {"id": "user-suitong", "name": "Sui Tong", "email": "suitong@revlaw.sg", "role": "partner"},
        {"id": "user-yikwee", "name": "Yik Wee", "email": "yikwee@revlaw.sg", "role": "partner"},
        {"id": "user-admin", "name": "Tech Admin", "email": "admin@revlaw.sg", "role": "admin"},
    ]

    for user_data in users:
        existing = await db.express.find_one("User", {
            "firm_id": FIRM_ID,
            "email": user_data["email"],
        })
        if not existing:
            password_hash = bcrypt.hashpw(
                "password123".encode(), bcrypt.gensalt(rounds=12)
            ).decode()
            await db.express.create("User", {
                **user_data,
                "firm_id": FIRM_ID,
                "password_hash": password_hash,
                "active": True,
            })
```

---

## 13. Migration Notes

### 13.1 Changes Required (Summary)

| Change                          | File                                     | Type          |
|---------------------------------|------------------------------------------|---------------|
| Add `password_hash` to User     | `src/legalcopilot/models/core.py`        | Field addition |
| Add `draft` to Document file_type | `src/legalcopilot/models/core.py`      | Validation update |
| Add CaseEvent model             | `src/legalcopilot/models/core.py`        | New model      |
| ~~Add StageTransition model~~   | ~~`src/legalcopilot/models/core.py`~~    | ~~New model~~ (REMOVED — simplified) |
| Add CaseResearch model          | `src/legalcopilot/models/core.py`        | New model      |
| Register new models in __init__ | `src/legalcopilot/models/__init__.py`    | Import update  |
| Create seed script              | `src/legalcopilot/scripts/seed_users.py` | New file       |

### 13.2 DataFlow Migration

With `auto_migrate=True` on the DataFlow instance, schema changes are applied automatically on startup:

- New models create new tables
- New fields on existing models add columns with defaults
- Validation changes (like adding `draft` to `file_type`) require no schema migration -- validation is application-level

No manual migration scripts are needed for these changes.

### 13.3 Registration in __init__.py

After adding new models, update `src/legalcopilot/models/__init__.py`:

```python
from legalcopilot.models.core import (
    Case,
    CaseEvent,        # NEW
    CaseResearch,     # NEW
    Document,
    Firm,
    # StageTransition removed — simplified
    User,
)

__all__ = [
    "db",
    # Core
    "Firm",
    "User",
    "Case",
    "Document",
    "CaseEvent",        # NEW
    # "StageTransition" removed — simplified
    "CaseResearch",     # NEW
    # ... rest unchanged
]
```

### 13.4 Model Count Summary

| Category      | Existing | New | Total |
|---------------|----------|-----|-------|
| Core          | 4        | 2   | 6     |
| Conversation  | 4        | 0   | 4     |
| Knowledge     | 9        | 0   | 9     |
| Governance    | 1        | 0   | 1     |
| **Total**     | **18**   | **2** | **20** |

DataFlow generates 11 nodes per model (Create, Read, Update, Delete, List, Count, BulkCreate, BulkUpdate, BulkDelete, Search, Exists), yielding **231 auto-generated nodes** across all 21 models.
