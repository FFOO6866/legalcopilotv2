"""Stage management and timeline API endpoints via Nexus.

Provides stage lifecycle (transition, template) and timeline CRUD endpoints.
"""

import logging
import uuid

from kailash import LocalRuntime
from nexus import Nexus

from legalcopilot.models.database import db
from legalcopilot.services.stage_manager import (
    get_next_stage,
    get_stage_template,
    validate_stage_transition,
    STAGE_ORDER,
    STAGE_TEMPLATES,
)

logger = logging.getLogger(__name__)

_workflows = None


def _get_workflows() -> dict:
    global _workflows
    if _workflows is None:
        _workflows = db.get_workflows()
    return _workflows


def register_stage_routes(app: Nexus) -> None:
    """Register stage management and timeline endpoints."""

    @app.handler("get_stage_info", description="Get stage template and checklist")
    async def get_stage_info(stage: str = "intake") -> dict:
        template = get_stage_template(stage)
        next_stage = get_next_stage(stage)
        return {
            "stage": stage,
            "template": template,
            "next_stage": next_stage,
            "all_stages": STAGE_ORDER,
        }

    @app.handler("transition_stage", description="Move a case to the next stage")
    async def transition_stage(
        case_id: str,
        firm_id: str,
        target_stage: str,
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}

        workflows = _get_workflows()
        case_wf = workflows["case_read"]
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(case_wf.build(), inputs={"id": case_id})
        case_record = results.get("result")
        if case_record is None or case_record.get("firm_id") != firm_id:
            return {"error": "Case not found", "case_id": case_id}

        current_stage = case_record.get("stage", "intake")
        validation = validate_stage_transition(current_stage, target_stage)
        if not validation.get("valid"):
            return {"error": validation.get("error"), "current_stage": current_stage}

        update_wf = workflows["case_update"]
        with LocalRuntime() as runtime:
            runtime.execute(
                update_wf.build(),
                inputs={
                    "filter": {"id": case_id, "firm_id": firm_id},
                    "fields": {"stage": target_stage},
                },
            )

        template = get_stage_template(target_stage)
        return {
            "case_id": case_id,
            "previous_stage": current_stage,
            "current_stage": target_stage,
            "template": template,
            "warning": validation.get("warning"),
        }

    @app.handler("add_timeline_event", description="Add a timeline event to a case")
    async def add_timeline_event(
        case_id: str,
        firm_id: str,
        description: str,
        event_date: str = "",
        event_date_text: str = "",
        significance: str = "medium",
        event_type: str = "general",
        source_document_id: str = "",
        parties_involved: list = None,
    ) -> dict:
        if parties_involved is None:
            parties_involved = []

        if not firm_id:
            return {"error": "firm_id is required"}
        if not description or not description.strip():
            return {"error": "description is required"}
        if len(description) > 2000:
            return {"error": "description exceeds maximum length (2000 characters)"}

        # Verify case belongs to firm
        workflows = _get_workflows()
        case_wf = workflows["case_read"]
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(case_wf.build(), inputs={"id": case_id})
        if results.get("result") is None or results.get("result", {}).get("firm_id") != firm_id:
            return {"error": "Case not found", "case_id": case_id}

        event_id = str(uuid.uuid4())
        data = {
            "id": event_id,
            "case_id": case_id,
            "firm_id": firm_id,
            "description": description,
            "event_date": event_date or None,
            "event_date_text": event_date_text,
            "significance": significance,
            "event_type": event_type,
            "parties_involved": parties_involved,
        }
        if source_document_id:
            data["source_document_id"] = source_document_id

        event_wf = workflows["caseevent_create"]
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(event_wf.build(), inputs={"data": data})
        return results.get("result", data)

    @app.handler("list_timeline_events", description="List timeline events for a case")
    async def list_timeline_events(
        case_id: str,
        firm_id: str = "",
        significance: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}

        effective_limit = max(1, min(limit, 200))
        effective_offset = max(0, offset)

        filter_conditions = {"case_id": case_id, "firm_id": firm_id}
        if significance:
            filter_conditions["significance"] = significance

        workflows = _get_workflows()
        event_wf = workflows["caseevent_list"]
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(
                event_wf.build(),
                inputs={
                    "filter": filter_conditions,
                    "limit": effective_limit,
                    "offset": effective_offset,
                },
            )
        events = results.get("result", [])
        return {
            "case_id": case_id,
            "events": events,
            "total": len(events),
            "limit": effective_limit,
            "offset": effective_offset,
        }

    @app.handler("delete_timeline_event", description="Delete a timeline event")
    async def delete_timeline_event(event_id: str, firm_id: str = "") -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}

        workflows = _get_workflows()
        read_wf = workflows["caseevent_read"]
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(read_wf.build(), inputs={"id": event_id})
        record = results.get("result")
        if record is None or record.get("firm_id") != firm_id:
            return {"error": "Event not found", "id": event_id}

        delete_wf = workflows["caseevent_delete"]
        with LocalRuntime() as runtime:
            runtime.execute(delete_wf.build(), inputs={"id": event_id, "firm_id": firm_id})
        return {"success": True, "id": event_id}

    @app.handler("get_case_context", description="Get assembled AI context for a case")
    async def get_case_context(case_id: str, firm_id: str = "") -> dict:
        if not firm_id:
            return {"error": "firm_id is required"}
        from legalcopilot.services.case_context import build_case_context_text

        context_text = build_case_context_text(case_id, firm_id)
        if not context_text:
            return {"error": "Case not found", "case_id": case_id}
        return {"case_id": case_id, "context": context_text}
