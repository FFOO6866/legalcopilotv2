"""DataFlow database instance — single source of truth."""

from dataflow import DataFlow

from legalcopilot.config import settings

db = DataFlow(
    settings.DATABASE_URL,
    auto_migrate=True,
)
