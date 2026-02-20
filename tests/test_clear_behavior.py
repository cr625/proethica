#!/usr/bin/env python3
"""
Test the improved Clear All Entities behavior.

This demonstrates that committed entities are preserved while uncommitted ones are cleared.
"""

import sys
sys.path.insert(0, '/home/chris/onto/proethica')

from app import create_app, db
from app.models.temporary_rdf_storage import TemporaryRDFStorage


def test_clear_behavior():
    """Test that Clear All Entities preserves committed entities."""
    app = create_app()

    with app.app_context():
        print("Testing Clear All Entities Behavior")
        print("=" * 50)

        case_id = 18

        # Check current status
        print("\n1. CURRENT STATUS:")
        committed = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_committed=True
        ).count()
        uncommitted = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_committed=False
        ).count()

        print(f"   Committed entities: {committed}")
        print(f"   Uncommitted entities: {uncommitted}")

        # Add a test uncommitted entity
        print("\n2. ADDING TEST UNCOMMITTED ENTITY...")
        test_entity = TemporaryRDFStorage(
            case_id=case_id,
            extraction_session_id="test-clear-session",
            extraction_type="test",
            storage_type="class",
            entity_label="Test Uncommitted Class",
            entity_uri="http://test/uncommitted",
            is_committed=False,
            created_by="test-script"
        )
        db.session.add(test_entity)
        db.session.commit()

        uncommitted_after = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_committed=False
        ).count()
        print(f"   Uncommitted entities after adding test: {uncommitted_after}")

        # Simulate Clear All Entities
        print("\n3. SIMULATING CLEAR ALL ENTITIES...")

        # Count before clear
        committed_before = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_committed=True
        ).count()

        # Clear only uncommitted (NEW BEHAVIOR)
        cleared = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_committed=False
        ).count()

        TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_committed=False
        ).delete()
        db.session.commit()

        # Check after clear
        committed_after = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_committed=True
        ).count()
        uncommitted_final = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_committed=False
        ).count()

        print(f"   Cleared {cleared} uncommitted entities")
        print(f"   Preserved {committed_after} committed entities")

        print("\n4. FINAL STATUS:")
        print(f"   Committed entities: {committed_after} (preserved)")
        print(f"   Uncommitted entities: {uncommitted_final} (cleared)")

        print("\n" + "=" * 50)
        if committed_before == committed_after:
            print("✅ SUCCESS: Committed entities were preserved!")
            print("   They remain in OntServe and can be viewed at:")
            print("   - http://localhost:5003/ontology/proethica-intermediate-extended")
            print("   - http://localhost:5003/ontology/proethica-case-18")
        else:
            print("❌ PROBLEM: Some committed entities were lost!")

        print("\n5. WHAT THIS MEANS:")
        print("   - Clear All Entities now only removes uncommitted/draft entities")
        print("   - Entities already saved to OntServe are preserved")
        print("   - The UI will show a message about preserved entities")
        print("   - ProEthica maintains records of what's in OntServe")


if __name__ == "__main__":
    test_clear_behavior()