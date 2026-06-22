"""Tests for Kaizen agent signatures and instantiation."""

import pytest

from legalcopilot.agents.signatures import (
    AssociateSignature,
    DraftingSignature,
    OrchestratorSignature,
    ParalegalSignature,
    QASignature,
    ResearchSignature,
)


class TestSignatureStructure:
    """Verify all signatures have correct InputField/OutputField definitions."""

    def test_orchestrator_has_inputs(self):
        sig = OrchestratorSignature()
        input_names = [f.name for f in sig.input_fields()]
        assert "request" in input_names
        assert "case_context" in input_names
        assert "conversation_history" in input_names

    def test_orchestrator_has_outputs(self):
        sig = OrchestratorSignature()
        output_names = [f.name for f in sig.output_fields()]
        assert "routing_decision" in output_names
        assert "case_type" in output_names
        assert "confidence" in output_names

    def test_paralegal_has_inputs(self):
        sig = ParalegalSignature()
        input_names = [f.name for f in sig.input_fields()]
        assert "document_text" in input_names
        assert "document_type" in input_names

    def test_paralegal_has_outputs(self):
        sig = ParalegalSignature()
        output_names = [f.name for f in sig.output_fields()]
        assert "classification" in output_names
        assert "parties" in output_names
        assert "is_privileged" in output_names
        assert "confidence" in output_names

    def test_associate_has_inputs(self):
        sig = AssociateSignature()
        input_names = [f.name for f in sig.input_fields()]
        assert "facts" in input_names
        assert "legal_issues" in input_names
        assert "jurisdiction" in input_names
        assert "rag_context" in input_names

    def test_associate_has_outputs(self):
        sig = AssociateSignature()
        output_names = [f.name for f in sig.output_fields()]
        assert "issue_analysis" in output_names
        assert "citations" in output_names
        assert "risk_assessment" in output_names

    def test_qa_has_verdict_output(self):
        sig = QASignature()
        output_names = [f.name for f in sig.output_fields()]
        assert "quality_verdict" in output_names
        assert "rework_instructions" in output_names
        assert "completeness_score" in output_names

    def test_research_has_outputs(self):
        sig = ResearchSignature()
        output_names = [f.name for f in sig.output_fields()]
        assert "relevant_cases" in output_names
        assert "applicable_statutes" in output_names
        assert "conflicting_authorities" in output_names

    def test_drafting_has_inputs(self):
        sig = DraftingSignature()
        input_names = [f.name for f in sig.input_fields()]
        assert "document_type" in input_names
        assert "instructions" in input_names
        assert "tone" in input_names

    def test_drafting_has_outputs(self):
        sig = DraftingSignature()
        output_names = [f.name for f in sig.output_fields()]
        assert "draft_text" in output_names
        assert "citations_used" in output_names
        assert "review_notes" in output_names


class TestSignatureDocstrings:
    """Signature docstrings become LLM system prompts — verify they exist."""

    def test_all_signatures_have_docstrings(self):
        for sig_class in [
            OrchestratorSignature,
            ParalegalSignature,
            AssociateSignature,
            QASignature,
            ResearchSignature,
            DraftingSignature,
        ]:
            assert sig_class.__doc__ is not None, f"{sig_class.__name__} missing docstring"
            assert len(sig_class.__doc__) > 50, f"{sig_class.__name__} docstring too short"


class TestAgentInstantiation:
    """Verify agents can be instantiated without errors."""

    def test_orchestrator_init(self):
        from legalcopilot.agents.orchestrator import OrchestratorAgent

        agent = OrchestratorAgent()
        assert agent is not None
        assert agent.quality_threshold == 0.80

    def test_paralegal_init(self):
        from legalcopilot.agents.paralegal import ParalegalAgent

        agent = ParalegalAgent()
        assert agent is not None

    def test_associate_init(self):
        from legalcopilot.agents.associate import AssociateAgent

        agent = AssociateAgent()
        assert agent is not None

    def test_drafting_init(self):
        from legalcopilot.agents.drafting import DraftingAgent

        agent = DraftingAgent()
        assert agent is not None

    def test_qa_reviewer_init(self):
        from legalcopilot.agents.qa_reviewer import QAReviewerAgent

        agent = QAReviewerAgent()
        assert agent is not None

    def test_researcher_init(self):
        from legalcopilot.agents.researcher import ResearchAgent

        agent = ResearchAgent()
        assert agent is not None


class TestOrchestratorHasAllSpecialists:
    """Orchestrator must have all specialist agents wired."""

    def test_has_all_specialists(self):
        from legalcopilot.agents.orchestrator import OrchestratorAgent

        orch = OrchestratorAgent()
        assert hasattr(orch, "paralegal")
        assert hasattr(orch, "associate")
        assert hasattr(orch, "drafting")
        assert hasattr(orch, "qa_reviewer")
        assert hasattr(orch, "researcher")


class TestAgentExports:
    """Verify __init__.py exports all agents."""

    def test_all_agents_exported(self):
        from legalcopilot.agents import (
            AssociateAgent,
            DraftingAgent,
            OrchestratorAgent,
            ParalegalAgent,
            QAReviewerAgent,
            ResearchAgent,
        )

        assert all(
            [
                OrchestratorAgent,
                ParalegalAgent,
                AssociateAgent,
                DraftingAgent,
                QAReviewerAgent,
                ResearchAgent,
            ]
        )
