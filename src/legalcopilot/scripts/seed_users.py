"""Seed the database with default users for RevLaw LLC.

Run: python -m legalcopilot.scripts.seed_users

Creates (idempotently):
  - Firm: RevLaw LLC
  - Users: Sui Tong (partner), Yik Wee (partner), Tech Admin (admin)
  - Default password for all: RevLaw2024!
"""

import logging
import uuid

from kailash import LocalRuntime

from legalcopilot.models.database import db
from legalcopilot.services.auth_service import hash_password

# Force model registration
import legalcopilot.models.core  # noqa: F401

logger = logging.getLogger(__name__)

FIRM_ID = "firm-revlaw-001"
DEFAULT_PASSWORD = "RevLaw2024!"

SEED_FIRM = {
    "id": FIRM_ID,
    "name": "RevLaw LLC",
    "domain": "revlawllc.com",
    "subscription_plan": "professional",
    "active": True,
}

SEED_USERS = [
    {
        "id": "user-suitong-001",
        "firm_id": FIRM_ID,
        "email": "suitong@revlawllc.com",
        "name": "Sui Tong",
        "role": "partner",
        "active": True,
    },
    {
        "id": "user-yikwee-001",
        "firm_id": FIRM_ID,
        "email": "yikwee@revlawllc.com",
        "name": "Yik Wee",
        "role": "partner",
        "active": True,
    },
    {
        "id": "user-admin-001",
        "firm_id": FIRM_ID,
        "email": "admin@revlawllc.com",
        "name": "Tech Admin",
        "role": "admin",
        "active": True,
    },
]


def seed() -> None:
    """Create the default firm and users if they don't exist."""
    workflows = db.get_workflows()
    password_hash = hash_password(DEFAULT_PASSWORD)

    # Seed firm
    firm_exists_wf = workflows.get("firm_exists")
    firm_create_wf = workflows.get("firm_create")

    if firm_exists_wf and firm_create_wf:
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(
                firm_exists_wf.build(), inputs={"id": FIRM_ID}
            )
        exists = any(v is True for v in results.values())

        if not exists:
            with LocalRuntime() as runtime:
                runtime.execute(firm_create_wf.build(), inputs={"data": SEED_FIRM})
            print(f"Created firm: {SEED_FIRM['name']}")
        else:
            print(f"Firm already exists: {SEED_FIRM['name']}")

    # Seed users
    user_search_wf = workflows.get("user_search")
    user_create_wf = workflows.get("user_create")

    if not user_search_wf or not user_create_wf:
        print("ERROR: user_search or user_create workflows not found")
        return

    for user_data in SEED_USERS:
        with LocalRuntime() as runtime:
            results, _ = runtime.execute(
                user_search_wf.build(),
                inputs={"search_params": {"email": user_data["email"]}, "limit": 1},
            )

        items = []
        for v in results.values():
            if isinstance(v, dict) and "items" in v:
                items = v["items"]
                break

        if items:
            print(f"User already exists: {user_data['email']}")
            # Update password hash if missing
            existing = items[0]
            if not existing.get("password_hash"):
                user_update_wf = workflows.get("user_update")
                if user_update_wf:
                    with LocalRuntime() as runtime:
                        runtime.execute(
                            user_update_wf.build(),
                            inputs={
                                "id": existing["id"],
                                "data": {"password_hash": password_hash},
                            },
                        )
                    print(f"  Updated password hash for: {user_data['email']}")
        else:
            create_data = {**user_data, "password_hash": password_hash}
            with LocalRuntime() as runtime:
                runtime.execute(user_create_wf.build(), inputs={"data": create_data})
            print(f"Created user: {user_data['name']} ({user_data['email']}) [{user_data['role']}]")

    print("\nSeed complete. Login credentials:")
    print(f"  Email: suitong@revlawllc.com  Password: {DEFAULT_PASSWORD}")
    print(f"  Email: yikwee@revlawllc.com   Password: {DEFAULT_PASSWORD}")
    print(f"  Email: admin@revlawllc.com    Password: {DEFAULT_PASSWORD}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed()
