#!/usr/bin/env python3
"""Migrate LegalCoPilot v1 data to v2 schema.

Reads from v1's database via a DataFlow connection and maps records into
v2's DataFlow models via auto-generated workflows.

Usage:
    python scripts/migrate_v1_data.py --source-db <v1_db_url> [--batch-size 500] [--dry-run]

Requires:
    - V1 database accessible via the provided connection string
    - V2 database configured via DATABASE_URL in .env
"""

import argparse
import logging
import os
import sys
import uuid

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("migrate_v1")


# V1 → V2 field mappings

COURT_MAP = {
    "High Court": "SGHC",
    "Court of Appeal": "SGCA",
    "District Court": "SGDC",
    "Magistrate Court": "SGMC",
    "Family Court": "SGFC",
    "State Courts": "SGSC",
}


def _read_v1_records(v1_db, query: str) -> list[dict]:
    """Read records from v1 database via DataFlow connection.

    Uses DataFlow's connection pool for the v1 (read-only) database.
    Returns rows as list of dicts keyed by column name.
    """
    from kailash import LocalRuntime, WorkflowBuilder

    wf = WorkflowBuilder("v1_read")
    wf.add_node("SQLQuery", "read", {"query": query, "connection": "v1_source"})
    with LocalRuntime() as runtime:
        results, _ = runtime.execute(wf.build())
    return results.get("read", {}).get("rows", [])


def _insert_batch(v2_db, model_name: str, batch: list[dict]) -> None:
    """Insert a batch of records using DataFlow bulk create workflow."""
    from kailash import LocalRuntime

    workflows = v2_db.get_workflows()
    wf_name = f"{model_name.lower()}_bulk_create"
    wf = workflows.get(wf_name)

    if not wf:
        logger.warning("Workflow %s not found, falling back to individual creates", wf_name)
        create_wf = workflows.get(f"{model_name.lower()}_create")
        if not create_wf:
            logger.error("No create workflow found for %s", model_name)
            return
        with LocalRuntime() as runtime:
            for record in batch:
                runtime.execute(create_wf.build(), inputs=record)
        return

    with LocalRuntime() as runtime:
        runtime.execute(wf.build(), inputs={"records": batch})


def migrate_knowledge_entries(v1_db, v2_db, batch_size: int, dry_run: bool) -> int:
    """Migrate case law entries from v1 to v2 KnowledgeEntry model."""
    logger.info("Migrating knowledge entries...")

    rows = _read_v1_records(
        v1_db,
        "SELECT id, citation, case_name, court, jurisdiction, decision_date, "
        "year, coram, full_text, summary, headnotes, source, source_url, "
        "has_full_judgment, metadata, created_at "
        "FROM knowledge_entries ORDER BY id",
    )

    count = 0
    batch = []

    for row in rows:
        entry = {
            "id": str(row.get("id", uuid.uuid4())),
            "citation": row.get("citation", ""),
            "case_name": row.get("case_name", ""),
            "court": COURT_MAP.get(row.get("court", ""), row.get("court", "")),
            "jurisdiction": row.get("jurisdiction", "SG"),
            "decision_date": row.get("decision_date"),
            "year": row.get("year"),
            "coram": row.get("coram"),
            "full_text": row.get("full_text"),
            "summary": row.get("summary"),
            "headnotes": row.get("headnotes"),
            "source": row.get("source", "elitigation"),
            "source_url": row.get("source_url"),
            "has_full_judgment": bool(row.get("has_full_judgment", False)),
            "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        }
        batch.append(entry)

        if len(batch) >= batch_size:
            if not dry_run:
                _insert_batch(v2_db, "KnowledgeEntry", batch)
            count += len(batch)
            logger.info("Knowledge entries migrated: %d", count)
            batch = []

    if batch:
        if not dry_run:
            _insert_batch(v2_db, "KnowledgeEntry", batch)
        count += len(batch)

    logger.info("Knowledge entries migration complete: %d total", count)
    return count


def migrate_citation_graph(v1_db, v2_db, batch_size: int, dry_run: bool) -> int:
    """Migrate citation edges from v1 to v2 KGCitationEdge model."""
    logger.info("Migrating citation graph...")

    rows = _read_v1_records(
        v1_db,
        "SELECT id, citing_entry_id, cited_entry_id, treatment, "
        "paragraph_refs, created_at "
        "FROM citation_edges ORDER BY id",
    )

    count = 0
    batch = []

    for row in rows:
        edge = {
            "id": str(row.get("id", uuid.uuid4())),
            "citing_entry_id": str(row.get("citing_entry_id", "")),
            "cited_entry_id": str(row.get("cited_entry_id", "")),
            "treatment": row.get("treatment", "cited"),
            "paragraph_refs": (
                row.get("paragraph_refs") if isinstance(row.get("paragraph_refs"), dict) else {}
            ),
        }
        batch.append(edge)

        if len(batch) >= batch_size:
            if not dry_run:
                _insert_batch(v2_db, "KGCitationEdge", batch)
            count += len(batch)
            logger.info("Citation edges migrated: %d", count)
            batch = []

    if batch:
        if not dry_run:
            _insert_batch(v2_db, "KGCitationEdge", batch)
        count += len(batch)

    logger.info("Citation graph migration complete: %d total", count)
    return count


def migrate_judges(v1_db, v2_db, batch_size: int, dry_run: bool) -> int:
    """Migrate judge records from v1 to v2 KGJudge model."""
    logger.info("Migrating judges...")

    rows = _read_v1_records(
        v1_db,
        "SELECT id, name, court, title, appointed_date, retired_date, "
        "metadata, created_at "
        "FROM judges ORDER BY id",
    )

    count = 0
    batch = []

    for row in rows:
        judge = {
            "id": str(row.get("id", uuid.uuid4())),
            "name": row.get("name", ""),
            "court": COURT_MAP.get(row.get("court", ""), row.get("court", "")),
            "title": row.get("title", ""),
            "appointed_date": row.get("appointed_date"),
            "retired_date": row.get("retired_date"),
            "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        }
        batch.append(judge)

        if len(batch) >= batch_size:
            if not dry_run:
                _insert_batch(v2_db, "KGJudge", batch)
            count += len(batch)
            batch = []

    if batch:
        if not dry_run:
            _insert_batch(v2_db, "KGJudge", batch)
        count += len(batch)

    logger.info("Judges migration complete: %d total", count)
    return count


def migrate_legislation_refs(v1_db, v2_db, batch_size: int, dry_run: bool) -> int:
    """Migrate legislation references from v1 to v2 KGLegislationRef model."""
    logger.info("Migrating legislation references...")

    rows = _read_v1_records(
        v1_db,
        "SELECT id, entry_id, statute_name, section, subsection, "
        "chapter, context_text, created_at "
        "FROM legislation_refs ORDER BY id",
    )

    count = 0
    batch = []

    for row in rows:
        ref = {
            "id": str(row.get("id", uuid.uuid4())),
            "entry_id": str(row.get("entry_id", "")),
            "statute_name": row.get("statute_name", ""),
            "section": row.get("section", ""),
            "subsection": row.get("subsection", ""),
            "chapter": row.get("chapter", ""),
            "context_text": row.get("context_text"),
        }
        batch.append(ref)

        if len(batch) >= batch_size:
            if not dry_run:
                _insert_batch(v2_db, "KGLegislationRef", batch)
            count += len(batch)
            batch = []

    if batch:
        if not dry_run:
            _insert_batch(v2_db, "KGLegislationRef", batch)
        count += len(batch)

    logger.info("Legislation refs migration complete: %d total", count)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate LegalCoPilot v1 data to v2")
    parser.add_argument(
        "--source-db",
        required=True,
        help="V1 database connection string (used as DataFlow connection)",
    )
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for inserts")
    parser.add_argument("--dry-run", action="store_true", help="Count records without writing")
    parser.add_argument(
        "--tables",
        nargs="+",
        default=["knowledge", "citations", "judges", "legislation"],
        help="Tables to migrate (default: all)",
    )
    args = parser.parse_args()

    logger.info("Starting v1 → v2 migration (dry_run=%s)", args.dry_run)

    # Set up V1 as a named DataFlow connection
    os.environ["DATAFLOW_V1_SOURCE_URL"] = args.source_db

    from dataflow import DataFlow

    v1_db = DataFlow(args.source_db)

    # Import v2 DataFlow
    from legalcopilot.models import db as v2_db

    totals = {}

    if "knowledge" in args.tables:
        totals["knowledge_entries"] = migrate_knowledge_entries(
            v1_db, v2_db, args.batch_size, args.dry_run
        )

    if "citations" in args.tables:
        totals["citation_edges"] = migrate_citation_graph(
            v1_db, v2_db, args.batch_size, args.dry_run
        )

    if "judges" in args.tables:
        totals["judges"] = migrate_judges(v1_db, v2_db, args.batch_size, args.dry_run)

    if "legislation" in args.tables:
        totals["legislation_refs"] = migrate_legislation_refs(
            v1_db, v2_db, args.batch_size, args.dry_run
        )

    logger.info("Migration complete. Totals: %s", totals)

    if args.dry_run:
        logger.info("DRY RUN — no data was written to v2 database")


if __name__ == "__main__":
    main()
