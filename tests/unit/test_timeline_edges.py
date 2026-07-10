"""Unit tests for the timeline membership applier (timeline_edges.py)."""
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef

from app.services.extraction.timeline_edges import (
    apply_timeline_haspart,
    check_timeline_haspart,
    reconstruct_timeline_haspart,
)

CASE = Namespace("http://proethica.org/ontology/case/15#")
CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
TIME = Namespace("http://www.w3.org/2006/time#")
DCTERMS = Namespace("http://purl.org/dc/terms/")
PROV = Namespace("http://www.w3.org/ns/prov#")

MEMBERS = (CASE["Design_Review"], CASE["Report_Submission"], CASE["Structural_Failure"])


def _graph(tmp_path):
    g = Graph()
    # the timeline island with STALE count literals (the 57/121 pattern)
    g.add((CASE["Case_15_Timeline"], RDF.type, TIME.TemporalEntity))
    g.add((CASE["Case_15_Timeline"], RDFS.label, Literal("Case 15 Timeline")))
    g.add((CASE["Case_15_Timeline"], PROETH.actionCount, Literal(9)))
    g.add((CASE["Case_15_Timeline"], PROETH.eventCount, Literal(6)))
    g.add((CASE["Case_15_Timeline"], PROETH.totalElements, Literal(15)))
    # members: two Actions, one Event
    g.add((CASE["Design_Review"], RDF.type, CORE.Action))
    g.add((CASE["Report_Submission"], RDF.type, CORE.Action))
    g.add((CASE["Structural_Failure"], RDF.type, CORE.Event))
    # non-members that must never aggregate into the timeline
    g.add((CASE["TemporalRelation_1"], RDF.type, PROETH.TemporalRelation))
    g.add((CASE["time_Design_Review"], RDF.type, TIME.Instant))
    g.add((CASE["some_prov_node"], RDF.type, PROV.Derivation))
    p = tmp_path / "c.ttl"
    g.serialize(destination=str(p), format="turtle")
    return p


def test_membership_and_count_refresh(tmp_path):
    p = _graph(tmp_path)
    res = apply_timeline_haspart(15, p, write_back=True)
    assert res["status"] == "ok"
    assert res["added"] == 3
    assert res["present"] == 0
    assert res["counts_refreshed"] == {
        "actionCount": {"from": 9, "to": 2},
        "eventCount": {"from": 6, "to": 1},
        "totalElements": {"from": 15, "to": 3},
    }

    g = Graph(); g.parse(str(p), format="turtle")
    parts = set(g.objects(CASE["Case_15_Timeline"], DCTERMS.hasPart))
    # exactly the core Action/Event members: no relation, anchor, or prov node
    assert parts == set(MEMBERS)
    assert g.value(CASE["Case_15_Timeline"], PROETH.actionCount) == Literal(2)
    assert g.value(CASE["Case_15_Timeline"], PROETH.eventCount) == Literal(1)
    assert g.value(CASE["Case_15_Timeline"], PROETH.totalElements) == Literal(3)
    # one provenance node per edge, on the family's IRI prefix
    prov_nodes = {s for s in g.subjects(RDF.type, PROV.Derivation)
                  if "#timeline_edge_provenance_" in str(s)}
    assert len(prov_nodes) == 3


def test_idempotent(tmp_path):
    p = _graph(tmp_path)
    apply_timeline_haspart(15, p, write_back=True)
    g1 = Graph(); g1.parse(str(p), format="turtle")
    res2 = apply_timeline_haspart(15, p, write_back=True)
    assert res2["added"] == 0
    assert res2["present"] == 3
    assert res2["counts_refreshed"] == {}
    g2 = Graph(); g2.parse(str(p), format="turtle")
    assert len(g2) == len(g1)


def test_check_gate(tmp_path):
    p = _graph(tmp_path)
    pre = check_timeline_haspart(15, p)
    assert pre["expected"] == 3
    assert len(pre["missing"]) == 3
    assert pre["extra"] == []

    apply_timeline_haspart(15, p, write_back=True)
    post = check_timeline_haspart(15, p)
    assert post["expected"] == 3
    assert post["missing"] == []
    assert post["extra"] == []


def test_check_flags_stale_edge_and_reconstruct_clears_it(tmp_path):
    p = _graph(tmp_path)
    apply_timeline_haspart(15, p, write_back=True)

    # simulate a layer rebuild removing one Action: its own triples go, but
    # the family edge and its prov node survive as orphans
    g = Graph(); g.parse(str(p), format="turtle")
    for t in list(g.triples((CASE["Design_Review"], None, None))):
        g.remove(t)
    g.serialize(destination=str(p), format="turtle")

    stale = check_timeline_haspart(15, p)
    assert stale["expected"] == 2
    assert stale["missing"] == []
    assert stale["extra"] == ["hasPart: Case_15_Timeline -> Design_Review"]

    res = reconstruct_timeline_haspart(15, p)
    assert res["reconstructed"] == {"edges_dropped": 3, "prov_dropped": 3}
    assert res["added"] == 2
    assert res["counts_refreshed"]["actionCount"]["to"] == 1
    assert res["counts_refreshed"]["totalElements"]["to"] == 2

    g = Graph(); g.parse(str(p), format="turtle")
    assert set(g.objects(CASE["Case_15_Timeline"], DCTERMS.hasPart)) == {
        CASE["Report_Submission"], CASE["Structural_Failure"]}
    prov_nodes = {s for s in g.subjects()
                  if "#timeline_edge_provenance_" in str(s)}
    assert len(prov_nodes) == 2
    clean = check_timeline_haspart(15, p)
    assert clean["missing"] == [] and clean["extra"] == []


def test_no_timeline_is_a_skip_not_a_raise(tmp_path):
    g = Graph()
    g.add((CASE["Design_Review"], RDF.type, CORE.Action))
    p = tmp_path / "c.ttl"
    g.serialize(destination=str(p), format="turtle")
    res = apply_timeline_haspart(15, p, write_back=True)
    assert res["status"] == "skipped"
    assert res["added"] == 0
    chk = check_timeline_haspart(15, p)
    assert chk["expected"] == 1
    assert chk["missing"] == ["hasPart: (no timeline) -> Design_Review"]


def test_two_timelines_is_a_skip_not_a_guess(tmp_path):
    g = Graph()
    g.add((CASE["Case_15_Timeline"], RDF.type, TIME.TemporalEntity))
    g.add((CASE["Other_Timeline"], RDF.type, TIME.TemporalEntity))
    g.add((CASE["Design_Review"], RDF.type, CORE.Action))
    p = tmp_path / "c.ttl"
    g.serialize(destination=str(p), format="turtle")
    res = apply_timeline_haspart(15, p, write_back=True)
    assert res["status"] == "skipped"
    assert "multiple" in res["reason"]
    g2 = Graph(); g2.parse(str(p), format="turtle")
    assert list(g2.subject_objects(DCTERMS.hasPart)) == []
