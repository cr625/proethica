"""Storage-time lessons from the NSPE case 24-1 (ProEthica case 8) review.

The review found five storage-time defects. Each test below reproduces one against
an in-memory SQLite database (the ORM models, no Postgres) or against the ORM
instance state alone, and asserts the handling now in place:

L1  the semantic dedup is scoped by storage_type: the role individual "Community
    Affected Public" no longer vanishes into the CLASS row "Affected Community"
    (cos 0.893, above the 0.88 threshold).
L2  every storage-time merge and every citation-designator refusal is named in
    provenance_activities (merged labels, surviving row id, cosine), beside the
    logger line that used to be the only record.
L3  in-place edits of the JSON columns persist: rdf_json_ld / provenance_metadata
    (TemporaryRDFStorage) and extraction_metadata (CasePrecedentFeatures) are
    MutableDict columns and the three editing services flag the attribute.
L4  extraction_prompts.results_summary is written after storage from the stored
    rows and carries stored_* and merged_into_existing counts.
L5  an individual's type IRI is the matched ontology class when the matcher found
    one, else the IRI the commit sanitizer mints ("Provider-Client Role" ->
    intermediate#ProviderClientRole, not #Provider-ClientRole).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from sqlalchemy import event, inspect as sa_inspect
from sqlalchemy.ext.mutable import MutableDict

import app.models.user  # noqa: F401  (World -> User relationship target; needed to configure mappers)
from app.models import db
from app.models.case_precedent_features import CasePrecedentFeatures
from app.models.extraction_prompt import ExtractionPrompt
from app.models.provenance import ProvenanceActivity, ProvenanceAgent
from app.models.temporary_rdf_storage import TemporaryRDFStorage
import app.services.entity.rdf_storage_service as rss
import app.services.precedent.phase4_connector as p4
from app.services.entity.entity_merge_service import EntityMergeService
from app.services.extraction.extraction_graph import (
    individual_type_iri, pydantic_to_rdf_data, store_extraction_result,
)
from app.services.extraction.schemas import CandidateRoleClass, MatchDecision, RoleIndividual

INTERMEDIATE = "http://proethica.org/ontology/intermediate#"

# Unit vectors standing in for sentence embeddings, keyed by entity label. The case-A pair
# sits at cos 0.893 (the value the review recorded); the case-E pair embeds identically
# (same composed definition apart from the case number); every other label gets an axis
# of its own, so unrelated labels are orthogonal to everything.
_VECTORS = {
    "Affected Community": (1.0, 0.0, 0.0),
    "Community Affected Public": (0.893, 0.45006, 0.0),
    "BER Case 22-5": (0.0, 1.0, 0.0),
    "BER Case 20-4": (0.0, 1.0, 0.0),
}
_DIM = 16
_OWN_AXIS = {}


def _fake_embed(text):
    label = text.split(":", 1)[0].strip()
    if label in _VECTORS:
        vec = list(_VECTORS[label])
    else:
        axis = _OWN_AXIS.setdefault(label, 3 + len(_OWN_AXIS))
        vec = [0.0] * (axis + 1)
        vec[axis] = 1.0
    return tuple(vec + [0.0] * (_DIM - len(vec)))


# ---------------------------------------------------------------------------
# Fixtures: a Flask app bound to in-memory SQLite with only the tables these
# services touch (CasePrecedentFeatures carries ARRAY columns SQLite cannot
# create, so it is exercised through instance state instead).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sqlite_app():
    flask_app = Flask("storage-persistence-test")
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    flask_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(flask_app)
    with flask_app.app_context():
        engine = db.engine

        # pysqlite needs an explicit BEGIN for SAVEPOINT (provenance track_pass) to work.
        @event.listens_for(engine, "connect")
        def _connect(dbapi_connection, _record):
            dbapi_connection.isolation_level = None

        @event.listens_for(engine, "begin")
        def _begin(conn):
            conn.exec_driver_sql("BEGIN")

        for model in (TemporaryRDFStorage, ExtractionPrompt, ProvenanceAgent, ProvenanceActivity):
            model.__table__.create(bind=engine)
        yield flask_app


@pytest.fixture
def session(sqlite_app):
    with sqlite_app.app_context():
        yield db.session
        db.session.rollback()
        for model in (ProvenanceActivity, ProvenanceAgent, ExtractionPrompt, TemporaryRDFStorage):
            db.session.query(model).delete()
        db.session.commit()
        db.session.remove()


@pytest.fixture
def fake_embeddings():
    with patch.object(rss, "_embed_text", side_effect=_fake_embed):
        yield


def _row(session, **kw):
    fields = dict(
        case_id=8, extraction_session_id="facts-1", extraction_type="roles",
        storage_type="class", ontology_target="proethica-intermediate", entity_type="Roles",
        rdf_json_ld={}, provenance_metadata={"section_type": "facts"},
        is_published=False, is_selected=True, property_count=0,
    )
    fields.update(kw)
    row = TemporaryRDFStorage(**fields)
    session.add(row)
    session.commit()
    return row


def _individual(label, definition, **props):
    return {
        "uri": f"http://proethica.org/ontology/case/8#{label.replace(' ', '_')}",
        "label": label,
        "definition": definition,
        "definitions": [{"text": definition, "source_type": "extraction", "is_primary": True}],
        "types": [f"{INTERMEDIATE}Role"],
        "properties": props or {"textReferences": ["quote"]},
        "relationships": [],
        "source_text": "quote",
        "match_decision": {},
    }


def _store(session, rdf_data, extraction_type="roles", session_id="discussion-1", section="discussion"):
    return rss.store_extraction_results(
        case_id=8, extraction_session_id=session_id, extraction_type=extraction_type,
        rdf_data=rdf_data, extraction_model="test-model",
        provenance_data={"section_type": section},
    )


# ---------------------------------------------------------------------------
# L1  storage_type scoping of the semantic dedup (defect A)
# ---------------------------------------------------------------------------

def test_semantic_match_never_crosses_storage_type(session, fake_embeddings):
    class_row = _row(session, entity_label="Affected Community",
                     entity_definition="the public bearing the effects of the project")
    definition = "the community affected by the engineer's work"

    # The unscoped lookup still reaches the class row: the pair is above the threshold.
    assert rss._find_semantic_match(8, "Community Affected Public", definition, "Roles") is class_row
    # Scoped to individuals, the class row is not a candidate.
    assert rss._find_semantic_match(
        8, "Community Affected Public", definition, "Roles", storage_type="individual") is None


def test_individual_is_stored_beside_a_near_identical_class_row(session, fake_embeddings):
    class_row = _row(session, entity_label="Affected Community",
                     entity_definition="the public bearing the effects of the project",
                     rdf_json_ld={"properties": {"textReferences": ["class quote"]}}, property_count=1)

    stored = _store(session, {"new_classes": [], "new_individuals": [
        _individual("Community Affected Public", "the community affected by the engineer's work")]})
    session.commit()

    assert [e.storage_type for e in stored] == ["individual"]
    individuals = TemporaryRDFStorage.query.filter_by(case_id=8, storage_type="individual").all()
    assert [i.entity_label for i in individuals] == ["Community Affected Public"]
    session.refresh(class_row)
    assert class_row.property_count == 1
    assert class_row.rdf_json_ld["properties"]["textReferences"] == ["class quote"]


def test_exact_label_lookup_is_scoped_too(session):
    _row(session, entity_label="NSPE Code of Ethics", storage_type="class", entity_type="Resources")
    assert rss._find_existing_entity(8, "NSPE Code of Ethics", "Resources", "s2",
                                     storage_type="individual") is None
    assert rss._find_existing_entity(8, "NSPE Code of Ethics", "Resources", "s2",
                                     storage_type="class") is not None


# ---------------------------------------------------------------------------
# L2  provenance activities for merges and designator refusals (defects A, E)
# ---------------------------------------------------------------------------

def test_storage_merges_are_recorded_as_a_merge_activity(session, fake_embeddings):
    engineer = _row(session, entity_label="Engineer A", storage_type="individual",
                    ontology_target="proethica-case-8", entity_definition="the engineer of record",
                    rdf_json_ld={"properties": {"textReferences": ["facts quote"]}}, property_count=1)
    community = _row(session, entity_label="Affected Community", storage_type="individual",
                     ontology_target="proethica-case-8",
                     entity_definition="the public bearing the effects of the project")

    _store(session, {"new_classes": [], "new_individuals": [
        _individual("Engineer A", "the engineer of record", textReferences=["discussion quote"]),
        _individual("Community Affected Public", "the community affected by the engineer's work"),
    ]})
    session.commit()

    activities = ProvenanceActivity.query.filter_by(case_id=8, activity_type="merge").all()
    assert len(activities) == 1
    act = activities[0]
    assert act.activity_name == "storage_dedup_merge"
    assert act.session_id == "discussion-1"
    assert act.status == "completed"
    assert act.execution_plan["concept_type"] == "roles"
    assert act.execution_plan["section"] == "discussion"
    merges = {m["label"]: m for m in act.activity_metadata["merges"]}
    assert act.activity_metadata["count"] == 2
    assert merges["Engineer A"]["into_id"] == engineer.id
    assert merges["Engineer A"]["method"] == "exact_label"
    assert merges["Community Affected Public"]["into_id"] == community.id
    assert merges["Community Affected Public"]["into_label"] == "Affected Community"
    assert merges["Community Affected Public"]["method"] == "semantic"
    assert merges["Community Affected Public"]["cosine"] == pytest.approx(0.893, abs=0.001)
    # The merged quotes reached the surviving row (L3 end to end).
    session.refresh(engineer)
    assert engineer.rdf_json_ld["properties"]["textReferences"] == ["facts quote", "discussion quote"]


def test_designator_guard_refusal_is_recorded_as_a_filter_activity(session, fake_embeddings):
    definition = "NSPE Board of Ethical Review precedent on disclosure duties"
    kept = _row(session, entity_label="BER Case 22-5", storage_type="individual",
                extraction_type="resources", entity_type="Resources",
                ontology_target="proethica-case-8", entity_definition=definition)

    _store(session, {"new_classes": [], "new_individuals": [_individual("BER Case 20-4", definition)]},
           extraction_type="resources")
    session.commit()

    labels = sorted(r.entity_label for r in TemporaryRDFStorage.query.filter_by(
        case_id=8, extraction_type="resources").all())
    assert labels == ["BER Case 20-4", "BER Case 22-5"]
    assert ProvenanceActivity.query.filter_by(case_id=8, activity_type="merge").count() == 0
    guard = ProvenanceActivity.query.filter_by(case_id=8, activity_type="filter",
                                               activity_name="designator_guard").one()
    refusal, = guard.activity_metadata["kept_separate"]
    assert refusal == {"label": "BER Case 20-4", "kept_separate_from": "BER Case 22-5",
                       "kept_separate_from_id": kept.id, "cosine": 1.0}


def test_no_activity_when_nothing_merged(session, fake_embeddings):
    _store(session, {"new_classes": [], "new_individuals": [_individual("Engineer B", "a reviewer")]})
    session.commit()
    assert ProvenanceActivity.query.filter_by(case_id=8).count() == 0


# ---------------------------------------------------------------------------
# L3  in-place JSON edits persist (defect B)
# ---------------------------------------------------------------------------

def test_merge_into_existing_persists_text_references(session):
    row = _row(session, entity_label="Engineer A", storage_type="individual",
               rdf_json_ld={"definition": "the engineer of record",
                            "properties": {"textReferences": ["facts quote"]}},
               property_count=1)
    session.expire_all()
    row = db.session.get(TemporaryRDFStorage, row.id)

    rss._merge_into_existing(row, {
        "properties": {"textReferences": ["discussion quote"]},
        "definitions": [{"text": "the engineer who signed the plans", "source_type": "extraction"}],
        "source_text": "discussion quote",
    }, "discussion")
    session.commit()
    session.expire_all()

    again = db.session.get(TemporaryRDFStorage, row.id)
    assert again.rdf_json_ld["properties"]["textReferences"] == ["facts quote", "discussion quote"]
    assert again.property_count == 2
    assert [d["text"] for d in again.rdf_json_ld["definitions"]] == [
        "the engineer of record", "the engineer who signed the plans"]
    assert again.rdf_json_ld["section_sources"] == ["facts", "discussion"]


def test_entity_merge_service_persists_text_references(session):
    row = _row(session, entity_label="Engineer A", storage_type="individual",
               rdf_json_ld={"properties": {"textReferences": ["facts quote"]}}, property_count=1)
    session.expire_all()
    row = db.session.get(TemporaryRDFStorage, row.id)

    EntityMergeService().merge_entity_properties(
        row, {"properties": {"textReferences": ["discussion quote"]}}, "discussion-1")
    session.commit()
    session.expire_all()

    again = db.session.get(TemporaryRDFStorage, row.id)
    assert again.rdf_json_ld["properties"]["textReferences"] == ["facts quote", "discussion quote"]
    assert again.property_count == 2


def test_provenance_metadata_in_place_edit_persists(session):
    row = _row(session, entity_label="Engineer A", provenance_metadata={"section_type": "facts"})
    session.expire_all()
    row = db.session.get(TemporaryRDFStorage, row.id)
    row.provenance_metadata["citation_resolved"] = True
    session.commit()
    session.expire_all()
    assert db.session.get(TemporaryRDFStorage, row.id).provenance_metadata == {
        "section_type": "facts", "citation_resolved": True}


def _as_loaded(instance):
    """Make a transient instance look freshly loaded: nothing pending, nothing modified."""
    state = sa_inspect(instance)
    state._commit_all(state.dict)
    assert not state.modified
    return state


def test_precedent_features_metadata_is_a_tracked_mutable_dict():
    features = CasePrecedentFeatures(case_id=8, extraction_metadata={"phase4_connected_at": "2025-12-21"})
    assert isinstance(features.extraction_metadata, MutableDict)
    state = _as_loaded(features)

    features.extraction_metadata["phase4_connected_at"] = "2026-07-10"

    assert state.modified
    assert state.attrs.extraction_metadata.history.added  # the column is in the next UPDATE


def test_phase4_connector_rewrites_metadata_on_rerun():
    features = CasePrecedentFeatures(
        case_id=8, transformation_type="transfer",
        extraction_metadata={"phase4_connected_at": "2025-12-21T00:00:00",
                             "narrative_elements": {"characters": 2, "events": 1,
                                                    "conflicts": 0, "decision_moments": 0}})
    state = _as_loaded(features)
    narrative = SimpleNamespace(characters=[1, 2, 3, 4], events=[1, 2], conflicts=[], decision_moments=[])
    query = MagicMock()
    query.filter_by.return_value.first.return_value = features

    with patch.object(p4.CasePrecedentFeatures, "query", query), \
         patch.object(p4, "db") as fake_db, \
         patch.object(p4.ModelConfig, "get_claude_model", return_value="test-model"), \
         patch("app.services.precedent.case_feature_extractor.board_outcome_for_case",
               return_value=None):
        assert p4.update_precedent_features_from_phase4(8, narrative_elements=narrative) is True

    fake_db.session.commit.assert_called_once()
    assert features.extraction_metadata["narrative_elements"] == {
        "characters": 4, "events": 2, "conflicts": 0, "decision_moments": 0}
    assert features.extraction_metadata["phase4_connected_at"] > "2026"
    assert state.attrs.extraction_metadata.history.added


# ---------------------------------------------------------------------------
# L4  results_summary written after storage from the stored rows (defect C)
# ---------------------------------------------------------------------------

def _match(**kw):
    return MatchDecision(**{"matches_existing": False, "confidence": 0.9, "reasoning": "new", **kw})


def test_results_summary_counts_stored_and_merged_rows(session, fake_embeddings):
    _row(session, entity_label="Engineer A", storage_type="individual",
         ontology_target="proethica-case-8", entity_definition="the engineer of record",
         rdf_json_ld={"properties": {"textReferences": ["facts quote"]}}, property_count=1)
    extractor = SimpleNamespace(model_name="test-model", last_prompt="prompt", last_raw_response="{}",
                                injection_mode="full", tool_call_log=None, ontology_definitions=None)
    classes = [CandidateRoleClass(label="Reviewing Engineer Role", definition="A reviewer.",
                                  match_decision=_match())]
    individuals = [
        RoleIndividual(name="Engineer A", role_class="Reviewing Engineer Role", match_decision=_match(),
                       case_involvement="the engineer of record"),
        RoleIndividual(name="Engineer B", role_class="Reviewing Engineer Role", match_decision=_match(),
                       case_involvement="the peer reviewer"),
    ]

    store_extraction_result(
        case_id=8, concept_type="roles", step_number=1, section_type="discussion",
        session_id="discussion-1", extractor=extractor, classes=classes, individuals=individuals,
        pass_number=1, extraction_pass="contextual_framework",
    )

    prompt = ExtractionPrompt.query.filter_by(extraction_session_id="discussion-1").one()
    assert prompt.results_summary == {
        "classes": 1, "individuals": 2,
        "stored_classes": 1, "stored_individuals": 1, "merged_into_existing": 1,
    }
    stored = TemporaryRDFStorage.query.filter_by(extraction_session_id="discussion-1").all()
    assert sorted(r.storage_type for r in stored) == ["class", "individual"]


def test_storage_summary_from_rows(session):
    _row(session, entity_label="A", extraction_session_id="s9", storage_type="class")
    _row(session, entity_label="b", extraction_session_id="s9", storage_type="individual")
    _row(session, entity_label="c", extraction_session_id="s9", storage_type="individual")
    _row(session, entity_label="other session", extraction_session_id="s8", storage_type="individual")
    assert rss.storage_summary(8, "s9", "roles", extracted_classes=1, extracted_individuals=4) == {
        "classes": 1, "individuals": 4, "stored_classes": 1, "stored_individuals": 2,
        "merged_into_existing": 2}


# ---------------------------------------------------------------------------
# L5  individual type IRI (defect D)
# ---------------------------------------------------------------------------

def test_unmatched_hyphenated_class_ref_uses_the_commit_sanitizer():
    assert individual_type_iri("Provider-Client Role", _match()) == f"{INTERMEDIATE}ProviderClientRole"


def test_matched_class_ref_uses_the_matched_uri():
    md = _match(matches_existing=True, matched_uri=f"{INTERMEDIATE}ProviderClientRole",
                matched_label="Provider Client Role", confidence=0.95)
    assert individual_type_iri("Provider-Client Role", md) == f"{INTERMEDIATE}ProviderClientRole"
    # A match without a resolvable IRI falls back to the sanitizer.
    md = _match(matches_existing=True, matched_uri="Provider Client Role")
    assert individual_type_iri("Provider-Client Role", md) == f"{INTERMEDIATE}ProviderClientRole"


def test_pydantic_to_rdf_data_types_provider_client_role():
    cls = CandidateRoleClass(label="Provider-Client Role", definition="A role facet toward a client.",
                             match_decision=_match())
    unmatched = RoleIndividual(name="Engineer A", role_class="Provider-Client Role", match_decision=_match())
    matched = RoleIndividual(
        name="Engineer B", role_class="Provider-Client Role",
        match_decision=_match(matches_existing=True, matched_uri=f"{INTERMEDIATE}ProviderClientRole",
                              matched_label="Provider Client Role"))

    out = pydantic_to_rdf_data(classes=[cls], individuals=[unmatched, matched], concept_type="roles",
                               case_id=8, section_type="facts", step_number=1)

    assert out["new_classes"][0]["uri"] == f"{INTERMEDIATE}ProviderClientRole"
    assert out["new_individuals"][0]["types"] == [f"{INTERMEDIATE}ProviderClientRole"]
    assert out["new_individuals"][1]["types"] == [f"{INTERMEDIATE}ProviderClientRole"]
    assert "Provider-ClientRole" not in str(out)
