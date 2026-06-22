"""SOP Template service — data-driven workflow configuration.

Loads SOP templates from the database (SOPTemplate model) with fallback
defaults for common Singapore legal case types. The orchestrator uses these
to configure specialist agents per case type.
"""

from legalcopilot.models.database import db


# Default templates for bootstrapping — seeded into DB on first run
DEFAULT_TEMPLATES = [
    {
        "name": "Contract Dispute Analysis",
        "practice_area": "contract",
        "case_type": "contract_dispute",
        "description": "Full IRAC analysis for contract disputes with breach assessment",
        "skills": {
            "research": {"focus": ["breach_of_contract", "damages", "remedies"]},
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {"types": ["advice_note", "letter_of_demand"]},
        },
        "knowledge_sources": {
            "primary": ["contract_act", "misrepresentation_act"],
            "secondary": ["sale_of_goods_act", "unfair_contract_terms_act"],
        },
        "tools": {
            "citation_search": True,
            "legislation_lookup": True,
            "judge_profile": True,
        },
        "quality_threshold": 0.85,
        "max_iterations": 3,
    },
    {
        "name": "Employment Dispute",
        "practice_area": "employment",
        "case_type": "employment_dispute",
        "description": "Employment law analysis covering EA, TAFEP, and MOM guidelines",
        "skills": {
            "research": {"focus": ["wrongful_dismissal", "salary_claims", "workplace_harassment"]},
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {"types": ["advisory_letter", "case_memo"]},
        },
        "knowledge_sources": {
            "primary": ["employment_act", "employment_claims_act"],
            "secondary": ["workplace_safety_health_act", "tafep_guidelines"],
        },
        "tools": {
            "citation_search": True,
            "legislation_lookup": True,
        },
        "quality_threshold": 0.85,
        "max_iterations": 3,
    },
    {
        "name": "Family Law Matter",
        "practice_area": "family",
        "case_type": "family_law",
        "description": "Family law proceedings — divorce, custody, maintenance, matrimonial assets",
        "skills": {
            "research": {"focus": ["divorce", "custody", "maintenance", "matrimonial_assets"]},
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {"types": ["submission", "affidavit"]},
        },
        "knowledge_sources": {
            "primary": ["womens_charter", "guardianship_of_infants_act"],
            "secondary": ["administration_of_muslim_law_act", "intestate_succession_act"],
        },
        "tools": {
            "citation_search": True,
            "legislation_lookup": True,
            "judge_profile": True,
        },
        "quality_threshold": 0.90,
        "max_iterations": 3,
    },
    {
        "name": "Criminal Defence",
        "practice_area": "criminal",
        "case_type": "criminal_defence",
        "description": "Criminal defence analysis — charges, defences, sentencing precedents",
        "skills": {
            "research": {"focus": ["elements_of_offence", "defences", "sentencing"]},
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {"types": ["submission", "case_memo"]},
        },
        "knowledge_sources": {
            "primary": ["penal_code", "criminal_procedure_code"],
            "secondary": ["evidence_act", "misuse_of_drugs_act"],
        },
        "tools": {
            "citation_search": True,
            "legislation_lookup": True,
            "judge_profile": True,
        },
        "quality_threshold": 0.90,
        "max_iterations": 3,
    },
    {
        "name": "Property & Conveyancing",
        "practice_area": "property",
        "case_type": "property_conveyancing",
        "description": "Property transactions, tenancy, strata, and land disputes",
        "skills": {
            "research": {"focus": ["conveyancing", "tenancy", "strata_management"]},
            "analysis": {"methodology": "IRAC", "depth": "standard"},
            "drafting": {"types": ["contract", "advisory_letter"]},
        },
        "knowledge_sources": {
            "primary": ["land_titles_act", "residential_property_act"],
            "secondary": ["building_maintenance_strata_management_act", "stamp_duties_act"],
        },
        "tools": {
            "citation_search": True,
            "legislation_lookup": True,
        },
        "quality_threshold": 0.85,
        "max_iterations": 2,
    },
    {
        "name": "General Legal Research",
        "practice_area": "general",
        "case_type": "general",
        "description": "General-purpose legal research and advice",
        "skills": {
            "research": {"focus": []},
            "analysis": {"methodology": "IRAC", "depth": "standard"},
            "drafting": {"types": ["advice_note", "case_memo"]},
        },
        "knowledge_sources": {
            "primary": [],
            "secondary": [],
        },
        "tools": {
            "citation_search": True,
            "legislation_lookup": True,
        },
        "quality_threshold": 0.80,
        "max_iterations": 3,
    },
]


def get_sop_template(case_type: str) -> dict:
    """Get the SOP template for a case type.

    Looks up the database first; falls back to DEFAULT_TEMPLATES
    if no database record exists for the case type.
    """
    # Try database lookup via DataFlow auto-generated read
    try:
        workflows = db.get_workflows()
        read_wf = workflows.get("soptemplate_read")
        if read_wf:
            from kailash import LocalRuntime

            with LocalRuntime() as runtime:
                results, _ = runtime.execute(read_wf.build(), inputs={"case_type": case_type})
            if results and results.get("result"):
                return results["result"]
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "SOP database lookup failed for case_type=%s, falling back to defaults: %s",
            case_type,
            exc,
        )

    # Fall back to defaults
    for template in DEFAULT_TEMPLATES:
        if template["case_type"] == case_type:
            return template

    # Ultimate fallback: general template
    return DEFAULT_TEMPLATES[-1]


def list_sop_templates(practice_area: str = "") -> list[dict]:
    """List all available SOP templates, optionally filtered by practice area."""
    templates = DEFAULT_TEMPLATES
    if practice_area:
        templates = [t for t in templates if t["practice_area"] == practice_area]
    return templates


def get_quality_threshold(case_type: str) -> float:
    """Get the quality threshold for a case type's SOP."""
    template = get_sop_template(case_type)
    return template.get("quality_threshold", 0.80)


def get_max_iterations(case_type: str) -> int:
    """Get the max PDCA iterations for a case type's SOP."""
    template = get_sop_template(case_type)
    return template.get("max_iterations", 3)
