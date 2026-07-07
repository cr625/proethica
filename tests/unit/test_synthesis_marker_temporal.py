"""Marker-mirror guard for temporal-shaped records (A/E properties review).

The routing-input exclusion compared the raw key, but Step-3 records carry
proeth:-prefixed top-level keys, so eventType markers kept minting (caught on
case-5 run 51). This exercises _emit_synthesis_literal_marker with a real
temporal-shaped dict.
"""
from rdflib import Graph, Namespace, URIRef

from app.services.commit.ontserve_commit_service import OntServeCommitService


def test_event_type_marker_excluded_and_shadows_listed():
    svc = OntServeCommitService.__new__(OntServeCommitService)
    g = Graph()
    prov = Namespace("http://proethica.org/provenance#")
    uri = URIRef("http://proethica.org/ontology/case/5#Event_X")
    rdf_data = {
        "@type": "proeth:Event",
        "proeth:description": "a test event",
        "proeth:eventType": "exogenous",
        "proeth:temporalMarker": "after the report",
        "proeth:initiates": ["Risk State"],
        "proeth:owlTimeURI": "http://www.w3.org/2006/time#intervalBefore",
    }
    svc._emit_synthesis_literal_marker(g, uri, rdf_data, prov)
    markers = {str(o) for o in g.objects(uri, prov["synthesisLiteral"])}
    assert "eventType" not in markers, markers
    assert "owlTimeURI" not in markers, markers          # IRI-value skip
    assert "initiatesText" in markers, markers           # RELATION -> Text shadow
    assert "temporalMarker" in markers, markers          # plain kept literal
