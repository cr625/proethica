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
