"""
Unit tests for RPOEdgeExtractor (Role -> Principle -> Obligation chain).

These mirror test_defeasibility_edges.py: a mocked Anthropic streaming client
feeds the extractor a JSON edge set so the suite runs without API access. The
focus is the two behaviors that broke during the KI2026 corpus pass:

  1. endpoint-category validation -- an edge whose subject/object does not match
     the property's domain/range category is dropped (this is what keeps the
     materialized edges from forcing a disjoint-class clash under Pellet).
  2. partial recovery -- a response truncated at max_tokens still yields the
     complete edges that landed before the cutoff, instead of an empty list.
"""

from __future__ import annotations

import json
from typing import List
from unittest.mock import MagicMock

import pytest
from rdflib import Graph, RDF, URIRef
from rdflib.namespace import Namespace

from app.services.extraction.rpo_edges import (
    ADHERES_TO,
    DERIVED_FROM,
    HAS_OBLIGATION,
    Indiv,
    RPOEdgeExtractor,
    add_edges_to_graph,
)

CASE_NS = "http://proethica.org/ontology/case/86#"
PROV = Namespace("http://www.w3.org/ns/prov#")

ROLE_IRI = f"{CASE_NS}Engineer_A_Role"
PRINCIPLE_IRI = f"{CASE_NS}Public_Welfare_Principle"
OBLIGATION_IRI = f"{CASE_NS}Obl_PublicWelfare"


# ---------------------------------------------------------------------------
# Fixtures: a minimal Role / Principle / Obligation triangle
# ---------------------------------------------------------------------------

@pytest.fixture
def roles() -> List[Indiv]:
    return [Indiv(iri=ROLE_IRI, label="Engineer A",
                  fields={"roleclass": "Environmental Engineer"})]


@pytest.fixture
def principles() -> List[Indiv]:
    return [Indiv(iri=PRINCIPLE_IRI, label="Public welfare paramount",
                  fields={"principleclass": "Public Welfare"})]


@pytest.fixture
def obligations() -> List[Indiv]:
    return [Indiv(iri=OBLIGATION_IRI, label="Hold public welfare paramount",
                  fields={"obligationstatement": "report the violation"})]


GOLD_OUTPUT = {
    "edges": [
        {"predicate": "hasObligation", "subject_iri": ROLE_IRI,
         "object_iri": OBLIGATION_IRI, "source_text": "role bears obligation",
         "confidence": 0.9},
        {"predicate": "adheresToPrinciple", "subject_iri": ROLE_IRI,
         "object_iri": PRINCIPLE_IRI, "source_text": "role guided by principle",
         "confidence": 0.9},
        {"predicate": "derivedFromPrinciple", "subject_iri": OBLIGATION_IRI,
         "object_iri": PRINCIPLE_IRI, "source_text": "obligation operationalizes principle",
         "confidence": 0.85},
    ]
}


# ---------------------------------------------------------------------------
# Mock client (mirrors the Anthropic streaming context-manager shape)
# ---------------------------------------------------------------------------

def _make_mock_client_raw_text(raw: str, stop_reason: str = "end_turn") -> MagicMock:
    client = MagicMock()
    final_msg = MagicMock()
    final_msg.stop_reason = stop_reason
    final_msg.usage = MagicMock(input_tokens=100, output_tokens=200)
    stream_obj = MagicMock()
    stream_obj.text_stream = iter([raw])
    stream_obj.get_final_message.return_value = final_msg
    stream_ctx = MagicMock()
    stream_ctx.__enter__ = MagicMock(return_value=stream_obj)
    stream_ctx.__exit__ = MagicMock(return_value=False)
    client.messages.stream.return_value = stream_ctx
    return client


def _make_mock_client(json_response: dict) -> MagicMock:
    return _make_mock_client_raw_text(json.dumps(json_response))


def _extractor(client) -> RPOEdgeExtractor:
    return RPOEdgeExtractor(llm_client=client, model="claude-test-model")


# ---------------------------------------------------------------------------
# Extraction with a mocked LLM
# ---------------------------------------------------------------------------

class TestExtractorWithMockedLLM:

    def test_produces_full_rpo_chain(self, roles, principles, obligations):
        edges = _extractor(_make_mock_client(GOLD_OUTPUT)).extract(
            86, roles, principles, obligations)
        by_pred = {e["predicate"] for e in edges}
        assert by_pred == {"hasObligation", "adheresToPrinciple", "derivedFromPrinciple"}
        assert len(edges) == 3

    def test_drops_category_mismatch(self, roles, principles, obligations):
        """A hasObligation edge whose object is a Principle (not an Obligation)
        is dropped. This is the guard that preserves Pellet consistency: an edge
        ranging over the wrong disjoint category would clash under
        owl:AllDisjointClasses."""
        bad = {"edges": [
            # object_iri is a Principle, but hasObligation ranges over Obligation
            {"predicate": "hasObligation", "subject_iri": ROLE_IRI,
             "object_iri": PRINCIPLE_IRI, "source_text": "wrong range",
             "confidence": 0.9},
            # valid edge survives
            {"predicate": "adheresToPrinciple", "subject_iri": ROLE_IRI,
             "object_iri": PRINCIPLE_IRI, "source_text": "ok", "confidence": 0.8},
        ]}
        edges = _extractor(_make_mock_client(bad)).extract(
            86, roles, principles, obligations)
        assert len(edges) == 1
        assert edges[0]["predicate"] == "adheresToPrinciple"

    def test_drops_subject_category_mismatch(self, roles, principles, obligations):
        """derivedFromPrinciple expects an Obligation subject; a Role subject is
        dropped."""
        bad = {"edges": [
            {"predicate": "derivedFromPrinciple", "subject_iri": ROLE_IRI,
             "object_iri": PRINCIPLE_IRI, "source_text": "role is not an obligation",
             "confidence": 0.9},
        ]}
        edges = _extractor(_make_mock_client(bad)).extract(
            86, roles, principles, obligations)
        assert edges == []

    def test_drops_invented_iris(self, roles, principles, obligations):
        bad = {"edges": [
            {"predicate": "hasObligation", "subject_iri": ROLE_IRI,
             "object_iri": f"{CASE_NS}Made_Up_Obligation", "source_text": "x",
             "confidence": 0.9},
        ]}
        edges = _extractor(_make_mock_client(bad)).extract(
            86, roles, principles, obligations)
        assert edges == []

    def test_dedup(self, roles, principles, obligations):
        dup = {"edges": [
            {"predicate": "hasObligation", "subject_iri": ROLE_IRI,
             "object_iri": OBLIGATION_IRI, "source_text": "first", "confidence": 0.6},
            {"predicate": "hasObligation", "subject_iri": ROLE_IRI,
             "object_iri": OBLIGATION_IRI, "source_text": "second", "confidence": 0.9},
        ]}
        edges = _extractor(_make_mock_client(dup)).extract(
            86, roles, principles, obligations)
        assert len(edges) == 1

    def test_strips_angle_brackets(self, roles, principles, obligations):
        wrapped = {"edges": [
            {"predicate": "hasObligation", "subject_iri": f"<{ROLE_IRI}>",
             "object_iri": f"<{OBLIGATION_IRI}>", "source_text": "x", "confidence": 0.9},
        ]}
        edges = _extractor(_make_mock_client(wrapped)).extract(
            86, roles, principles, obligations)
        assert len(edges) == 1
        assert edges[0]["subject_iri"] == ROLE_IRI
        assert edges[0]["object_iri"] == OBLIGATION_IRI

    def test_skip_when_no_roles(self, principles, obligations):
        client = _make_mock_client({"edges": []})
        edges = _extractor(client).extract(86, [], principles, obligations)
        assert edges == []
        client.messages.stream.assert_not_called()


# ---------------------------------------------------------------------------
# Partial recovery from a truncated response
# ---------------------------------------------------------------------------

class TestPartialRecovery:

    def test_recovers_truncated_response(self, roles, principles, obligations):
        # Two complete edges, then a third cut off mid-string (no closing
        # quote/brace/array), as happens when max_tokens is hit.
        truncated = (
            '{"edges": [\n'
            '  {"predicate": "hasObligation", '
            f'"subject_iri": "{ROLE_IRI}", "object_iri": "{OBLIGATION_IRI}", '
            '"source_text": "first", "confidence": 0.9},\n'
            '  {"predicate": "adheresToPrinciple", '
            f'"subject_iri": "{ROLE_IRI}", "object_iri": "{PRINCIPLE_IRI}", '
            '"source_text": "second", "confidence": 0.85},\n'
            '  {"predicate": "derivedFromPrinciple", '
            f'"subject_iri": "{OBLIGATION_IRI}", "object_iri": "{PRINCIPLE_IRI}", '
            '"source_text": "third was cut off by max_tokens'
        )
        edges = _extractor(
            _make_mock_client_raw_text(truncated, stop_reason="max_tokens")
        ).extract(86, roles, principles, obligations)
        preds = sorted(e["predicate"] for e in edges)
        assert preds == ["adheresToPrinciple", "hasObligation"]


# ---------------------------------------------------------------------------
# RDF emission
# ---------------------------------------------------------------------------

class TestAddEdgesToGraph:

    def test_emits_triples_and_prov(self):
        g = Graph()
        edges = [
            {"predicate": "hasObligation", "subject_iri": ROLE_IRI,
             "object_iri": OBLIGATION_IRI, "source_text": "bears", "confidence": 0.9},
            {"predicate": "adheresToPrinciple", "subject_iri": ROLE_IRI,
             "object_iri": PRINCIPLE_IRI, "source_text": "guided", "confidence": 0.9},
            {"predicate": "derivedFromPrinciple", "subject_iri": OBLIGATION_IRI,
             "object_iri": PRINCIPLE_IRI, "source_text": "operationalizes", "confidence": 0.85},
        ]
        added = add_edges_to_graph(g, edges, 86)
        assert added == 3
        assert (URIRef(ROLE_IRI), HAS_OBLIGATION, URIRef(OBLIGATION_IRI)) in g
        assert (URIRef(ROLE_IRI), ADHERES_TO, URIRef(PRINCIPLE_IRI)) in g
        assert (URIRef(OBLIGATION_IRI), DERIVED_FROM, URIRef(PRINCIPLE_IRI)) in g
        # one PROV-O derivation node per edge, each carrying its source text
        derivations = list(g.subjects(RDF.type, PROV.Derivation))
        assert len(derivations) == 3
        values = {str(o) for o in g.objects(None, PROV.value)}
        assert {"bears", "guided", "operationalizes"} <= values

    def test_idempotent_on_existing_edge(self):
        g = Graph()
        g.add((URIRef(ROLE_IRI), HAS_OBLIGATION, URIRef(OBLIGATION_IRI)))
        added = add_edges_to_graph(g, [
            {"predicate": "hasObligation", "subject_iri": ROLE_IRI,
             "object_iri": OBLIGATION_IRI, "source_text": "dup", "confidence": 0.9},
        ], 86)
        assert added == 0
