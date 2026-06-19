"""Unit tests for the resource-edge applier helpers (resource_edges.py).

The full apply_resource_edges path needs the DB (temporary_rdf_storage) and the
embedding service, and is exercised end-to-end by the case-15 commit. These tests
lock the pure / mockable logic: the Agent candidate pool, the batched LLM
multi-select mapping, and provenance idempotency.
"""
from rdflib import Graph, Namespace, RDF, RDFS, Literal

from app.services.extraction import resource_edges as re_
# _agent_pool was consolidated into edge_resolution (re-exported by resource_edges);
# patch _embed on its real home so _agent_pool (which reads edge_resolution._embed) sees it.
from app.services.extraction import edge_resolution as er

CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")
CASE = Namespace("http://proethica.org/ontology/case/15#")


def _agent_graph():
    """Two Agents, one bearing a Role facet, for pool tests."""
    g = Graph()
    g.add((CASE["Agent_Engineer_B"], RDF.type, CORE.Agent))
    g.add((CASE["Agent_Engineer_B"], RDFS.label, Literal("Engineer B")))
    g.add((CASE["Agent_Engineer_B"], CORE.hasRole, CASE["Engineer_B_Peer_Reviewer"]))
    g.add((CASE["Engineer_B_Peer_Reviewer"], RDFS.label, Literal("Engineer B Peer Reviewer")))
    g.add((CASE["Agent_Owner"], RDF.type, CORE.Agent))
    g.add((CASE["Agent_Owner"], RDFS.label, Literal("Owner")))
    return g


def test_agent_pool_includes_label_and_facet(monkeypatch):
    """The pool embeds each Agent's label plus its borne Role facet labels."""
    seen = {}

    def fake_embed(svc, text):
        seen[text] = True
        return [1.0, 0.0]

    monkeypatch.setattr(er, "_embed", fake_embed)
    g = _agent_graph()
    pool = re_._agent_pool(g, None)
    iris = {iri for iri, _t, _e in pool}
    assert CASE["Agent_Engineer_B"] in iris
    assert CASE["Agent_Owner"] in iris
    # Engineer B's matchable text carries both its label and the facet label.
    eng_text = next(t for iri, t, _e in pool if iri == CASE["Agent_Engineer_B"])
    assert "Engineer B" in eng_text and "Peer Reviewer" in eng_text


class _FakeStream:
    def __init__(self, text): self._text = text
    def __enter__(self): return self
    def __exit__(self, *a): return False
    @property
    def text_stream(self): return [self._text]


class _FakeClient:
    def __init__(self, text):
        self.messages = type("M", (), {"stream": lambda _self, **kw: _FakeStream(text)})()


def _items():
    return [
        {"id": 1, "subj": CASE["NSPE_Code"], "desc": "Engineer B and Engineer A",
         "resource_label": "NSPE Code",
         "shortlist": [(CASE["Agent_Engineer_B"], "Engineer B", 0.9),
                       (CASE["Agent_Engineer_A"], "Engineer A", 0.88),
                       (CASE["Agent_Owner"], "Owner", 0.4)]},
        {"id": 2, "subj": CASE["BER_Precedent"], "desc": "NSPE Board of Ethical Review",
         "resource_label": "BER Precedent",
         "shortlist": [(CASE["Agent_Engineer_B"], "Engineer B", 0.45)]},
    ]


def test_llm_select_multi_maps_arrays_and_empty():
    """Multi-select: an array of numbers -> list of IRIs; [] / 'none' -> empty."""
    client = _FakeClient('{"1": [1, 2], "2": []}')
    out = re_._llm_select_multi(_items(), client=client, model="x")
    assert out["1"] == [CASE["Agent_Engineer_B"], CASE["Agent_Engineer_A"]]
    assert out["2"] == []


def test_llm_select_multi_tolerates_bad_choices():
    """Out-of-range / unparseable / bare-number / 'none' values never raise."""
    out = re_._llm_select_multi(_items(), client=_FakeClient('{"1": 1, "2": "none"}'), model="x")
    assert out["1"] == [CASE["Agent_Engineer_B"]]   # bare number coerced to [number]
    assert out["2"] == []
    out2 = re_._llm_select_multi(_items(), client=_FakeClient('{"1": [9, "x"], "2": [1]}'), model="x")
    assert out2["1"] == []                           # 9 out of range, "x" unparseable
    assert out2["2"] == [CASE["Agent_Engineer_B"]]


def test_llm_select_multi_none_without_streaming_client():
    # a client without messages.stream -> None (caller falls back to embedding)
    assert re_._llm_select_multi(_items(), client=object(), model="x") is None


def test_emit_prov_idempotent():
    """The resource-edge prov node is deterministic from (subj, availableTo, obj); a
    second emission must not duplicate the node or multi-value its fields."""
    g = Graph()
    s, o = CASE["NSPE_Code"], CASE["Agent_Engineer_B"]
    re_._emit_prov(g, 15, s, o, "Engineer B and Engineer A")
    re_._emit_prov(g, 15, s, o, "Engineer B and Engineer A")
    provs = [x for x in g.subjects(RDF.type, PROV.Derivation) if "resource_edge_provenance" in str(x)]
    assert len(provs) == 1, provs
    assert len(list(g.objects(provs[0], PROV.value))) == 1
    assert (provs[0], PROV.wasDerivedFrom, s) in g
    assert (provs[0], PROV.wasDerivedFrom, o) in g
