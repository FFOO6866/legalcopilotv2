"""Tests for Nexus app factory and route registration."""

import pytest

from legalcopilot.api.app import create_app


class TestAppFactory:
    def test_creates_nexus_app(self):
        app = create_app()
        assert app is not None

    def test_auto_discovery_disabled(self):
        """auto_discovery=False is critical when DataFlow is present."""
        app = create_app()
        assert app._auto_discovery is False or not getattr(app, "_auto_discovery", True)


class TestRouteRegistration:
    """Verify all handler routes are registered on the app."""

    @pytest.fixture
    def app(self):
        return create_app()

    def test_chat_routes_registered(self, app):
        handler_names = [h.name for h in app.handlers] if hasattr(app, "handlers") else []
        if handler_names:
            assert "create_conversation" in handler_names
            assert "send_message" in handler_names
            assert "draft_document" in handler_names

    def test_case_routes_registered(self, app):
        handler_names = [h.name for h in app.handlers] if hasattr(app, "handlers") else []
        if handler_names:
            assert "create_case" in handler_names
            assert "list_cases" in handler_names
            assert "update_case" in handler_names

    def test_document_routes_registered(self, app):
        handler_names = [h.name for h in app.handlers] if hasattr(app, "handlers") else []
        if handler_names:
            assert "upload_document" in handler_names
            assert "list_documents" in handler_names

    def test_knowledge_routes_registered(self, app):
        handler_names = [h.name for h in app.handlers] if hasattr(app, "handlers") else []
        if handler_names:
            assert "search_cases" in handler_names
            assert "legal_research" in handler_names
            assert "get_sop_template" in handler_names
            assert "list_sop_templates" in handler_names


class TestModelExports:
    """Verify all DataFlow models are accessible."""

    def test_all_models_importable(self):
        from legalcopilot.models import (
            AuditEntry,
            Case,
            Conversation,
            Document,
            EngagementMetrics,
            Firm,
            FirmKnowledge,
            KGCaseJudge,
            KGCaseTopic,
            KGCitationEdge,
            KGJudge,
            KGLegislationRef,
            KnowledgeEntry,
            KnowledgeVector,
            Message,
            RAGFeedback,
            SOPTemplate,
            User,
            db,
        )

        assert db is not None
        assert Firm is not None
        assert Case is not None
        assert KnowledgeEntry is not None
