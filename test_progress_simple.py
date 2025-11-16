#!/usr/bin/env python3
"""
Simple test for Case Pipeline Progress without full Flask app initialization.
"""

import sys
import os

# Database connection test
from sqlalchemy import create_engine, text

def test_progress_tracking():
    """Test progress tracking by querying database directly."""

    print("=" * 70)
    print("Testing Case Pipeline Progress Tracking - Case 8 (Direct SQL)")
    print("=" * 70)
    print()

    # Connect to database
    db_url = "postgresql://postgres:PASS@localhost:5432/ai_ethical_dm"
    engine = create_engine(db_url)

    with engine.connect() as conn:
        case_id = 8

        # Test 1: Get extraction types and counts
        print("Test 1: Extraction Types and Counts")
        print("-" * 70)

        query = text("""
            SELECT
                extraction_type,
                is_committed,
                COUNT(*) as count
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
                AND extraction_type IS NOT NULL
            GROUP BY extraction_type, is_committed
            ORDER BY extraction_type, is_committed
        """)

        result = conn.execute(query, {"case_id": case_id})

        extraction_totals = {}
        for row in result:
            ext_type = row[0]
            is_committed = row[1]
            count = row[2]
            status = "committed" if is_committed else "uncommitted"
            print(f"  {ext_type} ({status}): {count} entities")

            if ext_type not in extraction_totals:
                extraction_totals[ext_type] = 0
            extraction_totals[ext_type] += count

        print()
        print("Total entities by type:")
        for ext_type, total in sorted(extraction_totals.items()):
            print(f"  {ext_type}: {total} total entities")
        print()

        # Test 2: Step completion mapping
        print("Test 2: Step Completion Status")
        print("-" * 70)

        step_requirements = {
            1: {
                'name': 'Contextual Framework',
                'extractions': ['roles', 'states', 'resources']
            },
            2: {
                'name': 'Normative Requirements',
                'extractions': ['principles', 'obligations', 'constraints', 'capabilities']
            },
            3: {
                'name': 'Temporal Dynamics',
                'extractions': ['temporal_dynamics_enhanced']
            },
            4: {
                'name': 'Whole-Case Synthesis',
                'extractions': ['provision', 'question', 'conclusion', 'precedent_case_reference']
            },
            5: {
                'name': 'Scenario Generation',
                'extractions': ['scenario_metadata', 'scenario_timeline', 'scenario_participant']
            }
        }

        completed_types = set(extraction_totals.keys())

        for step_num, step_info in sorted(step_requirements.items()):
            required = step_info['extractions']
            present = [ext for ext in required if ext in completed_types]
            missing = [ext for ext in required if ext not in completed_types]

            # For steps 1-3, require all extractions. For 4-5, require at least one
            if step_num <= 3:
                is_complete = len(missing) == 0
            else:
                is_complete = len(present) > 0

            status = "✓ COMPLETE" if is_complete else "✗ INCOMPLETE"

            print(f"\nStep {step_num}: {step_info['name']} - {status}")
            if present:
                print(f"  Present: {', '.join(present)}")
            if missing:
                print(f"  Missing: {', '.join(missing)}")

        print()

        # Test 3: Overall summary
        print("Test 3: Overall Summary")
        print("-" * 70)

        total_query = text("""
            SELECT COUNT(DISTINCT extraction_type) as type_count,
                   COUNT(*) as total_entities
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
                AND extraction_type IS NOT NULL
        """)

        result = conn.execute(total_query, {"case_id": case_id})
        row = result.fetchone()

        print(f"Unique extraction types: {row[0]}")
        print(f"Total entities: {row[1]}")
        print()

        # Calculate completed steps
        completed_steps = 0
        for step_num, step_info in step_requirements.items():
            required = step_info['extractions']
            present = [ext for ext in required if ext in completed_types]

            if step_num <= 3:
                if all(ext in completed_types for ext in required):
                    completed_steps += 1
            else:
                if any(ext in completed_types for ext in required):
                    completed_steps += 1

        total_steps = len(step_requirements)
        progress_pct = (completed_steps / total_steps) * 100

        print(f"Completed steps: {completed_steps}/{total_steps}")
        print(f"Progress: {progress_pct:.1f}%")

        print()
        print("=" * 70)
        print("Test Complete!")
        print("=" * 70)


if __name__ == '__main__':
    test_progress_tracking()
