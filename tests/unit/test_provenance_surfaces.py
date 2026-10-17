"""Provenance page surfaces: the lessons of the case 24-1 (ProEthica case 8) review, 2026-10.

L1: no case-and-name-only activity fallback (a prompt without a session match has no
    activity, and the card shows its own date and model with the duration not recorded).
L3: the storage wrapper keys are not literal extractions; types and parent come out as the
    separate "typed as" line.
L4: consolidation activities are grouped by pipeline run.
L5: a stored prompt or response whose length equals a round storage limit is flagged.
L6: the steps 1-2 section headers are named by section, not by a pass number.

Hermetic: the model queries are patched, no database.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.routes.provenance import helpers
from app.services.extraction.field_classification import FieldKind, group_properties


# --- L1 -----------------------------------------------------------------------------------

class _ActivityQuery:
    """Records every filter_by call; answers ``hit`` only to a session-scoped filter."""

    def __init__(self, hit=None):
        self.calls = []
        self.hit = hit

    def filter_by(self, **kwargs):
        self.calls.append(kwargs)
        chain = MagicMock()
        chain.order_by.return_value.first.return_value = self.hit if kwargs.get('session_id') else None
        return chain


def _prompt(session_id='sess-roles-facts'):
    return SimpleNamespace(extraction_session_id=session_id, prompt_text='p', raw_response='r')


def _activity(**overrides):
    agent = SimpleNamespace(agent_name='claude-sonnet-4-5', agent_type='llm_model', agent_version=None)
    fields = dict(
        id=5833, activity_type='llm_query', activity_name='dual_roles_extraction', agent=agent,
        duration_ms=22496, status='completed',
        started_at=datetime(2026, 7, 7, 14, 0, 0), ended_at=datetime(2026, 7, 7, 14, 0, 22),
        activity_metadata={'origin': 'automated_pipeline'},
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_prompt_without_session_match_has_no_provenance_and_no_name_only_lookup():
    """The July 2026 prompt of case 8 must not borrow the February activity 643."""
    query = _ActivityQuery(hit=None)
    with patch.object(helpers, 'ProvenanceActivity') as model:
        model.query = query
        assert helpers._get_provenance_for_prompt(8, 'roles', _prompt()) is None
    assert query.calls, 'the session-scoped lookups ran'
    assert all(call.get('session_id') == 'sess-roles-facts' for call in query.calls)
    assert all(call.get('case_id') == 8 for call in query.calls)


def test_prompt_without_session_id_returns_none_without_any_lookup():
    query = _ActivityQuery(hit=_activity())
    with patch.object(helpers, 'ProvenanceActivity') as model:
        model.query = query
        assert helpers._get_provenance_for_prompt(8, 'roles', _prompt(session_id=None)) is None
    assert query.calls == []


def test_session_match_builds_the_provenance_with_the_recorded_origin():
    query = _ActivityQuery(hit=_activity())
    with patch.object(helpers, 'ProvenanceActivity') as model:
        model.query = query
        prov = helpers._get_provenance_for_prompt(8, 'roles', _prompt())
    assert query.calls[0] == {'case_id': 8, 'session_id': 'sess-roles-facts',
                              'activity_name': 'dual_roles_extraction'}
    assert prov['activity_id'] == 5833
    assert prov['agent_name'] == 'claude-sonnet-4-5'
    assert prov['duration_ms'] == 22496
    assert prov['origin'] == 'automated_pipeline'
    assert prov['started_at'] == '2026-07-07T14:00:00'


@pytest.mark.parametrize('name,activity_type,metadata,expected', [
    ('dual_roles_extraction', 'llm_query', {'origin': 'automated_pipeline'}, 'automated_pipeline'),
    ('dual_roles_extraction', 'llm_query', None, 'user_initiated'),
    ('dual_roles_extraction', 'llm_query', {'origin': 'not-an-origin'}, 'user_initiated'),
    ('entities_pass_step1', 'extraction', {}, 'automated_pipeline'),
    ('decision_point_synthesis', 'composition', {}, 'algorithmic'),
])
def test_determine_origin_prefers_the_recorded_origin_then_the_name_heuristics(
        name, activity_type, metadata, expected):
    activity = SimpleNamespace(activity_name=name, activity_type=activity_type, activity_metadata=metadata)
    assert helpers._determine_origin(activity) == expected


# --- L3 -----------------------------------------------------------------------------------

_STORED_ROLE_INDIVIDUAL = {
    'uri': 'http://proethica.org/ontology/case/8#Engineer_A',
    'label': 'Engineer A',
    'definition': 'Licensed engineer retained to review the design.',
    'definitions': [
        {'text': 'Licensed engineer retained to review the design.', 'source_type': 'extraction',
         'source_section': 'facts', 'source_step': 1, 'source_case': 8, 'is_primary': True},
        {'text': 'A professional engineer role.', 'source_type': 'ontology',
         'source_uri': 'http://proethica.org/ontology/intermediate#EngineerRole', 'is_primary': False},
    ],
    'types': ['http://proethica.org/ontology/intermediate#StructuralEngineerRole'],
    'parent': 'http://proethica.org/ontology/core#Role',
    'properties': {
        'caseInvolvement': 'Reviews the structural design for the client.',
        'hasRole': 'Structural Engineer Role',
        'confidence': 0.9,
        'roleCategory': 'professional',
    },
    'source_text': 'Engineer A, a licensed professional engineer, was retained ...',
    'section_sources': ['facts'],
    'source_texts': {'facts': 'Engineer A, a licensed professional engineer, was retained ...'},
    'match_decision': {'matches_existing': False, 'matched_uri': None, 'matched_label': None,
                       'confidence': 0.4, 'reasoning': 'no existing individual'},
    'role_category': 'professional',
    'state_category': 'conflict',
}

_WRAPPER_KEYS = {'definitions', 'source_texts', 'match_decision', 'types', 'parent',
                 'role_category', 'state_category'}


def test_group_properties_skips_the_storage_wrapper_keys():
    groups = group_properties(_STORED_ROLE_INDIVIDUAL)
    emitted = {predicate for kind in groups.values() for predicate, _ in kind}
    assert emitted.isdisjoint(_WRAPPER_KEYS), emitted & _WRAPPER_KEYS
    assert ('caseInvolvement', 'Reviews the structural design for the client.') in groups[FieldKind.CONTENT.value]
    assert ('hasRole', 'Structural Engineer Role') in groups[FieldKind.RELATION.value]
    assert ('confidence', 0.9) in groups[FieldKind.ASSESSMENT.value]
    assert ('roleCategory', 'professional') in groups[FieldKind.CONTENT.value]


@pytest.mark.parametrize('category_key', [
    'role_category', 'state_category', 'resource_category', 'principle_category',
    'obligation_type', 'constraint_type', 'action_category', 'event_category',
])
def test_top_level_category_copies_are_not_literals(category_key):
    groups = group_properties({'label': 'x', 'properties': {}, category_key: 'some category'})
    assert all(not pairs for pairs in groups.values())


def test_entity_field_groups_renders_types_and_parent_as_typed_as():
    groups = helpers._entity_field_groups(_STORED_ROLE_INDIVIDUAL)
    assert groups['typed_as'] == {'types': ['StructuralEngineerRole'], 'parent': 'Role'}
    literal_predicates = {field['p'] for field in groups['literals']}
    assert literal_predicates.isdisjoint(_WRAPPER_KEYS)
    assert 'caseInvolvement' in literal_predicates
    assert [field['p'] for field in groups['relations']] == ['hasRole']


def test_entity_field_groups_without_type_anchors():
    groups = helpers._entity_field_groups({'label': 'x', 'properties': {'description': 'd'}})
    assert groups['typed_as'] == {'types': [], 'parent': None}
    assert helpers._entity_field_groups(None)['typed_as'] == {'types': [], 'parent': None}


# --- L4 -----------------------------------------------------------------------------------

T0 = datetime(2026, 7, 7, 9, 0, 0)


def _row(name, started_at, session_id=None, activity_type='reconciliation', result=None):
    return {'activity_type': activity_type, 'activity_name': name, 'started_at': started_at,
            'session_id': session_id, 'result': result or {}, 'status': 'completed'}


def test_consolidation_rows_group_by_run_with_filters_forward_and_commit_rows_backward():
    rows = [
        _row('precedent_filter', T0 + timedelta(minutes=5), activity_type='filter'),
        _row('entity_reconcile', T0 + timedelta(minutes=40), session_id='101',
             result={'auto_merged': 3, 'canonicalized': 2}),
        _row('edge_materialization', T0 + timedelta(minutes=55), activity_type='materialization',
             result={'total_edges': 41}),
        _row('conformance_check', T0 + timedelta(minutes=56), activity_type='validation',
             result={'conforms': True}),
        _row('individual_type_filter', T0 + timedelta(days=3), activity_type='filter',
             result={'dropped': ['Engineer'], 'count': 1}),
        _row('entity_reconcile', T0 + timedelta(days=3, minutes=30), session_id='202'),
        _row('unified_guard', T0 + timedelta(days=3, minutes=45), activity_type='guard'),
    ]
    runs = helpers.group_consolidation_by_run(list(reversed(rows)))  # newest first, as queried

    assert [run['session_id'] for run in runs] == ['202', '101']
    assert [a['activity_name'] for a in runs[1]['activities']] == [
        'precedent_filter', 'entity_reconcile', 'edge_materialization', 'conformance_check']
    assert [a['activity_name'] for a in runs[0]['activities']] == [
        'individual_type_filter', 'entity_reconcile', 'unified_guard']
    assert runs[1]['started_at'] == T0 + timedelta(minutes=5)
    assert runs[1]['ended_at'] == T0 + timedelta(minutes=56)
    assert runs[1]['activity_count'] == 4
    assert runs[1]['activities'][2]['result'] == {'total_edges': 41}


def test_unsessioned_rows_far_from_any_run_form_their_own_cluster():
    rows = [
        _row('entity_reconcile', T0, session_id='101'),
        _row('edge_materialization', T0 + timedelta(days=10), activity_type='materialization'),
        _row('conformance_check', T0 + timedelta(days=10, minutes=1), activity_type='validation'),
    ]
    runs = helpers.group_consolidation_by_run(rows)
    assert [run['session_id'] for run in runs] == [None, '101']
    assert runs[0]['activity_count'] == 2
    assert runs[0]['started_at'] == T0 + timedelta(days=10)
    assert runs[0]['ended_at'] == T0 + timedelta(days=10, minutes=1)


def test_a_sessioned_run_spanning_hours_stays_one_run():
    rows = [
        _row('temporal_sequence', T0, session_id='101'),
        _row('entity_reconcile', T0 + timedelta(hours=20), session_id='101'),
        _row('unified_guard', T0 + timedelta(hours=20, minutes=5), activity_type='guard'),
    ]
    runs = helpers.group_consolidation_by_run(rows)
    assert len(runs) == 1 and runs[0]['activity_count'] == 3


def test_group_consolidation_handles_empty_input_and_rows_without_timestamps():
    assert helpers.group_consolidation_by_run([]) == []
    assert helpers.group_consolidation_by_run([_row('x', None, session_id='1')]) == []


# --- L5 -----------------------------------------------------------------------------------

@pytest.mark.parametrize('length,expected', [
    (0, None), (9999, None), (10000, 10000), (10001, None),
    (20000, 20000), (50000, 50000), (50001, None),
])
def test_truncation_limit_flags_a_length_equal_to_a_round_limit(length, expected):
    assert helpers.truncation_limit('x' * length) == expected


def test_truncation_limit_ignores_missing_text():
    assert helpers.truncation_limit(None) is None
    assert helpers.truncation_limit(10000) is None


def test_stored_text_truncation_reports_prompt_and_response_separately():
    """extraction_prompts 8616, 8617 and 8620 of case 8: a 10000-character slice."""
    prompt = SimpleNamespace(prompt_text='p' * 10000, raw_response='r' * 4321)
    assert helpers._stored_text_truncation(prompt) == {'prompt': 10000, 'response': None}
    response_only = SimpleNamespace(prompt_text='p' * 777, raw_response='r' * 10000)
    assert helpers._stored_text_truncation(response_only) == {'prompt': None, 'response': 10000}


# --- L6 -----------------------------------------------------------------------------------

def test_pass_headers_name_the_section_not_a_pass_number():
    names = helpers.PIPELINE_STRUCTURE['pass_names']
    assert [names[section] for section in helpers.PIPELINE_STRUCTURE['passes']] == [
        'Facts pass', 'Discussion pass']
    assert not any(name.startswith('Pass ') for name in names.values())
