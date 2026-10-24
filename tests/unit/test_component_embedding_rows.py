"""The component embedding of a case reads its committed individuals in id order."""
from unittest import mock

import numpy as np

from app import db
from app.models.document import Document
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.models.world import World
from app.services.precedent.case_feature_extractor import CaseFeatureExtractor


def _seed_case(case_id):
    world = World.query.first() or World(name="Test World")
    if world.id is None:
        db.session.add(world)
        db.session.flush()
    if not Document.query.get(case_id):
        db.session.add(Document(id=case_id, title=f"Case {case_id}",
                                document_type="case", world_id=world.id))
    db.session.commit()


def _row(case_id, extraction_type, label, definition, storage_type="individual",
         published=True, selected=True):
    return TemporaryRDFStorage(
        case_id=case_id, extraction_session_id="test-component-rows",
        extraction_type=extraction_type, storage_type=storage_type,
        entity_label=label, entity_definition=definition,
        is_published=published, is_selected=selected, rdf_json_ld={})


def test_component_text_is_the_committed_individuals_in_id_order(app_context):
    case_id = 9301
    _seed_case(case_id)
    db.session.add_all([
        _row(case_id, "roles", "Engineer A", "the engineer of record"),
        _row(case_id, "roles", "Engineer Role", "a class definition", storage_type="class"),
        _row(case_id, "roles", "Dropped Role", "a gate drop", published=False, selected=False),
        _row(case_id, "roles", "Client B", "the client"),
        _row(case_id, "principles", "Honesty", "truthful statements"),
        _row(case_id, "obligations", "Disclosure Duty", "disclose the risk"),
    ])
    db.session.commit()

    texts = []

    def fake_embedding(self, text):
        texts.append(text)
        return np.ones(384) / np.sqrt(384)

    with mock.patch.object(CaseFeatureExtractor, "_get_local_embedding", fake_embedding):
        result = CaseFeatureExtractor().generate_component_aggregated_embedding(case_id)

    assert result is not None
    assert "Engineer A: the engineer of record Client B: the client" in texts
    joined = " ".join(texts)
    assert "a class definition" not in joined
    assert "a gate drop" not in joined
