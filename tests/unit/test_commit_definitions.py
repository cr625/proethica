"""Deterministic definitions for committed individuals (case-8 review, L1).

Fifty-nine committed individuals of case 8 carried neither skos:definition nor
rdfs:comment: the nine States (StateIndividual has no description field), 17
EthicalQuestion, 17 EthicalConclusion, 5 DecisionPoint, 10 CausalChain and the
timeline. The case page resolver indexes only definition-bearing entries, so no
state mention could be linked and OntServe cards showed a bare label. The
serializer now composes a definition from the fields the individual carries,
emits it as skos:definition (plus rdfs:comment for the types the generic
emitter serves) and writes it back onto the working-store row.

DB-free: the shared per-individual serializer runs on a service built with
__new__ and SimpleNamespace rows (the tests/unit/test_individual_serializer_unified
idiom).
"""
import types

from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS
from rdflib.namespace import SKOS

from app.services.commit.commit_context import build_commit_context
from app.services.commit.definitions import compose_definition
from app.services.commit.ontserve_commit_service import OntServeCommitService
from app.services.commit.working_store import write_back_definition, write_back_types
from app.services.entity.unified_entity_resolver import UnifiedEntityResolver

CASE = Namespace('http://proethica.org/ontology/case/8#')
INT_NS = 'http://proethica.org/ontology/intermediate#'


def _entity(extraction_type, label, definition=None, entity_type=None):
    return types.SimpleNamespace(
        extraction_type=extraction_type, entity_type=entity_type or extraction_type,
        entity_label=label, entity_definition=definition,
    )


def _serialize(entity, rdf_data, local):
    """Run the shared serializer on one individual; returns (graph, uri)."""
    svc = OntServeCommitService.__new__(OntServeCommitService)
    g = Graph()
    uri = CASE[local]
    g.add((uri, RDF.type, OWL.NamedIndividual))
    g.add((uri, RDFS.label, Literal(entity.entity_label)))
    ctx = build_commit_context(8, CASE, g, [(entity, rdf_data)], seed_rel_index_from_graph=False)
    svc._add_individual_properties(g, uri, entity, rdf_data, CASE, ctx=ctx)
    return g, uri


STATE_PROPS = {
    'subject': ['Client X, whose financial means constrain its willingness to fund contracted work'],
    'triggeringEvent': ['Client X encounters unexpected financial setbacks'],
    'activePeriod': ['From the unexpected financial setbacks onward'],
    'urgencyLevel': ['medium'],
}


def test_state_definition_composed_from_subject_trigger_and_period():
    entity = _entity('states', 'Client X Budget Constraint')
    g, uri = _serialize(entity, {'properties': dict(STATE_PROPS)}, 'Client_X_Budget_Constraint')
    expected = ('Client X, whose financial means constrain its willingness to fund contracted work. '
                'Triggered when Client X encounters unexpected financial setbacks. '
                'Holds from the unexpected financial setbacks onward.')
    assert str(g.value(uri, SKOS.definition)) == expected
    # States are served by the generic emitter, so the comment is emitted alongside.
    assert str(g.value(uri, RDFS.comment)) == expected
    # Written back to the working-store row, so the review pages agree with the TTL.
    assert entity.entity_definition == expected


def test_state_without_fields_falls_back_to_its_label():
    entity = _entity('states', 'Unquantified Risk State')
    g, uri = _serialize(entity, {'properties': {'confidence': ['0.8']}}, 'Unquantified_Risk_State')
    assert str(g.value(uri, SKOS.definition)) == 'Unquantified Risk State.'


def test_existing_state_definition_is_kept():
    entity = _entity('states', 'Design Under Review', definition='A given definition.')
    g, uri = _serialize(entity, {'properties': dict(STATE_PROPS)}, 'Design_Under_Review')
    assert str(g.value(uri, SKOS.definition)) == 'A given definition.'
    assert entity.entity_definition == 'A given definition.'
    assert len(list(g.objects(uri, SKOS.definition))) == 1


def test_question_definition_is_the_question_text_without_comment():
    text = ("If the historic heavy rainfall event had not occurred, would Engineer L's risk "
            "concerns have been established as a confirmed fact?")
    entity = _entity('ethical_question', 'Question_402')
    g, uri = _serialize(entity, {'questionText': text, 'questionType': 'counterfactual',
                                 'questionNumber': 402}, 'Question_402')
    # The question mark is terminal punctuation; no period is appended.
    assert str(g.value(uri, SKOS.definition)) == text
    # Synthesis types keep their text in the dedicated predicate: no redundant comment.
    assert g.value(uri, RDFS.comment) is None
    assert entity.entity_definition == text


def test_question_row_definition_wins_over_composition():
    entity = _entity('ethical_question', 'Question_1', definition='Row definition.')
    g, uri = _serialize(entity, {'questionText': 'Did Engineer L act ethically?',
                                 'questionNumber': 1}, 'Question_1')
    assert str(g.value(uri, SKOS.definition)) == 'Row definition.'


def test_conclusion_definition_is_the_conclusion_text():
    text = 'Engineer L acted ethically in notifying Client X of the increased risk'
    entity = _entity('ethical_conclusion', 'Conclusion_1')
    g, uri = _serialize(entity, {'conclusionText': text, 'conclusionNumber': 1,
                                 'conclusionType': 'compliance'}, 'Conclusion_1')
    assert str(g.value(uri, SKOS.definition)) == text + '.'
    assert g.value(uri, RDFS.comment) is None


def test_decision_point_definition_is_focus_else_question():
    entity = _entity('canonical_decision_point', 'DP4')
    g, uri = _serialize(entity, {
        'focus_id': 'DP4',
        'description': 'In scoping the original stormwater design, Engineer L must decide '
                       'whether to design for anticipated climate-driven precipitation changes',
        'decision_question': 'Should the original scope have incorporated projected increases?',
    }, 'DP4')
    assert str(g.value(uri, SKOS.definition)).startswith('In scoping the original stormwater design')
    assert str(g.value(uri, SKOS.definition)).endswith('.')

    entity2 = _entity('canonical_decision_point', 'DP5')
    g2, uri2 = _serialize(entity2, {
        'focus_id': 'DP5',
        'decision_question': 'Should Engineer L withdraw from the project?',
    }, 'DP5')
    assert str(g2.value(uri2, SKOS.definition)) == 'Should Engineer L withdraw from the project?'


def test_causal_chain_definition_from_cause_effect_and_language():
    entity = _entity('temporal_dynamics_enhanced',
                     'Historic Heavy Rainfall -> Stormwater Accumulation Increase',
                     entity_type='causal_chains')
    rdf = {
        '@type': 'proeth:CausalChain',
        '@id': 'http://proethica.org/cases/8#CausalChain_5',
        'rdfs:label': 'Historic Heavy Rainfall -> Stormwater Accumulation Increase',
        'proeth:cause': 'Historic Heavy Rainfall',
        'proeth:effect': 'Stormwater Accumulation Increase',
        'proeth:causalLanguage': 'An historic heavy rainfall leads to increased stormwater accumulation',
    }
    g, uri = _serialize(entity, rdf, 'CausalChain_5')
    assert str(g.value(uri, SKOS.definition)) == (
        'Causal chain in which Historic Heavy Rainfall leads to Stormwater Accumulation Increase. '
        'An historic heavy rainfall leads to increased stormwater accumulation.')
    # Temporal types receive skos:definition only (proeth:description, when present, is the comment).
    assert g.value(uri, RDFS.comment) is None


def test_timeline_definition_from_label_and_counts():
    entity = _entity('temporal_dynamics_enhanced', 'Case 8 Timeline', entity_type='timeline')
    rdf = {'@type': 'time:TemporalEntity', 'rdfs:label': 'Case 8 Timeline',
           'proeth:totalElements': 14, 'proeth:actionCount': 8, 'proeth:eventCount': 6}
    g, uri = _serialize(entity, rdf, 'Case_8_Timeline')
    assert str(g.value(uri, SKOS.definition)) == (
        'Case 8 Timeline: the ordered sequence of 8 actions and 6 events (14 elements) '
        'extracted from the case record.')


def test_action_with_description_is_unchanged():
    """An action carries its description as rdfs:comment already: nothing is added."""
    entity = _entity('temporal_dynamics_enhanced', 'Risk Notification', entity_type='actions')
    rdf = {'@type': 'proeth:Action', 'proeth:description': 'Engineer L notifies Client X.',
           'proeth:hasAgent': 'Engineer L', 'proeth:temporalMarker': 'After the studies'}
    g, uri = _serialize(entity, rdf, 'Risk_Notification')
    assert str(g.value(uri, RDFS.comment)) == 'Engineer L notifies Client X.'
    assert g.value(uri, SKOS.definition) is None
    assert entity.entity_definition is None


def test_compose_definition_rules():
    assert compose_definition('ethical_question', 'Q', {'questionText': 'Was it ethical?'}) == 'Was it ethical?'
    assert compose_definition('states', 'S', {'properties': {'activePeriod': ['During the design phase']}}) \
        == 'S. Holds during the design phase.'
    # A leading proper name is never lowercased.
    assert compose_definition('states', 'S', {'properties': {'activePeriod': ['Client X review onward']}}) \
        == 'S. Holds Client X review onward.'
    # Narrative fallback for a pass-1/2 individual without a definition.
    assert compose_definition('roles', 'Engineer L', {'properties': {
        'caseInvolvement': ['Designs the stormwater system']}}) == 'Designs the stormwater system.'
    # Nothing deterministic to say: empty, so the emitter leaves the node alone.
    assert compose_definition('roles', 'Engineer L', {'properties': {'confidence': ['0.9']}}) == ''
    assert compose_definition('temporal_dynamics_enhanced', 'Work Resumption',
                              {'@type': 'proeth:Event', 'proeth:temporalMarker': 'Several months later'}) \
        == 'Work Resumption, Several months later.'


def test_write_back_helpers():
    row = types.SimpleNamespace(entity_definition=None, rdf_json_ld={'types': ['a']})
    assert write_back_definition(row, 'Composed.') is True
    assert row.entity_definition == 'Composed.'
    assert write_back_definition(row, 'Other.') is False  # never overwrites
    assert row.entity_definition == 'Composed.'
    rdf = row.rdf_json_ld
    write_back_types(row, rdf, [f'{INT_NS}SafetyObligation'])
    assert rdf['types'] == [f'{INT_NS}SafetyObligation']
    # A copy passed as rdf_data keeps the row's own JSON in step.
    copy = dict(row.rdf_json_ld)
    write_back_types(row, copy, [f'{INT_NS}Other'])
    assert row.rdf_json_ld['types'] == [f'{INT_NS}Other'] and copy['types'] == [f'{INT_NS}Other']


def test_case_page_resolver_indexes_the_state_once_it_has_a_definition():
    """The downstream symptom of defect A: _build_label_index skips entries without
    a definition, so a committed state could not be linked in the case text."""
    resolver = UnifiedEntityResolver.__new__(UnifiedEntityResolver)
    resolver.case_id = 8
    entry = {'label': 'Client X Budget Constraint', 'definition': '', 'entity_type': 'State',
             'extraction_type': 'states', 'is_published': True, 'source_pass': 1,
             'provenance': {}, 'uri': str(CASE['Client_X_Budget_Constraint']),
             'text_references': [], 'ontology_target': 'proethica-case-8',
             'ontserve_path': '', 'rdf_agent': None, 'rdf_temporal': None, 'source': 'case'}
    resolver._build_label_index({entry['uri']: entry})
    assert 'client x budget constraint' not in resolver._label_index
    defined = dict(entry, definition=compose_definition('states', entry['label'],
                                                        {'properties': dict(STATE_PROPS)}))
    resolver._build_label_index({defined['uri']: defined})
    assert resolver._label_index['client x budget constraint']['definition'].startswith('Client X,')
