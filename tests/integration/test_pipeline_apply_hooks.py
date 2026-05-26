"""Integration tests for the A2/A3 apply services (study-corrections).

Both are the shared logic behind a live pipeline hook and a corpus backfill
driver. The extractors are faked so the tests are deterministic and make no
LLM call.

  * A3: apply_obligation_engagement -> re-partition Action obligations into
        fulfills/violates/raises.
  * A2: apply_board_conclusions -> synthesize conclusions for unanswered
        board questions, deduped against existing labels.
"""
import pytest

from app import db
from app.models.world import World
from app.models.document import Document
from app.models.document_section import DocumentSection
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.extraction.schemas import (
    PerActionEngagement,
    ObligationEngagementResult,
    BoardConclusionForQuestion,
    BoardConclusionExtractionResult,
)
from app.services.extraction.obligation_engagement_apply import apply_obligation_engagement
from app.services.extraction.board_conclusions_apply import apply_board_conclusions


def _seed_case(case_id):
    world = World.query.first() or World(name="Test World")
    if world.id is None:
        db.session.add(world)
        db.session.flush()
    if not Document.query.get(case_id):
        db.session.add(Document(id=case_id, title=f"Case {case_id}",
                                document_type="case", world_id=world.id))
    db.session.commit()
    return world


# --------------------------------------------------------------------------- A3
class _FakeEngagementExtractor:
    def __init__(self, per_action):
        self._per_action = per_action
        self.calls = 0

    def extract(self, case_id, case_title, actions, discussion_excerpt=""):
        self.calls += 1
        return ObligationEngagementResult(actions=self._per_action, rationale="fake")


def _action_row(case_id, frag, fulfills, violates, seq):
    iri = f"http://proethica.org/cases/{case_id}#{frag}"
    return TemporaryRDFStorage(
        case_id=case_id, extraction_session_id="t", storage_type="individual",
        extraction_type="temporal_dynamics_enhanced", entity_label=frag,
        rdf_json_ld={"@id": iri, "@type": "proeth:Action", "rdfs:label": frag,
                     "proeth:description": "", "proeth:temporalSequence": seq,
                     "proeth:fulfillsObligation": fulfills,
                     "proeth:violatesObligation": violates},
    ), iri


def test_obligation_engagement_repartitions(app_context):
    case_id = 9101
    _seed_case(case_id)
    r1, iri1 = _action_row(case_id, "Action_A", ["O1", "O2"], [], 1)
    db.session.add(r1)
    db.session.commit()

    # Fake moves O2 from fulfills -> raises, keeps O1 fulfilled.
    pa = PerActionEngagement(action_iri=iri1, fulfills=["O1"], violates=[], raises=["O2"])
    result = apply_obligation_engagement(case_id, extractor=_FakeEngagementExtractor([pa]))

    assert result["status"] == "ok"
    assert result["rows_updated"] == 1
    assert result["raises_emitted"] == 1
    assert result["moved_from_fulfills"] == 1
    row = TemporaryRDFStorage.query.filter_by(case_id=case_id).first()
    rdf = row.rdf_json_ld
    assert rdf["proeth:fulfillsObligation"] == ["O1"]
    assert rdf["proeth:raisesObligation"] == ["O2"]


def test_obligation_engagement_no_actions_skips_llm(app_context):
    case_id = 9102
    _seed_case(case_id)
    # An action with no obligations is skipped; no engageable actions remain.
    r1, _ = _action_row(case_id, "Action_A", [], [], 1)
    db.session.add(r1)
    db.session.commit()

    extractor = _FakeEngagementExtractor([])
    result = apply_obligation_engagement(case_id, extractor=extractor)
    assert result["status"] == "no_actions"
    assert extractor.calls == 0


# --------------------------------------------------------------------------- A2
class _FakeBoardExtractor:
    def __init__(self, conclusions):
        self._conclusions = conclusions
        self.calls = 0

    def extract(self, case_id, case_title, gaps, discussion_text, conclusion_text=""):
        self.calls += 1
        return BoardConclusionExtractionResult(conclusions=self._conclusions)


def _question_row(case_id, n):
    return TemporaryRDFStorage(
        case_id=case_id, extraction_session_id="t", storage_type="individual",
        extraction_type="ethical_question", entity_label=f"Question_{n}",
        entity_definition=f"Board question {n}?", is_published=True,
        rdf_json_ld={"questionType": "board_explicit"},
    )


def test_board_conclusion_fills_gap(app_context):
    case_id = 9201
    _seed_case(case_id)
    db.session.add(_question_row(case_id, 1))
    db.session.add(DocumentSection(document_id=case_id, section_id="discussion",
                                   section_type="discussion", content="Discussion body."))
    db.session.commit()

    concl = BoardConclusionForQuestion(question_number=1,
                                       conclusion_text="The Board concludes yes.",
                                       cited_provisions=["I.1"])
    result = apply_board_conclusions(case_id, extractor=_FakeBoardExtractor([concl]))

    assert result["status"] == "ok"
    assert result["rows_inserted"] == 1
    new = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="ethical_conclusion", entity_label="Conclusion_1").first()
    assert new is not None
    assert new.rdf_json_ld["answersQuestions"] == [1]


def test_board_conclusion_no_gaps_when_answered(app_context):
    case_id = 9202
    _seed_case(case_id)
    db.session.add(_question_row(case_id, 1))
    db.session.add(TemporaryRDFStorage(
        case_id=case_id, extraction_session_id="t", storage_type="individual",
        extraction_type="ethical_conclusion", entity_label="Conclusion_1", is_published=True,
        rdf_json_ld={"answersQuestions": [1]}))
    db.session.commit()

    extractor = _FakeBoardExtractor([])
    result = apply_board_conclusions(case_id, extractor=extractor)
    assert result["status"] == "no_gaps"
    assert extractor.calls == 0


def test_board_conclusion_dedupes_existing_label(app_context):
    case_id = 9203
    _seed_case(case_id)
    # Gap exists (Question_1 has no PRIMARY conclusion: existing Conclusion_1
    # answers a different question), but a row labeled Conclusion_1 already
    # exists -> the synthesized row must be skipped as a label collision.
    db.session.add(_question_row(case_id, 1))
    db.session.add(TemporaryRDFStorage(
        case_id=case_id, extraction_session_id="t", storage_type="individual",
        extraction_type="ethical_conclusion", entity_label="Conclusion_1", is_published=True,
        rdf_json_ld={"answersQuestions": [2]}))
    db.session.add(DocumentSection(document_id=case_id, section_id="discussion",
                                   section_type="discussion", content="Discussion body."))
    db.session.commit()

    concl = BoardConclusionForQuestion(question_number=1, conclusion_text="x", cited_provisions=[])
    result = apply_board_conclusions(case_id, extractor=_FakeBoardExtractor([concl]))
    assert result["status"] == "ok"
    assert result["rows_inserted"] == 0
    assert "Conclusion_1" in result["skipped_label_collisions"]
