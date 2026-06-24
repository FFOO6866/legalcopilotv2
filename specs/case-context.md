# Case Context Assembly

Domain specification for automatic case context construction, case-scoped RAG, cross-conversation memory, and draft persistence. This addresses the most architecturally significant gap in LegalCoPilot v2: the AI does not pull from prior case work when generating responses or drafts.

## Status

### Current state (broken)

1. **`send_message` accepts `case_context: str = "{}"`** (chat.py:181). The frontend must manually construct this JSON string. The backend passes it through to the orchestrator without enrichment. If the frontend sends `"{}"`, the AI has zero case awareness.

2. **Orchestrator receives `case_context` as an opaque string** (orchestrator.py:53-56). It PII-redacts the string and passes it to `self.run()` and specialist agents. It never queries the database for case materials, documents, timeline events, prior conversations, or prior drafts.

3. **Conversation model has `case_id` but it is not used to fetch case materials** (conversation.py:20). The field exists for organizational purposes (listing conversations by case) but the chat handler at chat.py:200-218 only fetches the last 20 messages from the current conversation -- never from sibling conversations on the same case.

4. **RAG pipeline searches by query text, not by case_id** (rag_pipeline.py:28-106). The `retrieve_context()` function accepts `filter_conditions` and `firm_id`, but no `case_id` filter. Document vectors in Qdrant carry `case_id` in their payload (document_processor.py:111-112), but this filter is never used. The RAG results mix the current case's documents with the entire knowledge base indiscriminately.

5. **`draft_document` also takes `case_context: str = "{}"`** (chat.py:503). Same problem: opaque string from frontend, no backend enrichment, no case awareness.

6. **No draft persistence**. When the AI generates a draft via `draft_document` or via the chat drafting agent, the result is returned to the frontend and lost. It is not saved as a Document record. A subsequent conversation cannot reference "the draft we generated earlier."

### What the brief requires

> "When generating a new document, AI pulls from ALL prior case work."

This means: every document summary, every conversation insight, every prior draft, every timeline event, every research finding -- all automatically assembled and injected into the LLM context when working on a case.

---

## Architecture Overview

```
Frontend sends message
    |
    v
chat.py: send_message(conversation_id, content, firm_id, ...)
    |
    |  1. Look up conversation -> get case_id
    |  2. If case_id exists:
    |     a. Call build_case_context(case_id, firm_id)
    |     b. Call build_case_context_text(case_id, firm_id, max_tokens=8000)
    |     c. Use this instead of frontend-provided case_context
    |
    v
orchestrator.process_request(request, case_context=<assembled>, ...)
    |
    |  The case_context now contains:
    |    - Case metadata (stage, practice_area, parties)
    |    - Document summaries
    |    - Timeline events (from chronology spec)
    |    - Prior conversation summaries
    |    - Prior draft references
    |    - Pinned research findings
    |
    v
Specialist agents (researcher, associate, drafter) receive rich context
```

---

## Case Context Assembly Service

**New file**: `src/legalcopilot/services/case_context.py`

### build_case_context()

Assembles the full structured context object for a case. Returns a dict that downstream consumers can inspect programmatically.

```python
def build_case_context(
    case_id: str,
    firm_id: str,
) -> dict:
    """Assemble complete structured context for a case.

    Args:
        case_id: Case to build context for.
        firm_id: Owning firm (tenant isolation on every query).

    Returns:
        {
            "case": { ... case metadata ... },
            "documents": [ ... document summaries ... ],
            "timeline": [ ... CaseEvent list sorted by date ... ],
            "conversations": [ ... conversation summaries ... ],
            "drafts": [ ... prior generated drafts ... ],
            "research": [ ... pinned research findings ... ],
            "assembled_at": "ISO 8601 timestamp",
            "source_counts": {
                "documents": 12,
                "timeline_events": 47,
                "conversations": 5,
                "drafts": 3,
                "research_findings": 0
            }
        }
    """
```

#### Section: `case` (metadata)

Source: `case_read` workflow.

```python
{
    "id": "...",
    "title": "Alpha Pte Ltd v Beta Corp",
    "practice_area": "contract",
    "case_type": "contract_dispute",
    "status": "in_progress",
    "stage": "analysis",
    "priority": "high",
    "client_name": "Alpha Pte Ltd",
    "opposing_party": "Beta Corp",
    "court": "SGHC",
    "filing_date": "2024-01-15",
    "tags": ["breach", "termination", "damages"],
    "description": "Breach of service agreement..."
}
```

#### Section: `documents` (summaries)

Source: `document_list` workflow, filter `case_id + firm_id`, all file types.

For each document, include a summary -- not the full text (that would blow the token budget). The summary is derived from `ocr_text` (first 500 chars as a preview) or from a pre-computed summary if one exists in `metadata`.

```python
[
    {
        "id": "doc-uuid-1",
        "filename": "Service_Agreement_v2.pdf",
        "file_type": "contract",
        "uploaded_at": "2024-06-01",
        "ocr_status": "complete",
        "summary": "Service agreement between Alpha Pte Ltd and Beta Corp dated 15 March 2024. Key terms: 24-month engagement, monthly retainer of $50,000, termination clause at Section 14...",
        "page_count_estimate": 12
    },
    {
        "id": "doc-uuid-2",
        "filename": "Notice_of_Termination.pdf",
        "file_type": "correspondence",
        "uploaded_at": "2024-06-03",
        "ocr_status": "complete",
        "summary": "Letter from Beta Corp to Alpha Pte Ltd dated 10 June 2024 purporting to terminate the Service Agreement under clause 14.2..."
    }
]
```

**Summary generation**: If `document.metadata.summary` exists (pre-computed), use it. Otherwise, truncate `ocr_text` to 500 chars at a sentence boundary. Future enhancement: run a summarization agent on upload to pre-compute summaries.

#### Section: `timeline` (chronological events)

Source: `caseevent_list` workflow (from chronology spec), sorted by `event_date ASC`.

```python
[
    {
        "event_date": "2024-03-15",
        "event_date_text": "15 March 2024",
        "description": "Service Agreement signed between Alpha and Beta",
        "significance": "high",
        "event_type": "contract_signed",
        "parties_involved": ["Alpha Pte Ltd", "Beta Corp"]
    },
    {
        "event_date": "2024-06-10",
        "event_date_text": "10 June 2024",
        "description": "Beta served notice of termination under clause 14.2",
        "significance": "critical",
        "event_type": "notice_served",
        "parties_involved": ["Beta Corp"]
    }
]
```

Only `critical` and `high` significance events included by default. Lower significance events included only if token budget allows.

#### Section: `conversations` (prior conversation summaries)

Source: `conversation_list` workflow, filter `case_id + firm_id`, status `active` or `closed`. For each conversation, fetch recent messages and summarize.

```python
[
    {
        "conversation_id": "conv-uuid-1",
        "title": "Initial case analysis",
        "type": "analysis",
        "status": "closed",
        "created_at": "2024-06-01",
        "message_count": 14,
        "summary": "Discussed breach of contract issues. Key findings: Alpha has strong position on termination clause. Recommended demanding specific performance before damages claim.",
        "key_conclusions": [
            "Termination clause 14.2 requires 60-day notice",
            "Beta gave only 15 days notice -- prima facie breach",
            "Recommend letter of demand before filing"
        ]
    }
]
```

**Summary generation strategy**:
1. Fetch the last 5 assistant messages from the conversation.
2. If conversation is `closed`, look for a final summary message (agent_name contains "summary" or the last message is a wrap-up).
3. If no pre-computed summary, concatenate the last 3 assistant messages and truncate to 500 chars.
4. Future enhancement: run a summarization agent on conversation close.

#### Section: `drafts` (prior AI-generated drafts)

Source: `document_list` workflow, filter `case_id + firm_id + file_type="draft"`.

```python
[
    {
        "id": "draft-uuid-1",
        "filename": "Letter_of_Demand_v1_draft.md",
        "file_type": "draft",
        "created_at": "2024-06-05",
        "summary": "Letter of demand to Beta Corp for breach of Service Agreement. Demands compliance within 14 days. Cites clauses 14.2, 18.1...",
        "template_used": "letter_of_demand",
        "word_count_estimate": 850
    }
]
```

#### Section: `research` (pinned research findings)

Source: Messages with `role="assistant"` and `agent_name="researcher"` across all case conversations, where `rag_context` is non-empty.

For v1, this is a best-effort extraction. The research agent's responses contain structured `relevant_cases` and `applicable_statutes` in their output. We extract and deduplicate these.

```python
[
    {
        "topic": "Termination clause enforceability",
        "key_cases": [
            {"citation": "[2023] SGHC 45", "case_name": "Foo v Bar", "relevance": "Applied similar notice period requirement"}
        ],
        "key_statutes": [
            {"statute": "Contracts Act", "section": "s.14", "relevance": "Notice requirements"}
        ],
        "summary": "Case law supports position that 60-day notice is a condition precedent to valid termination."
    }
]
```

---

### build_case_context_text()

Serializes the structured context into a token-budgeted text string suitable for LLM injection.

```python
def build_case_context_text(
    case_id: str,
    firm_id: str,
    max_tokens: int = 8000,
) -> str:
    """Serialize case context into a token-budgeted text for LLM injection.

    Args:
        case_id: Case ID.
        firm_id: Owning firm.
        max_tokens: Maximum token budget for the assembled text.

    Returns:
        Formatted text string within the token budget.

    Token budget allocation (priority order):
        1. Case metadata:        ~300 tokens  (always included in full)
        2. Timeline events:      ~2000 tokens (critical + high first)
        3. Recent drafts:        ~1500 tokens (most recent 3 drafts)
        4. Document summaries:   ~2000 tokens (by recency)
        5. Conversation summaries: ~1500 tokens (most recent 3 conversations)
        6. Research findings:    ~700 tokens  (if budget remains)

    Priority ranking rationale:
        - Case metadata is always needed (tiny, always fits)
        - Timeline is the factual backbone -- the LLM needs chronology
          to reason about causation, limitation periods, notice deadlines
        - Recent drafts show what has already been produced -- prevents
          the LLM from re-drafting the same document or contradicting it
        - Document summaries provide the evidentiary landscape
        - Conversation summaries capture prior reasoning and conclusions
        - Research findings are lowest priority because the RAG pipeline
          independently retrieves relevant law per-query
    """
```

#### Token budget algorithm

```python
def _allocate_budget(context: dict, max_tokens: int) -> str:
    """Allocate token budget across context sections by priority.

    Each section has:
        - priority (1 = highest)
        - min_tokens (guaranteed allocation if content exists)
        - content items (sorted by relevance within section)

    Algorithm:
        1. Allocate min_tokens to each section that has content
        2. Distribute remaining tokens to sections in priority order
        3. Within each section, include items by relevance until budget exhausted
        4. Truncate the last item at a sentence boundary if partial
    """

    BUDGET_PLAN = [
        {"section": "case",          "priority": 1, "min_tokens": 200,  "max_tokens": 500},
        {"section": "timeline",      "priority": 2, "min_tokens": 500,  "max_tokens": 3000},
        {"section": "drafts",        "priority": 3, "min_tokens": 300,  "max_tokens": 2000},
        {"section": "documents",     "priority": 4, "min_tokens": 400,  "max_tokens": 2500},
        {"section": "conversations", "priority": 5, "min_tokens": 300,  "max_tokens": 2000},
        {"section": "research",      "priority": 6, "min_tokens": 0,    "max_tokens": 1000},
    ]
    # ...
```

#### Output format

The serialized text follows a structured template:

```
=== CASE CONTEXT ===

## Case: Alpha Pte Ltd v Beta Corp
- Practice Area: Contract
- Type: Contract Dispute
- Status: In Progress (Analysis stage)
- Client: Alpha Pte Ltd
- Opposing Party: Beta Corp
- Court: SGHC
- Filed: 15 January 2024

## Timeline (12 events, showing 8 most significant)
- 15 Mar 2024: Service Agreement signed between Alpha and Beta [HIGH]
- 01 May 2024: Alpha reported performance issues to Beta [MEDIUM]
- 10 Jun 2024: Beta served notice of termination under clause 14.2 [CRITICAL]
- 25 Jun 2024: Alpha contested termination as invalid -- insufficient notice [CRITICAL]
...

## Prior Drafts (3 drafts)
- Letter of Demand v1 (05 Jun 2024): Demands compliance within 14 days, cites clauses 14.2, 18.1...
- Legal Memo -- Termination Analysis (08 Jun 2024): IRAC analysis of termination validity...
...

## Documents (12 documents)
- Service_Agreement_v2.pdf (contract): Key terms include 24-month engagement, monthly retainer...
- Notice_of_Termination.pdf (correspondence): Letter from Beta dated 10 June 2024...
- Email_Chain_May2024.pdf (correspondence): Exchange between parties re: performance concerns...
...

## Prior Conversations (5 conversations, showing 3 most recent)
- "Initial case analysis" (01 Jun 2024, closed): Discussed breach issues. Key conclusion: Alpha has strong position on termination clause.
- "Damages quantum research" (07 Jun 2024, closed): Researched damages for wrongful termination. Found [2023] SGHC 45 supporting liquidated damages claim.
...

## Research Findings
- Termination clause enforceability: [2023] SGHC 45 (Foo v Bar) -- applied similar notice period. Contracts Act s.14.
...

=== END CASE CONTEXT ===
```

---

## Wiring into Existing Handlers

### send_message (chat.py:~175-297)

**Current behavior** (chat.py:181): Accepts `case_context: str = "{}"` from the frontend and passes it through.

**New behavior**:

```python
@app.handler("send_message", description="Send a message and get AI response")
async def send_message(
    conversation_id: str,
    content: str,
    firm_id: str = "",
    user_id: str = "",
    case_context: str = "{}",  # kept for backward compatibility
) -> dict:
    # ... existing validation ...

    # Verify conversation belongs to the requesting firm
    conv_results = _execute_workflow("conversation_read", {"id": conversation_id})
    conv = conv_results.get("result")
    # ... existing firm_id check ...

    # --- NEW: Auto-build case context if conversation is bound to a case ---
    effective_case_context = case_context
    case_id = conv.get("case_id")
    if case_id:
        try:
            from legalcopilot.services.case_context import build_case_context_text
            effective_case_context = build_case_context_text(
                case_id=case_id,
                firm_id=firm_id,
                max_tokens=8000,
            )
            logger.info(
                "Built case context for case %s: %d chars",
                case_id, len(effective_case_context),
            )
        except Exception:
            logger.warning(
                "Failed to build case context for case %s, falling back to frontend-provided",
                case_id,
            )
    # --- END NEW ---

    # ... existing conversation history fetch ...

    orchestrator = _get_orchestrator()
    result = orchestrator.process_request(
        request=content,
        case_context=effective_case_context,  # was: case_context
        conversation_history=conversation_history,
    )
    # ... rest unchanged ...
```

**Backward compatibility**: If the conversation has no `case_id`, or if context assembly fails, the frontend-provided `case_context` string is used as a fallback. The frontend no longer needs to assemble case context, but existing frontend code that sends `case_context` still works.

### draft_document (chat.py:~494-553)

**Current behavior** (chat.py:503): Accepts `case_context: str = "{}"` and passes it to the drafter.

**New behavior**:

```python
@app.handler("draft_document", description="Draft a legal document using AI")
async def draft_document(
    document_type: str,
    instructions: str,
    firm_id: str = "",
    user_id: str = "",
    case_id: str = "",
    case_type: str = "general",
    facts: str = "",
    case_context: str = "{}",
    tone: str = "formal",
) -> dict:
    # ... existing validation ...

    # --- NEW: Auto-build case context if case_id is provided ---
    effective_case_context = case_context
    if case_id:
        try:
            from legalcopilot.services.case_context import build_case_context_text
            effective_case_context = build_case_context_text(
                case_id=case_id,
                firm_id=firm_id,
                max_tokens=8000,
            )
        except Exception:
            logger.warning(
                "Failed to build case context for draft, case %s", case_id
            )
    # --- END NEW ---

    # ... existing SOP + RAG logic, using effective_case_context ...

    drafter = DraftingAgent()
    result = drafter.draft(
        document_type=document_type,
        instructions=clean_instructions,
        facts=clean_facts,
        rag_context=rag_result["context_text"],
        tone=tone,
    )

    # --- NEW: Persist draft as a Document record ---
    draft_record = None
    if case_id and result.get("draft_text"):
        try:
            draft_record = _persist_draft(
                case_id=case_id,
                firm_id=firm_id,
                user_id=user_id,
                document_type=document_type,
                draft_text=result["draft_text"],
                case_type=case_type,
            )
        except Exception:
            logger.warning("Failed to persist draft for case %s", case_id)
    # --- END NEW ---

    response = {
        "document_type": document_type,
        "case_type": validated_case_type,
        "sop_template": sop.get("name", ""),
        "draft": result,
        "sources": rag_result["sources"],
    }
    if draft_record:
        response["saved_document"] = draft_record

    return response
```

---

## Draft Persistence

When the AI generates a draft (via `draft_document` or via the orchestrator's drafting agent in a chat), the draft is saved as a Document record so it becomes part of the case's permanent record and feeds back into future case context.

### _persist_draft() helper

```python
def _persist_draft(
    case_id: str,
    firm_id: str,
    user_id: str,
    document_type: str,
    draft_text: str,
    case_type: str = "general",
) -> dict:
    """Save an AI-generated draft as a Document record.

    The draft is stored inline (ocr_text field) rather than uploaded to S3.
    This keeps it immediately searchable and context-assemblable without
    a separate storage fetch.

    Args:
        case_id: Parent case.
        firm_id: Owning firm.
        user_id: User who requested the draft.
        document_type: e.g. "letter_of_demand", "advice_note".
        draft_text: The complete draft content.
        case_type: For filename generation.

    Returns:
        The created Document record dict.
    """
    import uuid
    from datetime import datetime

    doc_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{document_type}_{timestamp}_draft.md"

    data = {
        "id": doc_id,
        "case_id": case_id,
        "firm_id": firm_id,
        "uploaded_by_id": user_id,
        "filename": filename,
        "file_type": "draft",
        "storage_url": "",                      # stored inline, not in S3
        "file_size_bytes": len(draft_text.encode("utf-8")),
        "classification": {
            "document_type": document_type,
            "generated_by": "ai",
            "case_type": case_type,
        },
        "ocr_text": draft_text[:50_000],        # MAX_OCR_TEXT_CHARS from document_processor
        "ocr_status": "complete",               # already "processed" -- it's text
        "metadata": {
            "is_ai_draft": True,
            "draft_version": 1,
            "document_type": document_type,
            "generated_at": datetime.utcnow().isoformat(),
        },
    }

    workflows = _get_workflows()
    wf = workflows["document_create"]
    with LocalRuntime() as runtime:
        results, _ = runtime.execute(wf.build(), inputs={"data": data})

    doc_record = results.get("result", data)

    # Trigger vectorization so the draft is searchable via RAG
    try:
        from legalcopilot.services.document_processor import process_document
        process_document(
            document_id=doc_id,
            case_id=case_id,
            firm_id=firm_id,
            text=draft_text,
        )
    except Exception:
        logger.warning("Draft vectorization failed for %s, draft still saved", doc_id)

    return doc_record
```

### Draft in chat flow

When the orchestrator's `_execute_specialists()` invokes the drafting agent during a chat conversation (orchestrator.py:285-312), the draft result is embedded in the chat response. To persist it, the `send_message` handler inspects the orchestrator result:

```python
# In send_message, after orchestrator.process_request():
result = orchestrator.process_request(...)

# Persist any drafts generated during the chat
case_id = conv.get("case_id")
if case_id and isinstance(result.get("response"), dict):
    draft_content = result["response"].get("draft", {}).get("draft_text", "")
    if draft_content:
        try:
            doc_type = result["response"].get("draft", {}).get("document_type", "advice_note")
            _persist_draft(
                case_id=case_id,
                firm_id=firm_id,
                user_id=user_id,
                document_type=doc_type,
                draft_text=draft_content,
            )
        except Exception:
            logger.warning("Failed to persist chat-generated draft for case %s", case_id)
```

---

## Case-Scoped RAG

### Problem

The current `retrieve_context()` in `rag_pipeline.py` searches the entire Qdrant collection. Document vectors carry `case_id` in their payload (set by `document_processor.py:112`), but this is never filtered on. When a user asks a question about Case A, the RAG results may include chunks from Case B's documents, which is both a privacy concern (cross-case data leakage within a firm) and a relevance problem.

### Solution: retrieve_case_context()

**Add to**: `src/legalcopilot/services/rag_pipeline.py`

```python
def retrieve_case_context(
    query: str,
    case_id: str,
    firm_id: str,
    top_k: int = 10,
    token_budget: Optional[int] = None,
    include_general: bool = True,
    general_ratio: float = 0.3,
) -> dict:
    """Case-scoped RAG retrieval -- prioritizes current case's documents.

    Args:
        query: User's question or search text.
        case_id: Current case ID -- used as a Qdrant payload filter.
        firm_id: Owning firm.
        top_k: Total results to return.
        token_budget: Max tokens for assembled context.
        include_general: Also search the general knowledge base (case law, statutes).
        general_ratio: Proportion of top_k allocated to general results (0.3 = 30%).

    Returns:
        Same shape as retrieve_context(): {context_text, sources, token_count, truncated}

    Strategy:
        1. Search case-specific vectors: filter {case_id: case_id, firm_id: firm_id}
           - Allocate (1 - general_ratio) * top_k slots
        2. Search general knowledge base: existing behavior (no case_id filter)
           - Allocate general_ratio * top_k slots
        3. Search firm-specific knowledge: existing behavior
           - Allocate from general slots
        4. Merge, deduplicate, prioritize, token-budget as before
    """
    token_budget = token_budget or int(settings.get("RAG_TOKEN_BUDGET", "6000"))

    query_vector = embed_text(query)

    # Case-specific document search
    case_limit = max(3, int(top_k * (1 - general_ratio)))
    case_results = vector_search(
        query_vector=query_vector,
        limit=case_limit,
        score_threshold=0.25,  # lower threshold for case docs (always relevant)
        filter_conditions={"case_id": case_id, "firm_id": firm_id},
    )

    # General knowledge base search (case law, statutes)
    general_results = []
    if include_general:
        general_limit = max(3, int(top_k * general_ratio))
        general_results = vector_search(
            query_vector=query_vector,
            limit=general_limit,
            score_threshold=0.3,
            filter_conditions={"jurisdiction": "SG"},
        )
        # Exclude firm-private and case-specific vectors from general results
        general_results = [
            r for r in general_results
            if r.get("payload", {}).get("type") != "firm_knowledge"
            and r.get("payload", {}).get("case_id") != case_id
        ]

    # Firm-specific knowledge
    firm_results = []
    if firm_id:
        firm_limit = max(2, top_k // 5)
        firm_results = vector_search(
            query_vector=query_vector,
            limit=firm_limit,
            score_threshold=0.3,
            filter_conditions={"firm_id": firm_id, "type": "firm_knowledge"},
        )

    # Merge all results
    all_results = _merge_case_results(case_results, general_results, firm_results, top_k)

    if not all_results:
        return {"context_text": "", "sources": [], "token_count": 0, "truncated": False}

    # Enrich with KG (only for general results that have entry_id)
    if include_general:
        all_results = _enrich_with_kg(all_results)

    prioritized = _prioritize_results(all_results)
    context_chunks, sources, was_truncated = _allocate_token_budget(prioritized, token_budget)
    context_text = _assemble_context(context_chunks)
    token_count = _estimate_tokens(context_text)

    return {
        "context_text": context_text,
        "sources": sources,
        "token_count": token_count,
        "truncated": was_truncated,
    }
```

```python
def _merge_case_results(
    case_results: list[dict],
    general_results: list[dict],
    firm_results: list[dict],
    max_total: int,
) -> list[dict]:
    """Merge case-specific, general, and firm results.

    Case-specific results get a relevance boost (they are from the current case's
    own documents, so even a lower semantic score is highly relevant).
    """
    # Boost case-specific scores
    for r in case_results:
        r["_source"] = "case"
        r["score"] = min(1.0, r.get("score", 0) + 0.15)  # relevance boost

    for r in general_results:
        r["_source"] = "general"

    for r in firm_results:
        r["_source"] = "firm"

    # Combine and sort by boosted score
    all_results = case_results + general_results + firm_results
    all_results.sort(key=lambda r: r.get("score", 0), reverse=True)

    # Deduplicate by id
    seen_ids = set()
    merged = []
    for r in all_results:
        rid = r.get("id", "")
        if rid and rid in seen_ids:
            continue
        seen_ids.add(rid)
        merged.append(r)
        if len(merged) >= max_total:
            break

    return merged
```

### Wiring case-scoped RAG into the orchestrator

In the orchestrator's `process_request()` (orchestrator.py:97-100), replace the current `retrieve_context()` call:

```python
# Current (orchestrator.py:97):
rag_result = retrieve_context(
    query=rag_query,
    filter_conditions={"jurisdiction": "SG"},
)

# New:
case_context_dict = json.loads(clean_case_context) if clean_case_context != "{}" else {}
context_case_id = case_context_dict.get("case", {}).get("id", "")

if context_case_id:
    from legalcopilot.services.rag_pipeline import retrieve_case_context
    rag_result = retrieve_case_context(
        query=rag_query,
        case_id=context_case_id,
        firm_id=case_context_dict.get("case", {}).get("firm_id", ""),
        top_k=10,
    )
else:
    rag_result = retrieve_context(
        query=rag_query,
        filter_conditions={"jurisdiction": "SG"},
    )
```

**Alternatively**, the `case_id` and `firm_id` can be passed as explicit parameters to `process_request()` rather than parsed from the context string. This is cleaner:

```python
def process_request(
    self,
    request: str,
    case_context: str = "{}",
    conversation_history: str = "[]",
    case_id: str = "",            # NEW
    firm_id: str = "",            # NEW
) -> dict:
```

---

## Cross-Conversation Memory

### Problem

The current `send_message` handler fetches only the last 20 messages from the current conversation (chat.py:203-218). If a case has 5 conversations, the AI in conversation #5 has zero awareness of what was discussed in conversations #1-4.

### Solution

Cross-conversation memory is handled by the case context assembly, not by expanding the message history window. The `conversations` section of `build_case_context()` summarizes prior conversations. This approach is token-efficient: instead of injecting 100+ raw messages from 5 conversations, inject 5 conversation summaries at ~100 tokens each.

#### Current conversation history (unchanged)

The existing 20-message window for the current conversation provides turn-by-turn dialogue context. This stays as-is.

#### Prior conversation context (new, via case context)

The `conversations` section in the assembled case context provides awareness of prior work. The AI knows:
- What topics were discussed
- What conclusions were reached
- What was recommended
- What drafts were produced

This is injected as part of the `case_context` parameter, not as part of `conversation_history`.

### Conversation summarization

When a conversation is closed (via `close_conversation` handler at chat.py:444-489), generate a summary:

```python
# In close_conversation, after updating status to "closed":

# NEW: Generate conversation summary for cross-conversation memory
try:
    summary = _summarize_conversation(conversation_id, firm_id)
    _execute_workflow(
        "conversation_update",
        {
            "filter": {"id": conversation_id, "firm_id": firm_id},
            "fields": {
                "metadata": {
                    **conv.get("metadata", {}),
                    "summary": summary["summary"],
                    "key_conclusions": summary["key_conclusions"],
                    "summarized_at": datetime.utcnow().isoformat(),
                }
            },
        },
    )
except Exception:
    logger.warning("Failed to summarize conversation %s", conversation_id)
```

The `_summarize_conversation()` function uses a lightweight Kaizen agent:

```python
class ConversationSummarySignature(Signature):
    """Summarize a legal conversation for cross-conversation context.

    Produce a 2-3 sentence summary and a list of key conclusions/decisions.
    Focus on: what was decided, what was recommended, what was drafted,
    what open questions remain.
    """

    messages: str = InputField(description="JSON array of conversation messages")
    case_context: str = InputField(description="Case metadata for context", default="{}")

    summary: str = OutputField(description="2-3 sentence summary of the conversation")
    key_conclusions: list = OutputField(
        description="JSON array of key conclusions, decisions, or recommendations"
    )
```

### Token budgeting for cross-conversation memory

| Source | Token allocation | Rationale |
|--------|-----------------|-----------|
| Current conversation (20 messages) | ~4000 tokens (separate from case context budget) | Turn-by-turn dialogue context. Handled by existing `conversation_history` parameter. |
| Prior conversation summaries | ~1500 tokens (within case context budget) | High-level awareness of prior work. 3 conversations x 500 tokens each. |
| Timeline events | ~2000 tokens (within case context budget) | Factual backbone. |
| Document summaries | ~2000 tokens (within case context budget) | Evidentiary landscape. |
| Recent drafts | ~1500 tokens (within case context budget) | What has already been produced. |

**Total effective context for a case-bound message**: ~4000 (current conversation) + ~8000 (case context) = ~12000 tokens of context. With a typical 128K context window model, this leaves ample room for the RAG results (~6000 tokens) and the LLM's response.

---

## Edge Cases

### No case_id on conversation

If a conversation has no `case_id` (standalone/general conversation), the `send_message` handler skips case context assembly entirely. The frontend-provided `case_context` string (default `"{}"`) is used as-is. No behavioral change for general conversations.

### Case with no documents

`build_case_context()` returns empty arrays for `documents`, `timeline`, and `drafts`. The case metadata section is still populated. The LLM receives minimal context but is aware of the case's basic facts (title, parties, practice area, stage).

### Case with no prior conversations

`conversations` section is empty. No cross-conversation memory. First conversation on a case still benefits from document summaries and timeline events.

### Very large cases (50+ documents, 200+ events, 10+ conversations)

The token budget algorithm handles this by prioritization and truncation:
- Only `critical` and `high` significance timeline events (until budget fills)
- Only the 3 most recent conversations (by `updated_at`)
- Only the 3 most recent drafts
- Document summaries truncated to 200 chars each if there are more than 20 documents

### Context assembly latency

`build_case_context()` issues multiple DataFlow queries:
- 1x case_read
- 1x document_list
- 1x caseevent_list
- 1x conversation_list
- Nx message_list (one per conversation for summary, capped at 3)
- 1x document_list (draft filter)

Estimated latency: 50-200ms (SQLite) or 20-80ms (PostgreSQL). Acceptable for a chat interaction where the LLM call itself takes 2-10s.

**Caching strategy** (future): Cache the assembled context per case_id with a 60s TTL. Invalidate on document upload, event creation, or conversation close.

### Race condition: context assembly during document upload

If a user uploads a document and immediately sends a message, the document may not yet be processed (ocr_status: "pending"). The context assembly includes documents regardless of `ocr_status`, but the summary for pending documents is "(processing...)". This is acceptable -- the next message will include the processed document.

### Draft versioning

When the user requests a second draft of the same document type, the persisted draft gets a new `metadata.draft_version` (incremented from the highest existing version for that document_type + case_id). The filename includes the version: `letter_of_demand_v2_20240605_143000_draft.md`.

Prior drafts remain in the documents list and appear in the case context. The LLM can see "Letter of Demand v1" and "Letter of Demand v2" and understand the progression.

### Privacy: cross-case isolation

The case context assembly enforces tenant isolation at every query:
- Every DataFlow query includes `firm_id` in the filter
- `retrieve_case_context()` filters Qdrant by both `case_id` and `firm_id`
- A user working on Case A never sees documents, events, or conversations from Case B

Within a firm, cross-case isolation is maintained by the `case_id` filter. A firm's general knowledge (via `firm_knowledge` vectors) is shared across cases within that firm -- this is intentional.

---

## Frontend Changes

### Remove case_context construction

The frontend currently constructs the `case_context` JSON string before calling `send_message` or `draft_document`. This logic can be removed:

```typescript
// BEFORE (frontend had to build context):
const caseContext = JSON.stringify({
    practice_area: currentCase.practice_area,
    status: currentCase.status,
    // ... manually assembled ...
});
await sendMessage(conversationId, content, firmId, userId, caseContext);

// AFTER (backend builds it automatically):
await sendMessage(conversationId, content, firmId, userId);
// case_context parameter can be omitted or sent as "{}"
```

### Draft save indicator

When `draft_document` returns a `saved_document` field, the frontend should show:
- A toast: "Draft saved to case documents"
- A link to the saved document in the Documents tab
- The draft appears in the Documents list with `file_type: "draft"` badge

### Case context indicator (optional UX enhancement)

Show a small indicator in the chat UI when a conversation is case-bound:
- "Using context from 12 documents, 47 events, 3 prior conversations"
- Expandable to show the context sources

---

## Implementation Order

1. **Case context assembly service** -- `services/case_context.py` with `build_case_context()` and `build_case_context_text()`
2. **Wire into send_message** -- auto-build context when conversation has case_id
3. **Wire into draft_document** -- auto-build context when case_id provided
4. **Draft persistence** -- `_persist_draft()` helper, save drafts as Document records
5. **Document.file_type extension** -- add `"draft"` to validation (also in chronology spec)
6. **Case-scoped RAG** -- `retrieve_case_context()` in rag_pipeline.py
7. **Conversation summarization** -- generate summaries on conversation close
8. **ConversationSummarySignature** -- add to agents/signatures.py
9. **Wire case-scoped RAG into orchestrator** -- replace generic retrieve_context when case_id present
10. **Frontend cleanup** -- remove client-side context assembly, add draft save indicator

---

## Knowledge Graph Integration

The existing knowledge graph service (`src/legalcopilot/services/knowledge_graph.py`) exposes structured legal research endpoints -- `search_cases`, `get_citations`, and `search_legislation` -- that return structured citation data from Singapore case law and statutes. These endpoints are currently used only by the frontend's Research tab. This section wires them into the PDCA orchestrator's research agent so that case context assembly benefits from structured citation lookup, not just vector search.

### Wiring into the Research Agent

The orchestrator's research agent (invoked during the PDCA cycle when `routing.research == True`) currently relies solely on the RAG pipeline (`retrieve_context` / `retrieve_case_context`) for legal research. The knowledge graph endpoints provide higher-precision results for structured queries (specific case citations, statute sections, court hierarchies) that vector search handles poorly.

**Integration approach:**

1. The research agent calls KG endpoints for structured citation lookup alongside (not instead of) vector search.
2. KG results are merged into the case context assembly under the `research` key.
3. KG results are ranked by relevance to the current case's `practice_area` and `jurisdiction` (Singapore).

### build_case_context() Enhancement

The `research` section of `build_case_context()` is enhanced to include KG results:

```python
# In build_case_context(), after assembling the research section from
# conversation messages with agent_name="researcher":

# Enrich research findings with knowledge graph data
try:
    from legalcopilot.services.knowledge_graph import (
        search_cases,
        get_citations,
        search_legislation,
    )

    case_record = context["case"]
    practice_area = case_record.get("practice_area", "general")
    case_title = case_record.get("title", "")
    case_description = case_record.get("description", "")

    # Search for relevant case law via KG
    kg_cases = search_cases(
        query=case_description or case_title,
        practice_area=practice_area,
        jurisdiction="SG",
        limit=10,
    )

    # Search for relevant legislation via KG
    kg_legislation = search_legislation(
        query=case_description or case_title,
        practice_area=practice_area,
        jurisdiction="SG",
        limit=10,
    )

    # Merge KG results into research findings, deduplicating by citation
    existing_citations = {
        finding.get("citation", "")
        for finding in context.get("research", [])
        for case_ref in finding.get("key_cases", [])
        if (citation := case_ref.get("citation"))
    }

    kg_research = []
    for kg_case in kg_cases:
        citation = kg_case.get("citation", "")
        if citation and citation not in existing_citations:
            kg_research.append({
                "source": "knowledge_graph",
                "citation": citation,
                "case_name": kg_case.get("case_name", ""),
                "court": kg_case.get("court", ""),
                "relevance_score": kg_case.get("relevance_score", 0.0),
                "summary": kg_case.get("summary", ""),
            })
            existing_citations.add(citation)

    kg_statutes = []
    for statute in kg_legislation:
        kg_statutes.append({
            "source": "knowledge_graph",
            "statute": statute.get("statute_name", ""),
            "section": statute.get("section", ""),
            "relevance_score": statute.get("relevance_score", 0.0),
            "summary": statute.get("summary", ""),
        })

    # Append KG findings to the research section
    if kg_research or kg_statutes:
        context["research"].append({
            "topic": f"Knowledge graph results for {practice_area}",
            "key_cases": kg_research,
            "key_statutes": kg_statutes,
            "summary": f"Structured citation lookup via knowledge graph: "
                       f"{len(kg_research)} cases, {len(kg_statutes)} statutes.",
        })
        context["source_counts"]["kg_cases"] = len(kg_research)
        context["source_counts"]["kg_statutes"] = len(kg_statutes)

except Exception:
    logger.warning("Knowledge graph enrichment failed for case %s", case_id)
```

### KG Result Priority

KG results are ranked by relevance to the current case using:

1. **Practice area match**: Cases and statutes tagged with the same `practice_area` as the current case are ranked higher.
2. **Jurisdiction match**: Singapore (`SG`) jurisdiction results are prioritized. Foreign jurisdiction results are included only if the case's `tags` or `metadata` indicate a cross-jurisdictional matter.
3. **Recency**: More recent judgments are ranked higher within the same relevance tier.
4. **Citation frequency**: Cases cited more frequently across the knowledge graph are ranked higher (a proxy for authority).

### Token Budget Impact

KG results share the `research` section's token budget (~700 tokens in `build_case_context_text`). When KG results are present, the budget allocation is:

- Conversation-derived research findings: ~400 tokens (priority -- these are curated by prior agent interactions).
- KG-derived research findings: ~300 tokens (supplementary structured citations).

If no conversation-derived research exists, KG results can use the full ~700 token allocation.

---

## Dependencies

- **chronology spec** (`specs/chronology.md`): The `timeline` section of case context requires CaseEvent model and `build_case_timeline()` service.
- **Document model change**: Adding `"draft"` to `file_type` validation is shared between this spec and the chronology spec.
- **Conversation model**: No schema change needed. Summaries stored in the existing `metadata` dict field.
- **Qdrant payload**: Document vectors already carry `case_id` (set by document_processor.py:112). No Qdrant schema change needed for case-scoped RAG.
- **Knowledge graph service**: `src/legalcopilot/services/knowledge_graph.py` must expose `search_cases`, `get_citations`, and `search_legislation` functions. These already exist for the Research tab frontend.
