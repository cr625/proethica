#!/usr/bin/env python3
"""
Regenerate arguments for synthesized cases using the improved argument generator.

This script:
1. Loads decision points for a case (from entity-grounded pipeline)
2. Generates balanced PRO/CON arguments using tension-based reasoning
3. Validates arguments
4. Stores results in temporary_rdf_storage

Usage:
    python scripts/regenerate_arguments.py --case 7
    python scripts/regenerate_arguments.py --all-synthesized
    python scripts/regenerate_arguments.py --case 7 --dry-run
"""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/home/chris/onto')

from app import create_app
from app.models import TemporaryRDFStorage, db
from app.services.entity_analysis.argument_generator import generate_arguments
from app.services.entity_analysis.argument_validator import ArgumentValidator

# Synthesized cases (have canonical_decision_points from Step 4)
# Query: SELECT DISTINCT case_id FROM temporary_rdf_storage WHERE extraction_type = 'canonical_decision_point'
# As of 2026-01-02: 23 cases with decision points, 15 need argument regeneration
# Already processed: 4, 7, 8, 9, 11, 12, 15, 16
# Need processing: 5, 6, 10, 13, 14, 17, 18, 19, 20, 22, 56, 57, 58, 59, 60
SYNTHESIZED_CASES = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 56, 57, 58, 59, 60]


def regenerate_arguments(case_id: int, dry_run: bool = False) -> dict:
    """
    Regenerate arguments for a single case.

    Returns dict with counts and status.
    """
    print(f"\n{'='*60}")
    print(f"Processing Case {case_id}")
    print('='*60)

    # Check if case has decision points
    dp_count = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='canonical_decision_point'
    ).count()

    if dp_count == 0:
        print(f"  No decision points found for case {case_id}. Skipping.")
        return {'status': 'skipped', 'reason': 'no_decision_points'}

    print(f"  Found {dp_count} decision points")

    # Get current counts
    old_args = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='argument_generated'
    ).count()
    old_vals = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='argument_validation'
    ).count()

    print(f"  Current: {old_args} arguments, {old_vals} validations")

    if dry_run:
        # Generate but don't store
        result = generate_arguments(case_id)
        print(f"  Would generate: {len(result.arguments)} arguments")
        print(f"    PRO: {result.pro_argument_count}")
        print(f"    CON: {result.con_argument_count}")
        return {
            'status': 'dry_run',
            'would_generate': len(result.arguments),
            'pro': result.pro_argument_count,
            'con': result.con_argument_count
        }

    # Delete old arguments and validations
    TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='argument_generated'
    ).delete()
    TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='argument_validation'
    ).delete()
    db.session.commit()
    print(f"  Deleted {old_args} old arguments, {old_vals} old validations")

    # Generate new arguments
    result = generate_arguments(case_id)
    print(f"  Generated {len(result.arguments)} arguments ({result.pro_argument_count} PRO, {result.con_argument_count} CON)")

    # Store arguments
    import uuid
    session_id = str(uuid.uuid4())

    for arg in result.arguments:
        # Use arg.to_dict() to ensure all fields match template expectations
        # (includes claim, warrant, argument_id, etc.)
        entry = TemporaryRDFStorage(
            case_id=case_id,
            extraction_type='argument_generated',
            storage_type='individual',
            entity_uri=f"proethica:Argument_{arg.argument_id}",
            entity_label=arg.argument_id,
            entity_definition=arg.claim.text,
            extraction_session_id=session_id,
            rdf_json_ld=arg.to_dict()
        )
        db.session.add(entry)

    db.session.commit()
    print(f"  Stored {len(result.arguments)} arguments")

    # Validate arguments
    validator = ArgumentValidator()
    validation_results = validator.validate_arguments(case_id, result)

    # Store validations
    val_session_id = str(uuid.uuid4())
    valid_count = 0
    total_score = 0.0

    for val in validation_results.validations:
        entry = TemporaryRDFStorage(
            case_id=case_id,
            extraction_type='argument_validation',
            storage_type='individual',
            entity_uri=f"proethica:ArgumentValidation_{val.argument_id}",
            entity_label=val.argument_id,
            entity_definition=f"Score: {val.validation_score:.2f}, Valid: {val.is_valid}",
            extraction_session_id=val_session_id,
            rdf_json_ld=val.to_dict()
        )
        db.session.add(entry)
        if val.is_valid:
            valid_count += 1
        total_score += val.validation_score

    db.session.commit()
    avg_score = total_score / len(validation_results.validations) if validation_results.validations else 0

    print(f"  Stored {len(validation_results.validations)} validations")
    print(f"  Valid: {valid_count}/{len(validation_results.validations)}, Avg score: {avg_score:.2f}")

    # Verify final counts
    final_args = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='argument_generated'
    ).count()
    final_vals = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='argument_validation'
    ).count()

    print(f"  Final: {final_args} arguments, {final_vals} validations")

    return {
        'status': 'success',
        'arguments': len(result.arguments),
        'pro': result.pro_argument_count,
        'con': result.con_argument_count,
        'valid': valid_count,
        'avg_score': avg_score
    }


def main():
    parser = argparse.ArgumentParser(description='Regenerate arguments for synthesized cases')
    parser.add_argument('--case', type=int, help='Single case ID to process')
    parser.add_argument('--all-synthesized', action='store_true', help='Process all synthesized cases')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    args = parser.parse_args()

    if not args.case and not args.all_synthesized:
        parser.print_help()
        print("\nError: Specify --case ID or --all-synthesized")
        sys.exit(1)

    app = create_app()

    with app.app_context():
        cases = [args.case] if args.case else SYNTHESIZED_CASES
        results = {}

        for case_id in cases:
            results[case_id] = regenerate_arguments(case_id, args.dry_run)

        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"{'Case':<8} {'Status':<12} {'Args':<8} {'PRO':<6} {'CON':<6} {'Valid':<8} {'Score':<8}")
        print("-"*60)

        for case_id, r in results.items():
            if r['status'] == 'success':
                print(f"{case_id:<8} {r['status']:<12} {r['arguments']:<8} {r['pro']:<6} {r['con']:<6} {r['valid']:<8} {r['avg_score']:.2f}")
            elif r['status'] == 'dry_run':
                print(f"{case_id:<8} {r['status']:<12} {r['would_generate']:<8} {r['pro']:<6} {r['con']:<6} {'N/A':<8} {'N/A':<8}")
            else:
                print(f"{case_id:<8} {r['status']:<12} {r.get('reason', '')}")


if __name__ == '__main__':
    main()
