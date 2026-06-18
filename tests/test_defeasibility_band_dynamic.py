"""Dynamic cross-case defeasibility band: ranking and selection.

These cover get_cross_case_band_dynamic with the DB index and embedding service
mocked, so the scoring (loser-embedding cosine 0.7 + State Jaccard 0.3),
best-per-case dedup, and top-5 cap are verified deterministically. Index
population (refresh_band_index) is exercised end-to-end by the backfill script.
"""
from unittest.mock import patch, MagicMock

from app.services import defeasibility_view_service as svc


def test_cosine_basic():
    assert svc._cosine([1, 0, 0], [1, 0, 0]) == 1.0
    assert svc._cosine([1, 0, 0], [0, 1, 0]) == 0.0
    assert svc._cosine([0, 0, 0], [1, 0, 0]) == 0.0  # zero vector -> 0, no error


class _Row:
    def __init__(self, case_id, winner, loser, emb, ctx):
        self.case_id = case_id
        self.winner_label = winner
        self.loser_label = loser
        self.loser_embedding = emb
        self.context_labels = ctx


class _Doc:
    def __init__(self, cid):
        self.title = f"Case {cid} title"
        self.doc_metadata = {"case_number": f"{cid}-1"}


def _run(rows, anchor_featured, anchor_vec=(1.0, 0.0, 0.0)):
    emb_inst = MagicMock()
    emb_inst.get_embedding.return_value = list(anchor_vec)
    embedding_service = MagicMock()
    embedding_service.get_instance.return_value = emb_inst

    band_index = MagicMock()
    band_index.query.filter.return_value.all.return_value = rows

    document = MagicMock()
    document.query.get.side_effect = lambda cid: _Doc(cid)

    case_data = {"conflicts": [anchor_featured]}
    with patch('app.services.embedding_service.EmbeddingService', embedding_service), \
            patch('app.models.defeasibility_band_index.DefeasibilityBandIndex', band_index), \
            patch('app.models.Document', document):
        return svc.get_cross_case_band_dynamic(7, case_data)


def test_ranks_by_embedding_and_state_overlap():
    anchor = {"winner": "Public Safety", "loser": "Faithful Agent",
              "contexts": ["RiskState"], "featured": True}
    rows = [
        _Row(10, "WA", "LA", [1.0, 0.0, 0.0], ["RiskState"]),       # cos 1.0, jac 1.0 -> 1.00
        _Row(11, "WB", "LB", [0.0, 1.0, 0.0], ["OtherState"]),      # cos 0.0, jac 0.0 -> 0.00
        _Row(12, "WC", "LC", [0.6, 0.8, 0.0], ["RiskState", "X"]),  # cos 0.6, jac 0.5 -> 0.57
    ]
    band = _run(rows, anchor)
    assert band is not None
    assert band["dynamic"] is True
    assert band["label"] == "Faithful Agent yields to Public Safety"
    order = [r["case_id"] for r in band["rows"]]
    assert order == [10, 12, 11]
    assert band["rows"][0]["score"] == 1.0


def test_best_pattern_per_case_and_top_five_cap():
    anchor = {"winner": "W", "loser": "L", "contexts": [], "featured": True}
    # case 10 appears twice; the higher-scoring row must win (La points away from the
    # anchor -> cos 0; Lb is parallel -> cos 1). Seven distinct cases, six fillers scoring
    # below case 10 -> only the top five returned.
    rows = [_Row(10, "Wa", "La", [0.0, 1.0, 0.0], []),
            _Row(10, "Wb", "Lb", [1.0, 0.0, 0.0], [])]
    rows += [_Row(20 + i, f"W{i}", f"L{i}", [0.8, 0.6, 0.0], []) for i in range(6)]
    band = _run(rows, anchor)
    assert len(band["rows"]) == 5
    top = band["rows"][0]
    assert top["case_id"] == 10
    assert top["matches"][0]["loser"] == "Lb"  # the higher-scoring pattern for case 10


def test_none_when_no_conflict_or_empty_index():
    assert _run([], {"winner": "W", "loser": "L", "contexts": [], "featured": True}) is None
    assert svc.get_cross_case_band_dynamic(7, {"conflicts": []}) is None
