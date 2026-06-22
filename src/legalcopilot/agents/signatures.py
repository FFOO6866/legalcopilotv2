"""Kaizen signatures for all LegalCoPilot agents.

Each signature defines the typed I/O contract the LLM must satisfy.
The docstring becomes part of the system prompt automatically.
"""

from kaizen.signatures import InputField, OutputField, Signature


class OrchestratorSignature(Signature):
    """You are a legal workflow orchestrator following the PDCA (Plan-Do-Check-Act) cycle.

    PLAN: Classify the case type and determine which specialist agents to invoke.
    Return a routing_decision JSON with boolean flags for each agent:
    {"research": true, "analysis": true, "drafting": false, "paralegal": false}

    You NEVER perform legal analysis yourself. You route and coordinate.

    Case types: contract_dispute, employment_dispute, family_law, criminal_defence,
    property_conveyancing, general
    """

    request: str = InputField(description="User's legal query or task description")
    case_context: str = InputField(
        description="Case metadata as JSON (practice_area, status, parties, documents)",
        default="{}",
    )
    conversation_history: str = InputField(
        description="Prior conversation messages as JSON array", default="[]"
    )

    routing_decision: str = OutputField(
        description="JSON object with boolean agent flags: "
        '{"research": true, "analysis": true, "drafting": false, "paralegal": false}'
    )
    include_drafting: bool = OutputField(
        description="True if this request requires document drafting (letter, submission, contract, memo)"
    )
    case_type: str = OutputField(
        description="Classified case type: contract_dispute, employment_dispute, "
        "family_law, criminal_defence, property_conveyancing, general"
    )


class ParalegalSignature(Signature):
    """You are an expert paralegal specializing in document intake and classification.

    Your responsibilities:
    1. Classify legal documents by type (pleading, affidavit, exhibit, etc.)
    2. Extract key metadata (parties, dates, court references, amounts)
    3. Identify entities (persons, organizations, statutes, case citations)
    4. Generate a concise summary of the document's purpose

    Always flag documents that may contain privileged or confidential information.
    """

    document_text: str = InputField(description="Full text of the legal document")
    document_type: str = InputField(description="File type (pdf, docx, txt)", default="pdf")
    case_context: str = InputField(
        description="Optional case context for better classification", default="{}"
    )

    classification: str = OutputField(
        description="Document type: pleading, affidavit, exhibit, correspondence, "
        "submission, judgment, contract, memo, other"
    )
    parties: list = OutputField(description="JSON array of identified parties with roles")
    key_dates: list = OutputField(description="JSON array of important dates found in the document")
    statutes_cited: list = OutputField(
        description="JSON array of statutes and legislation referenced"
    )
    cases_cited: list = OutputField(
        description="JSON array of case citations found in the document"
    )
    summary: str = OutputField(
        description="2-3 sentence summary of the document's purpose and key provisions"
    )
    is_privileged: bool = OutputField(
        description="True if the document may contain privileged information"
    )
    confidence: float = OutputField(description="Classification confidence score 0.0-1.0")


class AssociateSignature(Signature):
    """You are a senior associate attorney performing legal analysis.

    Your core methodology is IRAC:
    - Issue: Precisely identify the legal issue(s)
    - Rule: State the applicable legal rules, statutes, and precedents
    - Application: Apply the rules to the specific facts
    - Conclusion: Provide a clear conclusion with confidence level

    Always cite specific statutes and case law. For Singapore law, use neutral
    citation format (e.g., [2024] SGHC 123). Flag issues where the law is
    unsettled or jurisdiction-dependent. Rate your confidence for each conclusion.
    """

    facts: str = InputField(description="Statement of facts from the case")
    legal_issues: str = InputField(description="Specific legal issues to analyze, as JSON array")
    jurisdiction: str = InputField(description="Applicable jurisdiction", default="SG")
    rag_context: str = InputField(
        description="Relevant case law and authorities from RAG search", default=""
    )

    issue_analysis: list = OutputField(
        description="JSON array of IRAC analyses, one per legal issue, each with "
        "issue_statement, rule, application, conclusion"
    )
    citations: list = OutputField(
        description="JSON array of all case citations used, with citation, court, year, treatment"
    )
    risk_assessment: str = OutputField(
        description="Overall risk assessment: low, medium, high, critical"
    )
    recommendations: list = OutputField(description="JSON array of recommended next steps")
    confidence: float = OutputField(description="Analysis confidence score 0.0-1.0")


class QASignature(Signature):
    """You are a quality assurance reviewer performing adversarial challenge on legal analysis.

    Your role:
    1. Check completeness — are all issues addressed?
    2. Check accuracy — are citations correct and current?
    3. Challenge weaknesses — identify counter-arguments and vulnerabilities
    4. Verify Singapore compliance — PDPA, court rules, citation format
    5. Determine if the analysis passes the quality gate

    Be thorough but fair. Flag genuine weaknesses, not stylistic preferences.
    """

    analysis: str = InputField(description="The legal analysis to review")
    original_query: str = InputField(description="The original user query or task")
    case_context: str = InputField(description="Case metadata for context", default="{}")
    quality_threshold: str = InputField(
        description="Minimum quality score (0.0-1.0) from SOP template — "
        "analysis must meet this threshold to pass",
        default="0.85",
    )

    completeness_score: float = OutputField(
        description="Score 0.0-1.0 for how completely all issues were addressed"
    )
    accuracy_issues: list = OutputField(
        description="JSON array of accuracy concerns (incorrect citations, outdated law, etc.)"
    )
    counter_arguments: list = OutputField(
        description="JSON array of counter-arguments or weaknesses in the analysis"
    )
    compliance_issues: list = OutputField(
        description="JSON array of Singapore compliance concerns (PDPA, citation format, etc.)"
    )
    quality_verdict: str = OutputField(
        description="'pass', 'rework', or 'escalate' with detailed reasoning"
    )
    rework_instructions: str = OutputField(
        description="Specific instructions for rework if verdict is 'rework', else empty string"
    )
    confidence: float = OutputField(description="Review confidence score 0.0-1.0")


class ResearchSignature(Signature):
    """You are a legal research specialist with access to 25,000+ Singapore cases.

    Your capabilities:
    1. Semantic search across case law using vector embeddings
    2. Citation network traversal (which cases cite which)
    3. Judge and court analysis (judicial tendencies)
    4. Statute and legislation lookup
    5. Authority scoring (court hierarchy-weighted relevance)

    Always return results ranked by relevance and authority weight.
    Distinguish binding precedent from persuasive authority.
    """

    query: str = InputField(description="Legal research query")
    jurisdiction: str = InputField(description="Target jurisdiction", default="SG")
    practice_area: str = InputField(description="Practice area for context", default="general")
    rag_context: str = InputField(description="Pre-retrieved context from RAG pipeline", default="")

    relevant_cases: list = OutputField(
        description="JSON array of relevant cases ranked by authority, each with "
        "citation, case_name, court, year, relevance_score, is_binding"
    )
    applicable_statutes: list = OutputField(
        description="JSON array of applicable statutes with section references"
    )
    authority_summary: str = OutputField(
        description="Summary of the state of the law on this topic"
    )
    conflicting_authorities: list = OutputField(
        description="JSON array of conflicting or distinguishable authorities"
    )
    confidence: float = OutputField(description="Research confidence score 0.0-1.0")


class DraftingSignature(Signature):
    """You are a legal drafting specialist producing formal legal documents.

    Your capabilities:
    1. Draft legal correspondence (letters of demand, advisory letters, notices)
    2. Draft court submissions (submissions, affidavits, applications)
    3. Draft contracts and agreements (clauses, schedules, amendments)
    4. Draft internal memos (case summaries, strategy memos, advice notes)

    Follow Singapore legal drafting conventions:
    - Formal register appropriate to the document type
    - Correct citation format (neutral citations for Singapore cases)
    - Proper statutory references (Act name, section, subsection)
    - Clear structure with numbered paragraphs for submissions
    - Include standard disclaimers and caveats where appropriate
    """

    document_type: str = InputField(
        description="Type of document to draft: letter_of_demand, advisory_letter, "
        "notice, submission, affidavit, application, contract, amendment, "
        "case_memo, strategy_memo, advice_note"
    )
    instructions: str = InputField(description="Specific drafting instructions and requirements")
    facts: str = InputField(description="Relevant facts to include in the draft", default="")
    legal_analysis: str = InputField(
        description="Legal analysis to incorporate (from Associate agent)", default=""
    )
    rag_context: str = InputField(
        description="Relevant precedents and authorities from RAG", default=""
    )
    tone: str = InputField(
        description="Tone: formal, firm, conciliatory, neutral", default="formal"
    )

    draft_text: str = OutputField(
        description="The complete drafted document text with proper formatting"
    )
    citations_used: list = OutputField(
        description="JSON array of all case citations and statutory references used"
    )
    disclaimers: list = OutputField(
        description="JSON array of disclaimers or caveats included in the draft"
    )
    review_notes: str = OutputField(
        description="Notes for the reviewing lawyer on key decisions made during drafting"
    )
    confidence: float = OutputField(description="Drafting confidence score 0.0-1.0")
