"""
Test the OntServe commit workflow data model.
"""

from app.models import db
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.models.document import Document
from app.models.world import World


def test_commit_workflow(app):
    """Test entity selection and review workflow."""
    with app.app_context():
        world = World(name="Test World", description="test", metadata={})
        db.session.add(world)
        db.session.flush()
        doc = Document(title="Test Case for Commit", document_type="case", world_id=world.id)
        db.session.add(doc)
        db.session.commit()
        case_id = doc.id

        entity = TemporaryRDFStorage(
            case_id=case_id,
            extraction_session_id="test-commit",
            extraction_type="roles",
            storage_type="class",
            entity_label="Test Role Class",
            entity_uri="http://test/role-class",
            is_selected=True,
            is_reviewed=False,
            created_by="test-script"
        )
        db.session.add(entity)
        db.session.commit()

        assert TemporaryRDFStorage.query.filter_by(case_id=case_id, is_reviewed=False).count() == 1

        entity.is_reviewed = True
        db.session.commit()

        assert TemporaryRDFStorage.query.filter_by(case_id=case_id, is_reviewed=True).count() == 1
