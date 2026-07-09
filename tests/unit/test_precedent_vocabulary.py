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


def test_relationship_vocabulary_matches_ontology(cases_graph):
    from app.services.precedent.precedent_discovery_service import RELATIONSHIP_TYPES
    ontology_terms = {}
    for concept in cases_graph.subjects(SKOS.inScheme, CASES.PrecedentRelationshipScheme):
        notation = str(next(cases_graph.objects(concept, SKOS.notation)))
        definition = str(next(cases_graph.objects(concept, SKOS.definition)))
        ontology_terms[notation] = definition
    assert ontology_terms == RELATIONSHIP_TYPES


def test_relationship_scheme_cross_links(cases_graph):
    """Every relationship concept except 'contrasting' closeMatches its
    citation-treatment counterpart; contrasting is deliberately unmatched."""
    links = {}
    for concept in cases_graph.subjects(SKOS.inScheme, CASES.PrecedentRelationshipScheme):
        notation = str(next(cases_graph.objects(concept, SKOS.notation)))
        links[notation] = list(cases_graph.objects(concept, SKOS.closeMatch))
    assert links['supporting'] == [CASES.SupportingCitation]
    assert links['distinguishing'] == [CASES.DistinguishingCitation]
    assert links['analogous'] == [CASES.AnalogizingCitation]
    assert links['contrasting'] == []


def test_outcome_vocabulary_matches_ontology(cases_graph):
    from app.services.precedent.case_feature_extractor import OUTCOME_TYPES
    ontology_terms = {}
    for concept in cases_graph.subjects(SKOS.inScheme, CASES.BoardOutcomeScheme):
        notation = str(next(cases_graph.objects(concept, SKOS.notation)))
        definition = str(next(cases_graph.objects(concept, SKOS.definition)))
        ontology_terms[notation] = definition
    assert ontology_terms == OUTCOME_TYPES


def test_outcome_alignment_semantics():
    """The ternary indicator the ontology documents: 1.0 identical, 0.0 for
    the ethical/unethical opposition, 0.5 for pairings involving
    mixed/unclear."""
    from app.services.precedent.similarity_service import PrecedentSimilarityService
    s = PrecedentSimilarityService()
    assert s._calculate_outcome_alignment('ethical', 'ethical') == 1.0
    assert s._calculate_outcome_alignment('ethical', 'unethical') == 0.0
    assert s._calculate_outcome_alignment('mixed', 'ethical') == 0.5
    assert s._calculate_outcome_alignment('unclear', 'unethical') == 0.5
    assert s._calculate_outcome_alignment(None, 'ethical') == 0.5
