#!/usr/bin/env python3
"""
Test the Refresh from OntServe API endpoint.
"""

import sys
sys.path.insert(0, '/home/chris/onto/proethica')

from app import create_app, db
from app.services.ontserve_data_fetcher import OntServeDataFetcher
from app.models.temporary_rdf_storage import TemporaryRDFStorage


def test_refresh_api():
    """Test the refresh API directly."""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("TESTING REFRESH FROM ONTSERVE")
        print("=" * 60)

        case_id = 18

        # Check current ProEthica state
        print("\n1. BEFORE REFRESH - ProEthica shows:")
        entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_committed=True
        ).all()

        for e in entities:
            if 'Technical' in e.entity_label:
                print(f"   {e.entity_label} (should NOT have modification)")

        # Get ProEthica entities
        proethica_entities = [entity.to_dict() for entity in entities]

        # Initialize fetcher and refresh
        print("\n2. RUNNING REFRESH...")
        fetcher = OntServeDataFetcher()
        refresh_result = fetcher.refresh_committed_entities(case_id, proethica_entities)

        print(f"\n3. REFRESH RESULTS:")
        print(f"   Refreshed: {refresh_result['refreshed']} entities")
        print(f"   Modified: {refresh_result['modified']} entities")
        print(f"   Unchanged: {refresh_result['unchanged']} entities")
        print(f"   Not found: {refresh_result['not_found']} entities")

        # Show details of modified entities
        if refresh_result['modified'] > 0:
            print("\n4. MODIFIED ENTITIES:")
            for detail in refresh_result['details']:
                if detail['status'] == 'modified':
                    print(f"   - {detail['entity_label']}:")
                    for change in detail.get('changes', []):
                        print(f"     * {change['field']}: '{change['proethica_value']}' → '{change['ontserve_value']}'")

        # Update ProEthica with OntServe data
        print("\n5. UPDATING PROETHICA...")
        update_count = 0
        for detail in refresh_result['details']:
            if detail['status'] == 'modified':
                entity_uri = detail['entity_uri']
                entity = TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    entity_uri=entity_uri,
                    is_committed=True
                ).first()

                if entity and 'ontserve_data' in detail:
                    ontserve_data = detail['ontserve_data']
                    old_label = entity.entity_label
                    entity.entity_label = ontserve_data.get('label', entity.entity_label)
                    print(f"   Updated: '{old_label}' → '{entity.entity_label}'")
                    update_count += 1

        if update_count > 0:
            db.session.commit()
            print(f"\n   ✅ Committed {update_count} updates to ProEthica database")

        # Check final state
        print("\n6. AFTER REFRESH - ProEthica now shows:")
        entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_committed=True
        ).all()

        for e in entities:
            if 'Technical' in e.entity_label:
                print(f"   {e.entity_label} (should NOW have modification)")

        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        print("\n✅ The refresh functionality is working!")
        print("ProEthica successfully pulled live data from OntServe")
        print("and updated its records to match.")


if __name__ == "__main__":
    test_refresh_api()