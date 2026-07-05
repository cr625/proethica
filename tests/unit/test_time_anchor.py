"""Unit tests for the OWL-Time anchor applier (time_anchor.py)."""
from rdflib import Graph, Namespace, RDF, RDFS, Literal

from app.services.extraction.time_anchor import apply_time_anchors

CASE = Namespace("http://proethica.org/ontology/case/15#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
CORE = Namespace("http://proethica.org/ontology/core#")
TIME = Namespace("http://www.w3.org/2006/time#")


def _graph(tmp_path):
    # Selection is TYPE-keyed since O-2 (416a62b): EVERY typed happening is
    # anchored, extent or not (untyped subjects are ignored). The fixture types
    # its happenings the way the commit does (core Action/Event).
    g = Graph()
    # an instant happening and an interval happening, each with extent + marker
    g.add((CASE["Notification_Consent"], RDF.type, CORE.Action))
    g.add((CASE["Notification_Consent"], PROETH.temporalExtent, Literal("instant")))
    g.add((CASE["Notification_Consent"], PROETH.temporalMarker, Literal("Month 3")))
    g.add((CASE["Dual_Tower_Design"], RDF.type, CORE.Event))
    g.add((CASE["Dual_Tower_Design"], PROETH.temporalExtent, Literal("interval")))
    g.add((CASE["Dual_Tower_Design"], PROETH.temporalMarker, Literal("Months 1-6")))
    # a happening with no extent -> anchored at a default time:Instant (O-2)
    g.add((CASE["No_Extent"], RDF.type, PROETH.Action))
    p = tmp_path / "c.ttl"
    g.serialize(destination=str(p), format="turtle")
    return p


def test_mints_instant_and_interval_with_hastime(tmp_path):
    p = _graph(tmp_path)
    res = apply_time_anchors(15, p, write_back=True)
    assert res["time_anchors"] == 3

    g = Graph(); g.parse(str(p), format="turtle")
    inst = g.value(CASE["Notification_Consent"], TIME.hasTime)
    intv = g.value(CASE["Dual_Tower_Design"], TIME.hasTime)
    assert (inst, RDF.type, TIME.Instant) in g
    assert (intv, RDF.type, TIME.ProperInterval) in g
    assert g.value(inst, RDFS.label) == Literal("Month 3")
    assert g.value(intv, RDFS.label) == Literal("Months 1-6")
    # no extent -> anchored anyway, defaulting to an unlabelled time:Instant (O-2)
    no_ext = g.value(CASE["No_Extent"], TIME.hasTime)
    assert no_ext is not None
    assert (no_ext, RDF.type, TIME.Instant) in g
    assert g.value(no_ext, RDFS.label) is None


def test_idempotent(tmp_path):
    p = _graph(tmp_path)
    apply_time_anchors(15, p, write_back=True)
    res2 = apply_time_anchors(15, p, write_back=True)
    assert res2["time_anchors"] == 0  # already anchored
    g = Graph(); g.parse(str(p), format="turtle")
    # exactly one time entity per happening
    assert len(list(g.objects(CASE["Notification_Consent"], TIME.hasTime))) == 1
