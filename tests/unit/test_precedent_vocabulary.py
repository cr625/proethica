"""Controlled-vocabulary single-sourcing guard (2026-07-09 Precedents audit;
question types added 2026-07-10). The AUTHORITATIVE definitions are the
skos:Concepts in OntServe/ontologies/proethica-cases.ttl (the
CitationTreatmentScheme, PrecedentRelationshipScheme, BoardOutcomeScheme, and
QuestionTypeScheme); the code-side vocabulary blocks carry the same text
(CITATION_TREATMENTS, RELATIONSHIP_TYPES, OUTCOME_TYPES, QUESTION_TYPES).
These tests fail when either side is edited without the other, so a
vocabulary cannot fork silently. Also covers the deterministic joint-citation
splitter and the Q&C relationship edge declarations (v3.5.0)."""
import os

import pytest
import rdflib

from app.routes.scenario_pipeline.step4.precedents import (
    CITATION_TREATMENTS,
    _treatments_block,
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
    """Since the step4-template migration the prompt is assembled at render
    time (build_precedent_prompt = seeded step4_precedents template +
    _treatments_block()); render the sidecar body directly so the guarantee
    holds without a seeded database."""
    from jinja2 import Template

    from app.utils.seed_step4_prompts import SIDECAR_DIR, parse_sidecar

    _, body = parse_sidecar(SIDECAR_DIR / 'step4_precedents.md')
    prompt = Template(body).render(
        case_text='CASE TEXT PLACEHOLDER',
        citation_treatments_block=_treatments_block(),
    )
    for term, definition in CITATION_TREATMENTS.items():
        assert f'"{term}"' in prompt
        assert definition in prompt


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


def test_question_type_vocabulary_matches_ontology(cases_graph):
    from app.services.step4_synthesis.question_analyzer import QUESTION_TYPES
    ontology_terms = {}
    for concept in cases_graph.subjects(SKOS.inScheme, CASES.QuestionTypeScheme):
        notation = str(next(cases_graph.objects(concept, SKOS.notation)))
        definition = str(next(cases_graph.objects(concept, SKOS.definition)))
        ontology_terms[notation] = definition
    assert ontology_terms == QUESTION_TYPES


def test_question_type_enum_matches_vocabulary():
    from app.services.step4_synthesis.question_analyzer import (
        QUESTION_TYPES,
        QuestionType,
    )
    assert set(QUESTION_TYPES) == {t.value for t in QuestionType}


def test_qc_edge_properties_declared(cases_graph):
    """The v3.5.0 Q&C relationship edges the commit bridge emits: declared as
    object properties with the domain/range that makes an endpoint typing
    error reasoner-visible, and extendsQuestion irreflexive per the
    prevailsOver precedent."""
    for prop, domain in [(CASES.answersQuestion, CASES.EthicalConclusion),
                         (CASES.extendsQuestion, CASES.EthicalQuestion)]:
        assert (prop, rdflib.RDF.type, rdflib.OWL.ObjectProperty) in cases_graph
        assert (prop, rdflib.RDFS.domain, domain) in cases_graph
        assert (prop, rdflib.RDFS.range, CASES.EthicalQuestion) in cases_graph
    assert (CASES.extendsQuestion, rdflib.RDF.type,
            rdflib.OWL.IrreflexiveProperty) in cases_graph


def test_analysis_record_edge_properties_declared(cases_graph):
    """The v3.6.0 analysis-record relationship family the deterministic
    applier (analysis_edges.py) emits: every predicate declared as an object
    property with the domain/range that makes an endpoint typing error
    reasoner-visible. ANALYSIS_PREDICATES is the applier's own emission list,
    so applier and ontology cannot drift apart."""
    from app.services.extraction.analysis_edges import ANALYSIS_PREDICATES
    CORE = rdflib.Namespace('http://proethica.org/ontology/core#')
    expected = {
        'explainsQuestion': (CASES.QuestionEmergence, CASES.EthicalQuestion),
        'describesResolutionOf': (CASES.ResolutionPattern, CASES.EthicalConclusion),
        'referencesProvision': (CASES.CodeProvisionReference, CORE.CodeProvision),
        'decidesQuestion': (CASES.DecisionPoint, CASES.EthicalQuestion),
        'addressesQuestion': (CASES.DecisionPoint, CASES.EthicalQuestion),
        'alignsWithConclusion': (CASES.DecisionPoint, CASES.EthicalConclusion),
        'involvesObligation': (CASES.DecisionPoint, CORE.Obligation),
        'involvesAction': (CASES.DecisionPoint, CORE.Action),
        'involvesConstraint': (CASES.DecisionPoint, CORE.Constraint),
        'decidedByAgent': (CASES.DecisionPoint, CORE.Agent),
    }
    assert set(ANALYSIS_PREDICATES) == set(expected)
    for name, (domain, range_) in expected.items():
        prop = CASES[name]
        assert (prop, rdflib.RDF.type, rdflib.OWL.ObjectProperty) in cases_graph, name
        assert (prop, rdflib.RDFS.domain, domain) in cases_graph, name
        assert (prop, rdflib.RDFS.range, range_) in cases_graph, name


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
