#!/usr/bin/env python3
"""
Test script for Case Pipeline Progress API

Tests the progress tracking functionality on Case 8.
Run this from the proethica directory:
    python test_progress_api.py
"""

import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.case_pipeline_progress import CasePipelineProgress


def test_progress_tracking():
    """Test the progress tracking service on Case 8."""

    print("=" * 70)
    print("Testing Case Pipeline Progress Tracking - Case 8")
    print("=" * 70)
    print()

    app = create_app('development')

    with app.app_context():
        case_id = 8

        # Test 1: Get completed extraction types
        print("Test 1: Get Completed Extraction Types")
        print("-" * 70)
        completed_types = CasePipelineProgress.get_completed_extraction_types(case_id)
        print(f"Completed extraction types for Case {case_id}:")
        for ext_type in sorted(completed_types):
            count = CasePipelineProgress.get_extraction_count(case_id, ext_type)
            print(f"  - {ext_type}: {count} entities")
        print()

        # Test 2: Check individual step completion
        print("Test 2: Individual Step Completion")
        print("-" * 70)
        for step_num in range(1, 6):
            is_complete = CasePipelineProgress.is_step_complete(case_id, step_num)
            can_access = CasePipelineProgress.can_access_step(case_id, step_num)
            status = "✓ COMPLETE" if is_complete else "✗ INCOMPLETE"
            access = "CAN ACCESS" if can_access else "CANNOT ACCESS"
            step_name = CasePipelineProgress.STEP_REQUIREMENTS.get(step_num, {}).get('name', 'Unknown')
            print(f"Step {step_num} ({step_name}): {status} | {access}")
        print()

        # Test 3: Get full case progress
        print("Test 3: Full Case Progress")
        print("-" * 70)
        progress = CasePipelineProgress.get_case_progress(case_id)
        for step_num, step_data in sorted(progress.items()):
            print(f"\nStep {step_num}: {step_data['name']}")
            print(f"  Complete: {step_data['complete']}")
            print(f"  Can Proceed: {step_data['can_proceed']}")
            print(f"  Total Entities: {step_data['total_entities']}")
            print(f"  Extractions:")
            for ext_type, count in sorted(step_data['extractions'].items()):
                print(f"    - {ext_type}: {count}")
        print()

        # Test 4: Get progress summary
        print("Test 4: Progress Summary")
        print("-" * 70)
        summary = CasePipelineProgress.get_progress_summary(case_id)
        print(f"Total Steps: {summary['total_steps']}")
        print(f"Completed Steps: {summary['completed_steps']}")
        print(f"Progress: {summary['progress_percentage']}%")
        print(f"Total Entities: {summary['total_entities']}")
        print(f"Next Step: {summary['next_step']}")
        print(f"Is Complete: {summary['is_complete']}")
        print()

        print("=" * 70)
        print("Test Complete!")
        print("=" * 70)


if __name__ == '__main__':
    test_progress_tracking()
