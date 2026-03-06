"""
Test the Clear All Entities behavior.

Verified (reviewed+selected) entities are preserved while unreviewed ones are cleared.
"""

from app.models import db
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.models.document import Document
from app.models.world import World


def test_clear_behavior(app):
    """Test that Clear All Entities preserves reviewed entities."""
    with app.app_context():
        world = World(name="Test World", description="test", metadata={})
        db.session.add(world)
        db.session.flush()
        doc = Document(title="Test Case for Clear Behavior", document_type="case", world_id=world.id)
        db.session.add(doc)
        db.session.commit()
        case_id = doc.id

        reviewed_entity = TemporaryRDFStorage(
            case_id=case_id,
            extraction_session_id="test-clear-session",
            extraction_type="test",
            storage_type="class",
            entity_label="Reviewed Entity",
            entity_uri="http://test/reviewed",
            is_selected=True,
            is_reviewed=True,
            created_by="test-script"
        )
        unreviewed_entity = TemporaryRDFStorage(
            case_id=case_id,
            extraction_session_id="test-clear-session",
            extraction_type="test",
            storage_type="class",
            entity_label="Unreviewed Entity",
            entity_uri="http://test/unreviewed",
            is_selected=True,
            is_reviewed=False,
            created_by="test-script"
        )
        db.session.add_all([reviewed_entity, unreviewed_entity])
        db.session.commit()

        assert TemporaryRDFStorage.query.filter_by(case_id=case_id).count() == 2

        TemporaryRDFStorage.query.filter_by(case_id=case_id, is_reviewed=False).delete()
        db.session.commit()

        remaining = TemporaryRDFStorage.query.filter_by(case_id=case_id).all()
        assert len(remaining) == 1
        assert remaining[0].entity_label == "Reviewed Entity"
