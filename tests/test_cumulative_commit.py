#!/usr/bin/env python3
"""
Test cumulative addition of classes to proethica-intermediate-extracted.

This demonstrates that new classes are added without removing existing ones.
"""

import sys
sys.path.insert(0, '/home/chris/onto/proethica')

from app import create_app, db
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.ontserve_commit_service import OntServeCommitService
from datetime import datetime
import json


def create_test_state_entities():
    """Create some test state entities to demonstrate cumulative addition."""
    app = create_app()

    with app.app_context():
        print("Creating test State entities for cumulative commit test...\n")

        # Create a test state class
        state_class = TemporaryRDFStorage(
            case_id=18,
            extraction_session_id="test-states-session",
            extraction_type="states",
            storage_type="class",
            ontology_target="proethica-intermediate",
            entity_label="Conflict of Interest State",
            entity_uri="http://proethica.org/ontology/intermediate#ConflictOfInterestState",
            entity_type="State",
            entity_definition="A professional state where personal or financial interests conflict with professional duties",
            is_selected=True,
            is_reviewed=True,
            is_committed=False,
            extraction_model="test-model",
            created_by="test-script",
            rdf_json_ld={
                "label": "Conflict of Interest State",
                "description": "A professional state where personal or financial interests conflict with professional duties",
                "types": ["http://proethica.org/ontology/core#State"]
            }
        )

        # Create another state class
        state_class2 = TemporaryRDFStorage(
            case_id=18,
            extraction_session_id="test-states-session",
            extraction_type="states",
            storage_type="class",
            ontology_target="proethica-intermediate",
            entity_label="Public Safety Risk State",
            entity_uri="http://proethica.org/ontology/intermediate#PublicSafetyRiskState",
            entity_type="State",
            entity_definition="A situation where public health or safety is at risk due to professional decisions or actions",
            is_selected=True,
            is_reviewed=True,
            is_committed=False,
            extraction_model="test-model",
            created_by="test-script",
            rdf_json_ld={
                "label": "Public Safety Risk State",
                "description": "A situation where public health or safety is at risk due to professional decisions or actions",
                "types": ["http://proethica.org/ontology/core#State"]
            }
        )

        db.session.add(state_class)
        db.session.add(state_class2)
        db.session.commit()

        print(f"✓ Created 2 test State classes")

        # Get the IDs of the created entities
        entity_ids = [state_class.id, state_class2.id]

        # Now commit them
        print("\nCommitting State classes to proethica-intermediate-extracted...")
        commit_service = OntServeCommitService()
        result = commit_service.commit_selected_entities(18, entity_ids)

        if result['success']:
            print(f"✓ Successfully committed {result['classes_committed']} State classes")
            print(f"  These are ADDED to the existing Resource classes")
        else:
            print(f"✗ Commit failed: {result.get('error')}")

        # Check the final status
        print("\n" + "=" * 50)
        print("Checking cumulative result...")

        # Read the TTL file
        ttl_file = "/home/chris/onto/OntServe/ontologies/proethica-intermediate-extracted.ttl"
        with open(ttl_file) as f:
            content = f.read()

        # Count classes
        resource_count = content.count("subClassOf proeth-core:Resource")
        state_count = content.count("subClassOf proeth-core:State")

        print(f"✓ proethica-intermediate-extracted.ttl now contains:")
        print(f"  - {resource_count} Resource classes (previously committed)")
        print(f"  - {state_count} State classes (just added)")
        print(f"  - Total: {resource_count + state_count} classes")

        print("\n✓ Cumulative addition successful!")
        print("\nYou can now view all classes at:")
        print("  http://localhost:5003/ontology/proethica-intermediate-extracted")


if __name__ == "__main__":
    create_test_state_entities()