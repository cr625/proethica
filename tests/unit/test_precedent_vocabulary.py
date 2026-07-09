"""Citation-treatment vocabulary single-sourcing guard (2026-07-09 Precedents
audit). The AUTHORITATIVE definitions are the skos:Concepts in
OntServe/ontologies/proethica-cases.ttl (CitationTreatmentScheme); the
extraction prompt carries the same text via CITATION_TREATMENTS. This test
fails when either side is edited without the other, so the vocabulary cannot
fork silently. Also covers the deterministic joint-citation splitter."""
import os

import pytest
import rdflib

from app.routes.scenario_pipeline.step4.precedents import (
    CITATION_TREATMENTS,
    PRECEDENT_EXTRACTION_PROMPT,
    normalize_precedents,
)

CASES_TTL = os.environ.get(
    'ONTSERVE_ONTOLOGIES_PATH',
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'OntServe', 'ontologies'),
)
SKOS = rdflib.Namespace('http://www.w3.org/2004/02/skos/core#')
CASES = rdflib.Namespace('http://proethica.org/ontology/cases#')


@pytest.fixture(scope='module')
def cases_graph():
    path = os.path.join(CASES_TTL, 'proethica-cases.ttl')
    if not os.path.exists(path):
        pytest.skip(f'proethica-cases.ttl not found at {path}')
    g = rdflib.Graph()
    g.parse(path, format='turtle')
    return g


def test_prompt_vocabulary_matches_ontology(cases_graph):
    ontology_terms = {}
    for concept in cases_graph.subjects(SKOS.inScheme, CASES.CitationTreatmentScheme):
        notation = str(next(cases_graph.objects(concept, SKOS.notation)))
        definition = str(next(cases_graph.objects(concept, SKOS.definition)))
        ontology_terms[notation] = definition
    assert ontology_terms == CITATION_TREATMENTS


def test_citation_type_property_declared(cases_graph):
    assert (CASES.citationType, rdflib.RDF.type,
            rdflib.OWL.DatatypeProperty) in cases_graph


def test_prompt_carries_every_term():
    for term, definition in CITATION_TREATMENTS.items():
        assert f'"{term}"' in PRECEDENT_EXTRACTION_PROMPT
        assert definition in PRECEDENT_EXTRACTION_PROMPT


def test_joint_citation_split():
    out = normalize_precedents([{
        'caseCitation': 'BER Cases 65-9 and 73-9',
        'caseNumber': '65-9, 73-9',
        'citationContext': 'shared ctx',
        'citationType': 'supporting',
    }])
    assert [p['caseNumber'] for p in out] == ['65-9', '73-9']
    assert all(p['citationContext'] == 'shared ctx' for p in out)
    assert out[0]['caseCitation'] == 'BER Case 65-9'


def test_single_and_nonber_pass_through():
    entries = [
        {'caseNumber': '94-8', 'caseCitation': 'BER Case 94-8'},
        {'caseNumber': '435 U.S. 679 (1978)', 'caseCitation': '435 U.S. 679 (1978)'},
    ]
    assert normalize_precedents(entries) == entries
