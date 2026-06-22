"""Kaizen agents for LegalCoPilot v2.

PDCA agent system:
- Orchestrator: routes requests, manages PDCA cycle, quality gates
- Paralegal: document classification, OCR, metadata extraction
- Associate: IRAC legal analysis, citation research, risk assessment
- QA Reviewer: adversarial challenge, compliance check, quality validation
- Researcher: RAG + knowledge graph legal research
"""

from legalcopilot.agents.associate import AssociateAgent
from legalcopilot.agents.drafting import DraftingAgent
from legalcopilot.agents.orchestrator import OrchestratorAgent
from legalcopilot.agents.paralegal import ParalegalAgent
from legalcopilot.agents.qa_reviewer import QAReviewerAgent
from legalcopilot.agents.researcher import ResearchAgent

__all__ = [
    "OrchestratorAgent",
    "ParalegalAgent",
    "AssociateAgent",
    "DraftingAgent",
    "QAReviewerAgent",
    "ResearchAgent",
]
