"""Tests for the matcher cross-category gate (Phase A item A1).

The prefer-existing matcher in UnifiedDualExtractor must reject a match whose
matched class chains (via the curated subClassOf* chain) to a core category
disjoint from the candidate's category. This stops a genuine Obligation being
merged into a class an earlier extraction mis-established as a Principle, which
otherwise forces a Pellet disjointness clash.

These tests are deliberately DB/MCP-free: the extractor is built with
object.__new__ to bypass __init__ (which loads MCP, DB templates, and schemas),
and the chain resolver is monkeypatched so no TTL parse is needed except in the
one real-resolver test for ProfessionalCompetence.

See docs-internal/reextraction/matcher-category-authority-design.md.
"""
from types import SimpleNamespace

from app.services.extraction import category_resolver
from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor


def _candidate(label, *, matches_existing=False, matched_uri=None,
               matched_label=None, confidence=0.0, reasoning=None):
    """A minimal candidate standing in for a Pydantic candidate model.

    The gate only touches candidate.label and candidate.match_decision.*.
    """
    md = SimpleNamespace(
        matches_existing=matches_existing,
        matched_uri=matched_uri,
        matched_label=matched_label,
        confidence=confidence,
        reasoning=reasoning,
    )
    return SimpleNamespace(label=label, match_decision=md)


def _bare_extractor(concept_type, existing_classes):
    """Build a UnifiedDualExtractor without running __init__ (no DB/MCP)."""
    ext = object.__new__(UnifiedDualExtractor)
    ext.concept_type = concept_type
    ext.existing_classes = existing_classes
    return ext


def test_obligation_matched_to_principle_chained_class_is_rejected(monkeypatch):
    # The matched class chains to Principle (a mis-established case-85 artifact),
    # but the candidate is an Obligation. The gate must drop the match.
    monkeypatch.setattr(
        category_resolver, "resolve_core_category",
        lambda ref: "Principle",
    )

    ext = _bare_extractor("obligations", existing_classes=[])
    cand = _candidate(
        "Project Success Notification Obligation",
        matches_existing=True,
        matched_uri="http://proethica.org/ontology/intermediate#ProjectSuccessNotificationObligation",
        matched_label="Project Success Notification Obligation",
        confidence=0.9,
        reasoning="Label match with existing ontology class",
    )

    ext._reject_cross_category_match(cand)

    assert cand.match_decision.matches_existing is False
    assert cand.match_decision.matched_uri is None
    assert cand.match_decision.matched_label is None
    assert cand.match_decision.confidence == 0.0
    assert "rejected cross-category match" in cand.match_decision.reasoning
    assert "Principle" in cand.match_decision.reasoning
    assert "Obligation" in cand.match_decision.reasoning


def test_same_category_match_is_kept(monkeypatch):
    # Matched class chains to Obligation; candidate is also an Obligation.
    monkeypatch.setattr(
        category_resolver, "resolve_core_category",
        lambda ref: "Obligation",
    )

    ext = _bare_extractor("obligations", existing_classes=[])
    cand = _candidate(
        "Public Welfare Paramount Obligation",
        matches_existing=True,
        matched_uri="http://proethica.org/ontology/intermediate#PublicWelfareParamountObligation",
        matched_label="Public Welfare Paramount Obligation",
        confidence=0.9,
        reasoning="Label match with existing ontology class",
    )

    ext._reject_cross_category_match(cand)

    assert cand.match_decision.matches_existing is True
    assert cand.match_decision.matched_uri == (
        "http://proethica.org/ontology/intermediate#PublicWelfareParamountObligation"
    )
    assert cand.match_decision.matched_label == "Public Welfare Paramount Obligation"
    assert cand.match_decision.confidence == 0.9
    assert cand.match_decision.reasoning == "Label match with existing ontology class"


def test_unresolvable_chain_leaves_match_untouched(monkeypatch):
    # Chain category unknown (class not in the curated tiers): the gate cannot
    # prove a conflict, so it must leave the match in place.
    monkeypatch.setattr(
        category_resolver, "resolve_core_category", lambda ref: None,
    )

    ext = _bare_extractor("obligations", existing_classes=[])
    cand = _candidate(
        "Some Novel Obligation",
        matches_existing=True,
        matched_uri="http://proethica.org/ontology/intermediate#SomeNovelClass",
        matched_label="Some Novel Class",
        confidence=0.9,
        reasoning="Label match with existing ontology class",
    )

    ext._reject_cross_category_match(cand)

    assert cand.match_decision.matches_existing is True
    assert cand.match_decision.matched_uri is not None


def test_non_match_is_ignored(monkeypatch):
    # A candidate that did not match anything must pass through untouched, and
    # the resolver must not even be consulted.
    def _boom(ref):
        raise AssertionError("resolver should not be called for a non-match")
    monkeypatch.setattr(category_resolver, "resolve_core_category", _boom)

    ext = _bare_extractor("obligations", existing_classes=[])
    cand = _candidate("Brand New Obligation", matches_existing=False)

    ext._reject_cross_category_match(cand)

    assert cand.match_decision.matches_existing is False


def test_check_existing_matches_runs_gate_end_to_end(monkeypatch):
    # Full _check_existing_matches path: a label match is established in the
    # lexical branch, then the gate rejects it because the existing class chains
    # to Principle while the candidate is an Obligation.
    monkeypatch.setattr(
        category_resolver, "resolve_core_category",
        lambda ref: "Principle",
    )

    existing = [{
        "uri": "http://proethica.org/ontology/intermediate#ProjectSuccessNotificationObligation",
        "label": "Project Success Notification Obligation",
    }]
    ext = _bare_extractor("obligations", existing_classes=existing)
    cand = _candidate("Project Success Notification Obligation")

    ext._check_existing_matches([cand])

    # The lexical branch would have matched on the identical label; the gate
    # then rejects it, so the candidate is treated as new.
    assert cand.match_decision.matches_existing is False
    assert cand.match_decision.matched_uri is None
    assert "rejected cross-category match" in (cand.match_decision.reasoning or "")


def test_gate_rejects_cross_category_individual_direct_match(monkeypatch):
    # _link_individuals_to_classes Case 2 links an individual DIRECTLY to an
    # existing class (existing_by_label, keyed off the STORED category, which can
    # disagree with the chain). The gate must also cover this path. Individuals
    # carry `identifier` (no `label`), so the label-safe logging must not crash.
    monkeypatch.setattr(
        category_resolver, "resolve_core_category",
        lambda ref: "Principle",
    )
    ext = _bare_extractor("obligations", existing_classes=[])
    md = SimpleNamespace(
        matches_existing=True,
        matched_uri="http://proethica.org/ontology/intermediate#ProjectSuccessNotificationObligation",
        matched_label="Project Success Notification Obligation",
        confidence=0.95,
        reasoning="Individual typed as existing ontology class",
    )
    individual = SimpleNamespace(identifier="Engineer_L_Runoff_Risk_Notification",
                                 match_decision=md)

    ext._reject_cross_category_match(individual)

    assert md.matches_existing is False
    assert md.matched_uri is None
    assert "rejected cross-category match" in md.reasoning


def test_resolve_core_category_risk_assessment_is_capability():
    # Real resolver over the curated TTLs: RiskAssessmentCapability chains to
    # proeth-core:Capability in proethica-intermediate. (The earlier exemplar,
    # ProfessionalCompetence, was removed in the 2026-06-28 Capability kind
    # taxonomy rework.)
    assert category_resolver.resolve_core_category("RiskAssessmentCapability") == "Capability"
    # URI and prefixed forms reduce to the same local name.
    assert category_resolver.resolve_core_category(
        "http://proethica.org/ontology/intermediate#RiskAssessmentCapability"
    ) == "Capability"
    assert category_resolver.resolve_core_category(
        "proeth:RiskAssessmentCapability"
    ) == "Capability"
