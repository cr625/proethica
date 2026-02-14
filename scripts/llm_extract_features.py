#!/usr/bin/env python3
"""
LLM-based precedent feature extraction.

Uses Claude Haiku to extract provisions_cited, outcome_type, and subject_tags
from case discussion and conclusion text. Identifies provisions even when not
explicitly cited by NSPE Code number.

Usage:
    python scripts/llm_extract_features.py --all
    python scripts/llm_extract_features.py --cases 73,74,75
    python scripts/llm_extract_features.py --all --dry-run
    python scripts/llm_extract_features.py --all --force
"""

import argparse
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/home/chris/onto')

from app import create_app
from app.models import Document, db
from app.models.document_section import DocumentSection
from sqlalchemy import text


def get_case_text(case_id):
    """Get discussion and conclusion text from document_sections."""
    discussion = DocumentSection.query.filter_by(
        document_id=case_id, section_type='discussion'
    ).first()
    conclusion = DocumentSection.query.filter_by(
        document_id=case_id, section_type='conclusion'
    ).first()

    return (
        discussion.content if discussion else '',
        conclusion.content if conclusion else '',
    )


def needs_extraction(case_id, force=False):
    """Check if a case needs LLM extraction."""
    if force:
        return True

    row = db.session.execute(text("""
        SELECT outcome_type, provision_count, subject_tags
        FROM case_precedent_features
        WHERE case_id = :case_id
    """), {'case_id': case_id}).fetchone()

    if not row:
        return True

    outcome_type, provision_count, subject_tags = row
    has_outcome = outcome_type and outcome_type != 'unclear'
    has_provisions = provision_count and provision_count > 0
    has_tags = subject_tags and subject_tags != '{}'

    # Extract if any feature is missing
    return not (has_outcome and has_provisions and has_tags)


def process_case(case_id, extractor, dry_run=False, force=False):
    """Extract features for a single case using LLM."""
    result = {
        'case_id': case_id,
        'success': False,
        'skipped': False,
        'outcome': None,
        'provision_count': 0,
        'tag_count': 0,
        'message': '',
    }

    if not needs_extraction(case_id, force):
        result['skipped'] = True
        result['success'] = True
        result['message'] = 'Already has all features'
        return result

    discussion_text, conclusion_text = get_case_text(case_id)
    if not discussion_text and not conclusion_text:
        result['message'] = 'No discussion or conclusion text'
        return result

    if dry_run:
        result['success'] = True
        result['message'] = (
            f"Would extract from {len(discussion_text)} chars discussion, "
            f"{len(conclusion_text)} chars conclusion"
        )
        return result

    try:
        features = extractor.llm_extract_features(discussion_text, conclusion_text)
    except Exception as e:
        result['message'] = f"LLM error: {e}"
        return result

    provisions = features.get('provisions_cited', [])
    outcome_type = features.get('outcome_type', 'unclear')
    outcome_reasoning = features.get('outcome_reasoning', '')
    subject_tags = features.get('subject_tags', [])

    result['outcome'] = outcome_type
    result['provision_count'] = len(provisions)
    result['tag_count'] = len(subject_tags)

    # Update case_precedent_features (preserves embeddings)
    db.session.execute(text("""
        UPDATE case_precedent_features SET
            outcome_type = :outcome_type,
            outcome_confidence = :confidence,
            outcome_reasoning = :reasoning,
            provisions_cited = :provisions,
            provision_count = :provision_count,
            subject_tags = :tags,
            extraction_method = 'llm_haiku',
            extracted_at = :now
        WHERE case_id = :case_id
    """), {
        'case_id': case_id,
        'outcome_type': outcome_type,
        'confidence': 0.85,
        'reasoning': outcome_reasoning,
        'provisions': provisions,
        'provision_count': len(provisions),
        'tags': subject_tags,
        'now': datetime.utcnow(),
    })

    db.session.commit()

    result['success'] = True
    result['message'] = (
        f"outcome={outcome_type}, "
        f"{len(provisions)} provisions ({', '.join(provisions[:5])}{'...' if len(provisions) > 5 else ''}), "
        f"{len(subject_tags)} tags"
    )
    return result


def main():
    parser = argparse.ArgumentParser(
        description='LLM-based precedent feature extraction'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--cases', type=str,
                       help='Comma-separated list of case IDs')
    group.add_argument('--all', action='store_true',
                       help='Process all cases in case_precedent_features')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without calling LLM')
    parser.add_argument('--force', action='store_true',
                        help='Re-extract even if case already has features')

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.all:
            rows = db.session.execute(text("""
                SELECT case_id FROM case_precedent_features
                ORDER BY case_id
            """)).fetchall()
            case_ids = [r[0] for r in rows]
        else:
            case_ids = [int(c.strip()) for c in args.cases.split(',')]

        if not case_ids:
            print("No cases to process.")
            return

        from app.services.precedent.case_feature_extractor import CaseFeatureExtractor
        extractor = CaseFeatureExtractor()

        print(f"\nLLM Feature Extraction (Haiku)")
        print(f"{'='*60}")
        print(f"Cases: {len(case_ids)} ({case_ids[0]}..{case_ids[-1]})")
        print(f"Dry run: {args.dry_run}")
        print(f"Force: {args.force}")
        print()

        outcomes = {}
        processed = 0
        skipped = 0
        failed = 0

        for case_id in case_ids:
            result = process_case(case_id, extractor,
                                  dry_run=args.dry_run, force=args.force)

            if result['skipped']:
                skipped += 1
                print(f"  Case {case_id:3d}: [SKIP] {result['message']}")
                continue

            status = "OK" if result['success'] else "FAIL"
            print(f"  Case {case_id:3d}: [{status}] {result['message']}")

            if result['success']:
                processed += 1
            else:
                failed += 1

            if result['outcome']:
                outcomes[result['outcome']] = outcomes.get(result['outcome'], 0) + 1

        # Summary
        print(f"\n{'='*60}")
        print("Summary")
        print(f"{'='*60}")
        print(f"Processed: {processed}")
        print(f"Skipped: {skipped}")
        print(f"Failed: {failed}")
        if outcomes:
            print(f"Outcome distribution: {dict(sorted(outcomes.items()))}")

        if not args.dry_run:
            row = db.session.execute(text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN outcome_type IS NOT NULL
                               AND outcome_type != ''
                               AND outcome_type != 'unclear' THEN 1 END) as has_clear_outcome,
                    COUNT(CASE WHEN provision_count > 0 THEN 1 END) as has_provisions,
                    COUNT(CASE WHEN subject_tags IS NOT NULL
                               AND subject_tags != '{}' THEN 1 END) as has_tags
                FROM case_precedent_features
            """)).fetchone()
            print(f"\nCoverage:")
            print(f"  Total cases: {row[0]}")
            print(f"  With clear outcome: {row[1]}")
            print(f"  With provisions: {row[2]}")
            print(f"  With tags: {row[3]}")


if __name__ == '__main__':
    main()
