#!/usr/bin/env python3
"""
Verify pipeline results for a case.

Usage:
    python scripts/verify_pipeline_results.py <case_id>
    python scripts/verify_pipeline_results.py --all  # Check all cases with Step 4
    python scripts/verify_pipeline_results.py --batch 20 22 56 57  # Check specific cases
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from app import create_app
from app.models import db

# Minimum entity counts for validation
ENTITY_MINIMUMS = {
    # Steps 1-3 entities
    'roles': 3,
    'states': 2,
    'resources': 3,
    'principles': 3,
    'obligations': 3,
    'constraints': 2,
    'capabilities': 2,
    'temporal_dynamics_enhanced': 5,
    # Step 4 entities
    'code_provision_reference': 3,
    'ethical_question': 5,
    'ethical_conclusion': 3,
    'causal_normative_link': 1,  # Critical - can be 0 due to LLM issue
    'canonical_decision_point': 1,
}

# Required Step 4 prompts
REQUIRED_STEP4_PROMPTS = [
    'ethical_question',
    'ethical_conclusion',
    'transformation_classification',
    'rich_analysis',
    'phase3_decision_synthesis',
    'phase4_narrative',
    'whole_case_synthesis',
]


def verify_case(case_id: int) -> dict:
    """
    Verify pipeline results for a single case.

    Returns dict with:
        - passed: bool
        - case_id: int
        - issues: list of issue strings
        - warnings: list of warning strings (non-blocking)
        - entity_counts: dict of type -> count
        - prompts_captured: list of captured prompt types
        - duration_sec: int or None
    """
    result = {
        'passed': True,
        'case_id': case_id,
        'issues': [],
        'warnings': [],
        'entity_counts': {},
        'prompts_captured': [],
        'duration_sec': None,
    }

    # Check pipeline run status (optional - UI-processed cases may not have this)
    run_query = db.session.execute(db.text("""
        SELECT status, steps_completed,
               EXTRACT(EPOCH FROM (completed_at - started_at))::int as duration_sec
        FROM pipeline_runs
        WHERE case_id = :case_id
        ORDER BY created_at DESC
        LIMIT 1
    """), {'case_id': case_id})
    run = run_query.fetchone()

    if run:
        if run.status != 'completed':
            result['warnings'].append(f'Pipeline status is {run.status}, expected completed')
        result['duration_sec'] = run.duration_sec

        # Check steps completed (warning only - older cases may lack this metadata)
        steps = run.steps_completed or []
        required_steps = ['step1_facts', 'step1_discussion', 'step2_facts', 'step2_discussion', 'step3', 'step4']
        missing_steps = [s for s in required_steps if s not in steps]
        if missing_steps:
            result['warnings'].append(f'Incomplete tracking metadata (steps_completed)')
    else:
        result['warnings'].append('No pipeline_run record (likely processed via UI)')

    # Get entity counts
    entity_query = db.session.execute(db.text("""
        SELECT extraction_type, COUNT(*) as count
        FROM temporary_rdf_storage
        WHERE case_id = :case_id
        GROUP BY extraction_type
    """), {'case_id': case_id})

    for row in entity_query:
        result['entity_counts'][row.extraction_type] = row.count

    # Check entity minimums
    for entity_type, minimum in ENTITY_MINIMUMS.items():
        count = result['entity_counts'].get(entity_type, 0)
        if count < minimum:
            severity = 'CRITICAL' if entity_type == 'causal_normative_link' else 'LOW'
            result['issues'].append(f'{severity}: {entity_type} count {count} < {minimum}')
            if severity == 'CRITICAL':
                result['passed'] = False

    # Check Step 4 prompts
    prompt_query = db.session.execute(db.text("""
        SELECT DISTINCT concept_type
        FROM extraction_prompts
        WHERE case_id = :case_id AND step_number = 4
    """), {'case_id': case_id})

    result['prompts_captured'] = [row.concept_type for row in prompt_query]

    missing_prompts = [p for p in REQUIRED_STEP4_PROMPTS if p not in result['prompts_captured']]
    if missing_prompts:
        result['issues'].append(f'Missing Step 4 prompts: {missing_prompts}')
        result['passed'] = False

    return result


def print_result(result: dict, verbose: bool = False):
    """Print verification result."""
    status = 'PASS' if result['passed'] else 'FAIL'
    case_id = result['case_id']
    duration = result.get('duration_sec')
    duration_str = f" ({duration}s)" if duration else ""

    has_warnings = bool(result.get('warnings'))
    if result['passed'] and not verbose and not has_warnings:
        print(f"  Case {case_id}: {status}{duration_str}")
        return

    print(f"\n  Case {case_id}: {status}{duration_str}")

    if result['issues']:
        for issue in result['issues']:
            marker = 'X' if 'CRITICAL' in issue else '!'
            print(f"    [{marker}] {issue}")

    if result.get('warnings') and verbose:
        for warning in result['warnings']:
            print(f"    [~] {warning}")

    if verbose:
        print(f"    Entity counts: {sum(result['entity_counts'].values())} total")
        key_entities = ['roles', 'obligations', 'ethical_question', 'causal_normative_link', 'canonical_decision_point']
        counts = [f"{k}:{result['entity_counts'].get(k, 0)}" for k in key_entities]
        print(f"    Key: {', '.join(counts)}")


def find_cases_with_step4() -> list:
    """Find all cases that have Step 4 data."""
    query = db.session.execute(db.text("""
        SELECT DISTINCT case_id
        FROM extraction_prompts
        WHERE step_number = 4 AND concept_type = 'whole_case_synthesis'
        ORDER BY case_id
    """))
    return [row.case_id for row in query]


def main():
    parser = argparse.ArgumentParser(description='Verify pipeline results')
    parser.add_argument('case_ids', nargs='*', type=int, help='Case ID(s) to verify')
    parser.add_argument('--all', action='store_true', help='Verify all cases with Step 4')
    parser.add_argument('--batch', nargs='+', type=int, help='Verify specific case IDs')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        if args.all:
            case_ids = find_cases_with_step4()
            print(f"Verifying {len(case_ids)} cases with Step 4 data...")
        elif args.batch:
            case_ids = args.batch
        elif args.case_ids:
            case_ids = args.case_ids
        else:
            parser.print_help()
            return 1

        passed = 0
        failed = 0
        critical_failures = []

        for case_id in case_ids:
            result = verify_case(case_id)
            print_result(result, verbose=args.verbose)

            if result['passed']:
                passed += 1
            else:
                failed += 1
                if any('CRITICAL' in issue for issue in result['issues']):
                    critical_failures.append(case_id)

        print(f"\n  Summary: {passed} passed, {failed} failed out of {len(case_ids)} cases")

        if critical_failures:
            print(f"\n  Critical failures (need Step 4 re-run): {critical_failures}")
            print(f"  Fix with: curl -X POST http://localhost:5000/pipeline/api/run_step4 -H 'Content-Type: application/json' -d '{{\"case_id\": <ID>}}'")

        return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
