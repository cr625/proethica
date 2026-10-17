"""Review of the storage-persistence lessons (brief 2 of docs/reviews/lessons/cloud_briefs.md).

The branch review/case8-lessons/storage-persistence, as merged into the integration branch
beside commit-definitions, against the commit-side type override.

Defect 1 (fixed). ``individual_type_iri`` adopted every ``matched_uri`` as the stored
rdf:type of an individual. The honoring rule of the commit (``_matched_class_override``)
treats
a row whose type already is its matched class as "nothing to honor", so the confidence
floor of commit-definitions (``match_policy.match_link_threshold``, 0.85) and the chain
category check never ran for a matched individual. Scenario: a 0.75 match ("matched to
parent with medium confidence", the Legal Obligation match of case 8 row 95622 that
cascades to its individual 95625) was typed to the matched class in the store and in the
TTL, where the floor keeps the minted type; a match to a core# or concepts# class (both are
matcher candidates) was stored under that namespace and re-minted at commit as a new
intermediate class named after the matched local name (``intermediate#Obligation``). The
stored type now adopts the matched IRI only when the decision is a link by the shared
policy and the IRI is an intermediate-namespace, sanitizer-stable local name; otherwise the
class reference is minted, as for an unmatched individual, and the commit applies its own
rule to the row, as the floor test of commit-definitions expects.

DB-free: pydantic models, the pure converter and a bare commit service with a stubbed chain.
"""
import pytest

from app.services.commit.ontserve_commit_service import OntServeCommitService
from app.services.extraction.extraction_graph import individual_type_iri, pydantic_to_rdf_data
from app.services.extraction.schemas import MatchDecision, ObligationIndividual

INT = "http://proethica.org/ontology/intermediate#"
CORE = "http://proethica.org/ontology/core#"
CONCEPTS = "http://proethica.org/ontology/concepts#"
CLASS_REF = "Environmental Standards Compliance Obligation"
MINTED = f"{INT}EnvironmentalStandardsComplianceObligation"


def _match(confidence, matched_uri=f"{INT}LegalObligation"):
    return MatchDecision(matches_existing=True, matched_uri=matched_uri,
                         matched_label="Legal Obligation", confidence=confidence, reasoning="test")


@pytest.fixture(autouse=True)
def _default_floor(monkeypatch):
    monkeypatch.delenv("PROETHICA_MATCH_LINK_THRESHOLD", raising=False)


def test_sub_floor_match_keeps_the_class_reference_type():
    assert individual_type_iri(CLASS_REF, _match(0.75)) == MINTED
    assert individual_type_iri(CLASS_REF, _match(0.85)) == f"{INT}LegalObligation"
    assert individual_type_iri(CLASS_REF, _match(0.9)) == f"{INT}LegalObligation"
    # The default decision carries confidence 0.0 and no IRI: minted, as before.
    assert individual_type_iri(CLASS_REF, MatchDecision()) == MINTED
    assert individual_type_iri(CLASS_REF, None) == MINTED


def test_floor_is_the_shared_link_threshold(monkeypatch):
    monkeypatch.setenv("PROETHICA_MATCH_LINK_THRESHOLD", "0.95")
    assert individual_type_iri(CLASS_REF, _match(0.9)) == MINTED
    assert individual_type_iri(CLASS_REF, _match(0.95)) == f"{INT}LegalObligation"


def test_matched_iri_outside_the_intermediate_namespace_is_not_the_stored_type():
    # The commit mints every type IRI in the intermediate namespace from its local name, so
    # a core# or concepts# match stored verbatim would commit as intermediate#Obligation or
    # intermediate#NonDeception, a class neither store nor TTL named before.
    assert individual_type_iri(CLASS_REF, _match(0.95, f"{CORE}Obligation")) == MINTED
    assert individual_type_iri(CLASS_REF, _match(0.95, f"{CONCEPTS}Non_Deception")) == MINTED
    # A local name the sanitizer would change cannot round-trip either.
    assert individual_type_iri(CLASS_REF, _match(0.95, f"{INT}Legal_Obligation")) == MINTED
    # A label in place of an IRI falls back, as on the branch.
    assert individual_type_iri(CLASS_REF, _match(0.95, "Legal Obligation")) == MINTED


def _bare_commit_service(chain):
    svc = object.__new__(OntServeCommitService)
    svc._established_core_category = chain
    return svc


def _individual(name, decision):
    return ObligationIndividual(identifier=name, obligation_class=CLASS_REF,
                                obligation_statement="A duty.", match_decision=decision)


def test_commit_override_applies_its_floor_to_the_stored_type():
    """Through the real converter and the real override: below the floor both stores keep
    the minted class, at the floor both name the matched class, and a core# match leaves
    the chain check to decide (here unresolved, so the minted class stands)."""
    out = pydantic_to_rdf_data(
        classes=[],
        individuals=[_individual("Compliance Duty Low", _match(0.75)),
                     _individual("Compliance Duty High", _match(0.85)),
                     _individual("Compliance Duty Core", _match(0.95, f"{CORE}Obligation"))],
        concept_type="obligations", case_id=8, section_type="discussion", step_number=2)
    low, high, core = out["new_individuals"]
    svc = _bare_commit_service(lambda local: "Obligation" if local == "LegalObligation" else None)

    assert low["types"] == [MINTED]
    assert svc._matched_class_override(low, "Obligation", low["types"]) is None

    assert high["types"] == [f"{INT}LegalObligation"]
    assert svc._matched_class_override(high, "Obligation", high["types"]) is None  # already typed

    assert core["types"] == [MINTED]
    assert svc._matched_class_override(core, "Obligation", core["types"]) is None
