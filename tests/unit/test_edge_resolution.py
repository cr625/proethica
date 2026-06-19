"""Unit tests for the shared edge-resolution primitives (edge_resolution.py).

These lock the pure / mockable logic the data-driven edge framework relies on: the
Agent candidate pool, the batched LLM multi-select mapping, and PROV-O idempotency.
The helpers were consolidated here from the (now-deleted) per-family appliers; the
full materialize_edge_family path is exercised end-to-end by the case-15 commit and
by tests/unit/test_edge_spec_equivalence.py under a mocked resolver.
"""
from rdflib import Graph, Namespace, RDF, RDFS, Literal

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
    pool = er._agent_pool(g, None)
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
    out = er._llm_select_multi(_items(), client=client, model="x")
    assert out["1"] == [CASE["Agent_Engineer_B"], CASE["Agent_Engineer_A"]]
    assert out["2"] == []


def test_llm_select_multi_tolerates_bad_choices():
    """Out-of-range / unparseable / bare-number / 'none' values never raise."""
    out = er._llm_select_multi(_items(), client=_FakeClient('{"1": 1, "2": "none"}'), model="x")
    assert out["1"] == [CASE["Agent_Engineer_B"]]   # bare number coerced to [number]
    assert out["2"] == []
    out2 = er._llm_select_multi(_items(), client=_FakeClient('{"1": [9, "x"], "2": [1]}'), model="x")
    assert out2["1"] == []                           # 9 out of range, "x" unparseable
    assert out2["2"] == [CASE["Agent_Engineer_B"]]


def test_llm_select_multi_none_without_streaming_client():
    # a client without messages.stream -> None (caller falls back to embedding)
    assert er._llm_select_multi(_items(), client=object(), model="x") is None


def test_emit_edge_prov_idempotent_and_property_scoped():
    """emit_edge_prov is deterministic from (prefix, prop, subj, obj); a second emission
    must not duplicate the node or multi-value its fields, and two different properties
    between the same pair get distinct nodes."""
    g = Graph()
    s, o = CASE["NSPE_Code"], CASE["Agent_Engineer_B"]
    args = (g, 15, "resource_edge_provenance_", "availableTo", s, o,
            "Engineer B and Engineer A", "Resource edge (availableTo)", "comment")
    er.emit_edge_prov(*args)
    er.emit_edge_prov(*args)
    provs = [x for x in g.subjects(RDF.type, PROV.Derivation) if "resource_edge_provenance" in str(x)]
    assert len(provs) == 1, provs
    assert len(list(g.objects(provs[0], PROV.value))) == 1
    assert (provs[0], PROV.wasDerivedFrom, s) in g
    assert (provs[0], PROV.wasDerivedFrom, o) in g
    # A different property between the same pair is a distinct node.
    er.emit_edge_prov(g, 15, "resource_edge_provenance_", "otherProp", s, o,
                      "desc", "label", "comment")
    assert len([x for x in g.subjects(RDF.type, PROV.Derivation)
                if "resource_edge_provenance" in str(x)]) == 2


def test_emit_edge_prov_omits_value_when_desc_empty():
    """An empty desc yields no prov:value triple (matches the historical emitter)."""
    g = Graph()
    er.emit_edge_prov(g, 15, "state_affects_provenance_", "affects",
                      CASE["State"], CASE["Agent_Owner"], "", "State edge (affects)", "comment")
    prov = next(iter(g.subjects(RDF.type, PROV.Derivation)))
    assert list(g.objects(prov, PROV.value)) == []
