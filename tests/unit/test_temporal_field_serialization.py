"""Unit tests for OntServeCommitService._add_temporal_fields.

Step-3 temporal dynamics (Actions/Events) arrive as a JSON-LD record from the
LangGraph converter (@type + proeth:* predicates), a different shape from the
unified Pydantic rdf_data. They previously fell through the commit serializer to
a bare label/conceptCategory stub. This locks the descriptive triples now emitted
and the OWL-DL-safety skips (IRI object refs, nested dicts, scenario metadata).
"""
from rdflib import Graph, Namespace, URIRef, RDF, RDFS, Literal

from app.services.commit.ontserve_commit_service import OntServeCommitService

CASE = Namespace('http://proethica.org/ontology/case/60#')
CORE = 'http://proethica.org/ontology/core#'
INT = 'http://proethica.org/ontology/intermediate#'


def _emit(rdf_data, object_properties=frozenset()):
    svc = OntServeCommitService.__new__(OntServeCommitService)
    # Control the declared-object-property set deterministically (no file load).
    svc._base_ontology_index._objprop_cache = set(object_properties)
    g = Graph()
    uri = CASE['Subject']
    svc._add_temporal_fields(g, uri, rdf_data)
    return g, uri


def test_action_fields_emitted_and_typed():
    g, uri = _emit({
        '@type': 'proeth:Action',
        'rdfs:label': 'Credential Title Selection',
        'proeth:description': 'Engineer A signed the report as Diplomate.',
        'proeth:hasAgent': 'Engineer A',
        'proeth:temporalMarker': 'At report signing',
        'proeth:temporalSequence': 6,  # numeric -> typed integer literal
        'proeth:foreseenUnintendedEffects': ['effect one', 'effect two'],
        'proeth:withinCompetence': False,
        'proeth:fulfillsObligation': 'Duty to present earned credentials',  # object prop + literal
        'proeth:causedByAction': 'http://proethica.org/cases/60#Action_Other',  # IRI -> skip
        'proeth:hasCompetingPriorities': {'@type': 'proeth:CompetingPriorities'},  # dict -> skip
        'proeth-scenario:stakes': 'high',  # scenario ns -> skip
    }, object_properties={'fulfillsObligation', 'causedByAction'})

    # Typed as the core Action class
    assert (uri, RDF.type, URIRef(CORE + 'Action')) in g
    # description -> rdfs:comment
    assert (uri, RDFS.comment, Literal('Engineer A signed the report as Diplomate.')) in g
    # scalar + list literals emitted under the intermediate namespace
    assert (uri, URIRef(INT + 'hasAgent'), Literal('Engineer A')) in g
    assert (uri, URIRef(INT + 'foreseenUnintendedEffects'), Literal('effect one')) in g
    assert (uri, URIRef(INT + 'foreseenUnintendedEffects'), Literal('effect two')) in g
    # native bool / int preserved as typed literals
    assert (uri, URIRef(INT + 'withinCompetence'), Literal(False)) in g
    assert (uri, URIRef(INT + 'temporalSequence'), Literal(6)) in g
    # object-property literal redirected to a <local>Text datatype sibling
    assert (uri, URIRef(INT + 'fulfillsObligationText'),
            Literal('Duty to present earned credentials')) in g
    assert not list(g.triples((uri, URIRef(INT + 'fulfillsObligation'), None)))

    # IRI object ref, nested dict, and scenario metadata are NOT emitted
    assert not list(g.triples((uri, URIRef(INT + 'causedByAction'), None)))
    assert not list(g.triples((uri, URIRef(INT + 'causedByActionText'), None)))
    assert not list(g.triples((uri, URIRef(INT + 'hasCompetingPriorities'), None)))
    assert not list(g.triples((uri, None, Literal('high'))))


def test_event_typed_as_core_event():
    g, uri = _emit({
        '@type': 'proeth:Event',
        'proeth:eventType': 'automatic_trigger',
        'proeth:createsObligation': ['Obtain_Licensure', 'Disclose_Status'],
    })
    assert (uri, RDF.type, URIRef(CORE + 'Event')) in g
    # eventType is a routing input (drives the origin subClassOf typing via
    # resolve_event_origin_category, which reads the JSON record); it is NOT
    # stored as a literal (B5, 2026-07-05).
    assert (uri, URIRef(INT + 'eventType'), None) not in g
    assert len(list(g.triples((uri, URIRef(INT + 'createsObligation'), None)))) == 2
