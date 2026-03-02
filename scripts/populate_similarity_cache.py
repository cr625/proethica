#!/usr/bin/env python3
"""
Pre-compute pairwise similarity scores and populate precedent_similarity_cache.

Prevents OOM errors on the /cases/precedents/network page by computing all
similarity pairs offline instead of on-the-fly during page load.

Usage:
    python scripts/populate_similarity_cache.py --all
    python scripts/populate_similarity_cache.py --all --force
    python scripts/populate_similarity_cache.py --cases 73,74,75
    python scripts/populate_similarity_cache.py --all --dry-run
"""

import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/home/chris/onto')

from app import create_app
from app.models import db
from sqlalchemy import text


def get_all_case_ids():
    """Get all case IDs that have precedent features."""
    rows = db.session.execute(text(
        "SELECT case_id FROM case_precedent_features ORDER BY case_id"
    )).fetchall()
    return [r[0] for r in rows]


def get_cached_pairs():
    """Get set of already-cached (source, target) pairs."""
    rows = db.session.execute(text(
        "SELECT source_case_id, target_case_id FROM precedent_similarity_cache"
    )).fetchall()
    pairs = set()
    for r in rows:
        pairs.add((r[0], r[1]))
        pairs.add((r[1], r[0]))
    return pairs


def main():
    parser = argparse.ArgumentParser(
        description='Pre-compute pairwise similarity cache for precedent network'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all', action='store_true',
                       help='Compute all missing pairs')
    group.add_argument('--cases', type=str,
                       help='Comma-separated case IDs (computes pairs among these)')
    parser.add_argument('--force', action='store_true',
                        help='Recompute even if already cached')
    parser.add_argument('--batch-size', type=int, default=50,
                        help='Commit every N pairs (default: 50)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be computed without saving')

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        from app.services.precedent.similarity_service import PrecedentSimilarityService
        service = PrecedentSimilarityService()

        if args.all:
            case_ids = get_all_case_ids()
        else:
            case_ids = [int(c.strip()) for c in args.cases.split(',')]

        if len(case_ids) < 2:
            print("Need at least 2 cases to compute pairs.")
            return

        total_possible = len(case_ids) * (len(case_ids) - 1) // 2

        # Build list of pairs to compute
        if args.force:
            cached_pairs = set()
        else:
            cached_pairs = get_cached_pairs()

        pairs_to_compute = []
        for i, src_id in enumerate(case_ids):
            for tgt_id in case_ids[i + 1:]:
                if (src_id, tgt_id) not in cached_pairs:
                    pairs_to_compute.append((src_id, tgt_id))

        print(f"\nSimilarity Cache Population")
        print(f"{'=' * 60}")
        print(f"Cases: {len(case_ids)} ({case_ids[0]}..{case_ids[-1]})")
        print(f"Total possible pairs: {total_possible}")
        print(f"Already cached: {total_possible - len(pairs_to_compute)}")
        print(f"To compute: {len(pairs_to_compute)}")
        print(f"Batch size: {args.batch_size}")
        print(f"Dry run: {args.dry_run}")
        print()

        if not pairs_to_compute:
            print("All pairs already cached.")
            return

        if args.dry_run:
            print(f"Would compute {len(pairs_to_compute)} pairs. Exiting (dry run).")
            return

        computed = 0
        skipped = 0
        errors = 0
        start_time = time.time()
        batch_start = time.time()

        for src_id, tgt_id in pairs_to_compute:
            try:
                result = service.calculate_similarity(src_id, tgt_id)
                service.cache_similarity(result)
                computed += 1
            except Exception as e:
                errors += 1
                print(f"  ERROR: ({src_id}, {tgt_id}): {e}")
                continue

            # Batch commit
            if computed % args.batch_size == 0:
                db.session.commit()
                elapsed = time.time() - start_time
                batch_elapsed = time.time() - batch_start
                rate = computed / elapsed if elapsed > 0 else 0
                remaining = (len(pairs_to_compute) - computed) / rate if rate > 0 else 0
                print(
                    f"  {computed}/{len(pairs_to_compute)} pairs "
                    f"({computed * 100 // len(pairs_to_compute)}%) "
                    f"- {rate:.1f} pairs/sec "
                    f"- ETA: {remaining:.0f}s"
                )
                batch_start = time.time()

        # Final commit
        db.session.commit()

        elapsed = time.time() - start_time
        print(f"\n{'=' * 60}")
        print(f"Complete")
        print(f"{'=' * 60}")
        print(f"Computed: {computed}")
        print(f"Errors: {errors}")
        print(f"Time: {elapsed:.1f}s ({computed / elapsed:.1f} pairs/sec)" if elapsed > 0 else "")

        # Verify
        row = db.session.execute(text(
            "SELECT COUNT(*) FROM precedent_similarity_cache"
        )).fetchone()
        print(f"Total cached pairs: {row[0]} / {total_possible}")


if __name__ == '__main__':
    main()
