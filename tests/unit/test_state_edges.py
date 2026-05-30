"""Unit tests for the state-edge applier helpers (state_edges.py).

The full apply_state_edges path needs the DB (temporary_rdf_storage) and the
embedding service, and is exercised end-to-end by the case-15 commit. These tests
lock the pure / mockable logic: cosine, normalization, embedding-threshold
resolution, and provenance idempotency.
"""
from rdflib import Graph, Namespace, RDF, RDFS, Literal

from app.services.extraction import state_edges as se

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
    monkeypatch.setattr(se, "_embed", lambda svc, t: vecs.get(t))
    pool = [
        (CASE["Obl_Review"], "commission independent review", vecs["commission independent review"]),
        (CASE["Obl_Notify"], "notify affected parties", vecs["notify affected parties"]),
    ]
    tgt, sim = se._resolve(None, "obligation to commission a review of related work", pool, 0.45)
    assert tgt == CASE["Obl_Review"], (tgt, sim)
    # An unrelated query (orthogonal) clears nothing -> None, still no exception.
    monkeypatch.setattr(se, "_embed", lambda svc, t: [0.0, 0.0, 1.0] if "unrelated" in t else None)
    pool2 = [(CASE["X"], "x", [1.0, 0.0, 0.0])]
    tgt2, sim2 = se._resolve(None, "totally unrelated thing", pool2, 0.45)
    assert tgt2 is None


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
