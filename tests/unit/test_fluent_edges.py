"""Unit tests for the fluent-transition applier (fluent_edges.py) and the converter
emission that feeds it.

The full apply_fluent_edges path needs the DB (temporary_rdf_storage) + the embedding
service, and is exercised end-to-end by the case-15 commit. These tests lock the mockable
logic: the two fluent specs, the guard-registry coverage (Action/Event union -> State), the
per-property prompt wording, the multi-select mapping, provenance idempotency, and the
rdf_converter emission of initiates / terminates / temporalExtent / hasTime.
"""
from rdflib import Graph, Namespace, RDF, RDFS

from app.services.extraction import fluent_edges as fe_
from app.services.extraction import resource_edges as re_
from app.services.extraction.rpo_edges import ALL_EDGE_RANGE
from app.services.temporal_dynamics.utils.rdf_converter import (
    convert_action_to_rdf, convert_event_to_rdf,
)

CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")
CASE = Namespace("http://proethica.org/ontology/case/15#")


def _items():
    return [
        {"id": 1, "subj": CASE["Event_Risk_Discovery"], "desc": "Public Safety Risk; Project Suspended",
         "subj_label": "Risk Discovery",
         "shortlist": [(CASE["Public_Safety_Risk"], "Public Safety Risk", 0.9),
                       (CASE["Project_Suspended"], "Project Suspended", 0.85),
                       (CASE["Unrelated_State"], "Unrelated State", 0.3)]},
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


def test_specs_are_initiates_and_terminates():
    props = [p for p, _ in fe_._FLUENT_SPECS]
    assert props == ["initiates", "terminates"]


def test_fluent_edges_guarded_as_happening_to_state():
    """Both fluent props must be in ALL_EDGE_RANGE with the union subject {Action,Event}
    and object State, so the unified guard validates them."""
    for prop in ("initiates", "terminates"):
        sub, obj = ALL_EDGE_RANGE[CORE[prop]]
        assert obj == "State", (prop, obj)
        assert sub == {"Action", "Event"}, (prop, sub)


def test_prompt_wording_distinguishes_initiates_from_terminates():
    p_init = fe_._build_fluent_prompt("initiates")(_items())
    assert "INITIATES" in p_init
    assert "candidate states" in p_init.lower()
    assert "Public Safety Risk" in p_init  # the state text is included verbatim
    p_term = fe_._build_fluent_prompt("terminates")(_items())
    assert "TERMINATES" in p_term


def test_multi_select_maps_chosen_states():
    client = _FakeClient('{"1": [1, 2]}')  # both real states, not the unrelated one
    out = re_._llm_select_multi(_items(), client=client, model="x",
                                prompt_builder=fe_._build_fluent_prompt("initiates"))
    assert out["1"] == [CASE["Public_Safety_Risk"], CASE["Project_Suspended"]]


def test_emit_prov_idempotent_and_property_scoped():
    g = Graph()
    s, o = CASE["Event_Risk_Discovery"], CASE["Public_Safety_Risk"]
    fe_._emit_prov(g, 15, "initiates", s, o, "Public Safety Risk")
    fe_._emit_prov(g, 15, "initiates", s, o, "Public Safety Risk")
    provs = [x for x in g.subjects(RDF.type, PROV.Derivation)
             if "fluent_edge_provenance" in str(x) and "initiates" in str(x)]
    assert len(provs) == 1, provs
    assert len(list(g.objects(provs[0], PROV.value))) == 1
    fe_._emit_prov(g, 15, "terminates", s, o, "Public Safety Risk")
    allp = [x for x in g.subjects(RDF.type, PROV.Derivation) if "fluent_edge_provenance" in str(x)]
    assert len(allp) == 2


def test_converter_emits_fluent_and_extent_fields():
    """The action/event converter must carry initiates / terminates (raw label lists) and
    the temporalExtent classification. A nested time:hasTime blank node is intentionally not
    emitted: the commit serializer drops nested-dict values, so it would never land."""
    action = {
        "label": "Risk Disclosure", "agent": "Engineer B", "temporal_marker": "Month 3",
        "initiates": ["Public Safety Risk Disclosed"], "terminates": ["Concealment State"],
        "temporal_extent": "instant",
    }
    rdf = convert_action_to_rdf(action, 15)
    assert rdf["proeth:initiates"] == ["Public Safety Risk Disclosed"]
    assert rdf["proeth:terminates"] == ["Concealment State"]
    assert rdf["proeth:temporalExtent"] == "instant"
    assert "time:hasTime" not in rdf  # nested blank node would be dropped at commit

    event = {
        "label": "Rainfall Event", "temporal_marker": "Month 5",
        "initiates": ["Acute Runoff Risk"], "temporal_extent": "interval",
    }
    erdf = convert_event_to_rdf(event, 15)
    assert erdf["proeth:initiates"] == ["Acute Runoff Risk"]
    assert "proeth:terminates" not in erdf  # empty terminates not emitted
    assert erdf["proeth:temporalExtent"] == "interval"
