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
        case_context: str = "{}",
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}
        if len(content) > 50_000:
            return {"error": "Message content exceeds maximum length (50000 characters)"}
        if len(case_context) > 10_000:
            return {"error": "Case context exceeds maximum length (10000 characters)"}

        # Verify conversation belongs to the requesting firm
        try:
            conv_results = _execute_workflow("conversation_read", {"id": conversation_id})
            conv = conv_results.get("result")
            if conv is None or conv.get("firm_id") != firm_id:
                return {"error": "Conversation not found", "conversation_id": conversation_id}
        except Exception:
            logger.exception("Failed to verify conversation %s", conversation_id)
            raise

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
        result = orchestrator.process_request(
            request=content,
            case_context=case_context,
            conversation_history=conversation_history,
        )

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
        assistant_content = redact_pii(json.dumps(result.get("response", {})))
        confidence = result.get("confidence", 0)
        rag_context = result.get("sources", [])

        assistant_msg_data = {
            "id": assistant_msg_id,
            "conversation_id": conversation_id,
            "firm_id": firm_id,
            "role": "assistant",
            "content": assistant_content,
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
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        effective_limit = max(1, min(limit, MAX_LIMIT))
        effective_offset = max(0, offset)

        filters: dict = {"firm_id": firm_id}
        if status:
            filters["status"] = status

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
    # draft_document — already does real work; no persistence needed
    # ------------------------------------------------------------------
    @app.handler("draft_document", description="Draft a legal document using AI")
    async def draft_document(
        document_type: str,
        instructions: str,
        firm_id: str = "",
        user_id: str = "",
        case_id: str = "",
        facts: str = "",
        case_context: str = "{}",
        tone: str = "formal",
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}
        if len(instructions) > 50_000:
            return {"error": "Instructions exceed maximum length (50000 characters)"}
        if len(facts) > 50_000:
            return {"error": "Facts exceed maximum length (50000 characters)"}

        drafter = DraftingAgent()

        # PII-redact before sending to embedding service and LLM
        clean_instructions = redact_pii(instructions)
        clean_facts = redact_pii(facts) if facts else ""

        # Get RAG context for the drafting task
        rag_result = retrieve_context(query=clean_instructions, top_k=10)

        result = drafter.draft(
            document_type=document_type,
            instructions=clean_instructions,
            facts=clean_facts,
            rag_context=rag_result["context_text"],
            tone=tone,
        )
        return {
            "document_type": document_type,
            "draft": result,
            "sources": rag_result["sources"],
        }
