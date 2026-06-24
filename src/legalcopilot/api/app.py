"""Nexus application factory for LegalCoPilot v2.

Creates the unified API server with auth, CORS, rate limiting, and health checks.
Critical: auto_discovery=False when DataFlow is present, or startup blocks.
"""

import logging

from kailash import LocalRuntime
from nexus import Nexus
from nexus.auth.plugin import NexusAuthPlugin
from nexus.auth import JWTConfig, TenantConfig
from nexus.auth.rate_limit.config import RateLimitConfig
from nexus.auth.audit.config import AuditConfig

from legalcopilot.config import settings
from legalcopilot.models import db
from legalcopilot.api.auth import register_auth_routes
from legalcopilot.api.chat import register_chat_routes
from legalcopilot.api.cases import register_case_routes, register_document_routes
from legalcopilot.api.firm_knowledge import register_firm_knowledge_routes
from legalcopilot.api.knowledge import register_knowledge_routes


def create_app() -> Nexus:
    """Create and configure the Nexus application."""
    app = Nexus(
        api_host=settings.API_HOST,
        api_port=settings.API_PORT,
        auto_discovery=False,
        cors_origins=settings.CORS_ORIGINS,
        cors_allow_credentials=False,
        rate_limit=settings.RATE_LIMIT_RPM,
        enable_monitoring=True,
        log_level=settings.LOG_LEVEL,
    )

    _configure_auth(app)
    _register_health_checks(app)
    _register_dataflow_workflows(app)

    # Register domain API routes
    register_auth_routes(app)
    register_chat_routes(app)
    register_case_routes(app)
    register_document_routes(app)
    register_knowledge_routes(app)
    register_firm_knowledge_routes(app)

    return app


def _configure_auth(app: Nexus) -> None:
    """Configure JWT auth, RBAC, rate limiting, tenant isolation, and audit."""
    auth = NexusAuthPlugin.enterprise(
        jwt=JWTConfig(
            secret=settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
            exempt_paths=["/health", "/health/detailed", "/docs", "/openapi.json"],
            exempt_handlers=["login", "refresh_token"],
        ),
        rbac={
            "partner": ["*"],
            "senior_associate": [
                "cases:*",
                "documents:*",
                "conversations:*",
                "knowledge:read",
                "firm_knowledge:*",
                "research:*",
            ],
            "associate": [
                "cases:read",
                "cases:write",
                "documents:*",
                "conversations:*",
                "knowledge:read",
                "firm_knowledge:read",
                "firm_knowledge:write",
                "research:*",
            ],
            "paralegal": [
                "cases:read",
                "documents:read",
                "documents:write",
                "conversations:read",
                "knowledge:read",
                "firm_knowledge:read",
            ],
            "admin": ["*"],
            "viewer": ["cases:read", "documents:read", "conversations:read"],
        },
        rate_limit=RateLimitConfig(
            requests_per_minute=settings.RATE_LIMIT_RPM,
            burst_size=20,
            backend="redis" if settings.REDIS_URL else "memory",
            redis_url=settings.REDIS_URL if settings.REDIS_URL else None,
            route_limits={
                "/health": None,
                "/health/detailed": None,
            },
        ),
        tenant_isolation=TenantConfig(
            jwt_claim="firm_id",
            admin_role="partner",
        ),
        audit=AuditConfig(backend="logging"),
    )
    app.add_plugin(auth)


def _register_health_checks(app: Nexus) -> None:
    """Register custom health check handlers for DB and Qdrant."""
    _health_logger = logging.getLogger(__name__ + ".health")

    @app.health_check_handler("database")
    def check_database():
        try:
            workflows = db.get_workflows()
            if not workflows:
                return {"status": "unhealthy"}
            # Run a lightweight count to verify DB connectivity
            wf = workflows.get("firm_count")
            if wf:
                with LocalRuntime() as runtime:
                    runtime.execute(wf.build(), inputs={})
            return {"status": "healthy"}
        except Exception:
            _health_logger.warning("Database health check failed", exc_info=True)
            return {"status": "unhealthy"}

    @app.health_check_handler("qdrant")
    def check_qdrant():
        try:
            if not settings.QDRANT_URL:
                return {"status": "not_configured"}
            from legalcopilot.services.vector_store import _get_client

            client = _get_client()
            client.get_collections()
            return {"status": "healthy"}
        except Exception:
            _health_logger.warning("Qdrant health check failed", exc_info=True)
            return {"status": "unhealthy"}


def _register_dataflow_workflows(app: Nexus) -> None:
    """Register DataFlow auto-generated CRUD workflows with Nexus."""
    for name, wf in db.get_workflows().items():
        app.register(name, wf)
