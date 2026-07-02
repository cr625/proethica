"""Tests for matched-class honoring and the label-tie source preference
(nine-component definition-prompt audit, Stage 2, work package 3C).

Two behaviors:

1. Commit-time honoring (OntServeCommitService._matched_class_override): when an
   individual's match decision says matchesExisting=true with a matchedOntologyClass,
   the commit types the individual to that EXISTING class instead of the minted
   near-duplicate -- but only after the matched class's curated subClassOf* chain
   resolves to the SAME core category as the component being committed (the KI2026
   lesson). On chain failure, a non-URI-safe local name, or any lookup error the
   override returns None and the minted types are kept exactly as before.

2. Match-step tie preference (MatchingMixin._existing_source_rank): when candidates
   tie on label similarity, prefer proethica-intermediate over intermediate-extended
   over concepts# rows.

DB/MCP-free: services are built with object.__new__ to bypass __init__, mirroring
tests/extraction/test_matcher_category_gate.py.
"""
from types import SimpleNamespace

import pytest

from app.services.commit.ontserve_commit_service import OntServeCommitService
from app.services.extraction import category_resolver
from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor

INT_NS = "http://proethica.org/ontology/intermediate#"
CONCEPTS_NS = "http://proethica.org/ontology/concepts#"


# ---------------------------------------------------------------------------
# Commit-time matched-class honoring
# ---------------------------------------------------------------------------

def _bare_commit_service(chain_resolver):
    """OntServeCommitService without __init__ (no OntServe paths / DB); the
    curated-chain resolution is stubbed per test."""
    svc = object.__new__(OntServeCommitService)
    svc._established_core_category = chain_resolver
    return svc


def _rdf_data(matches_existing=True, matched_uri=None):
    return {
        "match_decision": {
            "matches_existing": matches_existing,
            "matched_uri": matched_uri,
            "matched_label": "Attribution Obligation",
            "confidence": 0.9,
            "reasoning": "test",
        }
    }


def test_matched_class_with_valid_chain_is_honored():
    # The Opus case-7 fork: minted DisclosureObligation, matched
    # AttributionObligation with matchesExisting=true and a chain to Obligation.
    svc = _bare_commit_service(lambda local: "Obligation")
    honored = svc._matched_class_override(
        _rdf_data(matched_uri=f"{INT_NS}AttributionObligation"),
        "Obligation",
        [f"{INT_NS}DisclosureObligation"],
    )
    assert honored == "AttributionObligation"


def test_concepts_row_without_chain_falls_back():
    # A concepts# row whose type chain does not reach the component category:
    # the resolver returns None, so the minted class is kept.
    svc = _bare_commit_service(lambda local: None)
    honored = svc._matched_class_override(
        _rdf_data(matched_uri=f"{CONCEPTS_NS}NonDeception"),
        "Constraint",
        [f"{INT_NS}CredentialTitleAccuracyConstraint"],
    )
    assert honored is None


def test_non_uri_safe_local_name_falls_back_without_chain_lookup():
    # concepts#Non_Deception: the underscore would be mangled by the URI
    # sanitizer, so the override bails before the chain is even consulted.
    def _boom(local):
        raise AssertionError("chain resolver must not be consulted")
    svc = _bare_commit_service(_boom)
    honored = svc._matched_class_override(
        _rdf_data(matched_uri=f"{CONCEPTS_NS}Non_Deception"),
        "Constraint",
        [f"{INT_NS}CredentialTitleAccuracyConstraint"],
    )
    assert honored is None


def test_cross_category_chain_falls_back():
    # Matched class chains to Principle while an Obligation is being committed:
    # honoring would force a disjointness clash, so the minted class is kept.
    svc = _bare_commit_service(lambda local: "Principle")
    honored = svc._matched_class_override(
        _rdf_data(matched_uri=f"{INT_NS}PublicWelfarePrinciple"),
        "Obligation",
        [f"{INT_NS}SafetyObligation"],
    )
    assert honored is None


def test_matched_equals_minted_is_a_noop():
    def _boom(local):
        raise AssertionError("chain resolver must not be consulted")
    svc = _bare_commit_service(_boom)
    honored = svc._matched_class_override(
        _rdf_data(matched_uri=f"{INT_NS}SafetyObligation"),
        "Obligation",
        [f"{INT_NS}SafetyObligation"],
    )
    assert honored is None


def test_no_match_returns_none():
    svc = _bare_commit_service(lambda local: "Obligation")
    assert svc._matched_class_override(
        _rdf_data(matches_existing=False, matched_uri=f"{INT_NS}AttributionObligation"),
        "Obligation",
        [f"{INT_NS}DisclosureObligation"],
    ) is None
    assert svc._matched_class_override(
        _rdf_data(matched_uri=None), "Obligation", [f"{INT_NS}DisclosureObligation"],
    ) is None
    assert svc._matched_class_override({}, "Obligation", [f"{INT_NS}X"]) is None


def test_lookup_error_falls_back():
    def _explode(local):
        raise RuntimeError("simulated TTL parse failure")
    svc = _bare_commit_service(_explode)
    honored = svc._matched_class_override(
        _rdf_data(matched_uri=f"{INT_NS}AttributionObligation"),
        "Obligation",
        [f"{INT_NS}DisclosureObligation"],
    )
    assert honored is None


# ---------------------------------------------------------------------------
# Match-step label-tie source preference
# ---------------------------------------------------------------------------

def _bare_extractor(concept_type, existing_classes):
    ext = object.__new__(UnifiedDualExtractor)
    ext.concept_type = concept_type
    ext.existing_classes = existing_classes
    return ext


def _candidate(label):
    md = SimpleNamespace(
        matches_existing=False, matched_uri=None, matched_label=None,
        confidence=0.0, reasoning=None,
    )
    return SimpleNamespace(label=label, match_decision=md)


def _row(uri, label, ontology_name):
    return {"uri": uri, "label": label, "ontology_name": ontology_name}


def test_source_rank_ordering():
    rank = UnifiedDualExtractor._existing_source_rank
    intermediate = _row(f"{INT_NS}AttributionObligation", "Attribution Obligation",
                        "proethica-intermediate")
    extended = _row(f"{INT_NS}AttributionObligation", "Attribution Obligation",
                    "proethica-intermediate-extended")
    concepts = _row(f"{CONCEPTS_NS}AttributionObligation", "Attribution Obligation",
                    "concepts")
    assert rank(intermediate) < rank(extended) < rank(concepts)
    # concepts# detected from the URI even without an ontology_name
    assert rank({"uri": f"{CONCEPTS_NS}Foo", "label": "Foo"}) == 3


def test_label_tie_prefers_intermediate_over_extended(monkeypatch):
    monkeypatch.setattr(
        category_resolver, "resolve_core_category", lambda ref: "Obligation",
    )
    extended = _row(f"{INT_NS}AttributionObligationExt", "Attribution Obligation",
                    "proethica-intermediate-extended")
    intermediate = _row(f"{INT_NS}AttributionObligation", "Attribution Obligation",
                        "proethica-intermediate")
    # Extended FIRST in list order: the old first-match break would pick it.
    ext = _bare_extractor("obligations", [extended, intermediate])
    cand = _candidate("Attribution Obligation")

    ext._check_existing_matches([cand])

    assert cand.match_decision.matches_existing is True
    assert cand.match_decision.matched_uri == f"{INT_NS}AttributionObligation"


def test_label_tie_prefers_extended_over_concepts(monkeypatch):
    monkeypatch.setattr(
        category_resolver, "resolve_core_category", lambda ref: "Constraint",
    )
    concepts = _row(f"{CONCEPTS_NS}NonDeception", "Non Deception", "concepts")
    extended = _row(f"{INT_NS}NonDeceptionConstraint", "Non Deception",
                    "proethica-intermediate-extended")
    ext = _bare_extractor("constraints", [concepts, extended])
    cand = _candidate("Non Deception")

    ext._check_existing_matches([cand])

    assert cand.match_decision.matches_existing is True
    assert cand.match_decision.matched_uri == f"{INT_NS}NonDeceptionConstraint"


def test_build_existing_by_label_is_order_independent():
    intermediate = _row(f"{INT_NS}AttributionObligation", "Attribution Obligation",
                        "proethica-intermediate")
    extended = _row(f"{INT_NS}AttributionObligationExt", "Attribution Obligation",
                    "proethica-intermediate-extended")
    for order in ([intermediate, extended], [extended, intermediate]):
        ext = _bare_extractor("obligations", order)
        by_label = ext._build_existing_by_label()
        assert by_label["attribution obligation"] is intermediate


def test_rank_tie_keeps_first_list_entry(monkeypatch):
    # Two same-rank rows (both intermediate-extended): min() is stable, so the
    # first list entry wins, preserving the pre-change behavior within a rank.
    monkeypatch.setattr(
        category_resolver, "resolve_core_category", lambda ref: "Obligation",
    )
    first = _row(f"{INT_NS}FirstObligation", "Duplicate Label",
                 "proethica-intermediate-extended")
    second = _row(f"{INT_NS}SecondObligation", "Duplicate Label",
                  "proethica-intermediate-extended")
    ext = _bare_extractor("obligations", [first, second])
    cand = _candidate("Duplicate Label")

    ext._check_existing_matches([cand])

    assert cand.match_decision.matched_uri == f"{INT_NS}FirstObligation"
