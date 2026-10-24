"""The analysis-record applier reads the rows a commit is about to publish, never retracted ones."""
from app import db
from app.models.document import Document
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.models.world import World
from app.services.extraction.analysis_edges import _rows


def _seed_case(case_id):
    world = World.query.first() or World(name="Test World")
    if world.id is None:
        db.session.add(world)
        db.session.flush()
    if not Document.query.get(case_id):
        db.session.add(Document(id=case_id, title=f"Case {case_id}",
                                document_type="case", world_id=world.id))
    db.session.commit()


def _cpr(case_id, label, published, selected):
    return TemporaryRDFStorage(
        case_id=case_id, extraction_session_id="test-analysis-edge-rows",
        extraction_type="code_provision_reference", storage_type="individual",
        entity_label=label, entity_definition="A provision reference.",
        is_published=published, is_selected=selected, rdf_json_ld={})


def test_rows_pending_publication_are_read_and_retracted_rows_are_not(app_context):
    case_id = 9302
    _seed_case(case_id)
    db.session.add_all([
        _cpr(case_id, "II.4.a", published=False, selected=True),    # in the commit, not yet published
        _cpr(case_id, "III.1.b", published=True, selected=True),    # committed earlier
        _cpr(case_id, "III.3", published=False, selected=False),    # retracted
    ])
    db.session.commit()

    labels = [r.entity_label for r in _rows(case_id, "code_provision_reference")]

    assert labels == ["II.4.a", "III.1.b"]
