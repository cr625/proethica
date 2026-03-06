"""
Test entity refresh data model operations.
"""

from app.models import db
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.models.document import Document
from app.models.world import World


def test_refresh_api(app):
    """Test entity query and update operations used by refresh workflow."""
    with app.app_context():
        world = World(name="Test World", description="test", metadata={})
        db.session.add(world)
        db.session.flush()
        doc = Document(title="Test Case for Refresh", document_type="case", world_id=world.id)
        db.session.add(doc)
        db.session.commit()
        case_id = doc.id

        entity = TemporaryRDFStorage(
            case_id=case_id,
            extraction_session_id="test-refresh",
            extraction_type="roles",
            storage_type="class",
            entity_label="Original Label",
            entity_uri="http://test/refresh-entity",
            is_selected=True,
            is_reviewed=True,
            created_by="test-script"
        )
        db.session.add(entity)
        db.session.commit()

        reviewed = TemporaryRDFStorage.query.filter_by(case_id=case_id, is_reviewed=True).all()
        assert len(reviewed) == 1

        reviewed[0].entity_label = "Updated Label from OntServe"
        db.session.commit()

        updated = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, entity_uri="http://test/refresh-entity"
        ).first()
        assert updated.entity_label == "Updated Label from OntServe"
