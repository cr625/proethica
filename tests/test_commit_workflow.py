#!/usr/bin/env python3
"""
Test script for the OntServe commit workflow.

Tests the complete flow from temporary storage to permanent OntServe storage.
"""

import sys
import json
from pathlib import Path

# Add app to path
sys.path.insert(0, '/home/chris/onto/proethica')

from app import create_app, db
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.ontserve_commit_service import OntServeCommitService


def test_commit_workflow():
    """Test the commit workflow with sample data."""
    app = create_app()

    with app.app_context():
        print("Testing OntServe Commit Workflow\n")
        print("=" * 50)

        # Check for existing RDF entities
        case_id = 18  # Use case 18 as example
        entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_committed=False
        ).all()

        print(f"\nFound {len(entities)} uncommitted entities for case {case_id}")

        if not entities:
            print("No entities to commit. Please extract some entities first.")
            return

        # Group by type
        classes = []
        individuals = []

        for entity in entities:
            if entity.storage_type == 'class':
                classes.append(entity)
            elif entity.storage_type == 'individual':
                individuals.append(entity)

        print(f"  - {len(classes)} class definitions")
        print(f"  - {len(individuals)} individual instances")

        # Select first 2 of each for testing
        selected_ids = []
        if classes:
            selected_ids.extend([c.id for c in classes[:2]])
            print(f"\nSelected {len(classes[:2])} classes to commit:")
            for c in classes[:2]:
                print(f"  - {c.entity_label}")

        if individuals:
            selected_ids.extend([i.id for i in individuals[:2]])
            print(f"\nSelected {len(individuals[:2])} individuals to commit:")
            for i in individuals[:2]:
                print(f"  - {i.entity_label}")

        if not selected_ids:
            print("\nNo entities selected for commit.")
            return

        # Test the commit service
        print("\n" + "=" * 50)
        print("Testing Commit Service")
        print("=" * 50)

        commit_service = OntServeCommitService()

        # First check status
        print("\nChecking current commit status...")
        status = commit_service.get_commit_status(case_id)
        print(f"  Pending: {status['pending_count']}")
        print(f"  Committed: {status['committed_count']}")
        print(f"  Case ontology exists: {status['case_ontology_exists']}")
        print(f"  Extracted ontology exists: {status['extracted_ontology_exists']}")

        # Perform commit
        print(f"\nCommitting {len(selected_ids)} selected entities...")
        result = commit_service.commit_selected_entities(case_id, selected_ids)

        if result['success']:
            print("\n✓ Commit successful!")
            print(f"  - Classes committed: {result['classes_committed']}")
            print(f"  - Individuals committed: {result['individuals_committed']}")

            if result.get('errors'):
                print(f"\nWarnings:")
                for error in result['errors']:
                    print(f"  - {error}")

            # Check status after commit
            print("\nChecking status after commit...")
            status = commit_service.get_commit_status(case_id)
            print(f"  Pending: {status['pending_count']}")
            print(f"  Committed: {status['committed_count']}")

            if status['case_ontology_file']:
                print(f"\nCase ontology created at:")
                print(f"  {status['case_ontology_file']}")

            if status['extracted_ontology_file']:
                print(f"\nExtracted classes saved to:")
                print(f"  {status['extracted_ontology_file']}")

            # Check sync status
            if result.get('sync_status'):
                sync = result['sync_status']
                if sync['success']:
                    print("\n✓ Database synchronization successful")
                else:
                    print(f"\n✗ Database sync warning: {sync.get('error')}")

        else:
            print(f"\n✗ Commit failed: {result.get('error')}")

        print("\n" + "=" * 50)
        print("Test complete!")


def check_ttl_files():
    """Check the generated TTL files."""
    print("\n" + "=" * 50)
    print("Checking Generated TTL Files")
    print("=" * 50)

    ontserve_path = Path("/home/chris/onto/OntServe/ontologies")

    # Check for extracted classes file
    extracted_file = ontserve_path / "proethica-intermediate-extended.ttl"
    if extracted_file.exists():
        print(f"\n✓ Found extracted classes file:")
        print(f"  {extracted_file}")
        print(f"  Size: {extracted_file.stat().st_size} bytes")

        # Show first few lines
        with open(extracted_file) as f:
            lines = f.readlines()[:20]
            print("\n  First 20 lines:")
            for line in lines:
                print(f"    {line.rstrip()}")
    else:
        print("\n✗ No extracted classes file found")

    # Check for case files
    case_files = list(ontserve_path.glob("proethica-case-*.ttl"))
    if case_files:
        print(f"\n✓ Found {len(case_files)} case ontology files:")
        for cf in case_files:
            print(f"  - {cf.name} ({cf.stat().st_size} bytes)")
    else:
        print("\n✗ No case ontology files found")


if __name__ == "__main__":
    test_commit_workflow()
    check_ttl_files()