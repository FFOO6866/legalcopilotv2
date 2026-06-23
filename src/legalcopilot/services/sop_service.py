"""SOP Template service — data-driven workflow configuration.

Loads SOP templates from the database (SOPTemplate model) with fallback
defaults for common Singapore legal case types. The orchestrator uses these
to configure specialist agents per case type.
"""

import logging

from legalcopilot.models.database import db

logger = logging.getLogger(__name__)

# Canonical case types — the orchestrator validates LLM output against this set
VALID_CASE_TYPES = frozenset(
    {
        "contract_dispute",
        "employment_dispute",
        "family_law",
        "criminal_defence",
        "property_conveyancing",
        "arbitration",
        "corporate_commercial",
        "insolvency_restructuring",
        "intellectual_property",
        "tort_personal_injury",
        "probate_succession",
        "general",
    }
)

# Default templates for bootstrapping — seeded into DB on first run
DEFAULT_TEMPLATES = [
    {
        "name": "Contract Dispute Analysis",
        "practice_area": "contract",
        "case_type": "contract_dispute",
        "description": "Full IRAC analysis for contract disputes with breach assessment",
        "skills": {
            "research": {
                "focus": [
                    "breach_of_contract",
                    "damages",
                    "remedies",
                    "formation",
                    "vitiating_factors",
                    "limitation_periods",
                    "contractual_interpretation",
                    "termination",
                    "specific_performance",
                ],
            },
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {
                "types": [
                    "advice_note",
                    "letter_of_demand",
                    "submission",
                    "application",
                    "case_memo",
                ],
            },
        },
        "knowledge_sources": {
            "primary": [
                "civil_law_act",
                "contracts_rights_of_third_parties_act",
                "limitation_act",
            ],
            "secondary": [
                "misrepresentation_act",
                "sale_of_goods_act",
                "unfair_contract_terms_act",
                "supply_of_goods_act",
                "electronic_transactions_act",
                "rules_of_court_2021",
            ],
        },
        "tools": {},
        "adversarial_review": True,
        "quality_threshold": 0.85,
        "max_iterations": 3,
        "is_active": True,
        "metadata": {},
    },
    {
        "name": "Employment Dispute",
        "practice_area": "employment",
        "case_type": "employment_dispute",
        "description": "Employment law analysis covering EA, TAFEP, and MOM guidelines",
        "skills": {
            "research": {
                "focus": [
                    "wrongful_dismissal",
                    "constructive_dismissal",
                    "salary_claims",
                    "workplace_harassment",
                    "retrenchment",
                    "non_compete_clauses",
                    "foreign_worker_issues",
                    "cpf_contributions",
                    "retirement_reemployment",
                ],
            },
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {
                "types": [
                    "advisory_letter",
                    "letter_of_demand",
                    "case_memo",
                    "application",
                    "submission",
                ],
            },
        },
        "knowledge_sources": {
            "primary": [
                "employment_act",
                "employment_claims_act",
                "employment_of_foreign_manpower_act",
            ],
            "secondary": [
                "retirement_and_reemployment_act",
                "workplace_safety_health_act",
                "central_provident_fund_act",
                "industrial_relations_act",
                "child_development_cosavings_act",
                "tripartite_guidelines_fair_employment",
                "rules_of_court_2021",
            ],
        },
        "tools": {},
        "adversarial_review": True,
        "quality_threshold": 0.85,
        "max_iterations": 3,
        "is_active": True,
        "metadata": {},
    },
    {
        "name": "Family Law Matter",
        "practice_area": "family",
        "case_type": "family_law",
        "description": "Family law proceedings — divorce, custody, maintenance, matrimonial assets",
        "skills": {
            "research": {
                "focus": [
                    "divorce",
                    "custody",
                    "maintenance",
                    "matrimonial_assets",
                    "personal_protection_orders",
                    "adoption",
                    "muslim_family_law",
                    "relocation",
                    "variation_of_orders",
                ],
            },
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {
                "types": [
                    "submission",
                    "affidavit",
                    "application",
                    "case_memo",
                    "notice",
                ],
            },
        },
        "knowledge_sources": {
            "primary": [
                "womens_charter",
                "guardianship_of_infants_act",
                "family_justice_act",
            ],
            "secondary": [
                "administration_of_muslim_law_act",
                "intestate_succession_act",
                "mental_capacity_act",
                "adoption_of_children_act",
                "international_child_abduction_act",
                "maintenance_of_parents_act",
                "family_justice_rules",
            ],
        },
        "tools": {},
        "adversarial_review": True,
        "quality_threshold": 0.90,
        "max_iterations": 3,
        "is_active": True,
        "metadata": {},
    },
    {
        "name": "Criminal Defence",
        "practice_area": "criminal",
        "case_type": "criminal_defence",
        "description": "Criminal defence analysis — charges, defences, sentencing precedents",
        "skills": {
            "research": {
                "focus": [
                    "elements_of_offence",
                    "defences",
                    "sentencing",
                    "bail",
                    "criminal_motions",
                    "plea_bargaining",
                    "mitigation",
                    "criminal_procedure",
                    "mental_capacity_fitness",
                ],
            },
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {
                "types": [
                    "submission",
                    "case_memo",
                    "application",
                    "notice",
                    "mitigation_plea",
                    "representations_to_agc",
                    "bail_application",
                    "appeal_petition",
                ],
            },
        },
        "knowledge_sources": {
            "primary": [
                "penal_code",
                "criminal_procedure_code",
                "evidence_act",
            ],
            "secondary": [
                "misuse_of_drugs_act",
                "road_traffic_act",
                "computer_misuse_act",
                "corruption_drug_trafficking_act",
                "protection_from_harassment_act",
                "arms_offences_act",
                "probation_of_offenders_act",
            ],
        },
        "tools": {},
        "adversarial_review": True,
        "quality_threshold": 0.90,
        "max_iterations": 3,
        "is_active": True,
        "metadata": {},
    },
    {
        "name": "Property & Conveyancing",
        "practice_area": "property",
        "case_type": "property_conveyancing",
        "description": "Property transactions, tenancy, strata, HDB, and land disputes",
        "skills": {
            "research": {
                "focus": [
                    "conveyancing",
                    "tenancy",
                    "strata_management",
                    "hdb_transactions",
                    "en_bloc_sales",
                    "land_acquisition",
                    "mortgage",
                    "foreign_ownership",
                    "stamp_duty",
                ],
            },
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {
                "types": [
                    "contract",
                    "advisory_letter",
                    "application",
                    "notice",
                    "case_memo",
                ],
            },
        },
        "knowledge_sources": {
            "primary": [
                "land_titles_act",
                "conveyancing_and_law_of_property_act",
                "housing_and_development_act",
                "residential_property_act",
            ],
            "secondary": [
                "building_maintenance_strata_management_act",
                "land_titles_strata_act",
                "stamp_duties_act",
                "planning_act",
                "central_provident_fund_act",
                "land_acquisition_act",
                "rules_of_court_2021",
            ],
        },
        "tools": {},
        "adversarial_review": True,
        "quality_threshold": 0.85,
        "max_iterations": 3,
        "is_active": True,
        "metadata": {},
    },
    {
        "name": "International Arbitration",
        "practice_area": "arbitration",
        "case_type": "arbitration",
        "description": "International and domestic arbitration — SIAC, SICC, enforcement",
        "skills": {
            "research": {
                "focus": [
                    "arbitration_agreement",
                    "arbitral_procedure",
                    "enforcement_of_awards",
                    "setting_aside",
                    "interim_measures",
                    "investor_state_arbitration",
                    "mediation",
                ],
            },
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {
                "types": [
                    "submission",
                    "application",
                    "case_memo",
                    "advice_note",
                ],
            },
        },
        "knowledge_sources": {
            "primary": [
                "international_arbitration_act",
                "arbitration_act",
            ],
            "secondary": [
                "siac_rules",
                "uncitral_model_law",
                "new_york_convention",
                "singapore_convention_on_mediation",
                "supreme_court_of_judicature_act",
                "rules_of_court_2021",
            ],
        },
        "tools": {},
        "adversarial_review": True,
        "quality_threshold": 0.85,
        "max_iterations": 3,
        "is_active": True,
        "metadata": {},
    },
    {
        "name": "Corporate & Commercial",
        "practice_area": "corporate",
        "case_type": "corporate_commercial",
        "description": "Corporate governance, M&A, shareholder disputes, securities",
        "skills": {
            "research": {
                "focus": [
                    "directors_duties",
                    "shareholder_disputes",
                    "oppression_remedy",
                    "corporate_governance",
                    "mergers_acquisitions",
                    "securities_regulation",
                    "winding_up",
                ],
            },
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {
                "types": [
                    "advice_note",
                    "case_memo",
                    "submission",
                    "application",
                    "contract",
                ],
            },
        },
        "knowledge_sources": {
            "primary": [
                "companies_act",
                "securities_and_futures_act",
            ],
            "secondary": [
                "business_trusts_act",
                "limited_liability_partnerships_act",
                "variable_capital_companies_act",
                "takeover_code",
                "rules_of_court_2021",
            ],
        },
        "tools": {},
        "adversarial_review": True,
        "quality_threshold": 0.85,
        "max_iterations": 3,
        "is_active": True,
        "metadata": {},
    },
    {
        "name": "Insolvency & Restructuring",
        "practice_area": "insolvency",
        "case_type": "insolvency_restructuring",
        "description": "Corporate and personal insolvency, restructuring, judicial management",
        "skills": {
            "research": {
                "focus": [
                    "winding_up",
                    "judicial_management",
                    "scheme_of_arrangement",
                    "bankruptcy",
                    "voluntary_arrangement",
                    "cross_border_insolvency",
                    "preferential_transactions",
                ],
            },
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {
                "types": [
                    "application",
                    "submission",
                    "advice_note",
                    "case_memo",
                ],
            },
        },
        "knowledge_sources": {
            "primary": [
                "insolvency_restructuring_dissolution_act",
                "companies_act",
            ],
            "secondary": [
                "uncitral_model_law_cross_border_insolvency",
                "employment_act",
                "rules_of_court_2021",
            ],
        },
        "tools": {},
        "adversarial_review": True,
        "quality_threshold": 0.85,
        "max_iterations": 3,
        "is_active": True,
        "metadata": {},
    },
    {
        "name": "Intellectual Property",
        "practice_area": "ip",
        "case_type": "intellectual_property",
        "description": "IP disputes — patents, trademarks, copyright, confidential information, passing off",
        "skills": {
            "research": {
                "focus": [
                    "patent_infringement",
                    "trademark_infringement",
                    "copyright_infringement",
                    "passing_off",
                    "confidential_information",
                    "registered_designs",
                    "trade_secrets",
                    "licensing",
                    "ip_valuation",
                ],
            },
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {
                "types": [
                    "advice_note",
                    "letter_of_demand",
                    "submission",
                    "application",
                    "case_memo",
                    "cease_and_desist",
                ],
            },
        },
        "knowledge_sources": {
            "primary": [
                "patents_act",
                "trade_marks_act",
                "copyright_act",
            ],
            "secondary": [
                "registered_designs_act",
                "geographical_indications_act",
                "layout_designs_of_integrated_circuits_act",
                "plant_varieties_protection_act",
                "rules_of_court_2021",
            ],
        },
        "tools": {},
        "adversarial_review": True,
        "quality_threshold": 0.85,
        "max_iterations": 3,
        "is_active": True,
        "metadata": {},
    },
    {
        "name": "Tort & Personal Injury",
        "practice_area": "tort",
        "case_type": "tort_personal_injury",
        "description": "Tort claims — negligence, personal injury, motor accident, occupier's liability, defamation",
        "skills": {
            "research": {
                "focus": [
                    "negligence",
                    "duty_of_care",
                    "personal_injury",
                    "motor_accident_claims",
                    "occupiers_liability",
                    "defamation",
                    "nuisance",
                    "vicarious_liability",
                    "contributory_negligence",
                    "assessment_of_damages",
                ],
            },
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {
                "types": [
                    "letter_of_demand",
                    "submission",
                    "application",
                    "case_memo",
                    "advice_note",
                ],
            },
        },
        "knowledge_sources": {
            "primary": [
                "civil_law_act",
                "motor_vehicles_third_party_risks_and_compensation_act",
                "limitation_act",
            ],
            "secondary": [
                "work_injury_compensation_act",
                "protection_from_harassment_act",
                "defamation_act",
                "rules_of_court_2021",
            ],
        },
        "tools": {},
        "adversarial_review": True,
        "quality_threshold": 0.85,
        "max_iterations": 3,
        "is_active": True,
        "metadata": {},
    },
    {
        "name": "Probate & Succession",
        "practice_area": "probate",
        "case_type": "probate_succession",
        "description": "Wills, probate, letters of administration, estate disputes, trusts",
        "skills": {
            "research": {
                "focus": [
                    "grant_of_probate",
                    "letters_of_administration",
                    "testamentary_disputes",
                    "intestate_succession",
                    "family_provision",
                    "trusts",
                    "estate_duty",
                    "lasting_power_of_attorney",
                    "mental_capacity",
                ],
            },
            "analysis": {"methodology": "IRAC", "depth": "comprehensive"},
            "drafting": {
                "types": [
                    "application",
                    "affidavit",
                    "advice_note",
                    "case_memo",
                    "submission",
                ],
            },
        },
        "knowledge_sources": {
            "primary": [
                "wills_act",
                "intestate_succession_act",
                "probate_and_administration_act",
            ],
            "secondary": [
                "trustees_act",
                "mental_capacity_act",
                "inheritance_family_provision_act",
                "administration_of_muslim_law_act",
                "rules_of_court_2021",
            ],
        },
        "tools": {},
        "adversarial_review": True,
        "quality_threshold": 0.85,
        "max_iterations": 3,
        "is_active": True,
        "metadata": {},
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
        "tools": {},
        "adversarial_review": True,
        "quality_threshold": 0.80,
        "max_iterations": 3,
        "is_active": True,
        "metadata": {},
    },
]


def validate_case_type(case_type: str) -> str:
    """Validate and normalize LLM-classified case_type.

    Returns the validated case_type, or 'general' with a warning if invalid.
    """
    if case_type in VALID_CASE_TYPES:
        return case_type
    logger.warning(
        "LLM returned invalid case_type '%s', falling back to 'general'. " "Valid types: %s",
        case_type,
        sorted(VALID_CASE_TYPES),
    )
    return "general"


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
        logger.warning(
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


def get_sop_usage_stats(case_type: str) -> dict:
    """Get aggregated SOP usage statistics for a case type.

    Returns avg_confidence, pass_rate, avg_iterations, total_uses
    computed from SOPUsageRecord entries.
    """
    try:
        workflows = db.get_workflows()
        list_wf = workflows.get("sopusagerecord_list")
        if list_wf is None:
            return {"error": "SOP usage tracking not available"}

        from kailash import LocalRuntime

        with LocalRuntime() as runtime:
            results, _ = runtime.execute(
                list_wf.build(),
                inputs={
                    "filter": {"case_type": case_type},
                    "limit": 500,
                    "offset": 0,
                },
            )

        records = results.get("result", [])
        if not records:
            return {
                "case_type": case_type,
                "total_uses": 0,
                "pass_rate": 0.0,
                "avg_confidence": 0.0,
                "avg_iterations": 0.0,
                "escalation_rate": 0.0,
            }

        total = len(records)
        passes = sum(1 for r in records if r.get("quality_verdict") == "pass")
        escalations = sum(1 for r in records if r.get("quality_verdict") == "escalate")
        confidences = [r.get("confidence", 0) for r in records if r.get("confidence") is not None]
        iterations = [r.get("iterations", 1) for r in records]

        stats = {
            "case_type": case_type,
            "total_uses": total,
            "pass_rate": round(passes / total, 3) if total else 0.0,
            "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
            "avg_iterations": round(sum(iterations) / len(iterations), 2) if iterations else 0.0,
            "escalation_rate": round(escalations / total, 3) if total else 0.0,
        }
        if total >= 500:
            stats["truncated"] = True
            stats["note"] = "Stats computed over latest 500 records"
        return stats

    except Exception:
        logger.exception("Failed to compute SOP usage stats for case_type=%s", case_type)
        return {"error": "Failed to compute stats", "case_type": case_type}
