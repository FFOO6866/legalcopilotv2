"""Stage manager — Singapore Rules of Court 2021 case stages.

Defines the 8-stage case lifecycle and provides stage-specific templates,
checklists, and next-action guidance for each stage.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

STAGE_ORDER = [
    "intake",
    "fact_gathering",
    "research",
    "analysis",
    "drafting",
    "review",
    "submission",
    "complete",
]

STAGE_TEMPLATES = {
    "intake": {
        "name": "Case Intake",
        "description": "Initial case assessment and client onboarding",
        "checklist": [
            "Client engagement letter signed",
            "Conflict of interest check completed",
            "Initial facts gathered from client",
            "Key dates and limitation periods identified",
            "Opposing party identified",
            "Preliminary assessment of merits",
        ],
        "next_actions": [
            "Upload key documents (agreements, correspondence, notices)",
            "Create timeline of key events",
            "Identify practice area and case type",
        ],
        "ai_focus": "Summarize client's position and identify key legal issues",
    },
    "fact_gathering": {
        "name": "Fact Gathering",
        "description": "Collect and organize all relevant facts and evidence",
        "checklist": [
            "All relevant documents uploaded and classified",
            "Timeline of events constructed",
            "Witness statements collected",
            "Documentary evidence catalogued",
            "Gaps in evidence identified",
        ],
        "next_actions": [
            "Review uploaded documents for completeness",
            "Request missing documents from client",
            "Build comprehensive chronology",
        ],
        "ai_focus": "Extract key facts from documents and build event timeline",
    },
    "research": {
        "name": "Legal Research",
        "description": "Research applicable law, precedents, and procedural requirements",
        "checklist": [
            "Applicable legislation identified",
            "Relevant case authorities found",
            "Procedural requirements under ROC 2021 identified",
            "Limitation periods verified",
            "Jurisdictional issues addressed",
        ],
        "next_actions": [
            "Search for precedents on key issues",
            "Verify procedural compliance requirements",
            "Draft research memo",
        ],
        "ai_focus": "Find relevant Singapore case law and statutes",
    },
    "analysis": {
        "name": "Legal Analysis",
        "description": "Analyze facts against law using IRAC methodology",
        "checklist": [
            "IRAC analysis completed for each issue",
            "Strengths and weaknesses assessed",
            "Risk assessment documented",
            "Strategy recommendation prepared",
            "Client advised on options",
        ],
        "next_actions": [
            "Complete IRAC analysis for all legal issues",
            "Prepare strategy memo for client review",
            "Assess quantum of damages if applicable",
        ],
        "ai_focus": "Apply IRAC analysis to each identified legal issue",
    },
    "drafting": {
        "name": "Document Drafting",
        "description": "Draft court documents, letters, and submissions",
        "checklist": [
            "Originating process drafted (if filing)",
            "Supporting affidavits drafted",
            "Bundle of authorities prepared",
            "Written submissions drafted",
            "All documents reviewed for accuracy",
        ],
        "next_actions": [
            "Draft primary court document",
            "Prepare supporting documents",
            "Cross-reference all factual claims with evidence",
        ],
        "ai_focus": "Draft documents following Singapore court formats and conventions",
    },
    "review": {
        "name": "Review & Quality Check",
        "description": "Internal review of all documents before filing or sending",
        "checklist": [
            "Senior review completed",
            "All citations verified",
            "Factual accuracy confirmed",
            "Procedural compliance checked",
            "Client approval obtained",
        ],
        "next_actions": [
            "Submit documents for senior review",
            "Address review comments",
            "Obtain client sign-off",
        ],
        "ai_focus": "Check document accuracy, citations, and compliance",
    },
    "submission": {
        "name": "Filing & Submission",
        "description": "File documents with court or serve on parties",
        "checklist": [
            "Documents filed via eLitigation",
            "Service effected on all parties",
            "Proof of service filed",
            "Court fees paid",
            "Filing deadlines met",
        ],
        "next_actions": [
            "File via eLitigation portal",
            "Arrange service on opposing party",
            "Calendar next hearing date",
        ],
        "ai_focus": "Verify filing requirements and deadlines",
    },
    "complete": {
        "name": "Case Complete",
        "description": "Case concluded — judgment obtained or matter settled",
        "checklist": [
            "Final outcome recorded",
            "Client billing finalized",
            "File closed and archived",
            "Lessons learned documented",
        ],
        "next_actions": [],
        "ai_focus": "Summarize case outcome and key learnings",
    },
}


def get_stage_template(stage: str) -> dict:
    """Get the template for a given stage."""
    return STAGE_TEMPLATES.get(stage, STAGE_TEMPLATES["intake"])


def get_next_stage(current_stage: str) -> Optional[str]:
    """Get the next stage in the lifecycle."""
    try:
        idx = STAGE_ORDER.index(current_stage)
        if idx < len(STAGE_ORDER) - 1:
            return STAGE_ORDER[idx + 1]
    except ValueError:
        pass
    return None


def get_previous_stage(current_stage: str) -> Optional[str]:
    """Get the previous stage in the lifecycle."""
    try:
        idx = STAGE_ORDER.index(current_stage)
        if idx > 0:
            return STAGE_ORDER[idx - 1]
    except ValueError:
        pass
    return None


def validate_stage_transition(current_stage: str, target_stage: str) -> dict:
    """Validate whether a stage transition is allowed."""
    if current_stage not in STAGE_ORDER:
        return {"valid": False, "error": f"Unknown current stage: {current_stage}"}
    if target_stage not in STAGE_ORDER:
        return {"valid": False, "error": f"Unknown target stage: {target_stage}"}

    current_idx = STAGE_ORDER.index(current_stage)
    target_idx = STAGE_ORDER.index(target_stage)

    # Allow forward by 1, or backward by any amount (re-opening)
    if target_idx == current_idx + 1:
        return {"valid": True, "direction": "forward"}
    if target_idx < current_idx:
        return {"valid": True, "direction": "backward", "warning": "Moving case to an earlier stage"}
    if target_idx == current_idx:
        return {"valid": False, "error": "Already at this stage"}
    return {
        "valid": False,
        "error": f"Cannot skip stages. Next stage is '{STAGE_ORDER[current_idx + 1]}'",
    }
