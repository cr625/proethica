#!/usr/bin/env python3
"""
Populate precedent features (outcome, provisions, tags) for cases missing them.

Extracts outcome_type, provisions_cited, and subject_tags from document content
and metadata WITHOUT overwriting existing embeddings. Uses the same extraction
logic as CaseFeatureExtractor but only updates feature columns.

Usage:
    python scripts/populate_precedent_features.py --all
    python scripts/populate_precedent_features.py --cases 73,74,75
    python scripts/populate_precedent_features.py --all --dry-run
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


def process_case(case_id, extractor, dry_run=False):
    """Extract and save precedent features for a single case."""
    result = {
        'case_id': case_id,
        'success': False,
        'outcome': None,
        'provision_count': 0,
        'tag_count': 0,
        'message': ''
    }

    document = Document.query.get(case_id)
    if not document:
        result['message'] = 'Document not found'
        return result

    # Get document sections (from document_sections table)
    sections = extractor._get_document_sections(case_id)

    # Get metadata
    metadata = document.doc_metadata or {}
    doc_structure = metadata.get('document_structure', {})
    doc_sections = doc_structure.get('sections', {})

    # Extract outcome from conclusion
    conclusion_text = extractor._get_section_text(sections, doc_sections, 'conclusion')
    outcome_type, outcome_confidence, outcome_reasoning = extractor.extract_outcome(
        conclusion_text
    )

    # Extract provisions from references section
    references_text = extractor._get_section_text(sections, doc_sections, 'references')
    provisions_cited = extractor.extract_provisions(references_text)

    # If no provisions from references section, try the full discussion text
    if not provisions_cited:
        discussion_text = extractor._get_section_text(sections, doc_sections, 'discussion')
        provisions_cited = extractor.extract_provisions(discussion_text)

    # Get subject tags from metadata
    subject_tags = metadata.get('subject_tags', [])
    if not subject_tags:
        subject_tags = doc_structure.get('subject_tags', [])

    # Get Step 4 analysis data (will be empty for unprocessed cases)
    principle_tensions, obligation_conflicts, transformation_type, transformation_pattern = \
        extractor._get_step4_data(case_id)

    result['outcome'] = outcome_type
    result['provision_count'] = len(provisions_cited)
    result['tag_count'] = len(subject_tags)

    if dry_run:
        result['success'] = True
        result['message'] = (
            f"outcome={outcome_type}, {len(provisions_cited)} provisions, "
            f"{len(subject_tags)} tags"
        )
        return result

    # Update ONLY feature columns, preserving embeddings
    db.session.execute(text("""
        UPDATE case_precedent_features SET
            outcome_type = :outcome_type,
            outcome_confidence = :outcome_confidence,
            outcome_reasoning = :outcome_reasoning,
            provisions_cited = :provisions_cited,
            provision_count = :provision_count,
            subject_tags = :subject_tags,
            principle_tensions = :principle_tensions,
            obligation_conflicts = :obligation_conflicts,
            transformation_type = :transformation_type,
            transformation_pattern = :transformation_pattern,
            extraction_method = COALESCE(extraction_method, 'automatic'),
            extracted_at = :extracted_at
        WHERE case_id = :case_id
    """), {
        'case_id': case_id,
        'outcome_type': outcome_type,
        'outcome_confidence': outcome_confidence,
        'outcome_reasoning': outcome_reasoning,
        'provisions_cited': provisions_cited,
        'provision_count': len(provisions_cited),
        'subject_tags': subject_tags,
        'principle_tensions': json.dumps(principle_tensions) if principle_tensions else None,
        'obligation_conflicts': json.dumps(obligation_conflicts) if obligation_conflicts else None,
        'transformation_type': transformation_type,
        'transformation_pattern': transformation_pattern,
        'extracted_at': datetime.utcnow()
    })

    db.session.commit()

    result['success'] = True
    result['message'] = (
        f"outcome={outcome_type}, {len(provisions_cited)} provisions, "
        f"{len(subject_tags)} tags"
    )
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Populate precedent features for cases missing them'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--cases', type=str,
                       help='Comma-separated list of case IDs')
    group.add_argument('--all', action='store_true',
                       help='Process all cases missing outcome_type')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without saving')

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.all:
            rows = db.session.execute(text("""
                SELECT case_id FROM case_precedent_features
                WHERE outcome_type IS NULL OR outcome_type = ''
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

        print(f"\nPrecedent Feature Population")
        print(f"{'='*60}")
        print(f"Cases: {len(case_ids)} ({case_ids[0]}..{case_ids[-1]})")
        print(f"Dry run: {args.dry_run}")
        print()

        outcomes = {}
        for case_id in case_ids:
            result = process_case(case_id, extractor, dry_run=args.dry_run)

            status = "OK" if result['success'] else "FAIL"
            print(f"  Case {case_id:3d}: [{status}] {result['message']}")

            if result['outcome']:
                outcomes[result['outcome']] = outcomes.get(result['outcome'], 0) + 1

        # Summary
        print(f"\n{'='*60}")
        print("Summary")
        print(f"{'='*60}")
        print(f"Outcome distribution: {dict(sorted(outcomes.items()))}")
        total_provisions = sum(1 for cid in case_ids
                               for r in [process_case.__code__] if False)  # placeholder

        if not args.dry_run:
            # Verify
            row = db.session.execute(text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN outcome_type IS NOT NULL AND outcome_type != '' THEN 1 END) as has_outcome,
                    COUNT(CASE WHEN provisions_cited IS NOT NULL AND provisions_cited != '{}' THEN 1 END) as has_provisions,
                    COUNT(CASE WHEN subject_tags IS NOT NULL AND subject_tags != '{}' THEN 1 END) as has_tags
                FROM case_precedent_features
            """)).fetchone()
            print(f"\nTotal cases: {row[0]}")
            print(f"  With outcome: {row[1]}")
            print(f"  With provisions: {row[2]}")
            print(f"  With tags: {row[3]}")


if __name__ == '__main__':
    main()
