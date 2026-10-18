"""Principle hints and duplicate principle individuals in the R-P-O pass
(case-8 review, L8).

_derived_from_principle_hints fed an obligation's class-level principle hint
("Transparency Principle") to the extractor, which resolved it to every
same-case individual of that class and emitted two derivedFromPrinciple edges
per duty when a duplicate principle pair existed. A hint now resolves to the
single same-case individual of its class, a duplicate pair is treated as a
merge signal (logged, one edge to the Board-invoked individual when
distinguishable), and the extractor collapses Principle-range duplicates.

DB-free: the prompt template loader is stubbed and the LLM is a mock client.
"""
import json
import logging
from unittest.mock import MagicMock

import pytest
from rdflib import Graph

import app.services.extraction.rpo_edges as rpo
from app.services.extraction.rpo_edges import (
    Indiv, RPOEdgeExtractor, collapse_same_class_principle_edges, gather, resolve_principle_hint,
)

CASE_NS = "http://proethica.org/ontology/case/8#"
ROLE = f"{CASE_NS}Engineer_L_Design_Engineer"
OBL = f"{CASE_NS}Engineer_L_Disclosure_Duty"
P_FACTS = f"{CASE_NS}Transparency_Principle"
P_BOARD = f"{CASE_NS}Transparency_Principle_Discussion"
P_OTHER = f"{CASE_NS}Public_Welfare_Principle"


@pytest.fixture(autouse=True)
def _stub_rpo_template(monkeypatch):
    class _Stub:
        def render(self, **kw):
            return "USER"

        def render_system(self, **kw):
            return "SYSTEM"

    monkeypatch.setattr(rpo, "_load_rpo_template", lambda: _Stub())


def _principles():
    return [
        Indiv(iri=P_FACTS, label="Transparency",
              fields={"principleClass": "TransparencyPrinciple", "invokedBy": "Engineer L"}),
        Indiv(iri=P_BOARD, label="Transparency toward the client",
              fields={"principleClass": "TransparencyPrinciple",
                      "invokedBy": "Engineer L; NSPE Board of Ethical Review"}),
        Indiv(iri=P_OTHER, label="Public welfare paramount",
              fields={"principleClass": "PublicWelfarePrinciple", "invokedBy": "NSPE Board of Ethical Review"}),
    ]


def test_hint_resolves_to_the_single_individual_of_its_class():
    resolved, how = resolve_principle_hint("Public Welfare Principle", _principles())
    assert (resolved.iri, how) == (P_OTHER, "unique")
    # Label-stem and class-local spellings both match.
    assert resolve_principle_hint("public welfare", _principles())[0].iri == P_OTHER
    assert resolve_principle_hint("Nonexistent Principle", _principles()) == (None, "unresolved")
    assert resolve_principle_hint("", _principles()) == (None, "empty")


def test_duplicate_pair_is_a_merge_signal_resolved_to_the_board_invoked_one(caplog):
    with caplog.at_level(logging.WARNING, logger="app.services.extraction.rpo_edges"):
        resolved, how = resolve_principle_hint("Transparency Principle", _principles())
    assert (resolved.iri, how) == (P_BOARD, "board_invoked")
    assert any("merge signal" in r.getMessage() for r in caplog.records)


def test_indistinguishable_duplicates_leave_the_hint_unresolved():
    principles = _principles()
    principles[1].fields["invokedBy"] = "Client X"
    assert resolve_principle_hint("Transparency Principle", principles) == (None, "ambiguous")


def _edge(pred, s, o, conf=0.8):
    return {"predicate": pred, "subject_iri": s, "object_iri": o, "source_text": "q", "confidence": conf}


def test_collapse_keeps_one_edge_per_principle_class(caplog):
    edges = [
        _edge("hasObligation", ROLE, OBL),
        _edge("derivedFromPrinciple", OBL, P_FACTS, 0.9),
        _edge("derivedFromPrinciple", OBL, P_BOARD, 0.7),
        _edge("derivedFromPrinciple", OBL, P_OTHER),
        _edge("adheresToPrinciple", ROLE, P_FACTS),
        _edge("adheresToPrinciple", ROLE, P_BOARD),
    ]
    obligations = [Indiv(iri=OBL, label="Disclosure Duty", fields={})]
    with caplog.at_level(logging.WARNING, logger="app.services.extraction.rpo_edges"):
        out = collapse_same_class_principle_edges(edges, _principles(), obligations, 8)
    assert [(e["predicate"], e["object_iri"]) for e in out] == [
        ("hasObligation", OBL),
        ("derivedFromPrinciple", P_BOARD),   # the Board-invoked twin wins over the higher confidence
        ("derivedFromPrinciple", P_OTHER),
        ("adheresToPrinciple", P_BOARD),
    ]
    assert sum("merge signal" in r.getMessage() for r in caplog.records) == 2


def test_collapse_falls_back_to_the_hint_then_to_confidence():
    principles = _principles()
    principles[1].fields["invokedBy"] = "Client X"      # neither twin is Board-invoked
    hinted = [Indiv(iri=OBL, label="Disclosure Duty", fields={"statedDerivedFromPrincipleIRI": P_FACTS})]
    out = collapse_same_class_principle_edges(
        [_edge("derivedFromPrinciple", OBL, P_FACTS, 0.6), _edge("derivedFromPrinciple", OBL, P_BOARD, 0.9)],
        principles, hinted, 8)
    assert [e["object_iri"] for e in out] == [P_FACTS]
    unhinted = [Indiv(iri=OBL, label="Disclosure Duty", fields={})]
    out2 = collapse_same_class_principle_edges(
        [_edge("derivedFromPrinciple", OBL, P_FACTS, 0.6), _edge("derivedFromPrinciple", OBL, P_BOARD, 0.9)],
        principles, unhinted, 8)
    assert [e["object_iri"] for e in out2] == [P_BOARD]


def _mock_client(json_response):
    client = MagicMock()
    final_msg = MagicMock()
    final_msg.stop_reason = "end_turn"
    final_msg.usage = MagicMock(input_tokens=100, output_tokens=200)
    stream_obj = MagicMock()
    stream_obj.text_stream = iter([json.dumps(json_response)])
    stream_obj.get_final_message.return_value = final_msg
    stream_ctx = MagicMock()
    stream_ctx.__enter__ = MagicMock(return_value=stream_obj)
    stream_ctx.__exit__ = MagicMock(return_value=False)
    client.messages.stream.return_value = stream_ctx
    return client


def test_extract_emits_one_derived_from_principle_edge_per_duty():
    client = _mock_client({"edges": [
        _edge("hasObligation", ROLE, OBL),
        _edge("derivedFromPrinciple", OBL, P_FACTS),
        _edge("derivedFromPrinciple", OBL, P_BOARD),
    ]})
    extractor = RPOEdgeExtractor(llm_client=client, model="claude-test-model")
    roles = [Indiv(iri=ROLE, label="Engineer L", fields={})]
    obligations = [Indiv(iri=OBL, label="Disclosure Duty", fields={})]
    edges = extractor.extract(8, roles, _principles(), obligations)
    assert [(e["predicate"], e["object_iri"]) for e in edges] == [
        ("hasObligation", OBL), ("derivedFromPrinciple", P_BOARD)]


_TTL = """
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix proeth: <http://proethica.org/ontology/intermediate#> .
@prefix proeth-core: <http://proethica.org/ontology/core#> .
@prefix case: <http://proethica.org/ontology/case/8#> .

case:Engineer_L_Disclosure_Duty a owl:NamedIndividual, proeth-core:Obligation ;
    rdfs:label "Engineer L Disclosure Duty" ;
    proeth:obligationStatement "Disclose the increased risk." .
case:Transparency_Principle a owl:NamedIndividual, proeth-core:Principle, proeth:TransparencyPrinciple ;
    rdfs:label "Transparency" ;
    proeth-core:invokedBy case:Agent_Engineer_L .
case:Transparency_Principle_Discussion a owl:NamedIndividual, proeth-core:Principle,
        proeth:TransparencyPrinciple ;
    rdfs:label "Transparency toward the client" ;
    proeth-core:invokedBy case:Agent_NSPE_Board .
case:Agent_Engineer_L rdfs:label "Engineer L" .
case:Agent_NSPE_Board rdfs:label "NSPE Board of Ethical Review" .
"""


def test_gather_resolves_the_class_hint_to_the_board_invoked_individual(monkeypatch):
    monkeypatch.setattr(rpo, "_derived_from_principle_hints",
                        lambda case_id: {"Engineer L Disclosure Duty": "Transparency Principle"})
    g = Graph()
    g.parse(data=_TTL, format="turtle")
    _roles, principles, obligations = gather(g, 8)
    (o,) = obligations
    assert o.fields["statedDerivedFromPrinciple"] == "Transparency Principle"
    assert o.fields["statedDerivedFromPrincipleIRI"] == P_BOARD
    assert {p.iri for p in principles} == {P_FACTS, P_BOARD}
