"""Integration tests for apply_temporal_sequence (study-corrections A1).

Exercises the shared service that both the live Step-3 pipeline hook and the
corpus backfill driver call. The TemporalSequenceExtractor is replaced with a
fake so the test is deterministic and makes no LLM call.
"""
import pytest

from app import db
from app.models.world import World
from app.models.document import Document
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.extraction.temporal_sequence import TemporalSequenceResult
from app.services.extraction.temporal_sequence_apply import apply_temporal_sequence


class _FakeExtractor:
    """Returns a caller-supplied IRI order; records that it was called."""

    def __init__(self, ordered_iris):
        self._ordered = ordered_iris
        self.calls = 0

    def extract(self, case_id, entries):
        self.calls += 1
        return TemporalSequenceResult(ordered_iris=list(self._ordered), rationale="fake")


def _mk_row(case_id, frag, at_type, label):
    iri = f"http://proethica.org/cases/{case_id}#{frag}"
    return TemporaryRDFStorage(
        case_id=case_id,
        extraction_session_id="test-a1",
        storage_type="individual",
        extraction_type="temporal_dynamics_enhanced",
        entity_label=label,
        rdf_json_ld={"@id": iri, "@type": at_type, "rdfs:label": label,
                     "proeth:temporalMarker": "", "proeth:description": ""},
    ), iri


def _seed_case(case_id):
    world = World.query.first() or World(name="Test World")
    if world.id is None:
        db.session.add(world)
        db.session.flush()
    if not Document.query.get(case_id):
        db.session.add(Document(id=case_id, title=f"Case {case_id}",
                                document_type="case", world_id=world.id))
    db.session.commit()


def test_applies_sequence_in_extractor_order(app_context):
    case_id = 9001
    _seed_case(case_id)
    r1, iri1 = _mk_row(case_id, "Action_A", "proeth:Action", "A")
    r2, iri2 = _mk_row(case_id, "Event_B", "proeth:Event", "B")
    r3, iri3 = _mk_row(case_id, "Action_C", "proeth:Action", "C")
    db.session.add_all([r1, r2, r3])
    db.session.commit()

    # Fake says chronological order is C, A, B.
    extractor = _FakeExtractor([iri3, iri1, iri2])
    result = apply_temporal_sequence(case_id, extractor=extractor)

    assert result["status"] == "ok"
    assert result["rows_updated"] == 3
    seqs = {row.entity_label: (row.rdf_json_ld or {}).get("proeth:temporalSequence")
            for row in TemporaryRDFStorage.query.filter_by(case_id=case_id).all()}
    assert seqs == {"C": 1, "A": 2, "B": 3}


def test_idempotent_second_run(app_context):
    case_id = 9002
    _seed_case(case_id)
    r1, iri1 = _mk_row(case_id, "Action_A", "proeth:Action", "A")
    r2, iri2 = _mk_row(case_id, "Action_B", "proeth:Action", "B")
    db.session.add_all([r1, r2])
    db.session.commit()

    extractor = _FakeExtractor([iri1, iri2])
    first = apply_temporal_sequence(case_id, extractor=extractor)
    assert first["rows_updated"] == 2
    second = apply_temporal_sequence(case_id, extractor=extractor)
    assert second["rows_updated"] == 0  # already in place


def test_insufficient_entries_skips_llm(app_context):
    case_id = 9003
    _seed_case(case_id)
    r1, _ = _mk_row(case_id, "Action_A", "proeth:Action", "A")
    db.session.add(r1)
    db.session.commit()

    extractor = _FakeExtractor([])
    result = apply_temporal_sequence(case_id, extractor=extractor)
    assert result["status"] == "insufficient_entries"
    assert extractor.calls == 0


def test_dry_run_skips_llm_and_writes(app_context):
    case_id = 9004
    _seed_case(case_id)
    r1, _ = _mk_row(case_id, "Action_A", "proeth:Action", "A")
    r2, _ = _mk_row(case_id, "Event_B", "proeth:Event", "B")
    db.session.add_all([r1, r2])
    db.session.commit()

    extractor = _FakeExtractor([])
    result = apply_temporal_sequence(case_id, extractor=extractor, dry_run=True)
    assert result["status"] == "dry_run"
    assert extractor.calls == 0
    for row in TemporaryRDFStorage.query.filter_by(case_id=case_id).all():
        assert "proeth:temporalSequence" not in (row.rdf_json_ld or {})
