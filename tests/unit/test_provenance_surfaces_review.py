"""Review of the provenance-surfaces lessons (brief 2 of docs/reviews/lessons/cloud_briefs.md).

Two defects found in the merge review, each with the scenario that broke, and one
verification the branch tests left to a hand-built record:

1. The consolidation card split one pipeline run into many. group_consolidation_by_run
   took every session id for a pipeline run id, and the storage-persistence branch merged
   beside it records its storage dedup merges (activity type merge) and its designator
   refusals (type filter) with the extraction session id of one concept pass, a UUID the
   pipeline mints per concept and section. On the integration branch every concept pass
   that merged a row became a "Pipeline run <uuid>" header of its own beside the real run,
   and its rows left the run they belong to. The route now hands the helper the
   PipelineRun ids of the case; every other activity attaches by time, the extraction-time
   types (filter, merge) forward to the run that starts after them.

2. The truncation badge missed the phase 4 narrative prompts. Commit 35a80006 removed two
   slices, text[:10000] and text[:9950] + "\\n... [truncated]"; truncation_limit flagged
   the first form only, so a narrative prompt stored before 2026-07-11 (9966 characters,
   ending in the marker) carried no badge. The marker form is flagged at the length before
   the marker.

3. The wrapper-key test of lesson L3 ran on a hand-built record. The last tests run the
   real producer (pydantic_to_rdf_data and the storage cleaner) for six concept types and
   check that the top-level copies are hidden while the camelCase property keeps the
   category and the type anchors reach the "typed as" line.

Hermetic: no database, no model call.
"""
from datetime import datetime, timedelta

import pytest

from app.routes.provenance import helpers
from app.services.entity.rdf_storage_service import _clean_json_data
from app.services.extraction import schemas
from app.services.extraction.extraction_graph import pydantic_to_rdf_data
from app.services.extraction.field_classification import FieldKind, _STRUCTURAL_KEYS, group_properties


# --- 1. storage dedup rows and the pipeline run --------------------------------------------

T0 = datetime(2026, 7, 7, 9, 0, 0)
RUN = '48'
PASS_A = '2b7c3d1e-5f60-4a71-8b92-c3d4e5f60718'
PASS_B = 'a1b2c3d4-e5f6-4071-8293-a4b5c6d7e8f9'


def _row(name, started_at, session_id=None, activity_type='reconciliation'):
    return {'activity_type': activity_type, 'activity_name': name, 'started_at': started_at,
            'session_id': session_id, 'result': {}, 'status': 'completed'}


def _one_run_rows():
    return [
        _row('precedent_filter', T0 + timedelta(minutes=5), activity_type='filter'),
        _row('storage_dedup_merge', T0 + timedelta(minutes=6), session_id=PASS_A, activity_type='merge'),
        _row('designator_guard', T0 + timedelta(minutes=7), session_id=PASS_B, activity_type='filter'),
        _row('storage_dedup_merge', T0 + timedelta(minutes=12), session_id=PASS_B, activity_type='merge'),
        _row('entity_reconcile', T0 + timedelta(minutes=40), session_id=RUN),
        _row('edge_materialization', T0 + timedelta(minutes=55), activity_type='materialization'),
    ]


def test_storage_dedup_rows_of_a_concept_pass_attach_to_the_pipeline_run():
    """Case 8 shape: the pipeline passes carry the PipelineRun id (48), the storage dedup
    rows the extraction session UUID of their concept pass."""
    runs = helpers.group_consolidation_by_run(list(reversed(_one_run_rows())), run_ids={RUN})

    assert [run['session_id'] for run in runs] == [RUN]
    assert [a['activity_name'] for a in runs[0]['activities']] == [
        'precedent_filter', 'storage_dedup_merge', 'designator_guard', 'storage_dedup_merge',
        'entity_reconcile', 'edge_materialization']
    assert runs[0]['activity_count'] == 6
    assert runs[0]['started_at'] == T0 + timedelta(minutes=5)
    assert runs[0]['ended_at'] == T0 + timedelta(minutes=55)


def test_without_run_ids_every_session_id_opens_a_run_as_before():
    """The defect, kept as the documented behaviour of a call without run ids."""
    runs = helpers.group_consolidation_by_run(_one_run_rows())
    assert sorted(str(run['session_id']) for run in runs) == sorted([RUN, PASS_A, PASS_B])


def test_a_merge_row_before_the_next_run_attaches_forward_not_to_the_run_before():
    """A storage merge is an extraction-time pass: recorded minutes before the run it
    belongs to and hours after the previous run ended, it joins the later run."""
    rows = [
        _row('entity_reconcile', T0, session_id='101'),
        _row('conformance_check', T0 + timedelta(minutes=10), activity_type='validation'),
        _row('storage_dedup_merge', T0 + timedelta(hours=2, minutes=50), session_id=PASS_A,
             activity_type='merge'),
        _row('entity_reconcile', T0 + timedelta(hours=3), session_id='202'),
    ]
    runs = helpers.group_consolidation_by_run(rows, run_ids={'101', '202'})
    by_run = {run['session_id']: [a['activity_name'] for a in run['activities']] for run in runs}
    assert by_run == {'202': ['storage_dedup_merge', 'entity_reconcile'],
                      '101': ['entity_reconcile', 'conformance_check']}


def test_an_extraction_that_never_reached_a_run_scoped_pass_clusters_on_its_own():
    rows = [
        _row('entity_reconcile', T0, session_id='101'),
        _row('storage_dedup_merge', T0 + timedelta(days=4), session_id=PASS_A, activity_type='merge'),
        _row('individual_type_filter', T0 + timedelta(days=4, minutes=1), activity_type='filter'),
    ]
    runs = helpers.group_consolidation_by_run(rows, run_ids={'101'})
    assert [run['session_id'] for run in runs] == [None, '101']
    assert runs[0]['activity_count'] == 2


def test_run_ids_are_compared_as_strings():
    rows = [_row('entity_reconcile', T0, session_id='48'),
            _row('unified_guard', T0 + timedelta(minutes=5), activity_type='guard')]
    runs = helpers.group_consolidation_by_run(rows, run_ids={'48'})
    assert len(runs) == 1 and runs[0]['activity_count'] == 2
    assert helpers.group_consolidation_by_run(rows, run_ids=set())[0]['session_id'] is None


# --- 2. the truncation marker ----------------------------------------------------------------

MARKER = "\n... [truncated]"


@pytest.mark.parametrize('text,expected', [
    ('p' * 9950 + MARKER, 9950),
    ('p' * 9950, None),
    ('p' * 9966, None),
    ('p' * 10000, 10000),
    ('p' * 10000 + MARKER, 10000),
])
def test_truncation_limit_flags_the_marker_form_at_the_length_before_the_marker(text, expected):
    assert helpers.truncation_limit(text) == expected


def test_stored_text_truncation_reports_a_marker_prompt():
    """A phase4_narrative row written before 35a80006: the joined prompt sliced at 9950 with
    the marker appended, the response stored whole."""
    class Prompt:
        prompt_text = 'p' * 9950 + MARKER
        raw_response = 'r' * 12345
    assert helpers._stored_text_truncation(Prompt()) == {'prompt': 9950, 'response': None}


# --- 3. the real producer against the wrapper-key set --------------------------------------

QUOTE = 'Engineer A, a licensed professional engineer, was retained to review the design.'


def _first(enum_cls):
    return list(enum_cls)[0]


def _producer_input():
    return {
        'roles': ('role_category', 'roleCategory', schemas.CandidateRoleClass(
            label='Structural Engineer Role', definition='An engineer reviewing structures.',
            text_references=[QUOTE], source_text=QUOTE, confidence=0.9,
            role_category=_first(schemas.RoleCategory), role_kind=_first(schemas.RoleKind))),
        'states': ('state_category', 'stateCategory', schemas.CandidateStateClass(
            label='Risk State', definition='A hazard exposure.', text_references=[QUOTE],
            confidence=0.7, state_category=_first(schemas.StateCategory))),
        'resources': ('resource_category', 'resourceCategory', schemas.CandidateResourceClass(
            label='Ethics Code', definition='A code.', text_references=[QUOTE],
            confidence=0.7, resource_category=_first(schemas.ResourceCategory))),
        'principles': ('principle_category', 'principleCategory', schemas.CandidatePrincipleClass(
            label='Public Safety', definition='Hold safety paramount.', text_references=[QUOTE],
            confidence=0.7, principle_category=_first(schemas.PrincipleCategory))),
        'obligations': ('obligation_type', 'obligationType', schemas.CandidateObligationClass(
            label='Disclosure Duty', definition='Duty to disclose risks.', text_references=[QUOTE],
            confidence=0.8, obligation_type=_first(schemas.ObligationType))),
        'constraints': ('constraint_type', 'constraintType', schemas.CandidateConstraintClass(
            label='Budget Limit', definition='A budget boundary.', text_references=[QUOTE],
            confidence=0.7, constraint_type=_first(schemas.ConstraintType))),
    }


def _stored(record):
    """What rdf_storage_service.store_extraction_results writes as rdf_json_ld for a new row."""
    clean = _clean_json_data(record)
    clean['section_sources'] = ['facts']
    if clean.get('source_text'):
        clean['source_texts'] = {'facts': clean['source_text']}
    return clean


@pytest.mark.parametrize('concept', ['roles', 'states', 'resources', 'principles', 'obligations', 'constraints'])
def test_the_real_class_record_hides_its_wrapper_keys_and_keeps_the_category_property(concept):
    top_key, prop_key, cls = _producer_input()[concept]
    data = pydantic_to_rdf_data(classes=[cls], individuals=[], concept_type=concept, case_id=8,
                                section_type='facts', pass_number=1, step_number=1)
    stored = _stored(data['new_classes'][0])

    assert stored[top_key] == stored['properties'][prop_key][0], 'the producer writes the copy'
    assert {'definitions', 'match_decision', 'parent', 'source_texts', top_key} <= set(stored)
    groups = group_properties(stored)
    emitted = {predicate for kind in groups.values() for predicate, _ in kind}
    assert emitted.isdisjoint({'definitions', 'match_decision', 'parent', 'source_texts', top_key})
    assert (prop_key, stored['properties'][prop_key]) in groups[FieldKind.CONTENT.value]
    assert helpers._entity_field_groups(stored)['typed_as']['parent'] == stored['parent'].rsplit('#', 1)[-1]


def test_the_real_individual_record_hides_its_wrapper_keys_and_types_the_typed_as_line():
    individual = schemas.RoleIndividual(
        identifier='Engineer A', name='Engineer A', role_class='Structural Engineer Role',
        role_category=_first(schemas.RoleCategory), text_references=[QUOTE], source_text=QUOTE,
        confidence=0.9, case_involvement='Reviews the structural design for the client.',
        actor='Engineer A')
    data = pydantic_to_rdf_data(classes=[], individuals=[individual], concept_type='roles', case_id=8,
                                section_type='facts', pass_number=1, step_number=1)
    stored = _stored(data['new_individuals'][0])

    assert {'definitions', 'match_decision', 'types', 'source_texts'} <= set(stored)
    fields = helpers._entity_field_groups(stored)
    literal_predicates = {field['p'] for field in fields['literals']}
    assert literal_predicates.isdisjoint({'definitions', 'match_decision', 'types', 'source_texts'})
    assert {'caseInvolvement', 'roleCategory'} <= literal_predicates
    assert [field['p'] for field in fields['relations']] == ['actor']
    assert fields['typed_as'] == {'types': ['StructuralEngineerRole'], 'parent': None}


def test_every_wrapper_key_the_producer_writes_is_structural_except_the_quote():
    """The one top-level key of a stored record that still reaches the literal list is
    source_text, the quote (also shown through textReferences); recorded, not changed."""
    top_key, _, cls = _producer_input()['roles']
    data = pydantic_to_rdf_data(classes=[cls], individuals=[], concept_type='roles', case_id=8,
                                section_type='facts', pass_number=1, step_number=1)
    stored = _stored(data['new_classes'][0])
    assert [k for k in stored if k != 'properties' and k not in _STRUCTURAL_KEYS] == ['source_text']
