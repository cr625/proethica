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
from app.services.extraction import canonicalization, category_resolver
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
# _canonicalize_with_role_axis_resweep: the canonicalization ordering gap
# (model-split adversarial review). canonicalize_ttl runs AFTER the
# pre-canonicalization guard sweep in every commit path and can retype a role
# individual from a compound facet class the guard could not classify
# (axis-unresolvable -> ignored) onto an AXIS-SIDED canonical role, recreating
# a provable both-sides contradiction in the persisted TTL. The helper re-runs
# the same guard on the post-canonicalization graph and re-serializes only
# when it vetoed something. canonicalize_ttl is mocked (monkeypatched at its
# module) to perform exactly the retype the real recipe machinery would.
# ---------------------------------------------------------------------------

COMPOUND_LOCAL = "EngineerPublicAdvocateRole"


def _fake_canonicalize(canon_local):
    """A canonicalize_ttl stand-in honoring the real contract: parse the TTL,
    retype every instance of the compound class to the canonical role class
    (declared subClassOf core:Role only, exactly like _declare), drop the
    compound class declaration, write back, and return the stats dict with
    the post-rewrite graph under '_graph'."""
    def fake(case_id, ttl_path, write_back=True):
        g = Graph()
        g.parse(str(ttl_path), format="turtle")
        compound = PROETH[COMPOUND_LOCAL]
        canon = PROETH[canon_local]
        g.add((canon, RDF.type, OWL.Class))
        g.add((canon, RDFS.subClassOf, CORE.Role))
        for ind in list(g.subjects(RDF.type, compound)):
            g.remove((ind, RDF.type, compound))
            g.add((ind, RDF.type, canon))
        for t in list(g.triples((compound, None, None))):
            g.remove(t)
        g.serialize(destination=str(ttl_path), format="turtle")
        return {"roles_decomposed": 1, "states_materialized": 0,
                "obligations_materialized": 0, "compound_classes_removed": 1,
                "_graph": g}
    return fake


def _compound_role_case_graph(*side_type_locals, role_kind):
    """A case graph whose role individual carries the axis-unresolvable
    compound class plus zero or more axis-sided types, with the pre-sweep
    already run (and asserted to PASS -- the gap's precondition)."""
    g = Graph()
    compound = PROETH[COMPOUND_LOCAL]
    # The case TTL declares the genuinely-new compound class with its
    # subClassOf-core edge; core:Role is not an axis head, so the compound
    # stays unresolvable to the guard.
    g.add((compound, RDF.type, OWL.Class))
    g.add((compound, RDFS.subClassOf, CORE.Role))
    uri = _role_individual(g, "Engineer_B", COMPOUND_LOCAL, *side_type_locals)
    return g, uri, {uri: role_kind}


def test_ordering_gap_post_sweep_vetoes_professional_retype(svc, tmp_path, monkeypatch, caplog):
    # The gap scenario: PublicRole (participant) + the compound (unresolvable).
    # Pre-sweep passes; canonicalization retypes the compound to EngineerRole
    # (professional) -> both sides; the post-sweep must veto the professional
    # side (role_kind=participant) and re-serialize the TTL.
    g, uri, role_kinds = _compound_role_case_graph("PublicRole",
                                                   role_kind="participant")
    assert svc._apply_role_axis_guard(g, role_kinds) == 0  # pre-sweep PASSES
    ttl = tmp_path / "proethica-case-999.ttl"
    g.serialize(destination=str(ttl), format="turtle")

    monkeypatch.setattr(canonicalization, "canonicalize_ttl",
                        _fake_canonicalize("EngineerRole"))
    with caplog.at_level(logging.WARNING,
                         logger="app.services.commit.ontserve_commit_service"):
        stats = svc._canonicalize_with_role_axis_resweep(999, ttl, role_kinds)

    # Counted: in the returned stats (surfaced into the commit results).
    assert stats["role_axis_vetoes_post_canonicalization"] == 1
    assert stats["roles_decomposed"] == 1
    assert "_graph" not in stats  # internal handle stripped from the stats

    # The persisted TTL reflects the veto: correct side kept per role_kind.
    g2 = Graph()
    g2.parse(str(ttl), format="turtle")
    assert (uri, RDF.type, PROETH.EngineerRole) not in g2
    assert (uri, RDF.type, PROETH.PublicRole) in g2
    assert (uri, RDF.type, PROETH[COMPOUND_LOCAL]) not in g2  # canonicalized away
    assert (uri, RDF.type, CORE.Role) in g2
    assert (uri, RDF.type, OWL.NamedIndividual) in g2

    # Logged: the guard's both-sides warning plus the re-sweep summary.
    warnings = "\n".join(r.getMessage() for r in caplog.records
                         if r.levelno >= logging.WARNING)
    assert "EngineerRole" in warnings and "PublicRole" in warnings
    assert "AFTER canonicalization" in warnings


def test_ordering_gap_professional_role_kind_keeps_professional_side(svc, tmp_path, monkeypatch):
    # Mirror image: EngineerRole (professional) + the compound; canonicalization
    # retypes the compound to PublicRole (participant). role_kind=professional
    # -> the participant side is the contradicting one and is vetoed.
    g, uri, role_kinds = _compound_role_case_graph("EngineerRole",
                                                   role_kind="professional")
    assert svc._apply_role_axis_guard(g, role_kinds) == 0  # pre-sweep PASSES
    ttl = tmp_path / "proethica-case-999.ttl"
    g.serialize(destination=str(ttl), format="turtle")

    monkeypatch.setattr(canonicalization, "canonicalize_ttl",
                        _fake_canonicalize("PublicRole"))
    stats = svc._canonicalize_with_role_axis_resweep(999, ttl, role_kinds)

    assert stats["role_axis_vetoes_post_canonicalization"] == 1
    g2 = Graph()
    g2.parse(str(ttl), format="turtle")
    assert (uri, RDF.type, PROETH.PublicRole) not in g2
    assert (uri, RDF.type, PROETH.EngineerRole) in g2


def test_post_sweep_without_conflict_is_a_noop(svc, tmp_path, monkeypatch, caplog):
    # No axis-sided type on the other side: canonicalization's retype creates
    # a ONE-sided individual, the post-sweep must not act, and the TTL keeps
    # canonicalization's output byte-for-byte (no re-serialization).
    g, uri, role_kinds = _compound_role_case_graph(role_kind="professional")
    assert svc._apply_role_axis_guard(g, role_kinds) == 0
    ttl = tmp_path / "proethica-case-999.ttl"
    g.serialize(destination=str(ttl), format="turtle")

    monkeypatch.setattr(canonicalization, "canonicalize_ttl",
                        _fake_canonicalize("EngineerRole"))
    with caplog.at_level(logging.WARNING,
                         logger="app.services.commit.ontserve_commit_service"):
        stats = svc._canonicalize_with_role_axis_resweep(999, ttl, role_kinds)
    canonical_bytes = ttl.read_bytes()

    assert stats["role_axis_vetoes_post_canonicalization"] == 0
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    g2 = Graph()
    g2.parse(str(ttl), format="turtle")
    assert (uri, RDF.type, PROETH.EngineerRole) in g2
    assert ttl.read_bytes() == canonical_bytes


def test_post_sweep_default_role_kind_keeps_participant(svc, tmp_path, monkeypatch):
    # The lean-fallback wiring (auto_commit_service) passes an EMPTY role_kind
    # map: on a post-canonicalization both-sides conflict the guard keeps the
    # participant side (the documented weaker-commitment default).
    g, uri, _ = _compound_role_case_graph("PublicRole", role_kind=None)
    ttl = tmp_path / "proethica-case-999.ttl"
    g.serialize(destination=str(ttl), format="turtle")

    monkeypatch.setattr(canonicalization, "canonicalize_ttl",
                        _fake_canonicalize("EngineerRole"))
    stats = svc._canonicalize_with_role_axis_resweep(999, ttl, {})

    assert stats["role_axis_vetoes_post_canonicalization"] == 1
    g2 = Graph()
    g2.parse(str(ttl), format="turtle")
    assert (uri, RDF.type, PROETH.EngineerRole) not in g2
    assert (uri, RDF.type, PROETH.PublicRole) in g2


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
