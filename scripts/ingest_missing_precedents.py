#!/usr/bin/env python3
"""
Batch ingestion of missing precedent cases from NSPE website.

Reads case URLs from data/missing_precedent_cases.json and ingests each
using CitedCaseIngestor.ingest_from_url(). After ingestion, run:

    python scripts/populate_section_embeddings.py --all
    python scripts/llm_extract_features.py --all

Usage:
    python scripts/ingest_missing_precedents.py
    python scripts/ingest_missing_precedents.py --dry-run
    python scripts/ingest_missing_precedents.py --cases 82-5,85-3
"""

import argparse
import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/home/chris/onto')

from app import create_app
from app.models import db


def load_missing_cases(data_file):
    """Load the missing cases mapping."""
    with open(data_file) as f:
        data = json.load(f)
    return data['base_url'], data['cases']


def main():
    parser = argparse.ArgumentParser(
        description='Batch ingest missing precedent cases from NSPE'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show URLs without ingesting')
    parser.add_argument('--cases', type=str,
                        help='Comma-separated BER numbers to ingest (e.g., 82-5,85-3)')
    parser.add_argument('--world-id', type=int, default=1,
                        help='World ID for new documents (default: 1)')
    parser.add_argument('--data-file', type=str,
                        default=os.path.join(
                            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'data', 'missing_precedent_cases.json'
                        ),
                        help='Path to missing cases JSON')

    args = parser.parse_args()

    base_url, all_cases = load_missing_cases(args.data_file)

    # Filter to specific cases if requested
    if args.cases:
        requested = set(c.strip() for c in args.cases.split(','))
        cases = [c for c in all_cases if c['ber'] in requested]
        not_found = requested - {c['ber'] for c in cases}
        if not_found:
            print(f"Warning: BER numbers not in mapping: {not_found}")
    else:
        cases = all_cases

    print(f"\nMissing Precedent Case Ingestion")
    print(f"{'=' * 60}")
    print(f"Cases to process: {len(cases)}")
    print(f"Dry run: {args.dry_run}")
    print()

    if args.dry_run:
        for case in cases:
            url = base_url + case['slug']
            print(f"  BER {case['ber']:>5s}: {url}")
            print(f"           Title: {case['title']}")
            print(f"           Cited by: {case['cited_by']} ({case['citations']} citations)")
        print(f"\n{len(cases)} cases would be ingested.")
        return

    app = create_app()
    with app.app_context():
        from app.services.precedent.cited_case_ingestor import CitedCaseIngestor
        ingestor = CitedCaseIngestor()

        ingested = []
        failed = []
        skipped = []

        for i, case in enumerate(cases, 1):
            url = base_url + case['slug']
            ber = case['ber']

            print(f"[{i:2d}/{len(cases)}] BER {ber:>5s}: {case['title']}")

            # Check if already exists by case number
            from sqlalchemy import text
            existing = db.session.execute(text("""
                SELECT id FROM documents
                WHERE doc_metadata->>'case_number' = :ber
                LIMIT 1
            """), {'ber': ber}).fetchone()

            if existing:
                print(f"         SKIP - already exists as Case {existing[0]}")
                skipped.append({'ber': ber, 'existing_id': existing[0]})
                continue

            result = ingestor.ingest_from_url(url, world_id=args.world_id)

            if result and result.get('success'):
                print(f"         OK - Case {result['new_case_id']}: {result.get('title', '')}")
                ingested.append({
                    'ber': ber,
                    'case_id': result['new_case_id'],
                    'title': result.get('title', ''),
                })
            else:
                reason = result.get('reason', 'unknown') if result else 'no result'
                print(f"         FAIL - {reason}")
                failed.append({'ber': ber, 'url': url, 'reason': reason})

            # Brief pause between requests
            if i < len(cases):
                time.sleep(1)

        # Summary
        print(f"\n{'=' * 60}")
        print(f"Summary")
        print(f"{'=' * 60}")
        print(f"Ingested: {len(ingested)}")
        print(f"Skipped:  {len(skipped)}")
        print(f"Failed:   {len(failed)}")

        if ingested:
            new_ids = [str(r['case_id']) for r in ingested]
            print(f"\nNew case IDs: {', '.join(new_ids)}")
            print(f"\nNext steps:")
            print(f"  1. python scripts/populate_section_embeddings.py --cases {','.join(new_ids)}")
            print(f"  2. python scripts/llm_extract_features.py --cases {','.join(new_ids)}")

        if failed:
            print(f"\nFailed cases:")
            for f in failed:
                print(f"  BER {f['ber']}: {f['reason']}")
                print(f"    URL: {f['url']}")

        # Update resolved citations regardless
        print(f"\nUpdating resolved citations...")
        updated = ingestor.update_resolved_citations()
        print(f"Updated {updated} cases with resolved citation links.")


if __name__ == '__main__':
    main()
