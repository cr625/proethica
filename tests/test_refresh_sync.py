#!/usr/bin/env python3
"""
Test the Refresh from OntServe functionality.

This simulates editing an entity in OntServe and then refreshing ProEthica.
"""

import sys
sys.path.insert(0, '/home/chris/onto/proethica')

import psycopg2
from psycopg2.extras import RealDictCursor

def modify_entity_in_ontserve():
    """Directly modify an entity in OntServe to simulate external editing."""

    conn = psycopg2.connect(
        host="localhost",
        database="ontserve",
        user="postgres",
        password="PASS",
        cursor_factory=RealDictCursor
    )
    cursor = conn.cursor()

    # First, let's see what we have
    print("=" * 60)
    print("ENTITIES IN ONTSERVE BEFORE MODIFICATION")
    print("=" * 60)

    cursor.execute("""
        SELECT oe.label, oe.uri, o.name as ontology
        FROM ontology_entities oe
        JOIN ontologies o ON oe.ontology_id = o.id
        WHERE o.name IN ('proethica-intermediate-extended', 'proethica-case-18')
        ORDER BY o.name, oe.label
    """)

    for row in cursor.fetchall():
        print(f"  {row['ontology']}: {row['label']}")

    print("\n" + "=" * 60)
    print("MODIFYING AN ENTITY IN ONTSERVE")
    print("=" * 60)

    # Modify "Technical Evaluation Report" to add " (Modified)" to its label
    cursor.execute("""
        UPDATE ontology_entities
        SET label = label || ' (Modified in OntServe)'
        WHERE label = 'Technical Evaluation Report'
        AND ontology_id = (SELECT id FROM ontologies WHERE name = 'proethica-intermediate-extended')
        RETURNING label, uri
    """)

    result = cursor.fetchone()
    if result:
        print(f"✅ Modified: {result['label']}")
        print(f"   URI: {result['uri']}")
    else:
        print("❌ No entity found to modify")

    conn.commit()

    print("\n" + "=" * 60)
    print("ENTITIES IN ONTSERVE AFTER MODIFICATION")
    print("=" * 60)

    cursor.execute("""
        SELECT oe.label, oe.uri, o.name as ontology
        FROM ontology_entities oe
        JOIN ontologies o ON oe.ontology_id = o.id
        WHERE o.name IN ('proethica-intermediate-extended', 'proethica-case-18')
        ORDER BY o.name, oe.label
    """)

    for row in cursor.fetchall():
        print(f"  {row['ontology']}: {row['label']}")

    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print("\nNOW GO TO ProEthica AND:")
    print("1. Navigate to: http://localhost:5000/scenario_pipeline/case/18/entities/review")
    print("2. Check that 'Technical Evaluation Report' still shows WITHOUT '(Modified in OntServe)'")
    print("3. Click the 'Refresh from OntServe' button")
    print("4. You should see a message about 1 modified entity")
    print("5. After refresh, the entity should show WITH '(Modified in OntServe)'")
    print("\nThis proves that ProEthica is now showing live OntServe data!")


def check_proethica_state():
    """Check what ProEthica currently shows."""
    from app import create_app, db
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    app = create_app()
    with app.app_context():
        print("\n" + "=" * 60)
        print("ENTITIES IN PROETHICA DATABASE")
        print("=" * 60)

        entities = TemporaryRDFStorage.query.filter_by(
            case_id=18,
            is_committed=True
        ).all()

        for e in entities:
            print(f"  [{e.storage_type}] {e.entity_label}")
            if 'Technical' in e.entity_label:
                print(f"    --> This should NOT have '(Modified in OntServe)' yet")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        check_proethica_state()
    else:
        modify_entity_in_ontserve()
        check_proethica_state()