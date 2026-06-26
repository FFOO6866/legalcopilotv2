"""Case context assembly — build rich context for AI from all case materials.

Gathers case metadata, documents, timeline events, conversations, and drafts
into a structured context dict, then serializes to a token-budgeted text string
for LLM injection.
"""

import json
import logging
from datetime import datetime, timezone

from kailash import LocalRuntime
from legalcopilot.models.database import db

logger = logging.getLogger(__name__)

_workflows = None


def _get_workflows() -> dict:
    global _workflows
    if _workflows is None:
        _workflows = db.get_workflows()
    return _workflows


def _execute(workflow_key: str, inputs: dict) -> dict:
    workflows = _get_workflows()
    wf = workflows.get(workflow_key)
    if wf is None:
        logger.warning("Workflow '%s' not found", workflow_key)
        return {}
    with LocalRuntime() as runtime:
        results, _ = runtime.execute(wf.build(), inputs=inputs)
    return results


def build_case_context(case_id: str, firm_id: str) -> dict:
    """Assemble complete structured context for a case.

    Returns a dict with sections: case, documents, timeline,
    conversations, drafts, research, assembled_at, source_counts.
    """
    # 1. Case metadata
    case_results = _execute("case_read", {"id": case_id})
    case_record = case_results.get("result")
    if case_record is None or case_record.get("firm_id") != firm_id:
        return {"error": "Case not found", "case_id": case_id}

    case_meta = {
        "id": case_record.get("id"),
        "title": case_record.get("title", ""),
        "practice_area": case_record.get("practice_area", ""),
        "case_type": case_record.get("case_type", ""),
        "status": case_record.get("status", ""),
        "stage": case_record.get("stage", ""),
        "priority": case_record.get("priority", ""),
        "client_name": case_record.get("client_name", ""),
        "opposing_party": case_record.get("opposing_party", ""),
        "court": case_record.get("court", ""),
        "filing_date": case_record.get("filing_date", ""),
        "tags": case_record.get("tags", []),
        "description": case_record.get("description", ""),
    }

    # 2. Documents (summaries)
    doc_results = _execute(
        "document_list",
        {"filter": {"case_id": case_id, "firm_id": firm_id}, "limit": 50, "offset": 0},
    )
    all_docs = doc_results.get("result", [])
    documents = []
    drafts = []
    for doc in all_docs:
        summary = _get_document_summary(doc)
        entry = {
            "id": doc.get("id"),
            "filename": doc.get("filename", ""),
            "file_type": doc.get("file_type", ""),
            "uploaded_at": doc.get("created_at", ""),
            "ocr_status": doc.get("ocr_status", ""),
            "summary": summary,
        }
        if doc.get("file_type") == "draft" or doc.get("filename", "").endswith("_draft.md"):
            drafts.append(entry)
        else:
            documents.append(entry)

    # 3. Timeline events
    timeline = []
    try:
        event_results = _execute(
            "caseevent_list",
            {"filter": {"case_id": case_id, "firm_id": firm_id}, "limit": 100, "offset": 0},
        )
        events = event_results.get("result", [])
        # Sort by event_date, significance
        sig_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        events.sort(
            key=lambda e: (
                e.get("event_date", ""),
                sig_order.get(e.get("significance", "medium"), 2),
            )
        )
        for evt in events:
            timeline.append(
                {
                    "event_date": evt.get("event_date", ""),
                    "event_date_text": evt.get("event_date_text", ""),
                    "description": evt.get("description", ""),
                    "significance": evt.get("significance", "medium"),
                    "event_type": evt.get("event_type", "general"),
                    "parties_involved": evt.get("parties_involved", []),
                }
            )
    except Exception:
        logger.warning("Could not fetch timeline events for case %s", case_id)

    # 4. Conversations
    conversations = []
    try:
        conv_results = _execute(
            "conversation_list",
            {"filter": {"case_id": case_id, "firm_id": firm_id}, "limit": 20, "offset": 0},
        )
        convs = conv_results.get("result", [])
        # Only fetch message summaries for the 3 most recent conversations to avoid N+1
        for i, conv in enumerate(convs):
            summary = _get_conversation_summary(conv, firm_id) if i < 3 else ""
            conversations.append(
                {
                    "conversation_id": conv.get("id"),
                    "title": conv.get("title", ""),
                    "type": conv.get("conversation_type", ""),
                    "status": conv.get("status", ""),
                    "created_at": conv.get("created_at", ""),
                    "summary": summary,
                }
            )
    except Exception:
        logger.warning("Could not fetch conversations for case %s", case_id)

    # 5. Research (best effort — extract from assistant messages with rag_context)
    research = []

    return {
        "case": case_meta,
        "documents": documents,
        "timeline": timeline,
        "conversations": conversations,
        "drafts": drafts,
        "research": research,
        "assembled_at": datetime.now(timezone.utc).isoformat(),
        "source_counts": {
            "documents": len(documents),
            "timeline_events": len(timeline),
            "conversations": len(conversations),
            "drafts": len(drafts),
            "research_findings": len(research),
        },
    }


def build_case_context_text(case_id: str, firm_id: str, max_tokens: int = 8000) -> str:
    """Serialize case context into a token-budgeted text for LLM injection."""
    context = build_case_context(case_id, firm_id)
    if "error" in context:
        return ""

    sections = []

    # Case metadata (always included)
    case = context.get("case", {})
    meta_lines = ["=== CASE CONTEXT ===", ""]
    meta_lines.append(f"## Case: {case.get('title', 'Untitled')}")
    if case.get("practice_area"):
        meta_lines.append(f"- Practice Area: {case['practice_area']}")
    if case.get("case_type"):
        meta_lines.append(f"- Type: {case['case_type']}")
    if case.get("status"):
        stage_str = f" ({case['stage']} stage)" if case.get("stage") else ""
        meta_lines.append(f"- Status: {case['status']}{stage_str}")
    if case.get("client_name"):
        meta_lines.append(f"- Client: {case['client_name']}")
    if case.get("opposing_party"):
        meta_lines.append(f"- Opposing Party: {case['opposing_party']}")
    if case.get("court"):
        meta_lines.append(f"- Court: {case['court']}")
    if case.get("filing_date"):
        meta_lines.append(f"- Filed: {case['filing_date']}")
    if case.get("description"):
        meta_lines.append(f"- Description: {case['description'][:300]}")
    sections.append("\n".join(meta_lines))

    # Token budget: ~4 chars per token as rough estimate
    chars_per_token = 4
    max_chars = max_tokens * chars_per_token
    used_chars = len(sections[0])

    # Timeline
    timeline = context.get("timeline", [])
    if timeline:
        t_lines = [f"\n## Timeline ({len(timeline)} events)"]
        for evt in timeline:
            if used_chars > max_chars * 0.85:
                break
            sig = evt.get("significance", "").upper()
            line = (
                f"- {evt.get('event_date_text') or evt.get('event_date', '?')}: "
                f"{evt.get('description', '')} [{sig}]"
            )
            t_lines.append(line)
            used_chars += len(line)
        sections.append("\n".join(t_lines))

    # Drafts
    drafts = context.get("drafts", [])
    if drafts:
        d_lines = [f"\n## Prior Drafts ({len(drafts)} drafts)"]
        for d in drafts[:5]:
            if used_chars > max_chars * 0.90:
                break
            line = (
                f"- {d.get('filename', '')} ({d.get('uploaded_at', '')}): "
                f"{d.get('summary', '')[:200]}"
            )
            d_lines.append(line)
            used_chars += len(line)
        sections.append("\n".join(d_lines))

    # Documents
    documents = context.get("documents", [])
    if documents:
        doc_lines = [f"\n## Documents ({len(documents)} documents)"]
        for doc in documents[:10]:
            if used_chars > max_chars * 0.95:
                break
            line = (
                f"- {doc.get('filename', '')} ({doc.get('file_type', '')}): "
                f"{doc.get('summary', '')[:200]}"
            )
            doc_lines.append(line)
            used_chars += len(line)
        sections.append("\n".join(doc_lines))

    # Conversations
    conversations = context.get("conversations", [])
    if conversations:
        c_lines = [f"\n## Prior Conversations ({len(conversations)} conversations)"]
        for conv in conversations[:5]:
            if used_chars > max_chars:
                break
            line = (
                f"- {conv.get('title', 'Untitled')} ({conv.get('status', '')}): "
                f"{conv.get('summary', '')[:200]}"
            )
            c_lines.append(line)
            used_chars += len(line)
        sections.append("\n".join(c_lines))

    from legalcopilot.services.pii_filter import redact_pii

    return redact_pii("\n".join(sections))


def _get_document_summary(doc: dict) -> str:
    """Get a summary for a document — use pre-computed or truncate ocr_text."""
    meta_summary = doc.get("metadata", {}).get("summary")
    if meta_summary:
        return meta_summary
    ocr = doc.get("ocr_text", "")
    if not ocr:
        return f"[{doc.get('file_type', 'document')} — text not yet extracted]"
    # Truncate at sentence boundary within 500 chars
    if len(ocr) <= 500:
        return ocr
    cutoff = ocr[:500].rfind(".")
    if cutoff > 100:
        return ocr[: cutoff + 1]
    return ocr[:500] + "..."


def _get_conversation_summary(conv: dict, firm_id: str) -> str:
    """Get a summary for a conversation — fetch last assistant messages."""
    conv_id = conv.get("id")
    if not conv_id:
        return ""
    try:
        msg_results = _execute(
            "message_list",
            {"filter": {"conversation_id": conv_id, "firm_id": firm_id}, "limit": 5, "offset": 0},
        )
        messages = msg_results.get("result", [])
        assistant_msgs = [m.get("content", "") for m in messages if m.get("role") == "assistant"]
        if assistant_msgs:
            combined = " ".join(assistant_msgs[-3:])
            return combined[:500] + ("..." if len(combined) > 500 else "")
    except Exception:
        logger.warning("Could not fetch messages for conversation %s", conv_id)
    return ""
