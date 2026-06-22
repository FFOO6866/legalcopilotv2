"""Conversation and message models for structured legal engagements.

Conversations can be bound to a case (case-aware context) or standalone (general).
Messages track RAG context, agent attribution, and confidence scores.
"""

from datetime import datetime
from typing import Optional

from legalcopilot.models.database import db


@db.model
class Conversation:
    """A structured conversation — optionally bound to a legal case."""

    id: str
    firm_id: str
    user_id: str
    case_id: Optional[str] = None
    title: Optional[str] = None
    conversation_type: str = "general"
    status: str = "active"
    metadata: dict = {}
    created_at: datetime = None
    updated_at: datetime = None

    __validation__ = {
        "conversation_type": {
            "one_of": ["consultation", "research", "drafting", "analysis", "general"]
        },
        "status": {"one_of": ["active", "paused", "closed", "archived"]},
    }
    __dataflow__ = {
        "soft_delete": True,
        "audit_log": True,
    }
    __indexes__ = [
        {"fields": ["firm_id"]},
        {"fields": ["user_id"]},
        {"fields": ["case_id"]},
        {"fields": ["firm_id", "status"]},
        {"fields": ["firm_id", "user_id"]},
    ]


@db.model
class Message:
    """A single message in a conversation — user, assistant, or system."""

    id: str
    conversation_id: str
    role: str
    content: str
    agent_name: Optional[str] = None
    confidence: Optional[float] = None
    rag_context: Optional[dict] = None
    tokens_used: int = 0
    processing_time_ms: int = 0
    metadata: dict = {}
    created_at: datetime = None

    __validation__ = {
        "role": {"one_of": ["user", "assistant", "system"]},
        "content": {"min_length": 1},
        "confidence": {"range": {"min": 0.0, "max": 1.0}},
    }
    __indexes__ = [
        {"fields": ["conversation_id"]},
        {"fields": ["conversation_id", "created_at"]},
        {"fields": ["role"]},
    ]


@db.model
class RAGFeedback:
    """User feedback on RAG-augmented responses for quality tracking."""

    id: str
    message_id: str
    was_helpful: bool = True
    feedback_text: Optional[str] = None
    created_at: datetime = None

    __indexes__ = [
        {"fields": ["message_id"]},
    ]


@db.model
class EngagementMetrics:
    """Quality metrics for a conversation — tracks engagement quality."""

    id: str
    conversation_id: str
    turn_count: int = 0
    avg_response_time_ms: int = 0
    quality_score: Optional[float] = None
    practice_area: Optional[str] = None
    resolved: bool = False
    metadata: dict = {}
    created_at: datetime = None
    updated_at: datetime = None

    __validation__ = {
        "quality_score": {"range": {"min": 0.0, "max": 1.0}},
    }
    __indexes__ = [
        {"fields": ["conversation_id"], "unique": True},
        {"fields": ["practice_area"]},
        {"fields": ["resolved"]},
    ]
