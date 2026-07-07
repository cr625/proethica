"""Dynamic cross-case defeasibility band: pairwise ranking and selection.

These cover get_cross_case_band_dynamic with the DB index and embedding service
mocked, so the pairwise scoring (0.7 * mean of winner/loser label cosines +
0.3 * joined-context cosine), the MIN_BAND_SCORE floor, the legacy-row skip,
best-per-case dedup, and the top-5 cap are verified deterministically. Index
population (refresh_band_index, including the fresh-marker detection) is
exercised end-to-end by the backfill script.
"""
from unittest.mock import patch, MagicMock

import pytest

from app.services import defeasibility_view_service as svc


def test_cosine_basic():
    assert svc._cosine([1, 0, 0], [1, 0, 0]) == 1.0
    assert svc._cosine([1, 0, 0], [0, 1, 0]) == 0.0
    assert svc._cosine([0, 0, 0], [1, 0, 0]) == 0.0  # zero vector -> 0, no error


def test_context_text_sorted_joined():
    assert svc._context_text(["B State", "A State"]) == "A State; B State"
    assert svc._context_text([]) is None


class _Row:
    def __init__(self, case_id, winner, loser, winner_emb, loser_emb,
                 ctx=(), ctx_emb=None, fresh=True):
        self.case_id = case_id
        self.winner_label = winner
        self.loser_label = loser
        self.winner_embedding = winner_emb
        self.loser_embedding = loser_emb
        self.context_labels = list(ctx)
        self.context_embedding = ctx_emb
        self.fresh = fresh


class _Doc:
    def __init__(self, cid):
        self.title = f"Case {cid} title"
        self.doc_metadata = {"case_number": f"{cid}-1"}


# Anchor vocabulary: winner along x, loser along y, joined contexts along z.
_ANCHOR_VOCAB = {
    "W": [1.0, 0.0, 0.0],
    "L": [0.0, 1.0, 0.0],
    "C1; C2": [0.0, 0.0, 1.0],
}
_ANCHOR = {"winner": "W", "loser": "L", "contexts": ["C2", "C1"], "featured": True}


def _run(rows, anchor_featured=_ANCHOR, vocab=None):
    vocab = vocab or _ANCHOR_VOCAB
    emb_inst = MagicMock()
    emb_inst.get_embedding.side_effect = lambda text: vocab[text]
    embedding_service = MagicMock()
    embedding_service.get_instance.return_value = emb_inst

    band_index = MagicMock()
    band_index.query.filter.return_value.all.return_value = rows

    document = MagicMock()
    document.query.get.side_effect = lambda cid: _Doc(cid)

    case_data = {"conflicts": [anchor_featured]}
    with patch('app.services.embedding.embedding_service.EmbeddingService', embedding_service), \
            patch('app.models.defeasibility_band_index.DefeasibilityBandIndex', band_index), \
            patch('app.models.Document', document):
        return svc.get_cross_case_band_dynamic(7, case_data)


def test_band_score_pairwise_formula():
    anchor_vecs = {"winner": [1, 0, 0], "loser": [0, 1, 0], "context": [0, 0, 1]}
    row = _Row(10, "w", "l", [0.8, 0.6, 0.0], [0.6, 0.8, 0.0], ctx=["c"], ctx_emb=[0, 0, 1])
    # pair = 0.5*0.8 + 0.5*0.8 = 0.8; ctx = 1.0 -> 0.7*0.8 + 0.3*1.0 = 0.86
    assert svc._band_score(anchor_vecs, row) == pytest.approx(0.86)
    # No context on either side -> the context term contributes 0.
    row_no_ctx = _Row(10, "w", "l", [0.8, 0.6, 0.0], [0.6, 0.8, 0.0])
    assert svc._band_score(anchor_vecs, row_no_ctx) == pytest.approx(0.56)
    assert svc._band_score({**anchor_vecs, "context": None}, row) == pytest.approx(0.56)
    # Rows predating the pairwise columns are unrankable.
    legacy = _Row(11, "w", "l", None, [0.6, 0.8, 0.0])
    assert svc._band_score(anchor_vecs, legacy) is None


def test_ranks_pairwise_and_applies_floor():
    rows = [
        # Identical tension + context -> 1.0.
        _Row(10, "Wa", "La", [1, 0, 0], [0, 1, 0], ctx=["C"], ctx_emb=[0, 0, 1]),
        # Pair cosines 0.8 each, no contexts -> 0.56 (above floor).
        _Row(11, "Wb", "Lb", [0.8, 0.6, 0], [0.6, 0.8, 0]),
        # Orthogonal everything -> 0.0 (below floor; excluded).
        _Row(12, "Wc", "Lc", [0, 0, 1], [0, 0, 1]),
    ]
    band = _run(rows)
    assert band is not None
    assert band["dynamic"] is True
    assert band["label"] == "L yields to W"
    assert band["floor"] == svc.MIN_BAND_SCORE
    assert [r["case_id"] for r in band["rows"]] == [10, 11]
    assert band["rows"][0]["score"] == 1.0


def test_legacy_rows_without_pairwise_columns_are_skipped():
    rows = [_Row(12, "Wc", "Lc", None, [0, 1, 0])]  # perfect loser cosine, no winner emb
    band = _run(rows)
    assert band is not None
    assert band["rows"] == []


def test_empty_rows_when_all_below_floor():
    # Candidates exist, so a band is returned (the view renders the no-match
    # message), but nothing clears the floor.
    rows = [_Row(12, "Wc", "Lc", [0, 0, 1], [0, 0, 1])]
    band = _run(rows)
    assert band is not None
    assert band["rows"] == []
    assert band["label"] == "L yields to W"


def test_best_pattern_per_case_and_top_five_cap():
    # Case 10 appears twice; the higher-scoring pattern must represent it (Lb is
    # parallel to the anchor loser, La is not). Seven distinct cases, six fillers
    # scoring 0.56 -> only the top five returned.
    rows = [_Row(10, "Wa", "La", [1, 0, 0], [1, 0, 0]),
            _Row(10, "Wb", "Lb", [1, 0, 0], [0, 1, 0])]
    rows += [_Row(20 + i, f"W{i}", f"L{i}", [0.8, 0.6, 0], [0.6, 0.8, 0]) for i in range(6)]
    band = _run(rows)
    assert len(band["rows"]) == 5
    top = band["rows"][0]
    assert top["case_id"] == 10
    assert top["matches"][0]["loser"] == "Lb"


def test_none_when_no_conflict_or_empty_index():
    assert _run([]) is None
    assert svc.get_cross_case_band_dynamic(7, {"conflicts": []}) is None
