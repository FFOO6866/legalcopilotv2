"""Chat API endpoints — conversations and messages via Nexus.

Handles conversation lifecycle, message send/receive with RAG injection,
and real-time streaming via WebSocket.  All mutations persist through
DataFlow CRUD workflows (Conversation / Message models).
"""

import json
import logging
import uuid
from typing import Optional

from kailash import LocalRuntime
from nexus import Nexus

from legalcopilot.agents.drafting import DraftingAgent
from legalcopilot.agents.orchestrator import OrchestratorAgent
from legalcopilot.models.database import db
from legalcopilot.services.pii_filter import redact_pii
from legalcopilot.services.rag_pipeline import retrieve_context
from legalcopilot.services.sop_service import get_sop_template, validate_case_type

MAX_LIMIT = 200

logger = logging.getLogger(__name__)

_orchestrator: Optional[OrchestratorAgent] = None


def _get_orchestrator() -> OrchestratorAgent:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OrchestratorAgent()
    return _orchestrator


_workflows = None


def _get_workflows() -> dict:
    """Lazily fetch and cache the DataFlow workflow dict."""
    global _workflows
    if _workflows is None:
        _workflows = db.get_workflows()
    return _workflows


def _execute_workflow(workflow_key: str, inputs: dict) -> dict:
    """Look up a DataFlow auto-generated workflow by key and execute it.

    Returns the raw *results* dict from ``runtime.execute``.
    Raises ``RuntimeError`` when the requested workflow does not exist.
    """
    workflows = _get_workflows()
    wf = workflows.get(workflow_key)
    if wf is None:
        logger.error(
            "DataFlow workflow '%s' not found. Available: %s",
            workflow_key,
            sorted(workflows.keys()),
        )
        raise RuntimeError("Internal configuration error — please contact support.")
    with LocalRuntime() as runtime:
        results, _run_id = runtime.execute(wf.build(), inputs=inputs)
    return results


def _compute_engagement_metrics(
    conversation_id: str, firm_id: str, conversation: dict, resolved: bool
) -> dict:
    """Compute and persist EngagementMetrics when a conversation closes."""
    try:
        # Fetch all messages for this conversation
        msg_results = _execute_workflow(
            "message_list",
            {
                "filter": {"conversation_id": conversation_id, "firm_id": firm_id},
                "limit": 1000,
                "offset": 0,
            },
        )
        messages = msg_results.get("result", [])

        turn_count = len(messages)
        practice_area = conversation.get("metadata", {}).get("practice_area", "")

        # Compute average confidence from assistant messages
        confidences = [
            m.get("confidence")
            for m in messages
            if m.get("role") == "assistant" and m.get("confidence") is not None
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else None

        # Compute average response time from assistant messages
        response_times = [
            m.get("processing_time_ms", 0)
            for m in messages
            if m.get("role") == "assistant" and m.get("processing_time_ms")
        ]
        avg_response_time = int(sum(response_times) / len(response_times)) if response_times else 0

        metrics_id = str(uuid.uuid4())
        metrics_data = {
            "id": metrics_id,
            "firm_id": firm_id,
            "conversation_id": conversation_id,
            "turn_count": turn_count,
            "avg_response_time_ms": avg_response_time,
            "quality_score": avg_confidence,
            "practice_area": practice_area,
            "resolved": resolved,
            "metadata": {},
        }

        results = _execute_workflow("engagementmetrics_create", {"data": metrics_data})
        return results.get("result", metrics_data)

    except Exception:
        logger.exception("Failed to compute engagement metrics for %s", conversation_id)
        return {"error": "Failed to compute metrics"}


def register_chat_routes(app: Nexus) -> None:
    """Register all chat-related endpoints on the Nexus app."""

    # ------------------------------------------------------------------
    # create_conversation — persist via ConversationCreate workflow
    # ------------------------------------------------------------------
    @app.handler("create_conversation", description="Create a new conversation")
    async def create_conversation(
        firm_id: str,
        user_id: str,
        case_id: str = "",
        conversation_type: str = "general",
        title: str = "",
    ) -> dict:
        # Verify case belongs to this firm if case_id is provided
        if case_id:
            try:
                case_results = _execute_workflow("case_read", {"id": case_id})
                case_record = case_results.get("result")
                if case_record is None or case_record.get("firm_id") != firm_id:
                    return {"error": "Case not found", "case_id": case_id}
            except Exception:
                logger.exception("Failed to verify case %s", case_id)
                raise

        conversation_id = str(uuid.uuid4())
        resolved_title = title or f"Conversation {conversation_id[:8]}"

        data = {
            "id": conversation_id,
            "firm_id": firm_id,
            "user_id": user_id,
            "case_id": case_id or None,
            "conversation_type": conversation_type,
            "title": resolved_title,
            "status": "active",
            "metadata": {},
        }

        try:
            results = _execute_workflow("conversation_create", {"data": data})
            record = results.get("result", data)
        except Exception:
            logger.exception("Failed to persist conversation %s", conversation_id)
            raise

        return record

    # ------------------------------------------------------------------
    # send_message — orchestrator + persist user & assistant messages
    # ------------------------------------------------------------------
    @app.handler("send_message", description="Send a message and get AI response")
    async def send_message(
        conversation_id: str,
        content: str,
        firm_id: str = "",
        user_id: str = "",
        case_context: str = "",
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}
        if not content or not content.strip():
            return {"error": "Message content cannot be empty"}
        if len(content) > 50_000:
            return {"error": "Message content exceeds maximum length (50000 characters)"}
        # Verify conversation belongs to the requesting firm
        try:
            conv_results = _execute_workflow("conversation_read", {"id": conversation_id})
            conv = conv_results.get("result")
            if conv is None or conv.get("firm_id") != firm_id:
                return {"error": "Conversation not found", "conversation_id": conversation_id}
        except Exception:
            logger.exception("Failed to verify conversation %s", conversation_id)
            raise

        # Auto-build case context if conversation is case-bound
        case_id = conv.get("case_id", "")
        if case_id and not case_context:
            try:
                from legalcopilot.services.case_context import build_case_context_text

                case_context = build_case_context_text(case_id, firm_id, max_tokens=2500)
            except Exception:
                logger.warning("Failed to build case context for %s", case_id)

        if len(case_context) > 10_000:
            return {"error": "Case context exceeds maximum length (10000 characters)"}

        # Fetch recent conversation history for multi-turn context
        conversation_history = "[]"
        try:
            history_results = _execute_workflow(
                "message_list",
                {
                    "filter": {"conversation_id": conversation_id, "firm_id": firm_id},
                    "limit": 20,
                    "offset": 0,
                },
            )
            messages = history_results.get("result", [])
            if messages:
                conversation_history = json.dumps(
                    [{"role": m.get("role", ""), "content": m.get("content", "")} for m in messages]
                )
        except Exception:
            logger.warning("Could not fetch conversation history for %s", conversation_id)

        # Run through orchestrator PDCA cycle
        orchestrator = _get_orchestrator()
        try:
            result = orchestrator.process_request(
                request=content,
                case_context=case_context,
                conversation_history=conversation_history,
            )
        except Exception:
            logger.exception("Orchestrator failed for conversation %s", conversation_id)
            return {
                "error": "AI processing failed — please try again or rephrase your question",
            }

        # Persist the user message with PII redacted
        user_msg_id = str(uuid.uuid4())
        user_msg_data = {
            "id": user_msg_id,
            "conversation_id": conversation_id,
            "firm_id": firm_id,
            "role": "user",
            "content": redact_pii(content),
            "metadata": {},
        }

        try:
            user_results = _execute_workflow("message_create", {"data": user_msg_data})
            user_message = user_results.get("result", user_msg_data)
        except Exception:
            logger.exception("Failed to persist user message for conversation %s", conversation_id)
            raise

        # Persist the assistant message
        assistant_msg_id = str(uuid.uuid4())
        response_data = result.get("response", {})
        if isinstance(response_data, dict):
            assistant_content = redact_pii(
                response_data.get("text", response_data.get("content", json.dumps(response_data)))
            )
        elif isinstance(response_data, str):
            assistant_content = redact_pii(response_data)
        else:
            assistant_content = redact_pii(str(response_data))
        confidence = result.get("confidence", 0)
        rag_context = result.get("sources", [])

        assistant_msg_data = {
            "id": assistant_msg_id,
            "conversation_id": conversation_id,
            "firm_id": firm_id,
            "role": "assistant",
            "content": assistant_content,
            "agent_name": result.get("agent_name", "orchestrator"),
            "confidence": confidence,
            "rag_context": {"sources": rag_context},
            "metadata": {
                "iterations": result.get("iterations", 1),
                "status": result.get("status", "complete"),
            },
        }

        try:
            assistant_results = _execute_workflow("message_create", {"data": assistant_msg_data})
            assistant_message = assistant_results.get("result", assistant_msg_data)
        except Exception:
            logger.exception(
                "Failed to persist assistant message for conversation %s",
                conversation_id,
            )
            raise

        response_payload = {
            "user_message": user_message,
            "assistant_message": assistant_message,
        }

        # Surface quality gate status prominently so the frontend
        # can display warnings for non-pass outcomes
        status = result.get("status", "complete")
        if status != "complete":
            response_payload["quality_warning"] = {
                "status": status,
                "iterations": result.get("iterations", 1),
                "confidence": result.get("confidence", 0),
                "message": (
                    "Analysis was escalated for human review — "
                    "please verify before relying on this response."
                    if status == "escalated"
                    else "Analysis reached maximum quality iterations — "
                    "results may need additional review."
                ),
            }

        return response_payload

    # ------------------------------------------------------------------
    # get_conversation_history — query via MessageList workflow
    # ------------------------------------------------------------------
    @app.handler("get_conversation_history", description="Get messages for a conversation")
    async def get_conversation_history(
        conversation_id: str,
        firm_id: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}
        effective_limit = max(1, min(limit, MAX_LIMIT))
        effective_offset = max(0, offset)

        # Verify conversation belongs to the requesting firm
        try:
            conv_results = _execute_workflow(
                "conversation_read",
                {"id": conversation_id},
            )
            conv = conv_results.get("result")
            if conv is None or conv.get("firm_id") != firm_id:
                return {"error": "Conversation not found", "conversation_id": conversation_id}
        except Exception:
            logger.exception("Failed to verify conversation %s", conversation_id)
            raise

        try:
            results = _execute_workflow(
                "message_list",
                {
                    "filter": {"conversation_id": conversation_id, "firm_id": firm_id},
                    "limit": effective_limit,
                    "offset": effective_offset,
                },
            )
            messages = results.get("result", [])
        except Exception:
            logger.exception("Failed to fetch history for conversation %s", conversation_id)
            raise

        return {
            "conversation_id": conversation_id,
            "messages": messages,
            "total": len(messages),
            "limit": effective_limit,
            "offset": effective_offset,
        }

    # ------------------------------------------------------------------
    # search_conversations — query via ConversationList workflow
    # ------------------------------------------------------------------
    @app.handler("search_conversations", description="Search conversations for a firm")
    async def search_conversations(
        firm_id: str,
        query: str = "",
        status: str = "active",
        case_id: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        effective_limit = max(1, min(limit, MAX_LIMIT))
        effective_offset = max(0, offset)

        filters: dict = {"firm_id": firm_id}
        if status:
            filters["status"] = status
        if case_id:
            filters["case_id"] = case_id

        inputs: dict = {"filter": filters, "limit": effective_limit, "offset": effective_offset}
        if query:
            inputs["search"] = query

        try:
            results = _execute_workflow("conversation_list", inputs)
            conversations = results.get("result", [])
        except Exception:
            logger.exception("Failed to search conversations for firm %s", firm_id)
            raise

        return {
            "firm_id": firm_id,
            "conversations": conversations,
            "total": len(conversations),
            "query": query,
        }

    # ------------------------------------------------------------------
    # submit_feedback — create RAGFeedback record for a message
    # ------------------------------------------------------------------
    @app.handler("submit_feedback", description="Submit feedback on a message")
    async def submit_feedback(
        message_id: str,
        firm_id: str,
        was_helpful: bool = True,
        feedback_text: str = "",
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}

        # Verify message exists and belongs to this firm
        try:
            msg_results = _execute_workflow("message_read", {"id": message_id})
            msg = msg_results.get("result")
            if msg is None or msg.get("firm_id") != firm_id:
                return {"error": "Message not found", "message_id": message_id}
        except Exception:
            logger.exception("Failed to verify message %s", message_id)
            raise

        # Check for duplicate feedback on this message (scoped to firm)
        try:
            existing = _execute_workflow(
                "ragfeedback_list",
                {"filter": {"message_id": message_id, "firm_id": firm_id}, "limit": 1},
            )
            existing_records = existing.get("result", [])
            if existing_records:
                return {"error": "Feedback already submitted for this message"}
        except Exception:
            logger.warning(
                "Could not check for existing feedback on message %s, proceeding", message_id
            )

        if feedback_text and len(feedback_text) > 2000:
            return {"error": "Feedback text exceeds maximum length (2000 characters)"}

        feedback_id = str(uuid.uuid4())
        data = {
            "id": feedback_id,
            "firm_id": firm_id,
            "message_id": message_id,
            "was_helpful": was_helpful,
            "feedback_text": feedback_text or "",
        }

        try:
            results = _execute_workflow("ragfeedback_create", {"data": data})
            return results.get("result", data)
        except Exception:
            logger.exception("Failed to persist feedback for message %s", message_id)
            raise

    # ------------------------------------------------------------------
    # close_conversation — close and compute engagement metrics
    # ------------------------------------------------------------------
    @app.handler(
        "close_conversation", description="Close a conversation and compute engagement metrics"
    )
    async def close_conversation(
        conversation_id: str,
        firm_id: str,
        resolved: bool = False,
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}

        # Verify conversation belongs to the requesting firm
        try:
            conv_results = _execute_workflow("conversation_read", {"id": conversation_id})
            conv = conv_results.get("result")
            if conv is None or conv.get("firm_id") != firm_id:
                return {"error": "Conversation not found", "conversation_id": conversation_id}
        except Exception:
            logger.exception("Failed to verify conversation %s", conversation_id)
            raise

        # Guard against double-close
        if conv.get("status") == "closed":
            return {"error": "Conversation is already closed", "conversation_id": conversation_id}

        # Update conversation status to closed
        try:
            _execute_workflow(
                "conversation_update",
                {
                    "filter": {"id": conversation_id, "firm_id": firm_id},
                    "fields": {"status": "closed"},
                },
            )
        except Exception:
            logger.exception("Failed to close conversation %s", conversation_id)
            raise

        # Compute engagement metrics
        metrics = _compute_engagement_metrics(conversation_id, firm_id, conv, resolved)

        return {
            "conversation_id": conversation_id,
            "status": "closed",
            "metrics": metrics,
        }

    # ------------------------------------------------------------------
    # draft_document — already does real work; no persistence needed
    # ------------------------------------------------------------------
    @app.handler("draft_document", description="Draft a legal document using AI")
    async def draft_document(
        document_type: str,
        instructions: str,
        firm_id: str = "",
        user_id: str = "",
        case_id: str = "",
        case_type: str = "general",
        facts: str = "",
        case_context: str = "",
        tone: str = "formal",
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}
        if len(instructions) > 50_000:
            return {"error": "Instructions exceed maximum length (50000 characters)"}
        if len(facts) > 50_000:
            return {"error": "Facts exceed maximum length (50000 characters)"}

        # Load SOP template for case-type-aware drafting
        validated_case_type = validate_case_type(case_type)
        sop = get_sop_template(validated_case_type)
        sop_drafting_types = sop.get("skills", {}).get("drafting", {}).get("types", [])

        # Validate document_type against SOP-allowed types (warn but don't block)
        if sop_drafting_types and document_type not in sop_drafting_types:
            logger.warning(
                "Requested document_type '%s' not in SOP types for %s: %s",
                document_type,
                validated_case_type,
                sop_drafting_types,
            )

        # Enrich with case context if case_id provided and no user-provided context
        if case_id and not case_context:
            try:
                from legalcopilot.services.case_context import build_case_context_text

                auto_context = build_case_context_text(case_id, firm_id)
                if auto_context:
                    case_context = auto_context
            except Exception:
                logger.warning("Failed to build case context for drafting, case %s", case_id)

        drafter = DraftingAgent()

        # PII-redact instructions before sending to embedding service and LLM
        clean_instructions = redact_pii(instructions)

        # Inject case context into facts for the drafter
        # Don't redact facts here — the drafter does its own PII redaction internally
        draft_facts = facts or ""
        if case_context:
            draft_facts = f"{case_context}\n\n---\n\n{facts}" if facts else case_context

        # Enrich the RAG query with SOP research focus for better context
        research_focus = sop.get("skills", {}).get("research", {}).get("focus", [])
        rag_query = clean_instructions
        if research_focus:
            rag_query = f"{clean_instructions} [{' '.join(research_focus)}]"
        rag_result = retrieve_context(query=rag_query, top_k=10)

        result = drafter.draft(
            document_type=document_type,
            instructions=clean_instructions,
            facts=draft_facts,
            rag_context=rag_result["context_text"],
            tone=tone,
        )
        return {
            "document_type": document_type,
            "case_type": validated_case_type,
            "sop_template": sop.get("name", ""),
            "draft": result,
            "sources": rag_result["sources"],
        }
