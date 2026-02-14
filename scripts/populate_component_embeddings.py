#!/usr/bin/env python3
"""
Populate component-aggregated embeddings for cases.

This script generates per-component embeddings from the nine-component structure
(R, P, O, S, Rs, A, E, Ca, Cs) and stores them in case_precedent_features
(embedding_R through embedding_Cs columns, plus aggregated combined_embedding).

Usage:
    python scripts/populate_component_embeddings.py --case 7
    python scripts/populate_component_embeddings.py --all
    python scripts/populate_component_embeddings.py --cases 4,7,56,57
    python scripts/populate_component_embeddings.py --all --dry-run
"""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/home/chris/onto')

from app import create_app
from app.models import Document, TemporaryRDFStorage, db
from app.services.precedent.case_feature_extractor import (
    CaseFeatureExtractor,
    COMPONENT_WEIGHTS,
    EXTRACTION_TYPE_TO_COMPONENT,
    ENTITY_TYPE_TO_COMPONENT
)


def get_cases_with_components():
    """Get list of case IDs that have nine-component entities in temporary_rdf_storage."""
    # Find cases with at least one of the nine-component extraction types
    valid_extraction_types = list(EXTRACTION_TYPE_TO_COMPONENT.keys()) + ['temporal_dynamics_enhanced']

    result = db.session.execute(
        db.text("""
            SELECT DISTINCT case_id
            FROM temporary_rdf_storage
            WHERE extraction_type = ANY(:types)
            ORDER BY case_id
        """),
        {'types': valid_extraction_types}
    ).fetchall()

    return [row[0] for row in result]


def get_component_counts(case_id: int) -> dict:
    """Get count of entities per component type for a case."""
    counts = {}

    for ext_type, comp_code in EXTRACTION_TYPE_TO_COMPONENT.items():
        count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type=ext_type
        ).count()
        if count > 0:
            counts[comp_code] = count

    # Handle Actions and Events from temporal_dynamics_enhanced
    for entity_type, comp_code in ENTITY_TYPE_TO_COMPONENT.items():
        count = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            TemporaryRDFStorage.extraction_type == 'temporal_dynamics_enhanced',
            db.func.lower(TemporaryRDFStorage.entity_type) == entity_type
        ).count()
        if count > 0:
            counts[comp_code] = count

    return counts


def process_case(case_id: int, extractor: CaseFeatureExtractor, dry_run: bool = False) -> dict:
    """
    Process a single case to generate and store component-aggregated embedding.

    Returns dict with status and details.
    """
    result = {
        'case_id': case_id,
        'success': False,
        'component_counts': {},
        'message': ''
    }

    # Get component counts for reporting
    counts = get_component_counts(case_id)
    result['component_counts'] = counts

    if len(counts) < 3:
        result['message'] = f"Insufficient components: {len(counts)} types ({list(counts.keys())})"
        return result

    if dry_run:
        result['success'] = True
        result['message'] = f"Would process: {len(counts)} component types"
        return result

    # Generate and save embedding
    success = extractor.extract_and_save_component_embedding(case_id)

    if success:
        result['success'] = True
        result['message'] = f"Saved {len(counts)} per-component + aggregated embeddings"
    else:
        result['message'] = "Failed to generate or save embedding"

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Generate component-aggregated embeddings for ProEthica cases'
    )
    parser.add_argument('--case', type=int, help='Process a single case ID')
    parser.add_argument('--cases', type=str, help='Comma-separated list of case IDs')
    parser.add_argument('--all', action='store_true', help='Process all cases with components')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without saving')
    parser.add_argument('--min-components', type=int, default=3,
                       help='Minimum component types required (default: 3)')

    args = parser.parse_args()

    if not (args.case or args.cases or args.all):
        parser.print_help()
        print("\nError: Specify --case, --cases, or --all")
        sys.exit(1)

    # Create Flask app context
    app = create_app()
    with app.app_context():
        extractor = CaseFeatureExtractor()

        # Determine which cases to process
        if args.case:
            case_ids = [args.case]
        elif args.cases:
            case_ids = [int(c.strip()) for c in args.cases.split(',')]
        else:
            case_ids = get_cases_with_components()

        print(f"\nComponent Embedding Population")
        print(f"{'='*60}")
        print(f"Cases to process: {len(case_ids)}")
        print(f"Minimum components: {args.min_components}")
        print(f"Dry run: {args.dry_run}")
        print(f"\nComponent weights:")
        for code, weight in sorted(COMPONENT_WEIGHTS.items(), key=lambda x: -x[1]):
            print(f"  {code}: {weight:.2f}")
        print()

        # Process cases
        results = []
        for case_id in case_ids:
            print(f"\nCase {case_id}:")
            result = process_case(case_id, extractor, dry_run=args.dry_run)
            results.append(result)

            # Print component counts
            if result['component_counts']:
                counts_str = ', '.join(f"{k}:{v}" for k, v in sorted(result['component_counts'].items()))
                print(f"  Components: {counts_str}")

            status = "OK" if result['success'] else "SKIP"
            print(f"  [{status}] {result['message']}")

        # Summary
        print(f"\n{'='*60}")
        print("Summary")
        print(f"{'='*60}")
        success_count = sum(1 for r in results if r['success'])
        print(f"Processed: {success_count}/{len(results)} cases")

        if not args.dry_run:
            print(f"\nEmbeddings stored in case_precedent_features (embedding_R..Cs + combined_embedding)")


if __name__ == '__main__':
    main()
