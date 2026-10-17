"""Step 4 data helpers: service-layer location and summary counts."""
import pytest

from app.models import db
from app.models.temporary_rdf_storage import TemporaryRDFStorage


@pytest.fixture
def case_entities(app):
    with app.app_context():
        from app.models.document import Document
        from app.models.world import World

        world = World(name="Summary World", description="test", metadata={})
        db.session.add(world)
        db.session.flush()
        db.session.add_all([
            Document(id=991, title="Case A", document_type="case", world_id=world.id),
            Document(id=992, title="Case B", document_type="case", world_id=world.id),
        ])
        db.session.flush()
        rows = [
            TemporaryRDFStorage(case_id=991, extraction_session_id="s",
                                extraction_type="roles", storage_type="class",
                                entity_label="R1"),
            TemporaryRDFStorage(case_id=991, extraction_session_id="s",
                                extraction_type="roles", storage_type="individual",
                                entity_label="R2"),
            TemporaryRDFStorage(case_id=991, extraction_session_id="s",
                                extraction_type="obligations", storage_type="class",
                                entity_label="O1"),
            TemporaryRDFStorage(case_id=991, extraction_session_id="s",
                                extraction_type="temporal_dynamics_enhanced",
                                storage_type="individual", entity_label="A1"),
            TemporaryRDFStorage(case_id=992, extraction_session_id="s",
                                extraction_type="roles", storage_type="class",
                                entity_label="OtherCase"),
        ]
        db.session.add_all(rows)
        db.session.commit()
        yield 991


def test_get_entities_summary_counts_and_totals(case_entities):
    from app.services.step4_synthesis.step4_data_helpers import get_entities_summary

    summary = get_entities_summary(case_entities)
    assert summary["roles"] == 2
    assert summary["obligations"] == 1
    assert summary["temporal_dynamics"] == 1
    assert summary["pass1_total"] == 2
    assert summary["pass2_total"] == 1
    assert summary["pass3_total"] == 1
    assert summary["total"] == 4


def test_route_helpers_reexport_is_same_function():
    from app.routes.scenario_pipeline.step4.helpers import (
        get_entities_summary as route_summary,
    )
    from app.services.step4_synthesis.step4_data_helpers import (
        get_entities_summary as service_summary,
    )

    assert route_summary is service_summary

