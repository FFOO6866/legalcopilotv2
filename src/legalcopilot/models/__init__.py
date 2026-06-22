"""DataFlow models for LegalCoPilot v2."""

from legalcopilot.models.database import db
from legalcopilot.models.core import Case, Document, Firm, User
from legalcopilot.models.knowledge import (
    FirmKnowledge,
    KGCaseJudge,
    KGCaseTopic,
    KGCitationEdge,
    KGJudge,
    KGLegislationRef,
    KnowledgeEntry,
    KnowledgeVector,
    SOPTemplate,
)
from legalcopilot.models.conversation import (
    Conversation,
    EngagementMetrics,
    Message,
    RAGFeedback,
)
from legalcopilot.models.governance import AuditEntry

__all__ = [
    "db",
    # Core
    "Firm",
    "User",
    "Case",
    "Document",
    # Knowledge
    "KnowledgeEntry",
    "KnowledgeVector",
    "KGCitationEdge",
    "KGJudge",
    "KGCaseJudge",
    "KGCaseTopic",
    "KGLegislationRef",
    "SOPTemplate",
    "FirmKnowledge",
    # Conversation
    "Conversation",
    "Message",
    "RAGFeedback",
    "EngagementMetrics",
    # Governance
    "AuditEntry",
]
