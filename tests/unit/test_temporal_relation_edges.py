"""Unit tests for the temporal (Allen) relation endpoint family.

The fromEntity/toEntity resolution + the time:* extra triple are materialised by the
data-driven framework and exercised end-to-end (under a mocked resolver) by
tests/unit/test_edge_spec_equivalence.py. This file locks the family DATA + the unified
domain/range guard behaviour: fromEntity/toEntity declare a union(Action, Event) range,
and the guard drops any endpoint mis-resolved to a State so the case stays OWL-DL
consistent.
"""
from rdflib import Graph, Namespace, Literal, RDF, RDFS, OWL

from app.services.extraction import edge_spec as es
from app.services.extraction.rpo_edges import drop_domain_range_violations, ALL_EDGE_RANGE

CASE = 999
NS = Namespace(f"http://proethica.org/ontology/case/{CASE}#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
CORE = Namespace("http://proethica.org/ontology/core#")


def _ind(g, local, label, cat, core):
    u = NS[local]
    g.add((u, RDF.type, OWL.NamedIndividual))
    g.add((u, RDF.type, core))
    g.add((u, RDFS.label, Literal(label)))
    g.add((u, PROETH.conceptCategory, Literal(cat)))
    return u


def _rel(g, local, label):
    u = NS[local]
    g.add((u, RDF.type, OWL.NamedIndividual))
    g.add((u, RDF.type, PROETH.TemporalRelation))
    g.add((u, RDFS.label, Literal(label)))
    return u


def test_endpoints_are_single_valued_union_action_event():
    """Both endpoint predicates resolve to a single Action/Event individual (the spec is
    single-valued) and declare a union(Action, Event) range."""
    assert es._TEMPORAL_RELATION_SPEC.single_valued is True
    by_prop = {p.prop: p for p in es._TEMPORAL_RELATION_SPEC.predicates}
    assert set(by_prop) == {"fromEntity", "toEntity"}
    for p in by_prop.values():
        assert p.range_union == ("Action", "Event")


def test_endpoints_are_guarded():
    """fromEntity/toEntity must be in ALL_EDGE_RANGE so the unified guard validates them."""
    for prop in ("fromEntity", "toEntity"):
        assert PROETH[prop] in ALL_EDGE_RANGE


def test_unified_guard_drops_state_range_violation():
    """Belt-and-suspenders: even if an endpoint were mis-resolved to a State, the
    unified guard (fromEntity/toEntity registered in ALL_EDGE_RANGE) drops it so the
    case stays OWL-DL consistent; a valid Action endpoint survives."""
    g = Graph()
    st = _ind(g, "SomeState", "Some State", "State", CORE.State)
    act = _ind(g, "SomeAction", "Some Action", "Action", CORE.Action)
    rel = _rel(g, "TemporalRelation_1", "x before y")
    g.add((rel, PROETH.fromEntity, st))   # range violation
    g.add((rel, PROETH.toEntity, act))    # valid
    dropped = drop_domain_range_violations(g, CASE, edge_range=ALL_EDGE_RANGE)
    assert dropped == 1
    assert not list(g.objects(rel, PROETH.fromEntity))
    assert act in set(g.objects(rel, PROETH.toEntity))
