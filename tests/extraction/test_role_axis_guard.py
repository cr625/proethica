"""Tests for the professional/participant role-axis contradiction guard
(the case-4 run-20 lesson, work package 2).

Run 20 committed a role individual typed BOTH proeth:PublicRole (a
ParticipantRole descendant) AND proeth:PublicResponsibilityRole, whose
equivalentClass axiom plus owesDutyToward's rdfs:domain ProfessionalRole
entailed ProfessionalRole, making the commit Pellet-inconsistent under the
ProfessionalRole owl:disjointWith ParticipantRole axiom. The Stage-2 chain
guard missed it because both classes chain to core:Role -- the
professional/participant axis sits BELOW the nine core categories.

Two layers under test:

1. RoleAxisResolver (app.services.extraction.category_resolver): local-name ->
   'professional' / 'participant' over the curated tiers via the asserted
   rdfs:subClassOf* closure; classes with no chain to either head resolve to
   None. Includes the ontology-explicitness half of the fix: the real
   proethica-intermediate now asserts PublicResponsibilityRole rdfs:subClassOf
   ProfessionalRole so the closure can see its professional side.

2. OntServeCommitService._apply_role_axis_guard: the finalized-graph sweep.
   Acts ONLY when one individual's asserted classes provably land on BOTH
   sides of the axis; drops the side contradicting the extraction's own
   role_kind decision (absent signal => keep participant, the weaker
   commitment); logs a warning naming both sides; returns the drop count for
   the commit stats (role_axis_vetoes). Unresolvable classes and one-sided
   individuals are never touched.

DB/MCP/LLM-free: the service is built with object.__new__ (mirroring
tests/extraction/test_match_honoring.py) and the resolver reads a small
fixture TTL from tmp_path; no API calls.
"""
import logging

import pytest
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL

from app.services.commit.ontserve_commit_service import OntServeCommitService
from app.services.extraction import category_resolver
from app.services.extraction.category_resolver import RoleAxisResolver

INT_NS = "http://proethica.org/ontology/intermediate#"
CORE_NS = "http://proethica.org/ontology/core#"
CASE_NS = Namespace("http://proethica.org/ontology/case/999#")
PROETH = Namespace(INT_NS)
CORE = Namespace(CORE_NS)

_FIXTURE_INTERMEDIATE = """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix proeth: <http://proethica.org/ontology/intermediate#> .
@prefix proeth-core: <http://proethica.org/ontology/core#> .

proeth:ProfessionalRole a owl:Class ; rdfs:subClassOf proeth-core:Role .
proeth:ParticipantRole a owl:Class ; rdfs:subClassOf proeth-core:Role .
proeth:ProfessionalRole owl:disjointWith proeth:ParticipantRole .

proeth:EngineerRole a owl:Class ; rdfs:subClassOf proeth:ProfessionalRole .
proeth:StructuralEngineerRole a owl:Class ; rdfs:subClassOf proeth:EngineerRole .
proeth:PublicRole a owl:Class ; rdfs:subClassOf proeth:ParticipantRole .

proeth:RelationalRole a owl:Class ; rdfs:subClassOf proeth-core:Role .
# Mirrors the 2026-07-02 explicitness fix: professional-side by assertion.
proeth:PublicResponsibilityRole a owl:Class ;
    rdfs:subClassOf proeth:RelationalRole, proeth:ProfessionalRole .
# Axis-neutral relational archetype (no occupational parent, by design).
proeth:ProviderClientRole a owl:Class ; rdfs:subClassOf proeth:RelationalRole .
"""


@pytest.fixture()
def fixture_resolver(tmp_path):
    (tmp_path / "proethica-intermediate.ttl").write_text(_FIXTURE_INTERMEDIATE)
    return RoleAxisResolver(ontologies_dir=tmp_path)


@pytest.fixture()
def svc(fixture_resolver, monkeypatch):
    """OntServeCommitService without __init__ (no OntServe paths / DB), with
    the module-level resolve_role_axis pointed at the fixture resolver."""
    monkeypatch.setattr(
        category_resolver, "resolve_role_axis", fixture_resolver.resolve
    )
    return object.__new__(OntServeCommitService)


def _role_individual(g, local, *type_locals, ns=PROETH):
    uri = CASE_NS[local]
    g.add((uri, RDF.type, OWL.NamedIndividual))
    g.add((uri, RDF.type, CORE.Role))
    g.add((uri, RDFS.label, Literal(local)))
    for t in type_locals:
        g.add((uri, RDF.type, ns[t]))
    return uri


# ---------------------------------------------------------------------------
# RoleAxisResolver
# ---------------------------------------------------------------------------

def test_axis_resolver_maps_both_sides(fixture_resolver):
    r = fixture_resolver
    assert r.resolve("PublicRole") == "participant"
    assert r.resolve("EngineerRole") == "professional"
    assert r.resolve("StructuralEngineerRole") == "professional"
    assert r.resolve("PublicResponsibilityRole") == "professional"
    # Heads resolve to their own side.
    assert r.resolve("ProfessionalRole") == "professional"
    assert r.resolve("ParticipantRole") == "participant"


def test_axis_resolver_leaves_neutral_classes_unresolved(fixture_resolver):
    r = fixture_resolver
    assert r.resolve("RelationalRole") is None
    assert r.resolve("ProviderClientRole") is None
    assert r.resolve("NoSuchClass") is None
    assert r.resolve("") is None


def test_axis_resolver_accepts_full_uris(fixture_resolver):
    assert fixture_resolver.resolve(f"{INT_NS}PublicRole") == "participant"
    assert (
        fixture_resolver.resolve(f"{INT_NS}PublicResponsibilityRole")
        == "professional"
    )


# ---------------------------------------------------------------------------
# _apply_role_axis_guard: the case-4 scenario and its variants
# ---------------------------------------------------------------------------

def test_case4_scenario_participant_decided_drops_professional_side(svc, caplog):
    # The run-20 individual: PublicRole (participant) + PublicResponsibilityRole
    # (professional, explicit parent now present). Extraction called it
    # participant, so the professional side is the contradicting one.
    g = Graph()
    uri = _role_individual(
        g, "Affected_Underserved_Community",
        "PublicRole", "PublicResponsibilityRole",
    )
    with caplog.at_level(logging.WARNING,
                         logger="app.services.commit.ontserve_commit_service"):
        dropped = svc._apply_role_axis_guard(g, {uri: "participant"})

    assert dropped == 1
    assert (uri, RDF.type, PROETH.PublicResponsibilityRole) not in g
    assert (uri, RDF.type, PROETH.PublicRole) in g
    # The CMT-1 core type and the NamedIndividual declaration are untouched.
    assert (uri, RDF.type, CORE.Role) in g
    assert (uri, RDF.type, OWL.NamedIndividual) in g
    warning = "\n".join(r.message for r in caplog.records)
    assert "PublicRole" in warning and "PublicResponsibilityRole" in warning


def test_absent_role_kind_defaults_to_keeping_participant(svc, caplog):
    # No role_kind signal recorded for the individual: participant standing is
    # the weaker commitment, so the professional side is dropped.
    g = Graph()
    uri = _role_individual(g, "Community_Group",
                           "PublicRole", "PublicResponsibilityRole")
    with caplog.at_level(logging.WARNING,
                         logger="app.services.commit.ontserve_commit_service"):
        dropped = svc._apply_role_axis_guard(g, {})

    assert dropped == 1
    assert (uri, RDF.type, PROETH.PublicResponsibilityRole) not in g
    assert (uri, RDF.type, PROETH.PublicRole) in g
    assert any("role_kind=None" in r.message for r in caplog.records)


def test_professional_decided_drops_participant_side(svc):
    g = Graph()
    uri = _role_individual(g, "Engineer_A",
                           "EngineerRole", "PublicRole")
    dropped = svc._apply_role_axis_guard(g, {uri: "professional"})

    assert dropped == 1
    assert (uri, RDF.type, PROETH.PublicRole) not in g
    assert (uri, RDF.type, PROETH.EngineerRole) in g


def test_professional_individual_with_matched_professional_class_untouched(svc, caplog):
    # One-sided individual (the common case): the guard must not act.
    g = Graph()
    uri = _role_individual(g, "Engineer_A",
                           "EngineerRole", "StructuralEngineerRole",
                           "PublicResponsibilityRole")
    before = set(g)
    with caplog.at_level(logging.WARNING,
                         logger="app.services.commit.ontserve_commit_service"):
        dropped = svc._apply_role_axis_guard(g, {uri: "professional"})

    assert dropped == 0
    assert set(g) == before
    assert not caplog.records


def test_unresolvable_classes_are_ignored(svc):
    # Classes with no asserted path to either head (relational archetypes,
    # case-local classes without an axis parent) are never touched, even
    # alongside one resolvable side.
    g = Graph()
    uri = _role_individual(g, "Client_W",
                           "PublicRole", "ProviderClientRole")
    g.add((uri, RDF.type, CASE_NS["UnanchoredLocalRole"]))
    before = set(g)
    dropped = svc._apply_role_axis_guard(g, {uri: "participant"})

    assert dropped == 0
    assert set(g) == before


def test_case_local_subclass_resolves_through_graph_chain(svc):
    # A genuinely-new case-local class parented onto ProfessionalRole by the
    # role_kind backstop resolves through the case graph's own subClassOf edge
    # and participates in the contradiction check.
    g = Graph()
    local_cls = CASE_NS["CommunityEngineerRole"]
    g.add((local_cls, RDF.type, OWL.Class))
    g.add((local_cls, RDFS.subClassOf, PROETH.ProfessionalRole))
    uri = _role_individual(g, "Community_Engineer", "PublicRole")
    g.add((uri, RDF.type, local_cls))

    dropped = svc._apply_role_axis_guard(g, {})

    assert dropped == 1
    assert (uri, RDF.type, local_cls) not in g
    assert (uri, RDF.type, PROETH.PublicRole) in g
    # The class declaration itself is untouched (only the rdf:type is vetoed).
    assert (local_cls, RDFS.subClassOf, PROETH.ProfessionalRole) in g


def test_multiple_classes_on_dropped_side_all_removed_and_counted(svc):
    g = Graph()
    uri = _role_individual(g, "Group_X",
                           "PublicRole", "PublicResponsibilityRole",
                           "EngineerRole")
    dropped = svc._apply_role_axis_guard(g, {uri: "participant"})

    assert dropped == 2
    assert (uri, RDF.type, PROETH.PublicResponsibilityRole) not in g
    assert (uri, RDF.type, PROETH.EngineerRole) not in g
    assert (uri, RDF.type, PROETH.PublicRole) in g


# ---------------------------------------------------------------------------
# _extract_role_kind
# ---------------------------------------------------------------------------

def test_extract_role_kind_reads_all_signal_shapes():
    f = OntServeCommitService._extract_role_kind
    assert f({"properties": {"roleKind": "professional"}}) == "professional"
    assert f({"properties": {"role_kind": ["Participant"]}}) == "participant"
    assert f({"role_kind": "professional"}) == "professional"
    assert f({"properties": {"roleKind": "stakeholder"}}) is None
    assert f({"properties": {}}) is None
    assert f({}) is None
    assert f(None) is None


# ---------------------------------------------------------------------------
# The real curated base (integration): the ontology-explicitness half
# ---------------------------------------------------------------------------

def _real_ontologies_dir():
    try:
        from app.services.ontserve.ontserve_config import get_ontserve_base_path
        d = get_ontserve_base_path() / "ontologies"
        return d if (d / "proethica-intermediate.ttl").exists() else None
    except Exception:
        return None


@pytest.mark.skipif(_real_ontologies_dir() is None,
                    reason="OntServe ontologies dir not available")
def test_real_intermediate_makes_public_responsibility_professional():
    # The chain-visible half of the case-4 fix: the deployed intermediate must
    # assert PublicResponsibilityRole rdfs:subClassOf ProfessionalRole so the
    # guard can see the professional side it previously only entailed.
    r = RoleAxisResolver(ontologies_dir=_real_ontologies_dir())
    assert r.resolve("PublicResponsibilityRole") == "professional"
    assert r.resolve("PublicRole") == "participant"
    # The other relational archetypes stay axis-neutral by design.
    assert r.resolve("ProviderClientRole") is None
    assert r.resolve("ProfessionalPeerRole") is None
    assert r.resolve("EmployerRelationshipRole") is None
