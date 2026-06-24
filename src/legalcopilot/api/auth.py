"""Authentication API endpoints — login, logout, me, refresh.

These endpoints are JWT-exempt (added to exempt_paths in app.py).
All other endpoints require a valid JWT token.
"""

import datetime
import logging

from kailash import LocalRuntime
from nexus import Nexus

from legalcopilot.models.database import db
from legalcopilot.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)

logger = logging.getLogger(__name__)

_workflows = None


def _get_workflows() -> dict:
    global _workflows
    if _workflows is None:
        _workflows = db.get_workflows()
    return _workflows


def register_auth_routes(app: Nexus) -> None:
    """Register authentication endpoints on the Nexus app."""

    @app.handler("login", description="Authenticate with email and password")
    async def login(email: str, password: str) -> dict:
        wf = _get_workflows().get("user_search")
        if not wf:
            return {"error": "Auth service unavailable", "success": False}

        with LocalRuntime() as runtime:
            results, _ = runtime.execute(
                wf.build(),
                inputs={"search_params": {"email": email}, "limit": 1},
            )

        items = []
        for v in results.values():
            if isinstance(v, dict) and "items" in v:
                items = v["items"]
                break

        if not items:
            return {"error": "Invalid email or password", "success": False}

        user = items[0]

        if not user.get("active", False):
            return {"error": "Account is deactivated", "success": False}

        if user.get("password_hash") is None:
            return {"error": "Account not set up — no password configured", "success": False}

        if not verify_password(password, user["password_hash"]):
            return {"error": "Invalid email or password", "success": False}

        # Update last_login_at
        update_wf = _get_workflows().get("user_update")
        if update_wf:
            try:
                with LocalRuntime() as runtime:
                    runtime.execute(
                        update_wf.build(),
                        inputs={
                            "id": user["id"],
                            "data": {
                                "last_login_at": datetime.datetime.now(
                                    datetime.timezone.utc
                                ).isoformat(),
                            },
                        },
                    )
            except Exception:
                logger.warning("Failed to update last_login_at for user %s", user["id"])

        access_token = create_access_token(
            user_id=user["id"],
            firm_id=user["firm_id"],
            role=user["role"],
            email=user["email"],
        )
        refresh_token = create_refresh_token(
            user_id=user["id"],
            firm_id=user["firm_id"],
        )

        return {
            "success": True,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user["id"],
                "firm_id": user["firm_id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
            },
        }

    @app.handler("logout", description="Invalidate the current session")
    async def logout(user_id: str = "") -> dict:
        # JWT is stateless — logout is handled client-side by discarding the token.
        # This endpoint exists for the frontend to call on logout.
        return {"success": True, "message": "Logged out"}

    @app.handler("get_current_user", description="Get the authenticated user's profile")
    async def get_current_user(user_id: str, firm_id: str) -> dict:
        wf = _get_workflows().get("user_read")
        if not wf:
            return {"error": "Auth service unavailable"}

        with LocalRuntime() as runtime:
            results, _ = runtime.execute(
                wf.build(),
                inputs={"id": user_id},
            )

        user = None
        for v in results.values():
            if isinstance(v, dict) and "id" in v:
                user = v
                break

        if not user:
            return {"error": "User not found"}

        if user.get("firm_id") != firm_id:
            return {"error": "User not found"}

        return {
            "id": user["id"],
            "firm_id": user["firm_id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "active": user.get("active", True),
            "last_login_at": user.get("last_login_at"),
            "created_at": user.get("created_at"),
        }

    @app.handler("refresh_token", description="Refresh an expired access token")
    async def refresh_token(token: str) -> dict:
        payload = decode_token(token)
        if not payload:
            return {"error": "Invalid or expired refresh token", "success": False}

        if payload.get("type") != "refresh":
            return {"error": "Not a refresh token", "success": False}

        user_id = payload.get("sub")
        firm_id = payload.get("firm_id")

        # Verify user still exists and is active
        wf = _get_workflows().get("user_read")
        if not wf:
            return {"error": "Auth service unavailable", "success": False}

        with LocalRuntime() as runtime:
            results, _ = runtime.execute(wf.build(), inputs={"id": user_id})

        user = None
        for v in results.values():
            if isinstance(v, dict) and "id" in v:
                user = v
                break

        if not user or not user.get("active", False):
            return {"error": "User account no longer active", "success": False}

        access_token = create_access_token(
            user_id=user["id"],
            firm_id=user["firm_id"],
            role=user["role"],
            email=user["email"],
        )

        return {
            "success": True,
            "access_token": access_token,
        }
