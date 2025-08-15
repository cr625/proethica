#!/usr/bin/env python3
"""
Run the GuidelineTripleCleanupService in-app context.

Usage examples:
  python3 scripts/run_guideline_triple_cleanup.py --world-id 1           # dry run (default)
  python3 scripts/run_guideline_triple_cleanup.py --world-id 1 --apply   # apply changes
  python3 scripts/run_guideline_triple_cleanup.py --exclude-ids 18,33    # protect guideline IDs
"""
import argparse
import json
import sys
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app  # noqa: E402
from app.services.guideline_triple_cleanup_service import (  # noqa: E402
    get_guideline_triple_cleanup_service,
)


def parse_args():
    p = argparse.ArgumentParser(description="Cleanup guideline triples")
    p.add_argument("--world-id", type=int, default=None, help="Restrict to world ID")
    p.add_argument(
        "--exclude-ids",
        type=str,
        default="",
        help="Comma-separated guideline IDs to exclude from deletion/nullify",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    p.add_argument(
        "--no-delete-non-core",
        action="store_true",
        help="Do not delete non-core triples (only report)",
    )
    p.add_argument(
        "--no-nullify",
        action="store_true",
        help="Do not nullify core triples with orphan guideline refs",
    )
    return p.parse_args()


def main():
    args = parse_args()
    exclude = []
    if args.exclude_ids.strip():
        try:
            exclude = [int(x) for x in args.exclude_ids.split(",") if x.strip().isdigit()]
        except Exception:
            exclude = []

    # Ensure we load enhanced config which sets SQLALCHEMY_DATABASE_URI
    if not os.environ.get('CONFIG_MODULE'):
        os.environ['CONFIG_MODULE'] = 'config'
    app = create_app(os.environ['CONFIG_MODULE'])
    with app.app_context():
        svc = get_guideline_triple_cleanup_service()
        result = svc.cleanup(
            world_id=args.world_id,
            exclude_guideline_ids=exclude,
            delete_non_core=not args.no_delete_non_core,
            nullify_core_if_orphan_guideline=not args.no_nullify,
            dry_run=not args.apply,
        )

        # Pretty print JSON result
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    sys.exit(main())
