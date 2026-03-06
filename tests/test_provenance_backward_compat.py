"""
Test backward compatibility of provenance integration.
"""

from app.models import db
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.models.document import Document
from app.models.world import World


def _create_test_case():
    world = World(name="Test World", description="test", metadata={})
    db.session.add(world)
    db.session.flush()
    doc = Document(title="Test Case for Provenance", document_type="case", world_id=world.id)
    db.session.add(doc)
    db.session.commit()
    return doc.id


def test_store_extraction_without_provenance(app):
    """Test that store_extraction_results works without provenance parameter."""
    with app.app_context():
        case_id = _create_test_case()

        rdf_data = {
            'new_classes': [
                {
                    'label': 'Test Role Class',
                    'uri': 'http://test.org/TestRole',
                    'definition': 'A test role for backward compatibility',
                    'properties': {}
                }
            ],
            'new_individuals': [
                {
                    'label': 'Test Individual',
                    'uri': 'http://test.org/TestIndividual',
                    'properties': {},
                    'relationships': []
                }
            ]
        }

        entities = TemporaryRDFStorage.store_extraction_results(
            case_id=case_id,
            extraction_session_id='test_session_backward_compat',
            extraction_type='roles',
            rdf_data=rdf_data,
            extraction_model='test-model'
        )

        assert len(entities) == 2
        for entity in entities:
            assert entity.provenance_metadata == {}


def test_store_extraction_with_provenance(app):
    """Test that store_extraction_results works WITH provenance parameter."""
    with app.app_context():
        case_id = _create_test_case()

        rdf_data = {
            'new_classes': [],
            'new_individuals': [
                {
                    'label': 'Test Individual With Prov',
                    'uri': 'http://test.org/TestIndividualProv',
                    'properties': {},
                    'relationships': []
                }
            ]
        }

        provenance_data = {
            'extraction_activity_id': 123,
            'section_type': 'questions',
            'extracted_at': '2025-10-12T15:00:00'
        }

        entities = TemporaryRDFStorage.store_extraction_results(
            case_id=case_id,
            extraction_session_id='test_session_with_prov',
            extraction_type='roles',
            rdf_data=rdf_data,
            extraction_model='test-model',
            provenance_data=provenance_data
        )

        assert len(entities) == 1
        assert entities[0].provenance_metadata == provenance_data
