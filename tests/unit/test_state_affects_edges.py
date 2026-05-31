"""Unit tests for the state-affects applier helpers (state_affects_edges.py).

The full apply_state_affects_edges path needs the DB (temporary_rdf_storage) and the
embedding service, and is exercised end-to-end by the case-15 commit. These tests
lock the mockable logic: the affected-parties prompt builder, the reused multi-select
mapping (via resource_edges._llm_select_multi with the affects prompt builder), and
provenance idempotency.
"""
from rdflib import Graph, Namespace, RDF, RDFS, Literal

from app.services.extraction import state_affects_edges as sa_
from app.services.extraction import resource_edges as re_

CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")
CASE = Namespace("http://proethica.org/ontology/case/15#")


def _items():
    return [
        {"id": 1, "subj": CASE["Defect_State"], "desc": "Owner; Engineer A; future occupants and public",
         "state_label": "Engineer A Design Errors Discovered",
         "shortlist": [(CASE["Agent_Owner"], "Owner", 0.9),
                       (CASE["Agent_Engineer_A"], "Engineer A", 0.88),
                       (CASE["Agent_Engineer_B"], "Engineer B", 0.3)]},
    ]


class _FakeStream:
    def __init__(self, text): self._text = text
    def __enter__(self): return self
    def __exit__(self, *a): return False
    @property
    def text_stream(self): return [self._text]


class _FakeClient:
    def __init__(self, text):
        self.messages = type("M", (), {"stream": lambda _self, **kw: _FakeStream(text)})()


def test_affects_prompt_mentions_state_and_generic_exclusion():
    """The affects prompt asks for the parties a STATE bears on and excludes generic
    groups (which is how 'future occupants and public' yields no edge)."""
    p = sa_._build_affects_prompt(_items())
    assert "STATE" in p
    assert "affected parties" in p.lower()
    assert "future occupants" in p  # the request text is included verbatim
    assert "generic" in p.lower()


def test_multi_select_with_affects_prompt_maps_agents():
    """The affects applier reuses resource_edges._llm_select_multi with its own prompt
    builder; the chosen candidate numbers map to Agent IRIs, [] to none."""
    client = _FakeClient('{"1": [1, 2]}')  # Owner + Engineer A; not the generic group
    out = re_._llm_select_multi(_items(), client=client, model="x",
                                prompt_builder=sa_._build_affects_prompt)
    assert out["1"] == [CASE["Agent_Owner"], CASE["Agent_Engineer_A"]]


def test_emit_prov_idempotent():
    """The state-affects prov node is deterministic from (subj, affects, obj); a
    second emission must not duplicate the node or multi-value its fields."""
    g = Graph()
    s, o = CASE["Defect_State"], CASE["Agent_Owner"]
    sa_._emit_prov(g, 15, s, o, "Owner; Engineer A")
    sa_._emit_prov(g, 15, s, o, "Owner; Engineer A")
    provs = [x for x in g.subjects(RDF.type, PROV.Derivation) if "state_affects_provenance" in str(x)]
    assert len(provs) == 1, provs
    assert len(list(g.objects(provs[0], PROV.value))) == 1
    assert (provs[0], PROV.wasDerivedFrom, s) in g
    assert (provs[0], PROV.wasDerivedFrom, o) in g
