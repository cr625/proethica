#!/usr/bin/env python3
"""
Test script for Scenario Generation Stage 1 (Data Collection).

Tests eligibility checking and data collection on Cases 10 and 13.

Usage:
    python test_scenario_generation_stage1.py
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ''))

from app import create_app, db
from app.services.scenario_generation import ScenarioDataCollector


def test_eligibility_check():
    """Test eligibility checking on Cases 10 and 13."""
    print("=" * 80)
    print("SCENARIO GENERATION STAGE 1 TEST: Eligibility Check")
    print("=" * 80)
    print()

    collector = ScenarioDataCollector()

    # Test Case 10
    print("Testing Case 10...")
    print("-" * 80)
    report10 = collector.check_eligibility(case_id=10)
    print(f"Case ID: {report10.case_id}")
    print(f"Eligible: {report10.eligible}")
    print(f"Summary: {report10.summary}")
    print()
    print("Pass Completion:")
    for pass_name, status in report10.pass_completion.items():
        print(f"  {pass_name}: {'✓' if status.complete else '✗'} "
              f"({status.entity_count} entities in {', '.join(status.sections_complete)})")
    print()
    print("Entity Counts:")
    for entity_type, count in sorted(report10.entity_counts.items()):
        print(f"  {entity_type}: {count}")
    print()
    print(f"Temporal Dynamics Available: {report10.has_temporal_dynamics}")
    if report10.has_temporal_dynamics:
        print(f"  Actions: {report10.temporal_summary.get('actions', 0)}")
        print(f"  Events: {report10.temporal_summary.get('events', 0)}")
    print()
    print(f"Step 4 Complete: {report10.step4_complete}")
    if report10.step4_complete:
        print(f"  Questions: {report10.step4_summary.get('questions', 0)}")
        print(f"  Conclusions: {report10.step4_summary.get('conclusions', 0)}")
    print()
    print()

    # Test Case 13
    print("Testing Case 13...")
    print("-" * 80)
    report13 = collector.check_eligibility(case_id=13)
    print(f"Case ID: {report13.case_id}")
    print(f"Eligible: {report13.eligible}")
    print(f"Summary: {report13.summary}")
    print()
    print("Pass Completion:")
    for pass_name, status in report13.pass_completion.items():
        print(f"  {pass_name}: {'✓' if status.complete else '✗'} "
              f"({status.entity_count} entities in {', '.join(status.sections_complete)})")
    print()
    print("Entity Counts:")
    for entity_type, count in sorted(report13.entity_counts.items()):
        print(f"  {entity_type}: {count}")
    print()
    print(f"Temporal Dynamics Available: {report13.has_temporal_dynamics}")
    if report13.has_temporal_dynamics:
        print(f"  Actions: {report13.temporal_summary.get('actions', 0)}")
        print(f"  Events: {report13.temporal_summary.get('events', 0)}")
    print()
    print(f"Step 4 Complete: {report13.step4_complete}")
    if report13.step4_complete:
        print(f"  Questions: {report13.step4_summary.get('questions', 0)}")
        print(f"  Conclusions: {report13.step4_summary.get('conclusions', 0)}")
    print()


def test_data_collection():
    """Test data collection on Case 10."""
    print("=" * 80)
    print("SCENARIO GENERATION STAGE 1 TEST: Data Collection")
    print("=" * 80)
    print()

    collector = ScenarioDataCollector()

    print("Collecting data for Case 10...")
    print("-" * 80)

    try:
        data = collector.collect_all_data(case_id=10)

        print(f"Case: {data.case_metadata.title}")
        print(f"Case Number: {data.case_metadata.case_number}")
        print()

        print("Temporary Entities (case-specific):")
        for entity_type, entities in sorted(data.temporary_entities.items()):
            print(f"  {entity_type}: {len(entities)} entities")
        print()

        print("Committed Entities (formal ontology):")
        if data.committed_entities:
            for entity_type, entities in sorted(data.committed_entities.items()):
                print(f"  {entity_type}: {len(entities)} entities")
        else:
            print("  (none)")
        print()

        print("Merged Entities (combined):")
        for entity_type, entities in sorted(data.merged_entities.items()):
            print(f"  {entity_type}: {len(entities)} entities")
        print()

        print("Total Entity Count:")
        print(f"  Temporary: {sum(len(e) for e in data.temporary_entities.values())}")
        print(f"  Committed: {sum(len(e) for e in data.committed_entities.values())}")
        print(f"  Merged: {sum(len(e) for e in data.merged_entities.values())}")
        print()

        print("Provenance:")
        print(f"  Extraction Sessions: {len(data.provenance.extraction_sessions)}")
        print(f"  Pass Completion: {data.provenance.pass_completion}")
        print(f"  Step 4 Complete: {data.provenance.step4_complete}")
        print()

        # Sample entities
        print("Sample Entities:")
        for entity_type in ['Role', 'Principle', 'Action']:
            entities = data.get_entities_by_type(entity_type)
            if entities:
                print(f"  {entity_type} examples:")
                for entity in entities[:3]:  # First 3
                    print(f"    - {entity.label} (from {entity.section_type})")
        print()

        print("✓ Data collection successful!")

    except Exception as e:
        print(f"✗ Error during data collection: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main test function."""
    app = create_app()

    with app.app_context():
        # Test eligibility checking
        test_eligibility_check()

        # Test data collection
        test_data_collection()

    print()
    print("=" * 80)
    print("TESTS COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    main()
