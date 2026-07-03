"""Tests for matched-class honoring and the label-tie source preference
(nine-component definition-prompt audit, Stage 2, work package 3C).

Three behaviors:

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

3. Dual-channel placement (the run-21 review finding): an INDIVIDUAL temp row
   always commits as a case NamedIndividual carrying the match annotation --
   matching an existing class re-types it, it never demotes it to class-level-
   only. The class-level-only TTL blocks are the D15 anchor declarations of the
   CLASS channel (storage_type='class' rows), which by design dedup against the
   curated base and never become individuals.

DB/MCP-free: services are built with object.__new__ to bypass __init__, mirroring
tests/extraction/test_matcher_category_gate.py.
"""
from types import SimpleNamespace

import pytest
from rdflib import Graph, Namespace, OWL, RDF, RDFS, URIRef

from app.services.commit.ontserve_commit_service import OntServeCommitService
from app.services.extraction import category_resolver
from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor

INT_NS = "http://proethica.org/ontology/intermediate#"
CONCEPTS_NS = "http://proethica.org/ontology/concepts#"
CORE_NS = "http://proethica.org/ontology/core#"
PROV_NS = Namespace("http://proethica.org/provenance#")


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


# ---------------------------------------------------------------------------
# Dual-channel placement (run-21 review): matched individuals stay individuals
# ---------------------------------------------------------------------------

def _placement_entity(label, extraction_type='principles'):
    """Stand-in for a TemporaryRDFStorage row (the attributes the commit
    paths read)."""
    return SimpleNamespace(
        extraction_type=extraction_type,
        entity_type=extraction_type,
        entity_label=label,
        entity_definition='A test definition.',
        iao_document_uri=None,
        iao_document_label=None,
        cited_by_role=None,
        available_to_role=None,
        extraction_model=None,
    )


def _placement_service(tmp_path, monkeypatch, chain_resolver):
    """OntServeCommitService wired to a tmp ontologies dir with the DB / LLM /
    OntServe touchpoints stubbed (edge materialization, canonicalization, the
    role-axis resolver, the case-title lookup, edge provenance)."""
    import app.services.extraction.canonicalization as canon
    import app.services.extraction.edge_materialization as edge_mat

    svc = object.__new__(OntServeCommitService)
    svc.ontologies_dir = tmp_path
    svc._established_core_category = chain_resolver
    svc._case_title = lambda case_id: 'Mock Case'
    svc._record_edge_provenance = lambda *a, **k: None
    monkeypatch.setattr(edge_mat, 'materialize_edges_on_ttl',
                        lambda cid, f: {'stubbed': True})
    monkeypatch.setattr(canon, 'canonicalize_ttl',
                        lambda cid, f: {'stubbed': True})
    monkeypatch.setattr(category_resolver, 'resolve_role_axis',
                        lambda uri: None)
    return svc


def test_matched_class_principle_individual_commits_as_case_individual(
        tmp_path, monkeypatch):
    """The run-21 misread, locked as a regression test: a principle INDIVIDUAL
    whose matcher matched an existing curated class (the ToolSubstitution-
    ProhibitionPrinciple case) must commit as a case NamedIndividual typed to
    the matched class and carrying the match annotation -- honoring re-types
    the individual, it never demotes it to a class-level-only declaration."""
    matched_local = 'ToolSubstitutionProhibitionPrinciple'
    svc = _placement_service(
        tmp_path, monkeypatch,
        lambda local: 'Principle' if local == matched_local else None)

    rdf_data = {
        'types': [f'{INT_NS}JudgmentPrimacyPrinciple'],  # minted near-duplicate
        'match_decision': {
            'matches_existing': True,
            'matched_uri': f'{INT_NS}{matched_local}',
            'matched_label': 'Professional Judgment Primacy Principle',
            'confidence': 0.9,
            'reasoning': 'folds into the curated base class per the reuse policy',
        },
    }
    entity = _placement_entity('Judgment Primacy over AI Outputs')

    result = svc._commit_individuals_to_case_ontology(7, [(entity, rdf_data)])

    assert result.get('error') is None, result
    assert result['count'] == 1

    g = Graph()
    g.parse(result['file'], format='turtle')
    case_ns = Namespace('http://proethica.org/ontology/case/7#')
    ind = case_ns['Judgment_Primacy_over_AI_Outputs']
    matched_cls = URIRef(f'{INT_NS}{matched_local}')

    # The individual EXISTS in the case TTL (not class-level-only) ...
    assert (ind, RDF.type, OWL.NamedIndividual) in g
    # ... typed to the HONORED existing class, not the minted near-duplicate ...
    assert (ind, RDF.type, matched_cls) in g
    assert (ind, RDF.type, URIRef(f'{INT_NS}JudgmentPrimacyPrinciple')) not in g
    # ... with the materialized direct core type ...
    assert (ind, RDF.type, URIRef(f'{CORE_NS}Principle')) in g
    # ... and the match annotation (XAI provenance) on the INDIVIDUAL.
    assert (ind, PROV_NS['matchedOntologyClass'], matched_cls) in g
    assert (ind, PROV_NS['matchReasoning'], None) in g

    # The shared class is anchored in the case TTL (owl:Class + subClassOf
    # core) -- the block the run-21 review misread as a lost entity. It
    # coexists WITH the committed individual.
    assert (matched_cls, RDF.type, OWL.Class) in g
    assert (matched_cls, RDFS.subClassOf, URIRef(f'{CORE_NS}Principle')) in g


def test_unmatched_individual_still_commits_with_minted_type(
        tmp_path, monkeypatch):
    """Recall guard: an individual with NO match commits exactly as before
    (minted type + local class declaration), so the honoring path cannot
    reduce counts elsewhere."""
    svc = _placement_service(tmp_path, monkeypatch, lambda local: None)
    rdf_data = {
        'types': [f'{INT_NS}ReviewAdequacyPrinciple'],
        'match_decision': {'matches_existing': False, 'confidence': 0.0,
                           'reasoning': 'no candidate'},
    }
    entity = _placement_entity('Review Adequacy of AI Outputs')

    result = svc._commit_individuals_to_case_ontology(7, [(entity, rdf_data)])

    assert result.get('error') is None, result
    assert result['count'] == 1
    g = Graph()
    g.parse(result['file'], format='turtle')
    ind = Namespace('http://proethica.org/ontology/case/7#')[
        'Review_Adequacy_of_AI_Outputs']
    minted = URIRef(f'{INT_NS}ReviewAdequacyPrinciple')
    assert (ind, RDF.type, OWL.NamedIndividual) in g
    assert (ind, RDF.type, minted) in g
    # Genuinely-new class: declared locally with its subClassOf-core.
    assert (minted, RDF.type, OWL.Class) in g
    assert (minted, RDFS.subClassOf, URIRef(f'{CORE_NS}Principle')) in g


def test_class_channel_row_dedups_against_curated_base_without_individual(
        tmp_path, monkeypatch):
    """The other half of the run-21 finding: a CLASS-channel temp row whose
    label already lives in the curated base is skipped by the D15 rule (no
    copy into the extended store) and can never become an individual -- that
    is the intended dedup, not entity loss."""
    svc = object.__new__(OntServeCommitService)
    svc.ontologies_dir = tmp_path
    # Curated-base stand-in: the label chains to Principle in the base.
    svc._base_cat_cache = {'TransparencyPrinciple': 'Principle'}
    entity = _placement_entity('Transparency Principle')

    result = svc._commit_classes_to_intermediate([(entity, {})])

    assert result.get('error') is None, result
    assert result['count'] == 0  # D15 skip: already in the curated base

    extended = tmp_path / 'proethica-intermediate-extended.ttl'
    assert extended.exists()
    g = Graph()
    g.parse(extended, format='turtle')
    cls = URIRef(f'{INT_NS}TransparencyPrinciple')
    assert (cls, RDF.type, OWL.Class) not in g
    # The class channel never mints individuals, matched or not.
    assert not list(g.subjects(RDF.type, OWL.NamedIndividual))


def test_new_class_channel_row_still_writes_to_extended(tmp_path, monkeypatch):
    """Recall guard for the class channel: a genuinely-new class (not in the
    curated base) still lands in the extended store."""
    svc = object.__new__(OntServeCommitService)
    svc.ontologies_dir = tmp_path
    svc._base_cat_cache = {}  # nothing reserved in the base
    entity = _placement_entity('Novel AI Verification Principle')

    result = svc._commit_classes_to_intermediate([(entity, {})])

    assert result.get('error') is None, result
    assert result['count'] == 1
    g = Graph()
    g.parse(tmp_path / 'proethica-intermediate-extended.ttl', format='turtle')
    cls = URIRef(f'{INT_NS}NovelAIVerificationPrinciple')
    assert (cls, RDF.type, OWL.Class) in g
    assert not list(g.subjects(RDF.type, OWL.NamedIndividual))
