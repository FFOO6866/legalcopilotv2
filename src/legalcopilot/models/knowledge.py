"""Knowledge base models: case law entries, vectors, citations, judges, topics, legislation.

These models represent the 25K+ Singapore case law knowledge base,
the citation graph (215K edges), and the supporting legal metadata.
"""

from datetime import datetime
from typing import List, Optional

from legalcopilot.models.database import db


@db.model
class KnowledgeEntry:
    """Ingested case law entry from eLitigation, LexisNexis, or manual upload."""

    id: str
    citation: str
    case_name: str
    court: str
    jurisdiction: str = "SG"
    decision_date: Optional[datetime] = None
    year: Optional[int] = None
    coram: Optional[str] = None
    full_text: Optional[str] = None
    summary: Optional[str] = None
    headnotes: Optional[str] = None
    source: str = "elitigation"
    source_url: Optional[str] = None
    has_full_judgment: bool = False
    metadata: dict = {}
    created_at: datetime = None
    updated_at: datetime = None

    __validation__ = {
        "citation": {"min_length": 1, "max_length": 500},
        "case_name": {"min_length": 1, "max_length": 1000},
        "court": {"min_length": 1, "max_length": 200},
        "jurisdiction": {"one_of": ["SG", "UK", "AU", "MY", "HK", "IN", "NZ", "CA", "INTL"]},
        "source": {"one_of": ["elitigation", "lexisnexis", "lawnet", "manual", "subscription"]},
    }
    __dataflow__ = {
        "soft_delete": True,
        "audit_log": True,
    }
    __indexes__ = [
        {"fields": ["citation"], "unique": True},
        {"fields": ["court"]},
        {"fields": ["jurisdiction"]},
        {"fields": ["year"]},
        {"fields": ["court", "year"]},
    ]


@db.model
class KnowledgeVector:
    """Vector embedding chunk for a knowledge entry (stored in Qdrant, metadata here)."""

    id: str
    entry_id: str
    chunk_text: str
    chunk_index: int = 0
    embedding_model: str = "text-embedding-3-small"
    dimensions: int = 1536
    qdrant_point_id: Optional[str] = None
    created_at: datetime = None

    __validation__ = {
        "embedding_model": {
            "one_of": ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"]
        },
    }
    __dataflow__ = {
        "audit_log": True,
    }
    __indexes__ = [
        {"fields": ["entry_id"]},
        {"fields": ["entry_id", "chunk_index"]},
        {"fields": ["qdrant_point_id"]},
    ]


@db.model
class KGCitationEdge:
    """Citation relationship between two knowledge entries (215K+ edges)."""

    id: str
    citing_id: str
    cited_id: str
    treatment: str = "cited"
    context_text: Optional[str] = None
    paragraph_num: Optional[int] = None
    created_at: datetime = None

    __validation__ = {
        "treatment": {
            "one_of": [
                "cited",
                "followed",
                "applied",
                "distinguished",
                "overruled",
                "referred",
                "considered",
                "approved",
                "not_followed",
            ]
        },
    }
    __dataflow__ = {
        "audit_log": True,
    }
    __indexes__ = [
        {"fields": ["citing_id"]},
        {"fields": ["cited_id"]},
        {"fields": ["citing_id", "cited_id"], "unique": True},
        {"fields": ["treatment"]},
    ]


@db.model
class KGJudge:
    """Judge entity in the knowledge graph (499+ judges)."""

    id: str
    name: str
    court: Optional[str] = None
    title: Optional[str] = None
    appointment_start: Optional[datetime] = None
    appointment_end: Optional[datetime] = None
    metadata: dict = {}
    created_at: datetime = None

    __validation__ = {
        "name": {"min_length": 1, "max_length": 300},
    }
    __indexes__ = [
        {"fields": ["name"]},
        {"fields": ["court"]},
    ]


@db.model
class KGCaseJudge:
    """Many-to-many: which judges presided over which cases."""

    id: str
    entry_id: str
    judge_id: str
    role: str = "judge"
    created_at: datetime = None

    __validation__ = {
        "role": {"one_of": ["judge", "chief_justice", "justice_of_appeal", "registrar"]},
    }
    __indexes__ = [
        {"fields": ["entry_id"]},
        {"fields": ["judge_id"]},
        {"fields": ["entry_id", "judge_id"], "unique": True},
    ]


@db.model
class KGCaseTopic:
    """Topic classification for a knowledge entry (9,977+ entries)."""

    id: str
    entry_id: str
    topic: str
    confidence: float = 1.0
    created_at: datetime = None

    __validation__ = {
        "topic": {"min_length": 1, "max_length": 300},
        "confidence": {"range": {"min": 0.0, "max": 1.0}},
    }
    __indexes__ = [
        {"fields": ["entry_id"]},
        {"fields": ["topic"]},
        {"fields": ["entry_id", "topic"], "unique": True},
    ]


@db.model
class KGLegislationRef:
    """Legislation reference from a knowledge entry (43K+ refs)."""

    id: str
    entry_id: str
    statute_name: str
    section: Optional[str] = None
    subsection: Optional[str] = None
    chapter: Optional[str] = None
    created_at: datetime = None

    __validation__ = {
        "statute_name": {"min_length": 1, "max_length": 500},
    }
    __indexes__ = [
        {"fields": ["entry_id"]},
        {"fields": ["statute_name"]},
        {"fields": ["statute_name", "section"]},
    ]


@db.model
class SOPTemplate:
    """Data-driven SOP template for a case type (replaces hardcoded sop_templates.py)."""

    id: str
    name: str
    practice_area: str
    case_type: str
    description: Optional[str] = None
    skills: dict = {}
    knowledge_sources: dict = {}
    tools: dict = {}
    quality_threshold: float = 0.8
    adversarial_review: bool = True
    max_iterations: int = 3
    is_active: bool = True
    metadata: dict = {}
    created_at: datetime = None
    updated_at: datetime = None

    __validation__ = {
        "name": {"min_length": 1, "max_length": 200},
        "quality_threshold": {"range": {"min": 0.0, "max": 1.0}},
        "max_iterations": {"range": {"min": 1, "max": 10}},
    }
    __dataflow__ = {
        "soft_delete": True,
        "audit_log": True,
    }
    __indexes__ = [
        {"fields": ["case_type"], "unique": True},
        {"fields": ["practice_area"]},
        {"fields": ["is_active"]},
    ]


@db.model
class FirmKnowledge:
    """Firm-specific knowledge (private precedents, internal playbooks, custom templates)."""

    id: str
    firm_id: str
    category: str
    title: str
    content: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"
    qdrant_point_id: Optional[str] = None
    is_active: bool = True
    metadata: dict = {}
    created_at: datetime = None
    updated_at: datetime = None

    __validation__ = {
        "category": {
            "one_of": [
                "precedent",
                "playbook",
                "template",
                "policy",
                "training",
                "other",
            ]
        },
        "title": {"min_length": 1, "max_length": 500},
    }
    __dataflow__ = {
        "soft_delete": True,
        "audit_log": True,
    }
    __indexes__ = [
        {"fields": ["firm_id"]},
        {"fields": ["firm_id", "category"]},
        {"fields": ["is_active"]},
    ]
