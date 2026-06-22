"""Core domain models: Firm, User, Case, Document.

These are the foundational entities for multi-tenant legal case management.
DataFlow auto-generates 11 CRUD nodes per model (Create, Read, Update, Delete,
List, Count, BulkCreate, BulkUpdate, BulkDelete, Search, Exists).
"""

from datetime import datetime
from typing import List, Optional

from legalcopilot.models.database import db


@db.model
class Firm:
    """Law firm — the multi-tenancy root entity."""

    id: str
    name: str
    domain: Optional[str] = None
    subscription_plan: str = "free"
    settings: dict = {}
    active: bool = True
    created_at: datetime = None
    updated_at: datetime = None

    __validation__ = {
        "name": {"min_length": 1, "max_length": 200},
        "subscription_plan": {"one_of": ["free", "professional", "enterprise"]},
    }
    __dataflow__ = {
        "soft_delete": True,
        "audit_log": True,
    }
    __indexes__ = [
        {"fields": ["domain"], "unique": True},
        {"fields": ["name"]},
    ]


@db.model
class User:
    """Lawyer or staff member belonging to a firm."""

    id: str
    firm_id: str
    email: str
    name: str
    role: str = "associate"
    permissions: dict = {}
    active: bool = True
    last_login_at: Optional[datetime] = None
    created_at: datetime = None
    updated_at: datetime = None

    __validation__ = {
        "email": {"validators": ["email"]},
        "name": {"min_length": 1, "max_length": 150},
        "role": {
            "one_of": [
                "partner",
                "senior_associate",
                "associate",
                "paralegal",
                "admin",
                "viewer",
            ]
        },
    }
    __dataflow__ = {
        "soft_delete": True,
        "audit_log": True,
        "multi_tenant": True,
    }
    __indexes__ = [
        {"fields": ["firm_id", "email"], "unique": True},
        {"fields": ["firm_id"]},
        {"fields": ["firm_id", "role"]},
    ]


@db.model
class Case:
    """Legal case — the primary work unit for lawyers."""

    id: str
    firm_id: str
    created_by_id: str
    assigned_user_id: Optional[str] = None
    case_number: Optional[str] = None
    title: str
    description: Optional[str] = None
    practice_area: str = "general"
    case_type: str = "general"
    status: str = "open"
    stage: str = "intake"
    priority: str = "normal"
    client_name: Optional[str] = None
    client_reference: Optional[str] = None
    opposing_party: Optional[str] = None
    court: Optional[str] = None
    filing_date: Optional[datetime] = None
    tags: List[str] = []
    metadata: dict = {}
    created_at: datetime = None
    updated_at: datetime = None

    __validation__ = {
        "title": {"min_length": 1, "max_length": 500},
        "status": {
            "one_of": [
                "open",
                "in_progress",
                "pending_review",
                "under_review",
                "closed",
                "archived",
            ]
        },
        "stage": {
            "one_of": [
                "intake",
                "fact_gathering",
                "research",
                "analysis",
                "drafting",
                "review",
                "submission",
                "complete",
            ]
        },
        "priority": {"one_of": ["low", "normal", "high", "urgent"]},
        "practice_area": {
            "one_of": [
                "general",
                "commercial_disputes",
                "restructuring_insolvency",
                "labour_employment",
                "corporate",
                "litigation",
                "arbitration",
                "intellectual_property",
                "real_estate",
                "family",
                "criminal",
            ]
        },
    }
    __dataflow__ = {
        "soft_delete": True,
        "audit_log": True,
        "multi_tenant": True,
    }
    __indexes__ = [
        {"fields": ["firm_id"]},
        {"fields": ["firm_id", "status"]},
        {"fields": ["firm_id", "practice_area"]},
        {"fields": ["firm_id", "created_at"]},
        {"fields": ["assigned_user_id"]},
        {"fields": ["case_number"], "unique": True},
    ]


@db.model
class Document:
    """Document attached to a case (pleadings, evidence, correspondence, etc.)."""

    id: str
    case_id: str
    firm_id: str
    uploaded_by_id: str
    filename: str
    file_type: str = "other"
    storage_url: str = ""
    file_size_bytes: int = 0
    classification: dict = {}
    ocr_text: Optional[str] = None
    ocr_status: str = "pending"
    metadata: dict = {}
    created_at: datetime = None
    updated_at: datetime = None

    __validation__ = {
        "filename": {"min_length": 1, "max_length": 500},
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
                "other",
            ]
        },
        "ocr_status": {"one_of": ["pending", "processing", "complete", "failed"]},
    }
    __dataflow__ = {
        "soft_delete": True,
        "audit_log": True,
        "multi_tenant": True,
    }
    __indexes__ = [
        {"fields": ["case_id"]},
        {"fields": ["firm_id"]},
        {"fields": ["firm_id", "case_id"]},
        {"fields": ["firm_id", "created_at"]},
        {"fields": ["uploaded_by_id"]},
        {"fields": ["file_type"]},
    ]
