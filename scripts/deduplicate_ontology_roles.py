#!/usr/bin/env python3
import os
import sys

from app import create_app, db


def main():
    if len(sys.argv) < 2:
        print("Usage: deduplicate_ontology_roles.py <ontology_id> [--dry-run]")
        sys.exit(1)

    ontology_id = int(sys.argv[1])
    dry = '--dry-run' in sys.argv

    app = create_app('config')
    with app.app_context():
        from ontology_editor.services.entity_service import EntityService
        res = EntityService.deduplicate_roles(ontology_id, dry_run=dry)
        print("=== Deduplication Result ===")
        for k, v in res.items():
            if k == 'groups':
                print(f"{k}: {len(v)} groups with duplicates")
                for g in v:
                    print(f"  label={g['label']}\n    winner={g['winner']}\n    losers={len(g['losers'])}")
            else:
                print(f"{k}: {v}")


if __name__ == '__main__':
    main()
