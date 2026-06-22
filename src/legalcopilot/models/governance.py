"""Governance models: audit trail, PII filtering patterns, clearance levels.

PACT-backed governance for multi-tenant legal platform. Every AI recommendation
gets wrapped in an audit entry with provenance chain.
"""

from datetime import datetime
from typing import Optional

from legalcopilot.models.database import db


@db.model
class AuditEntry:
    """Immutable audit trail — every AI action, data access, and state change."""

    id: str
    firm_id: str
    user_id: Optional[str] = None
    agent_name: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    details: dict = {}
    pact_envelope: dict = {}
    clearance_level: str = "internal"
    ip_address: Optional[str] = None
    created_at: datetime = None

    __validation__ = {
        "action": {
            "one_of": [
                "create",
                "read",
                "update",
                "delete",
                "analyze",
                "generate",
                "search",
                "export",
                "login",
                "logout",
            ]
        },
        "clearance_level": {"one_of": ["public", "internal", "confidential", "privileged"]},
    }
    __dataflow__ = {
        "audit_log": False,
        "multi_tenant": True,
    }
    __indexes__ = [
        {"fields": ["firm_id"]},
        {"fields": ["firm_id", "created_at"]},
        {"fields": ["user_id"]},
        {"fields": ["entity_type", "entity_id"]},
        {"fields": ["action"]},
        {"fields": ["agent_name"]},
    ]
