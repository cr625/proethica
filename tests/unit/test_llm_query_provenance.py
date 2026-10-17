"""L2 of the case 24-1 (ProEthica case 8) review, 2026-10: the step 1 and 2 model calls of
the Celery extraction path are recorded as llm_query provenance activities (the session id
of the extraction_prompts row, agent = the model, started and ended timestamps, duration,
case id, concept type, section) with the prompt and response as provenance entities, through
the recorder the temporal pass uses.

Hermetic: the ORM session and the model classmethods are patched, no database.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models import db
from app.models.extraction_prompt import ExtractionPrompt
from app.models.provenance import (
    ProvenanceActivity, ProvenanceDerivation, ProvenanceEntity, ProvenanceUsage,
)
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.extraction import extraction_graph
from app.services.provenance_service import ProvenanceService


def _session():
    """A session stub whose flush assigns ids to the pending objects, as the database would."""
    session = MagicMock()
    added = []
    ids = iter(range(1000, 2000))

    def flush():
        for obj in added:
            if getattr(obj, 'id', None) is None:
                obj.id = next(ids)

    session.add.side_effect = added.append
    session.flush.side_effect = flush
    session.added = added
    return session


def _service():
    service = ProvenanceService(session=_session())
    service.get_or_create_agent = MagicMock(
        return_value=SimpleNamespace(id=7, agent_name='claude-sonnet-4-5', agent_type='llm_model'))
    return service


STARTED = datetime(2026, 7, 7, 14, 0, 0)
ENDED = STARTED + timedelta(milliseconds=22496)


def test_record_llm_query_creates_the_activity_with_the_session_id_and_linked_entities():
    service = _service()

    activity = service.record_llm_query(
        activity_name='dual_roles_extraction', case_id=8, session_id='sess-roles-facts',
        model_name='claude-sonnet-4-5', prompt_text='PROMPT', response_text='RESPONSE',
        started_at=STARTED, ended_at=ENDED,
        execution_plan={'concept_type': 'roles', 'section': 'facts', 'step': 1},
        activity_metadata={'origin': 'automated_pipeline'},
    )

    service.get_or_create_agent.assert_called_once_with(
        agent_type='llm_model', agent_name='claude-sonnet-4-5')
    assert isinstance(activity, ProvenanceActivity)
    assert activity.activity_type == 'llm_query'
    assert activity.activity_name == 'dual_roles_extraction'
    assert activity.session_id == 'sess-roles-facts'
    assert activity.case_id == 8
    assert activity.agent_id == 7
    assert (activity.started_at, activity.ended_at, activity.duration_ms) == (STARTED, ENDED, 22496)
    assert activity.status == 'completed'
    assert activity.activity_metadata == {'origin': 'automated_pipeline'}

    added = service.session.added
    entities = [o for o in added if isinstance(o, ProvenanceEntity)]
    assert [(e.entity_type, e.content, e.generating_activity_id, e.case_id) for e in entities] == [
        ('prompt', 'PROMPT', activity.id, 8), ('response', 'RESPONSE', activity.id, 8)]
    usage = [o for o in added if isinstance(o, ProvenanceUsage)]
    assert [(u.activity_id, u.entity_id, u.usage_role) for u in usage] == [
        (activity.id, entities[0].id, 'input')]
    derivations = [o for o in added if isinstance(o, ProvenanceDerivation)]
    assert [(d.derived_entity_id, d.source_entity_id) for d in derivations] == [
        (entities[1].id, entities[0].id)]
    service.session.commit.assert_not_called()


def test_record_llm_query_without_a_response_records_the_prompt_only():
    service = _service()
    activity = service.record_llm_query(
        activity_name='dual_states_extraction', case_id=8, session_id='sess-states-facts',
        model_name='claude-sonnet-4-5', prompt_text='PROMPT', response_text=None,
        started_at=STARTED, ended_at=ENDED)
    entities = [o for o in service.session.added if isinstance(o, ProvenanceEntity)]
    assert [e.entity_type for e in entities] == ['prompt']
    assert not [o for o in service.session.added if isinstance(o, ProvenanceDerivation)]
    assert activity.duration_ms == 22496


def test_record_llm_query_without_timestamps_records_a_zero_duration_now():
    service = _service()
    activity = service.record_llm_query(
        activity_name='dual_roles_extraction', case_id=8, session_id='s',
        model_name='m', prompt_text='P')
    assert activity.started_at == activity.ended_at
    assert activity.duration_ms == 0


def _prompt_row(**overrides):
    fields = dict(
        id=8616, case_id=8, concept_type='roles', section_type='facts', step_number=1,
        prompt_text='PROMPT', raw_response='RESPONSE', llm_model='claude-sonnet-4-5',
        extraction_session_id='sess-roles-facts', injection_mode='full',
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _extractor():
    return SimpleNamespace(
        model_name='claude-sonnet-4-5', last_prompt='PROMPT', last_raw_response='RESPONSE',
        injection_mode='full', tool_call_log=[], ontology_definitions=None,
        last_llm_started_at=STARTED, last_llm_ended_at=ENDED,
    )


def _store(row, extractor, prov, origin='automated_pipeline'):
    """store_extraction_result with the database replaced; returns the storage mock."""
    with patch.object(ExtractionPrompt, 'save_prompt', return_value=row) as save, \
            patch.object(extraction_graph, 'pydantic_to_rdf_data',
                         return_value={'new_classes': [], 'new_individuals': []}), \
            patch.object(TemporaryRDFStorage, 'store_extraction_results') as store, \
            patch.object(db, 'session', MagicMock()) as session, \
            patch('app.services.provenance_service.get_provenance_service', return_value=prov):
        extraction_graph.store_extraction_result(
            case_id=8, concept_type='roles', step_number=1, section_type='facts',
            session_id='sess-roles-facts', extractor=extractor, classes=[], individuals=[],
            pass_number=1, extraction_pass='contextual_framework', origin=origin,
        )
    return save, store, session


def test_store_extraction_result_records_one_llm_query_for_the_saved_prompt_session():
    row = _prompt_row()
    prov = MagicMock()

    save, store, session = _store(row, _extractor(), prov)

    assert save.call_args.kwargs['extraction_session_id'] == 'sess-roles-facts'
    kwargs = prov.record_llm_query.call_args.kwargs
    assert prov.record_llm_query.call_count == 1
    assert kwargs['session_id'] == row.extraction_session_id == 'sess-roles-facts'
    assert kwargs['activity_name'] == 'dual_roles_extraction'
    assert kwargs['case_id'] == 8
    assert kwargs['model_name'] == 'claude-sonnet-4-5'
    assert (kwargs['started_at'], kwargs['ended_at']) == (STARTED, ENDED)
    assert (kwargs['prompt_text'], kwargs['response_text']) == ('PROMPT', 'RESPONSE')
    assert kwargs['execution_plan'] == {'concept_type': 'roles', 'section': 'facts',
                                        'step': 1, 'injection_mode': 'full'}
    assert kwargs['activity_metadata'] == {
        'concept_type': 'roles', 'section_type': 'facts', 'step_number': 1,
        'extraction_prompt_id': 8616, 'classes': 0, 'individuals': 0,
        'origin': 'automated_pipeline'}
    session.begin_nested.assert_called_once()
    store.assert_called_once()


def test_store_extraction_result_without_origin_leaves_it_to_the_display_heuristics():
    prov = MagicMock()
    _store(_prompt_row(), _extractor(), prov, origin=None)
    assert 'origin' not in prov.record_llm_query.call_args.kwargs['activity_metadata']


def test_a_failing_provenance_recorder_never_costs_the_extraction_its_entities():
    prov = MagicMock()
    prov.record_llm_query.side_effect = RuntimeError('provenance insert failed')
    _, store, _ = _store(_prompt_row(), _extractor(), prov)
    store.assert_called_once()


def test_no_saved_prompt_means_no_activity():
    prov = MagicMock()
    with patch.object(ExtractionPrompt, 'save_prompt', side_effect=RuntimeError('db down')), \
            patch.object(extraction_graph, 'pydantic_to_rdf_data',
                         return_value={'new_classes': [], 'new_individuals': []}), \
            patch.object(TemporaryRDFStorage, 'store_extraction_results'), \
            patch.object(db, 'session', MagicMock()), \
            patch('app.services.provenance_service.get_provenance_service', return_value=prov):
        extraction_graph.store_extraction_result(
            case_id=8, concept_type='roles', step_number=1, section_type='facts',
            session_id='sess-roles-facts', extractor=_extractor(), classes=[], individuals=[])
    prov.record_llm_query.assert_not_called()


def test_extraction_activity_name_matches_the_provenance_page_map():
    from app.routes.provenance.helpers import CONCEPT_ACTIVITY_MAP
    for concept in ('roles', 'states', 'resources', 'principles', 'obligations',
                    'constraints', 'capabilities'):
        assert extraction_graph.extraction_activity_name(concept) == CONCEPT_ACTIVITY_MAP[concept]


def test_the_celery_wrapper_declares_the_pipeline_as_origin():
    from app.tasks import pipeline_tasks
    result = SimpleNamespace(classes=[1, 2], individuals=[3])
    with patch('app.services.extraction.concept_extraction_service.extract_concept',
               return_value=result) as extract:
        counts = pipeline_tasks.run_extraction('text', 8, 'facts', 'roles', step_number=1)
    assert counts == {'classes': 2, 'individuals': 1}
    assert extract.call_args.kwargs['origin'] == 'automated_pipeline'


def test_extract_concept_passes_the_origin_to_storage():
    from app.services.extraction import concept_extraction_service as ces
    extractor = _extractor()
    extractor.extract = MagicMock(return_value=([], []))
    with patch('app.services.extraction.unified_dual_extractor.UnifiedDualExtractor',
               return_value=extractor), \
            patch.object(extraction_graph, 'store_extraction_result') as store:
        ces.extract_concept('text', 8, 'roles', section_type='facts', step_number=1,
                            session_id='sess-roles-facts', origin='automated_pipeline')
    assert store.call_args.kwargs['origin'] == 'automated_pipeline'
    assert store.call_args.kwargs['session_id'] == 'sess-roles-facts'


def test_the_temporal_trace_uses_the_shared_recorder_with_the_call_timestamps():
    from app.services.temporal_dynamics.nodes import stage7_storage
    trace = [{
        'stage': 'action_extraction', 'model': 'claude-opus-4-1', 'prompt': 'P', 'response': 'R',
        'timestamp': '2026-07-07T14:00:00', 'end_timestamp': '2026-07-07T14:00:30',
        'parsed_output': {'actions': 3}, 'tokens': {'input': 10},
    }]
    with patch.object(stage7_storage, 'ProvenanceService') as service_cls, \
            patch.object(stage7_storage, 'db'):
        stored = stage7_storage._store_llm_trace(8, 'sess-temporal', trace)
    assert stored == 1
    kwargs = service_cls.return_value.record_llm_query.call_args.kwargs
    assert kwargs['activity_name'] == 'temporal_action_extraction'
    assert kwargs['session_id'] == 'sess-temporal'
    assert kwargs['model_name'] == 'claude-opus-4-1'
    assert (kwargs['started_at'], kwargs['ended_at']) == (
        datetime(2026, 7, 7, 14, 0, 0), datetime(2026, 7, 7, 14, 0, 30))
    assert (kwargs['prompt_text'], kwargs['response_text']) == ('P', 'R')
    assert kwargs['prompt_metadata'] == {'stage': 'action_extraction', 'timestamp': '2026-07-07T14:00:00'}
    assert kwargs['response_metadata'] == {'parsed_output': {'actions': 3}, 'tokens': {'input': 10}}
