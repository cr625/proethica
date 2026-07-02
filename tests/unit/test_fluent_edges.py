"""Unit tests for the fluent-transition family spec (edge_spec._FLUENT_SPEC) and the
converter emission that feeds it.

The Action/Event initiates|terminates State edges are materialised by the data-driven
framework; these tests lock the family DATA (the two predicates, the union subject pool
guard, the per-predicate prompt wording) and the rdf_converter emission of initiates /
terminates / temporalExtent that the framework reads. The full materialize_edge_family
path is exercised by tests/unit/test_edge_spec_equivalence.py under a mocked resolver.
"""
from rdflib import Namespace

from app.services.extraction import edge_spec as es
from app.services.extraction.rpo_edges import ALL_EDGE_RANGE
from app.services.temporal_dynamics.utils.rdf_converter import (
    convert_action_to_rdf, convert_event_to_rdf,
)

CORE = Namespace("http://proethica.org/ontology/core#")
CASE = Namespace("http://proethica.org/ontology/case/15#")


def _items():
    return [
        {"id": 1, "desc": "Public Safety Risk; Project Suspended",
         "subj_label": "Risk Discovery",
         "shortlist": [(CASE["Public_Safety_Risk"], "Public Safety Risk", 0.9),
                       (CASE["Project_Suspended"], "Project Suspended", 0.85),
                       (CASE["Unrelated_State"], "Unrelated State", 0.3)]},
    ]


def test_specs_are_initiates_and_terminates():
    props = [p.prop for p in es._FLUENT_SPEC.predicates]
    assert props == ["initiates", "terminates"]


def test_fluent_edges_guarded_as_happening_to_state():
    """Both fluent props must be in ALL_EDGE_RANGE with the union subject {Action,Event}
    and object State, so the unified guard validates them."""
    for prop in ("initiates", "terminates"):
        sub, obj = ALL_EDGE_RANGE[CORE[prop]]
        assert obj == "State", (prop, obj)
        assert sub == {"Action", "Event"}, (prop, sub)


def test_prompt_wording_distinguishes_initiates_from_terminates():
    by_prop = {p.prop: p for p in es._FLUENT_SPEC.predicates}
    p_init = es._fluent_prompt_factory(by_prop["initiates"], es._FLUENT_SPEC)(_items())
    assert "INITIATES" in p_init
    assert "candidate states" in p_init.lower()
    assert "Public Safety Risk" in p_init  # the state text is included verbatim
    p_term = es._fluent_prompt_factory(by_prop["terminates"], es._FLUENT_SPEC)(_items())
    assert "TERMINATES" in p_term


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


def test_event_converter_emits_text_references_and_confidence():
    """Stage-2 audit convergence: events must carry verbatim grounding + confidence to temp
    storage under the same proeth:textReferences key the commit serializer routes for the
    pass-1/2 components (events committed with zero textReference in both case-7 runs)."""
    event = {
        "label": "Structural Failure", "temporal_marker": "Month 5",
        "text_references": ["a critical structural flaw was found", "  ", ""],
        "confidence": 0.92,
    }
    erdf = convert_event_to_rdf(event, 15)
    assert erdf["proeth:textReferences"] == ["a critical structural flaw was found"]
    # Plain string literal, not float: proeth:confidence declares rdfs:range xsd:string, and
    # a float serializes as xsd:double at commit (made the run-17 commit Pellet-inconsistent).
    assert erdf["proeth:confidence"] == "0.92"

    # Absent / empty grounding fields are not emitted; a bool confidence is rejected.
    bare = convert_event_to_rdf({"label": "Permit Denial", "confidence": True}, 15)
    assert "proeth:textReferences" not in bare
    assert "proeth:confidence" not in bare

    # A single-string text_references (model drift) is normalized to a one-item list.
    single = convert_event_to_rdf(
        {"label": "Permit Denial", "text_references": "the permit was denied"}, 15)
    assert single["proeth:textReferences"] == ["the permit was denied"]


def test_action_converter_emits_text_references():
    """Stage-3 action grounding parity: the action converter stores verbatim grounding at
    the top level of the action's rdf_json_ld under the same proeth:textReferences key as
    the event path (shared _add_text_references helper), trimmed and with single-string
    model drift normalized to a one-item list."""
    action = {
        "label": "Task Assignment", "agent": "Engineer A", "temporal_marker": "Month 3",
        "text_references": ["assigned the complex bridge analysis to the intern", "  ", ""],
    }
    rdf = convert_action_to_rdf(action, 15)
    assert rdf["proeth:textReferences"] == ["assigned the complex bridge analysis to the intern"]

    # Absent / empty grounding is not emitted.
    bare = convert_action_to_rdf({"label": "Report Sealing", "agent": "Engineer B"}, 15)
    assert "proeth:textReferences" not in bare

    # A single-string text_references (model drift) is normalized to a one-item list.
    single = convert_action_to_rdf(
        {"label": "Report Sealing", "agent": "Engineer B",
         "text_references": "the engineer sealed the report"}, 15)
    assert single["proeth:textReferences"] == ["the engineer sealed the report"]
