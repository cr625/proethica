#!/usr/bin/env python3
"""
Purge scenarios and all dependent rows safely.

Features:
- Dry run preview (default) to show counts per table.
- Confirmation gate (--yes) to run destructive deletes.
- Optional filtering by scenario IDs.

Usage examples:
  python3 scripts/purge_scenarios.py --dry-run
  python3 scripts/purge_scenarios.py --scenario-id 7 --scenario-id 13 --yes

Notes:
- Runs in a single DB transaction; if anything fails, nothing is deleted.
- Requires application config to be valid for DB connection.
"""
from __future__ import annotations

import argparse
import sys
from typing import Dict, List, Tuple
from pathlib import Path

from sqlalchemy import text

# Ensure app context and database session
try:
    # Add project root to sys.path for module resolution when run directly
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from app import create_app, db
except Exception as e:
    print(f"Error importing app: {e}")
    sys.exit(1)


TABLES_ORDERED: List[Tuple[str, str]] = [
    # deepest dependents first
    ("wizard_steps", "DELETE FROM wizard_steps WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})"),
    ("user_wizard_sessions", "DELETE FROM user_wizard_sessions WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})"),
    ("simulation_states", "DELETE FROM simulation_states WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})"),
    ("simulation_sessions", "DELETE FROM simulation_sessions WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})"),
    ("conditions", "DELETE FROM conditions WHERE character_id IN (SELECT id FROM characters WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter}))"),
    ("character_triples", "DELETE FROM character_triples WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})"),
    ("entity_triples", "DELETE FROM entity_triples WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})"),
    ("actions", "DELETE FROM actions WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})"),
    ("events", "DELETE FROM events WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})"),
    ("resources", "DELETE FROM resources WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})"),
    ("decisions", "DELETE FROM decisions WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})"),
    ("characters", "DELETE FROM characters WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})"),
    ("scenario_templates", "DELETE FROM scenario_templates WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})"),
    ("scenarios", "DELETE FROM scenarios WHERE {filter}"),
]

COUNT_QUERIES: Dict[str, str] = {
    "scenarios": "SELECT COUNT(*) FROM scenarios WHERE {filter}",
    "characters": "SELECT COUNT(*) FROM characters WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})",
    "events": "SELECT COUNT(*) FROM events WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})",
    "actions": "SELECT COUNT(*) FROM actions WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})",
    "resources": "SELECT COUNT(*) FROM resources WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})",
    "decisions": "SELECT COUNT(*) FROM decisions WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})",
    "conditions": "SELECT COUNT(*) FROM conditions WHERE character_id IN (SELECT id FROM characters WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter}))",
    "wizard_steps": "SELECT COUNT(*) FROM wizard_steps WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})",
    "user_wizard_sessions": "SELECT COUNT(*) FROM user_wizard_sessions WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})",
    "simulation_states": "SELECT COUNT(*) FROM simulation_states WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})",
    "simulation_sessions": "SELECT COUNT(*) FROM simulation_sessions WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})",
    "character_triples": "SELECT COUNT(*) FROM character_triples WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})",
    "entity_triples": "SELECT COUNT(*) FROM entity_triples WHERE scenario_id IN (SELECT id FROM scenarios WHERE {filter})",
}


def build_filter(scenario_ids: List[int] | None) -> Tuple[str, Dict[str, object]]:
    if scenario_ids:
        placeholders = ",".join([f":sid{i}" for i, _ in enumerate(scenario_ids)])
        params: Dict[str, object] = {f"sid{i}": sid for i, sid in enumerate(scenario_ids)}
        return f"id IN ({placeholders})", params
    # default: all scenarios
    return "1=1", {}


def fetch_counts(filter_sql: str, params: Dict[str, object]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for table, sql in COUNT_QUERIES.items():
        q = text(sql.format(filter=filter_sql))
        res = db.session.execute(q, params).scalar()
        counts[table] = int(res or 0)
    return counts


def purge(filter_sql: str, params: Dict[str, object]) -> Dict[str, int]:
    deleted: Dict[str, int] = {}
    for table, sql in TABLES_ORDERED:
        q = text(sql.format(filter=filter_sql))
        result = db.session.execute(q, params)
        # result.rowcount may be -1 for some drivers; coerce to 0+ with max
        deleted[table] = max(result.rowcount or 0, 0)
    return deleted


def main():
    parser = argparse.ArgumentParser(description="Purge scenarios and dependents safely.")
    parser.add_argument(
        "--scenario-id",
        action="append",
        type=int,
        help="Scenario ID to purge. Repeatable. If omitted, purges ALL scenarios.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without making changes.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt and proceed with deletion.",
    )

    args = parser.parse_args()

    app = create_app('config')  # use enhanced config if available
    with app.app_context():
        filter_sql, params = build_filter(args.scenario_id)

        counts_before = fetch_counts(filter_sql, params)
        total_scenarios = counts_before.get("scenarios", 0)

        print("Preview (matches filter):")
        for key in sorted(counts_before.keys()):
            print(f"  {key}: {counts_before[key]}")

        if total_scenarios == 0:
            print("No scenarios matched the filter. Nothing to do.")
            return 0

        if args.dry_run:
            print("\nDry run only. No changes made.")
            return 0

        if not args.yes:
            print("\nThis will permanently delete the above records in a single transaction.")
            resp = input("Type 'delete' to confirm: ").strip().lower()
            if resp != "delete":
                print("Aborted.")
                return 1

        try:
            # begin transaction
            deleted_totals: Dict[str, int] = {}
            # Use session.begin() context manager for transactional scope
            with db.session.begin():
                deleted_totals = purge(filter_sql, params)

            print("\nDeleted rows:")
            for table, count in deleted_totals.items():
                print(f"  {table}: {count}")

            # Verify post state
            counts_after = fetch_counts(filter_sql, params)
            print("\nRemaining (should be 0 for all except unrelated tables):")
            for key in sorted(counts_after.keys()):
                print(f"  {key}: {counts_after[key]}")

            return 0
        except Exception as e:
            db.session.rollback()
            print(f"Error during purge, rolled back: {e}")
            return 2


if __name__ == "__main__":
    sys.exit(main())
