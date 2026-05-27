"""Tests for the R->P->O applier + Pellet-safety domain/range guard.

Covers the deterministic, consistency-critical pieces without an LLM:
  - drop_domain_range_violations removes edges whose endpoint resolves (via the
    merged core+intermediate+case type chain) to a category conflicting with the
    property domain/range, and keeps type-valid edges.
  - apply_rpo_edges adds emitted edges + PROV, applies the guard, and writes back.
  - materialize_edges_on_ttl is best-effort: one applier raising does not raise.

These reproduce, at commit time, the behaviour of the KI2026 batch repair
(repair_rpo_type_violations.py) so re-extraction cannot reintroduce the
disjointness-violating edge class.
"""
import textwrap
from pathlib import Path

import pytest
from rdflib import Graph, RDF, RDFS, URIRef, Literal, Namespace

from app.services.extraction.rpo_edges import (
    add_edges_to_graph,
    drop_domain_range_violations,
    apply_rpo_edges,
    HAS_OBLIGATION,
    ADHERES_TO,
)

CASE = Namespace("http://proethica.org/ontology/case/9999#")
CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")

ROLE = str(CASE.role1)
PRIN = str(CASE.prin1)
OBL = str(CASE.obl1)
# Individual mis-tagged conceptCategory=Principle but typed to a Capability
# core class -- the reasoner-visible chain (Capability) must win.
CAP_AS_PRIN = str(CASE.cap1)


def _fixture_graph() -> Graph:
    ttl = textwrap.dedent(f"""\
    @prefix case: <http://proethica.org/ontology/case/9999#> .
    @prefix proeth: <http://proethica.org/ontology/intermediate#> .
    @prefix proeth-core: <http://proethica.org/ontology/core#> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

    case:role1 a owl:NamedIndividual, proeth-core:Role ;
        rdfs:label "Engineer" ; proeth:conceptCategory "Role" .
    case:prin1 a owl:NamedIndividual, proeth-core:Principle ;
        rdfs:label "Public Safety" ; proeth:conceptCategory "Principle" .
    case:obl1 a owl:NamedIndividual, proeth-core:Obligation ;
        rdfs:label "Hold Paramount" ; proeth:conceptCategory "Obligation" .
    case:cap1 a owl:NamedIndividual, proeth-core:Capability ;
        rdfs:label "Risk Assessment" ; proeth:conceptCategory "Principle" .
    """)
    g = Graph()
    g.parse(data=ttl, format="turtle")
    return g


def test_guard_drops_range_violation_keeps_valid():
    g = _fixture_graph()
    edges = [
        {"predicate": "adheresToPrinciple", "subject_iri": ROLE, "object_iri": PRIN,
         "source_text": "valid principle", "confidence": 0.9},
        {"predicate": "hasObligation", "subject_iri": ROLE, "object_iri": OBL,
         "source_text": "valid obligation", "confidence": 0.9},
        {"predicate": "adheresToPrinciple", "subject_iri": ROLE, "object_iri": CAP_AS_PRIN,
         "source_text": "bad: object is a Capability", "confidence": 0.9},
    ]
    added = add_edges_to_graph(g, edges, 9999)
    assert added == 3

    removed = drop_domain_range_violations(g, 9999)
    assert removed >= 1  # the cap1 edge + its PROV triples

    # Valid edges survive.
    assert (URIRef(ROLE), ADHERES_TO, URIRef(PRIN)) in g
    assert (URIRef(ROLE), HAS_OBLIGATION, URIRef(OBL)) in g
    # The range-violating edge is gone.
    assert (URIRef(ROLE), ADHERES_TO, URIRef(CAP_AS_PRIN)) not in g


def test_guard_noop_when_all_valid():
    g = _fixture_graph()
    edges = [
        {"predicate": "adheresToPrinciple", "subject_iri": ROLE, "object_iri": PRIN,
         "source_text": "x", "confidence": 0.9},
        {"predicate": "derivedFromPrinciple", "subject_iri": OBL, "object_iri": PRIN,
         "source_text": "y", "confidence": 0.9},
    ]
    add_edges_to_graph(g, edges, 9999)
    assert drop_domain_range_violations(g, 9999) == 0


class _StubExtractor:
    def __init__(self, edges):
        self._edges = edges

    def extract(self, case_id, roles, principles, obligations):
        return self._edges


def test_apply_rpo_edges_writes_back_and_guards(tmp_path):
    ttl_file = tmp_path / "proethica-case-9999.ttl"
    _fixture_graph().serialize(destination=str(ttl_file), format="turtle")

    stub = _StubExtractor([
        {"predicate": "hasObligation", "subject_iri": ROLE, "object_iri": OBL,
         "source_text": "ok", "confidence": 0.9},
        {"predicate": "adheresToPrinciple", "subject_iri": ROLE, "object_iri": CAP_AS_PRIN,
         "source_text": "bad", "confidence": 0.9},
    ])
    result = apply_rpo_edges(9999, ttl_file, extractor=stub, write_back=True)

    assert result["status"] == "ok"
    assert result["edges_emitted"] == 2
    assert result["triples_added"] == 2
    assert result["triples_dropped"] >= 1

    g = Graph()
    g.parse(str(ttl_file), format="turtle")
    assert (URIRef(ROLE), HAS_OBLIGATION, URIRef(OBL)) in g
    assert (URIRef(ROLE), ADHERES_TO, URIRef(CAP_AS_PRIN)) not in g


def test_apply_rpo_edges_no_edges(tmp_path):
    ttl_file = tmp_path / "proethica-case-9999.ttl"
    _fixture_graph().serialize(destination=str(ttl_file), format="turtle")
    result = apply_rpo_edges(9999, ttl_file, extractor=_StubExtractor([]), write_back=True)
    assert result["status"] == "no_edges"


def test_apply_rpo_edges_missing_ttl(tmp_path):
    result = apply_rpo_edges(9999, tmp_path / "does-not-exist.ttl")
    assert result["status"] == "missing_ttl"


def test_established_core_category_resolves_corrected_classes():
    """Regression guard for direction A (type-chain authoritative) + the 6
    re-parented discovered classes. Reads the live intermediate ontologies, so it
    fails if either the resolver breaks or a correction is reverted."""
    from app.services.ontserve_commit_service import OntServeCommitService
    svc = OntServeCommitService()

    # The 6 drifted classes corrected on 2026-05-27 (were Principle/Resource).
    expected = {
        "ClientRefusalEscalationObligation": "Obligation",
        "RiskDisclosureTimingObligation": "Obligation",
        "ExpertWitnessDisclosureObligation": "Obligation",
        "PublicSafetyDisclosureObligation": "Obligation",
        "Single-ClientDual-RoleSelf-ReviewHeightenedCautionObligation": "Obligation",
        "Part-TimeMunicipalEngineerCompetitiveDisadvantageAcknowledgmentandEthicalConstraint": "Constraint",
    }
    for cls, cat in expected.items():
        assert svc._established_core_category(cls) == cat, cls

    # A class whose established chain is genuinely Capability stays Capability
    # (the literal must not override the ontology).
    assert svc._established_core_category("ProfessionalCompetence") == "Capability"
    # Unknown classes resolve to None (fresh classes fall back to the extraction category).
    assert svc._established_core_category("DefinitelyNotARealClass12345") is None


def test_materialize_is_best_effort(monkeypatch, tmp_path):
    """A raising applier is recorded as an error, never propagated."""
    ttl_file = tmp_path / "proethica-case-9999.ttl"
    _fixture_graph().serialize(destination=str(ttl_file), format="turtle")

    import app.services.extraction.edge_materialization as em

    def _boom(*a, **k):
        raise RuntimeError("simulated applier failure")

    monkeypatch.setattr(
        "app.services.extraction.defeasibility_pipeline.apply_defeasibility_edges",
        _boom, raising=True,
    )
    monkeypatch.setattr(
        "app.services.extraction.rpo_edges.apply_rpo_edges", _boom, raising=True,
    )
    monkeypatch.setattr(
        "app.services.extraction.provision_citation_resolver.apply_cites_provision_on_ttl",
        _boom, raising=True,
    )

    result = em.materialize_edges_on_ttl(9999, ttl_file)
    assert "error" in result["defeasibility"]
    assert "error" in result["rpo"]
    assert "error" in result["cites_provision"]
