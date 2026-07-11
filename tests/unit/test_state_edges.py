"""Unit tests for the state-edge applier helpers (state_edges.py).

The full apply_state_edges path needs the DB (temporary_rdf_storage) and the
embedding service, and is exercised end-to-end by the case-15 commit. These tests
lock the pure / mockable logic: cosine, normalization, embedding-threshold
resolution, and provenance idempotency.
"""
from rdflib import Graph, Namespace, RDF, RDFS, Literal

from app.services.extraction import state_edges as se
# The embedding / shortlist / resolve primitives were consolidated into
# edge_resolution (re-exported by state_edges). Patch _embed on its real home so the
# functions under test (which read edge_resolution._embed) see the stub.
from app.services.extraction import edge_resolution as er

CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")
CASE = Namespace("http://proethica.org/ontology/case/15#")


def test_cosine_and_norm():
    assert se._cosine([1, 0, 0], [1, 0, 0]) == 1.0
    assert se._cosine([1, 0], [0, 1]) == 0.0
    assert se._cosine([], [1]) == 0.0
    assert se._norm("  Design_Error-Discovered  STATE ") == "design error discovered state"
    # CamelCase split (states NEW-1): the CamelCase and spaced spellings of a
    # state class label must key to the same class.
    assert se._norm("EthicalDilemmaState") == se._norm("Ethical Dilemma State")


def test_resolve_picks_best_above_threshold(monkeypatch):
    """_resolve returns the closest pool member only when it clears the threshold."""
    vecs = {
        "commission independent review": [1.0, 0.0],
        "notify affected parties": [0.0, 1.0],
        # query close to the first candidate
        "obligation to commission a review of related work": [0.96, 0.28],
    }
    monkeypatch.setattr(er, "_embed", lambda svc, t: vecs.get(t))
    pool = [
        (CASE["Obl_Review"], "commission independent review", vecs["commission independent review"]),
        (CASE["Obl_Notify"], "notify affected parties", vecs["notify affected parties"]),
    ]
    tgt, sim = se._resolve(None, "obligation to commission a review of related work", pool, 0.45)
    assert tgt == CASE["Obl_Review"], (tgt, sim)
    # An unrelated query (orthogonal) clears nothing -> None, still no exception.
    monkeypatch.setattr(er, "_embed", lambda svc, t: [0.0, 0.0, 1.0] if "unrelated" in t else None)
    pool2 = [(CASE["X"], "x", [1.0, 0.0, 0.0])]
    tgt2, sim2 = se._resolve(None, "totally unrelated thing", pool2, 0.45)
    assert tgt2 is None


def test_shortlist_topk_above_floor(monkeypatch):
    vecs = {"q": [1.0, 0.0], "a": [0.99, 0.1], "b": [0.6, 0.8], "c": [0.0, 1.0]}
    monkeypatch.setattr(er, "_embed", lambda svc, t: vecs.get(t))
    pool = [(CASE["A"], "a", vecs["a"]), (CASE["B"], "b", vecs["b"]), (CASE["C"], "c", vecs["c"])]
    sl = se._shortlist(None, "q", pool, floor=0.5, k=2)
    assert [iri for iri, _l, _s in sl] == [CASE["A"], CASE["B"]]  # top-2 above floor, best first
    # the orthogonal candidate (c, sim 0.0) is below floor and excluded
    assert all(s >= 0.5 for _i, _l, s in sl)


class _FakeStream:
    def __init__(self, text): self._text = text
    def __enter__(self): return self
    def __exit__(self, *a): return False
    @property
    def text_stream(self): return [self._text]


class _FakeClient:
    def __init__(self, text):
        self.messages = type("M", (), {"stream": lambda _self, **kw: _FakeStream(text)})()


def test_llm_select_maps_numbers_to_iris_and_none():
    items = [
        {"id": 1, "prop": "activatesObligation", "subj": CASE["S"], "desc": "d1",
         "shortlist": [(CASE["O1"], "o1", 0.6), (CASE["O2"], "o2", 0.5)]},
        {"id": 2, "prop": "terminatedByEvent", "subj": CASE["S"], "desc": "d2",
         "shortlist": [(CASE["E1"], "e1", 0.55)]},
    ]
    client = _FakeClient('{"1": 2, "2": "none"}')
    out = se._llm_select(items, client=client, model="x")
    assert out == {"1": CASE["O2"], "2": None}
    # out-of-range / unparseable choices resolve to None, never an exception
    out2 = se._llm_select(items, client=_FakeClient('{"1": 9, "2": "garbage"}'), model="x")
    assert out2 == {"1": None, "2": None}


def test_llm_select_returns_none_without_streaming_client():
    # a client without messages.stream -> None (caller falls back to embedding)
    assert se._llm_select([{"id": 1, "prop": "activatesObligation", "subj": CASE["S"],
                            "desc": "d", "shortlist": [(CASE["O1"], "o1", 0.6)]}],
                           client=object(), model="x") is None


# --- run-21 F2b regression suite: batched select anomalies ------------------
# Run 21 sent 34 shortlisted items in one call and got None for all 34; an
# identical-prompt replay on the identical model resolved 28/34 three times
# over. The select layer now retries an all-none batch (>= 5 items) once and
# then hands control to the caller's calibrated embedding fallback, and
# tolerates the format drifts that were previously silent Nones.

class _SeqClient:
    """Fake Anthropic client returning queued responses across successive
    stream() calls (the last response repeats if the queue empties)."""
    def __init__(self, *texts):
        self._texts = list(texts)
        self.calls = 0
        outer = self

        class _M:
            def stream(_self, **_kw):
                outer.calls += 1
                text = outer._texts.pop(0) if len(outer._texts) > 1 else outer._texts[0]
                return _FakeStream(text)
        self.messages = _M()


def _mk_items(n, prop="activatedByEvent"):
    """n items, each with a 2-deep shortlist (E<i>a, E<i>b)."""
    return [
        {"id": i + 1, "prop": prop, "subj": CASE["S"], "desc": f"description {i + 1}",
         "shortlist": [(CASE[f"E{i + 1}a"], f"event {i + 1} alpha", 0.55),
                       (CASE[f"E{i + 1}b"], f"event {i + 1} beta", 0.45)]}
        for i in range(n)
    ]


def _allnone_json(n):
    """Run 21's zero-yield selection shape: every request id mapped to "none"."""
    return "{" + ", ".join(f'"{i}": "none"' for i in range(1, n + 1)) + "}"


def test_llm_select_unanimous_allnone_accepted_under_voting():
    """The 2026-07-11 calibration: state_edges votes 3x on the default tier,
    and a UNANIMOUS all-none majority is accepted as the answer -- three
    independent judgments already guard the one-flaky-call case the
    single-vote retry existed for, and overriding them with embedding
    thresholds would undo the precision layer."""
    items = _mk_items(6)
    client = _SeqClient(_allnone_json(6))
    out = se._llm_select(items, client=client, model="x")
    assert out == {str(i): None for i in range(1, 7)}
    assert client.calls == 3


def test_llm_select_majority_recovers_from_one_anomalous_vote():
    """One anomalous all-none vote against two healthy votes: the per-item
    majority keeps the healthy picks, so the run-to-run flip the single call
    suffered (the pilot's 2->0 repeat) can no longer zero the family."""
    items = _mk_items(6)
    healthy = '{"1": 1, "2": 2, "3": 1, "4": 1, "5": "none", "6": 2}'
    client = _SeqClient(_allnone_json(6), healthy, healthy)
    out = se._llm_select(items, client=client, model="x")
    assert client.calls == 3
    assert out["1"] == CASE["E1a"]
    assert out["2"] == CASE["E2b"]
    assert out["5"] is None
    assert sum(1 for v in out.values() if v is not None) == 5


def test_llm_select_small_allnone_is_a_judgment():
    """A small all-none batch stays an accepted judgment under voting."""
    items = _mk_items(2)
    client = _SeqClient(_allnone_json(2))
    out = se._llm_select(items, client=client, model="x")
    assert out == {"1": None, "2": None}
    assert client.calls == 3


def test_llm_select_unwraps_single_key_wrapper():
    """A {"selections": {...}} wrapper previously mapped to {} (indistinguishable
    from all-none); it is unwrapped on every vote."""
    items = _mk_items(6)
    wrapped = ('{"selections": {"1": 1, "2": "none", "3": 2, "4": 1, "5": 1, "6": 1}}')
    client = _SeqClient(wrapped)
    out = se._llm_select(items, client=client, model="x")
    assert client.calls == 3
    assert out["1"] == CASE["E1a"]
    assert out["2"] is None
    assert out["3"] == CASE["E3b"]


def test_generic_single_vote_keeps_run21_allnone_semantics():
    """Every OTHER caller of the shared driver stays on votes=1, whose run-21
    contract is unchanged: a large all-none batch is retried once then handed
    to the embedding fallback (None); a small all-none batch is an accepted
    judgment on the first call."""
    items = _mk_items(6)
    client = _SeqClient(_allnone_json(6))
    out = er._llm_select(items, se._build_select_prompt, client=client, model="x")
    assert out is None
    assert client.calls == 2

    small = _mk_items(2)
    client2 = _SeqClient(_allnone_json(2))
    out2 = er._llm_select(small, se._build_select_prompt, client=client2, model="x")
    assert out2 == {"1": None, "2": None}
    assert client2.calls == 1


def test_llm_select_coerces_numeric_strings_floats_and_labels():
    """Numeric strings, integral floats, and a candidate label echoed back all
    resolve; previously each was a silent None."""
    items = _mk_items(3)
    resp = '{"1": "2", "2": 1.0, "3": "Event 3 Beta"}'
    out = se._llm_select(items, client=_SeqClient(resp), model="x")
    assert out["1"] == CASE["E1b"]     # numeric string
    assert out["2"] == CASE["E2a"]     # integral float
    assert out["3"] == CASE["E3b"]     # label matched case-insensitively


def test_llm_select_warns_on_unrecognized_values(caplog):
    """Unrecognized shapes still resolve to None (never raise) but now leave a
    WARNING trail instead of being silently coerced."""
    import logging
    items = _mk_items(2)
    resp = '{"1": {"choice": 1}, "2": 9, "99": 1}'
    with caplog.at_level(logging.WARNING,
                         logger="app.services.extraction.edge_resolution"):
        out = se._llm_select(items, client=_SeqClient(resp), model="x")
    assert out == {"1": None, "2": None}
    messages = [r.getMessage() for r in caplog.records]
    assert any("unrecognized value type" in m for m in messages)   # dict value
    assert any("out-of-range" in m for m in messages)              # 9 of 2
    assert any("matching no request id" in m for m in messages)    # key "99"


def test_emit_prov_idempotent():
    """The state-edge prov node is deterministic from (subj, prop, obj); a second
    emission must not duplicate the node or multi-value its fields."""
    g = Graph()
    s, o = CASE["State_A"], CASE["Obl_B"]
    se._emit_prov(g, 15, s, "activatesObligation", o, "some description")
    se._emit_prov(g, 15, s, "activatesObligation", o, "some description")
    provs = [x for x in g.subjects(RDF.type, PROV.Derivation) if "state_edge_provenance" in str(x)]
    assert len(provs) == 1, provs
    assert len(list(g.objects(provs[0], PROV.value))) == 1
    assert (provs[0], PROV.wasDerivedFrom, s) in g
    assert (provs[0], PROV.wasDerivedFrom, o) in g
