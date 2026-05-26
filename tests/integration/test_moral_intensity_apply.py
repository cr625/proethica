"""Integration tests for apply_moral_intensity (study-corrections A5).

Shared logic behind the live Phase-4 post-pass and the corpus backfill driver.
The MoralIntensityExtractor is faked so the tests are deterministic and make no
LLM call.
"""
import json

import pytest

from app import db
from app.models.extraction_prompt import ExtractionPrompt
from app.services.extraction.moral_intensity import is_rated, MoralIntensityTension
from app.services.extraction.moral_intensity_apply import apply_moral_intensity


class _FakeMIExtractor:
    def __init__(self, ratings_by_id):
        self._ratings = ratings_by_id
        self.calls = 0
        self.seen_ids = None

    def extract(self, case_id, tensions):
        self.calls += 1
        self.seen_ids = [t.conflict_id for t in tensions]
        return self._ratings


def _phase4_row(case_id, conflicts):
    return ExtractionPrompt(
        case_id=case_id, concept_type="phase4_narrative", section_type="discussion",
        step_number=4, prompt_text="p",
        raw_response=json.dumps({"narrative_elements": {"conflicts": conflicts}}),
    )


def test_is_rated_helper():
    assert not is_rated({"entity1_label": "A"})
    assert is_rated({"magnitude_of_consequences": "high"})


def test_rates_only_unrated(app_context):
    case_id = 9301
    conflicts = [
        {"conflict_id": "t1", "entity1_label": "A", "entity2_label": "B"},
        {"conflict_id": "t2", "entity1_label": "C", "entity2_label": "D",
         "magnitude_of_consequences": "high"},  # already rated
    ]
    db.session.add(_phase4_row(case_id, conflicts))
    db.session.commit()

    extractor = _FakeMIExtractor({"t1": {"magnitude_of_consequences": "low",
                                         "proximity": "direct"}})
    stats = apply_moral_intensity(case_id, extractor=extractor)

    assert stats == {"total": 2, "already_rated": 1, "newly_rated": 1, "missed": 0}
    assert extractor.seen_ids == ["t1"]  # only the unrated tension is sent

    row = (ExtractionPrompt.query.filter_by(case_id=case_id, concept_type="phase4_narrative")
           .order_by(ExtractionPrompt.created_at.desc()).first())
    data = json.loads(row.raw_response)
    t1 = next(c for c in data["narrative_elements"]["conflicts"] if c["conflict_id"] == "t1")
    assert t1["magnitude_of_consequences"] == "low"
    assert "moral_intensity_backfilled_at" in data


def test_counts_missed_when_llm_omits(app_context):
    case_id = 9302
    db.session.add(_phase4_row(case_id, [{"conflict_id": "t1", "entity1_label": "A"}]))
    db.session.commit()

    extractor = _FakeMIExtractor({})  # LLM returned no rating for t1
    stats = apply_moral_intensity(case_id, extractor=extractor)
    assert stats["newly_rated"] == 0
    assert stats["missed"] == 1


def test_no_unrated_skips_llm(app_context):
    case_id = 9303
    db.session.add(_phase4_row(case_id, [
        {"conflict_id": "t1", "magnitude_of_consequences": "high"}]))
    db.session.commit()

    extractor = _FakeMIExtractor({"t1": {"proximity": "direct"}})
    stats = apply_moral_intensity(case_id, extractor=extractor)
    assert stats == {"total": 1, "already_rated": 1, "newly_rated": 0, "missed": 0}
    assert extractor.calls == 0


def test_dry_run_skips_llm_and_write(app_context):
    case_id = 9304
    db.session.add(_phase4_row(case_id, [{"conflict_id": "t1", "entity1_label": "A"}]))
    db.session.commit()

    extractor = _FakeMIExtractor({"t1": {"proximity": "direct"}})
    stats = apply_moral_intensity(case_id, extractor=extractor, dry_run=True)
    assert extractor.calls == 0
    assert stats["total"] == 1
    row = (ExtractionPrompt.query.filter_by(case_id=case_id, concept_type="phase4_narrative")
           .order_by(ExtractionPrompt.created_at.desc()).first())
    assert "moral_intensity_backfilled_at" not in json.loads(row.raw_response)


def test_no_phase4_row_returns_empty(app_context):
    stats = apply_moral_intensity(9305, extractor=_FakeMIExtractor({}))
    assert stats == {"total": 0, "already_rated": 0, "newly_rated": 0, "missed": 0}
