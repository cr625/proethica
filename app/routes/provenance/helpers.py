"""Shared module-level constants and non-route helper functions for the provenance pipeline view. The three mapping constants (CONCEPT_ACTIVITY_MAP, PIPELINE_STRUCTURE, ENTITY_COLORS) plus the _-prefixed extraction/provenance helpers used by get_case_pipeline, and the pure functions behind the card surfaces (truncation_limit, group_consolidation_by_run). The helpers call each other (e.g. _get_extraction_data->_entity_field_groups + _get_provenance_for_prompt; _get_provenance_for_prompt->_determine_origin; _build_algorithmic_trace->_parse_results_summary) and read CONCEPT_ACTIVITY_MAP/PIPELINE_STRUCTURE/ENTITY_COLORS, so they stay together at module level. Imported by pipeline_routes.py."""
import logging
from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from sqlalchemy import desc, func, text
import json
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

from app.models import db
from app.models.provenance import (
    ProvenanceAgent, ProvenanceActivity, ProvenanceEntity,
    ProvenanceDerivation, ProvenanceUsage, ProvenanceCommunication,
    ProvenanceBundle
)
from app.models.document import Document
from app.models.extraction_prompt import ExtractionPrompt
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.provenance_service import get_provenance_service
from app.utils.environment_auth import auth_optional


CONCEPT_ACTIVITY_MAP = {
    'roles': 'dual_roles_extraction',
    'states': 'dual_states_extraction',
    'resources': 'dual_resources_extraction',
    'principles': 'dual_principles_extraction',
    'obligations': 'dual_obligations_extraction',
    'constraints': 'dual_constraints_extraction',
    'capabilities': 'dual_capabilities_extraction',
    'actions': 'temporal_action_extraction',
    'events': 'temporal_event_extraction',
    'causal_chains': 'temporal_causal_analysis',
    'allen_relations': 'temporal_temporal_markers',
    'timeline': 'temporal_temporal_markers',
}


PIPELINE_STRUCTURE = {
    'steps': [
        {
            'step': 1,
            'name': 'Contextual Framework',
            'color': '#3b82f6',  # Blue
            'concepts': ['roles', 'states', 'resources']
        },
        {
            'step': 2,
            'name': 'Normative Framework',
            'color': '#8b5cf6',  # Purple
            'concepts': ['principles', 'obligations', 'constraints', 'capabilities']
        },
        {
            'step': 3,
            'name': 'Temporal Framework',
            'color': '#14b8a6',  # Teal
            'concepts': ['actions', 'events', 'causal_chains', 'allen_relations', 'timeline']
        }
    ],
    'step4_phases': [
        {'phase': '2A', 'name': 'Code Provisions', 'concept_type': 'code_provision_reference'},
        {'phase': '2B', 'name': 'Precedent Cases', 'concept_type': 'precedent_case_reference'},
        {'phase': '2C-Q', 'name': 'Ethical Questions', 'concept_type': 'ethical_question'},
        {'phase': '2C-C', 'name': 'Ethical Conclusions', 'concept_type': 'ethical_conclusion'},
        {'phase': '2D', 'name': 'Transformation Analysis', 'concept_type': 'transformation_classification'},
        {'phase': '2E', 'name': 'Rich Analysis', 'concept_type': 'rich_analysis'},
        {'phase': '3', 'name': 'Decision Point Synthesis', 'concept_type': 'phase3_decision_synthesis'},
        {'phase': '4', 'name': 'Narrative Construction', 'concept_type': 'phase4_narrative'}
    ],
    'step4_color': '#64748b',  # Slate
    'passes': ['facts', 'discussion'],
    # Section headers of the steps 1-2 passes. Named by the section, not by a pass
    # number: the case page resolver (unified_entity_resolver.PASS_MAP) uses "Pass N"
    # for the STEP number, so "Pass 1 (Facts)" read as a conflicting numbering.
    'pass_names': {'facts': 'Facts pass', 'discussion': 'Discussion pass'},
}


# The nine concept colours come from the canonical map (app/concept_meta.py);
# the extra keys below are provenance-timeline-specific.
from app.concept_meta import CONCEPT_COLORS
ENTITY_COLORS = {
    **CONCEPT_COLORS,
    'causal_chains': '#dc3545',   # Red
    'allen_relations': '#6f42c1', # Purple
    'timeline': '#0dcaf0',        # Cyan
}


def _entity_field_groups(rdf_json_ld: dict) -> dict:
    """Partition an entity's emitted fields into structural relations vs kept literal
    extractions for the provenance display, using the field_classification source of
    truth. Returns {relations: [{p, v}], literals: [{p, v, kind}], derived: [{p, v}],
    typed_as: {types: [local], parent: local|None}} with short, JS-ready predicate
    locals + stringified values. ``typed_as`` carries the storage wrapper's type anchors
    (the individual's rdf:type classes, the class's parent), which the card renders as its
    own "typed as" line rather than as literal extractions."""
    from app.services.extraction.field_classification import group_properties, FieldKind

    def _fmt(v):
        if isinstance(v, dict):
            return json.dumps(v)
        if isinstance(v, (list, tuple)):
            return '; '.join(str(x) for x in v)
        return str(v)

    def _local(p):
        return p.split('#')[-1].split('/')[-1].split(':')[-1]

    data = rdf_json_ld if isinstance(rdf_json_ld, dict) else {}
    groups = group_properties(data)
    types = data.get('types') or []
    if isinstance(types, str):
        types = [types]
    parent = data.get('parent')
    return {
        'relations': [{'p': _local(p), 'v': _fmt(v)} for p, v in groups[FieldKind.RELATION.value]],
        'literals': (
            [{'p': _local(p), 'v': _fmt(v), 'kind': 'content'} for p, v in groups[FieldKind.CONTENT.value]]
            + [{'p': _local(p), 'v': _fmt(v), 'kind': 'assessment'} for p, v in groups[FieldKind.ASSESSMENT.value]]
        ),
        'derived': [{'p': _local(p), 'v': _fmt(v)} for p, v in groups[FieldKind.DERIVED.value]],
        'typed_as': {
            'types': [_local(str(t)) for t in types if t],
            'parent': _local(str(parent)) if parent else None,
        },
    }


def _get_extraction_data(case_id: int, step_number: int, section_type: str, concept_type: str) -> dict:
    """Get extraction prompt and entities for a specific step/section/concept."""
    # Get the most recent extraction prompt
    prompt = ExtractionPrompt.query.filter_by(
        case_id=case_id,
        step_number=step_number,
        section_type=section_type,
        concept_type=concept_type,
        is_active=True
    ).order_by(ExtractionPrompt.created_at.desc()).first()

    # Get entities from TemporaryRDFStorage
    entities = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type=concept_type
    ).all()

    # Filter entities by section if needed (check provenance_metadata)
    section_entities = []
    for entity in entities:
        # Check if entity is from this section
        prov_meta = entity.provenance_metadata or {}
        entity_section = prov_meta.get('section_type', 'facts')
        if entity_section == section_type or section_type in (entity.rdf_json_ld or {}).get('section_sources', []):
            section_entities.append({
                'id': entity.id,
                'label': entity.entity_label,
                'definition': entity.entity_definition,
                'uri': entity.entity_uri,
                'type': entity.entity_type,
                'is_published': entity.is_published,
                'color': ENTITY_COLORS.get(concept_type, '#6c757d'),
                'fields': _entity_field_groups(entity.rdf_json_ld)
            })

    # Provenance metadata
    provenance = _get_provenance_for_prompt(case_id, concept_type, prompt)

    # History count (how many prior prompts exist)
    history_count = ExtractionPrompt.query.filter_by(
        case_id=case_id,
        step_number=step_number,
        section_type=section_type,
        concept_type=concept_type
    ).count()

    return {
        'concept': concept_type,
        'concept_label': concept_type.replace('_', ' ').title(),
        'color': ENTITY_COLORS.get(concept_type, '#6c757d'),
        'has_data': prompt is not None,
        'prompt': {
            'id': prompt.id,
            'text': prompt.prompt_text,
            'response': prompt.raw_response,
            'model': prompt.llm_model,
            'created_at': prompt.created_at.isoformat() if prompt.created_at else None,
            'results_summary': prompt.results_summary,
            'session_id': prompt.extraction_session_id,
            'truncation': _stored_text_truncation(prompt),
        } if prompt else None,
        'entities': section_entities,
        'entity_count': len(section_entities),
        'provenance': provenance,
        'history_count': history_count
    }


def _get_temporal_extraction_data(case_id: int, concept_type: str) -> dict:
    """Get extraction data for Step 3 temporal concepts.

    Step 3 uses extraction_type='temporal_dynamics_enhanced' with entity_type
    differentiation, and stores provenance in PROV-O tables (not extraction_prompts).
    """
    # Query entities by extraction_type + entity_type
    entities = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='temporal_dynamics_enhanced',
        entity_type=concept_type
    ).all()

    entity_list = [{
        'id': e.id,
        'label': e.entity_label,
        'definition': e.entity_definition,
        'uri': e.entity_uri,
        'type': e.entity_type,
        'is_published': e.is_published,
        'color': ENTITY_COLORS.get(concept_type, '#6c757d'),
        'fields': _entity_field_groups(e.rdf_json_ld)
    } for e in entities]

    # Look up provenance directly from PROV-O (no extraction_prompts for Step 3)
    activity_name = CONCEPT_ACTIVITY_MAP.get(concept_type)
    provenance = None
    if activity_name:
        activity = ProvenanceActivity.query.filter_by(
            case_id=case_id,
            activity_name=activity_name
        ).order_by(ProvenanceActivity.started_at.desc()).first()

        if activity:
            agent = activity.agent
            provenance = {
                'activity_id': activity.id,
                'activity_type': activity.activity_type,
                'activity_name': activity.activity_name,
                'agent_name': agent.agent_name if agent else None,
                'agent_type': agent.agent_type if agent else None,
                'agent_version': agent.agent_version if agent else None,
                'duration_ms': activity.duration_ms,
                'status': activity.status,
                'started_at': activity.started_at.isoformat() if activity.started_at else None,
                'ended_at': activity.ended_at.isoformat() if activity.ended_at else None,
                'origin': _determine_origin(activity)
            }

    # Get extraction model from first entity (all share the same model)
    extraction_model = None
    if entities:
        extraction_model = entities[0].extraction_model

    # Pull prompt/response text from provenance_entities for this activity.
    # Step 3 stores these via ProvenanceService.record_prompt/record_response,
    # not via extraction_prompts like Steps 1-2.
    prompt_text = None
    response_text = None
    if activity_name:
        activity = ProvenanceActivity.query.filter_by(
            case_id=case_id,
            activity_name=activity_name
        ).order_by(ProvenanceActivity.started_at.desc()).first()
        if activity:
            prompt_entity = ProvenanceEntity.query.filter_by(
                generating_activity_id=activity.id,
                entity_type='prompt'
            ).first()
            response_entity = ProvenanceEntity.query.filter_by(
                generating_activity_id=activity.id,
                entity_type='response'
            ).first()
            if prompt_entity:
                prompt_text = prompt_entity.content
            if response_entity:
                response_text = response_entity.content

    return {
        'concept': concept_type,
        'concept_label': concept_type.replace('_', ' ').title(),
        'color': ENTITY_COLORS.get(concept_type, '#6c757d'),
        'has_data': len(entity_list) > 0,
        'prompt': {
            'model': extraction_model,
            'created_at': entities[0].created_at.isoformat() if entities and entities[0].created_at else None,
            'session_id': entities[0].extraction_session_id if entities else None,
            'text': prompt_text,
            'response': response_text,
        } if entity_list else None,
        'entities': entity_list,
        'entity_count': len(entity_list),
        'provenance': provenance,
        'history_count': 0
    }


def _get_step4_phase_data(case_id: int, phase_def: dict) -> dict:
    """Get Step 4 phase data from extraction prompts."""
    concept_type = phase_def['concept_type']

    # Get the most recent extraction prompt for this phase
    prompt = ExtractionPrompt.query.filter_by(
        case_id=case_id,
        step_number=4,
        concept_type=concept_type
    ).order_by(ExtractionPrompt.created_at.desc()).first()

    # Get entities from TemporaryRDFStorage if applicable
    entities = []
    if concept_type in ['code_provision_reference', 'ethical_question', 'ethical_conclusion']:
        storage_entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type=concept_type
        ).all()
        entities = [{
            'id': e.id,
            'label': e.entity_label,
            'definition': e.entity_definition,
            'uri': e.entity_uri,
            'is_published': e.is_published,
            'fields': _entity_field_groups(e.rdf_json_ld)
        } for e in storage_entities]
    elif concept_type == 'phase3_decision_synthesis':
        # Get canonical decision points
        decision_points = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='canonical_decision_point'
        ).all()
        entities = [{
            'id': dp.id,
            'label': dp.entity_label,
            'definition': dp.entity_definition,
            'uri': dp.entity_uri,
            'rdf_data': dp.rdf_json_ld,
            'fields': _entity_field_groups(dp.rdf_json_ld)
        } for dp in decision_points]

    # Provenance metadata
    provenance = _get_provenance_for_prompt(case_id, concept_type, prompt)

    # Phase 3 synthesis trace: algorithmic composition, Q&C alignment,
    # entity resolution, timing -- stored on provenance_metadata of the
    # first canonical_decision_point entity.
    synthesis_trace = None
    if concept_type == 'phase3_decision_synthesis':
        first_dp = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='canonical_decision_point'
        ).order_by(TemporaryRDFStorage.id).first()
        if first_dp and first_dp.provenance_metadata:
            synthesis_trace = dict(first_dp.provenance_metadata)

        # Add pipeline funnel from results_summary
        parsed_rs = _parse_results_summary(prompt)
        if synthesis_trace and parsed_rs:
            synthesis_trace['pipeline_summary'] = parsed_rs

        # Add argument validation summary
        if synthesis_trace:
            arg_validations = TemporaryRDFStorage.query.filter_by(
                case_id=case_id, extraction_type='argument_validation'
            ).all()
            if arg_validations:
                valid_count = sum(
                    1 for v in arg_validations
                    if (v.rdf_json_ld or {}).get('is_valid')
                )
                scores = [
                    (v.rdf_json_ld or {}).get('validation_score', 0)
                    for v in arg_validations
                ]
                avg_score = sum(scores) / len(scores)
                fv = sum(
                    1 for v in arg_validations
                    if (v.rdf_json_ld or {}).get(
                        'founding_value_validation', {}
                    ).get('is_compliant')
                )
                ev = sum(
                    1 for v in arg_validations
                    if (v.rdf_json_ld or {}).get(
                        'entity_validation', {}
                    ).get('is_valid')
                )
                vv = sum(
                    1 for v in arg_validations
                    if (v.rdf_json_ld or {}).get(
                        'virtue_validation', {}
                    ).get('is_valid')
                )
                arg_count = TemporaryRDFStorage.query.filter_by(
                    case_id=case_id, extraction_type='argument_generated'
                ).count()
                synthesis_trace['argument_validation'] = {
                    'arguments_generated': arg_count,
                    'validations_run': len(arg_validations),
                    'valid_count': valid_count,
                    'avg_score': round(avg_score, 2),
                    'entity_valid': ev,
                    'founding_compliant': fv,
                    'virtue_valid': vv,
                }

    # Algorithmic trace for non-Phase-3 phases
    algorithmic_trace = _build_algorithmic_trace(case_id, concept_type, prompt)

    result = {
        'phase': phase_def['phase'],
        'name': phase_def['name'],
        'concept_type': concept_type,
        'color': PIPELINE_STRUCTURE['step4_color'],
        'has_data': prompt is not None or len(entities) > 0,
        'prompt': {
            'id': prompt.id,
            'text': prompt.prompt_text,
            'response': prompt.raw_response,
            'model': prompt.llm_model,
            'created_at': prompt.created_at.isoformat() if prompt.created_at else None,
            'results_summary': prompt.results_summary if isinstance(prompt.results_summary, dict) else None,
            'session_id': prompt.extraction_session_id,
            'truncation': _stored_text_truncation(prompt),
        } if prompt else None,
        'entities': entities,
        'entity_count': len(entities),
        'provenance': provenance
    }
    if synthesis_trace:
        result['synthesis_trace'] = synthesis_trace
    if algorithmic_trace:
        result['algorithmic_trace'] = algorithmic_trace
    return result


def _parse_results_summary(prompt) -> dict:
    """Parse results_summary, handling double-encoded JSON strings."""
    if not prompt or prompt.results_summary is None:
        return None
    rs = prompt.results_summary
    if isinstance(rs, dict):
        return rs
    if isinstance(rs, str):
        try:
            parsed = json.loads(rs)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            pass
    return None


def _build_algorithmic_trace(case_id: int, concept_type: str, prompt) -> dict:
    """Build algorithmic trace data for Step 4 phases.

    Returns a dict with 'type' key indicating the trace kind, or None if
    no algorithmic component exists for this phase.
    """
    rs = _parse_results_summary(prompt)

    if concept_type == 'code_provision_reference':
        # Phase 2A: Algorithmic provision detection + entity linking
        prov_entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='code_provision_reference'
        ).all()
        if not prov_entities:
            return None
        total_links = sum(
            len((e.rdf_json_ld or {}).get('appliesTo', []))
            for e in prov_entities
        )
        return {
            'type': 'code_provision_extraction',
            'total': len(prov_entities),
            'total_links': total_links,
            'provisions': [{
                'code': e.entity_label,
                'text': (e.entity_definition or '')[:120],
                'link_count': len((e.rdf_json_ld or {}).get('appliesTo', [])),
            } for e in prov_entities]
        }

    if concept_type == 'precedent_case_reference':
        # Phase 2B: Case number resolution against internal document DB
        prec_entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='precedent_case_reference'
        ).all()
        if not prec_entities:
            return None
        resolved_count = sum(
            1 for e in prec_entities
            if str((e.rdf_json_ld or {}).get('resolved', '')).lower() == 'true'
        )
        return {
            'type': 'precedent_resolution',
            'total': len(prec_entities),
            'resolved': resolved_count,
            'unresolved': len(prec_entities) - resolved_count,
            'cases': [{
                'label': e.entity_label,
                'case_number': (e.rdf_json_ld or {}).get('caseNumber'),
                'citation_type': (e.rdf_json_ld or {}).get('citationType'),
                'resolved': str(
                    (e.rdf_json_ld or {}).get('resolved', '')
                ).lower() == 'true',
                'internal_id': (e.rdf_json_ld or {}).get('internalCaseId'),
            } for e in prec_entities]
        }

    if concept_type == 'ethical_question' and rs:
        return {
            'type': 'question_classification',
            'total': rs.get('total', 0),
            'board_explicit': rs.get('board_explicit', 0),
            'analytical': rs.get('analytical', 0),
        }

    if concept_type == 'ethical_conclusion' and rs:
        return {
            'type': 'conclusion_classification',
            'total': rs.get('total', 0),
            'board_explicit': rs.get('board_explicit', 0),
            'analytical': rs.get('analytical', 0),
            'qc_links': rs.get('qc_links', 0),
        }

    if concept_type == 'transformation_classification' and rs:
        return {
            'type': 'transformation_classification',
            'transformation_type': rs.get('transformation_type'),
            'confidence': rs.get('confidence'),
        }

    if concept_type == 'rich_analysis':
        causal = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='causal_normative_link'
        ).count()
        qe = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='question_emergence'
        ).count()
        rp = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='resolution_pattern'
        ).count()
        if causal + qe + rp > 0:
            return {
                'type': 'rich_analysis',
                'causal_links': causal,
                'question_emergence': qe,
                'resolution_patterns': rp,
            }

    if concept_type == 'phase4_narrative' and rs:
        ne = rs.get('narrative_elements', {})
        tl = rs.get('timeline', {})
        if ne:
            return {
                'type': 'narrative_structure',
                'characters': ne.get('characters', 0),
                'events': ne.get('events', 0),
                'conflicts': ne.get('conflicts', 0),
                'decision_moments': ne.get('decision_moments', 0),
                'has_setting': ne.get('has_setting', False),
                'has_resolution': ne.get('has_resolution', False),
                'timeline_events': tl.get('events_count', 0),
            }

    return None


def _get_provenance_for_prompt(case_id, concept_type, prompt):
    """Look up the PROV-O activity recorded for an extraction prompt.

    The match is by the prompt's extraction session id: first together with the
    concept-specific activity name (CONCEPT_ACTIVITY_MAP), then any activity of that
    session and case. There is no fallback by case id and activity name alone. Such a
    match borrowed the activity of an unrelated earlier run whenever the model call
    behind the prompt had not been recorded (case 24-1 review, 2026-10: a prompt of
    2026-07-07 shown with the agent, duration and origin of an activity of 2026-02-18),
    so a prompt without a session match returns None and the card shows the prompt's
    own date and model with the duration not recorded.
    """
    if not prompt or not prompt.extraction_session_id:
        return None

    activity_name = CONCEPT_ACTIVITY_MAP.get(concept_type)

    activity = None
    if activity_name:
        # Primary match: session_id + concept-specific activity
        activity = ProvenanceActivity.query.filter_by(
            case_id=case_id,
            session_id=prompt.extraction_session_id,
            activity_name=activity_name
        ).order_by(ProvenanceActivity.started_at.desc()).first()

    if not activity:
        # Secondary match: any activity in this session for this case
        activity = ProvenanceActivity.query.filter_by(
            case_id=case_id,
            session_id=prompt.extraction_session_id
        ).order_by(ProvenanceActivity.started_at.desc()).first()

    if not activity:
        return None

    agent = activity.agent
    return {
        'activity_id': activity.id,
        'activity_type': activity.activity_type,
        'activity_name': activity.activity_name,
        'agent_name': agent.agent_name if agent else None,
        'agent_type': agent.agent_type if agent else None,
        'agent_version': agent.agent_version if agent else None,
        'duration_ms': activity.duration_ms,
        'status': activity.status,
        'started_at': activity.started_at.isoformat() if activity.started_at else None,
        'ended_at': activity.ended_at.isoformat() if activity.ended_at else None,
        'origin': _determine_origin(activity)
    }


ORIGINS = ('automated_pipeline', 'user_initiated', 'individual_extraction', 'algorithmic')


def _determine_origin(activity):
    """Classify extraction origin from activity metadata.

    An origin the recorder stored explicitly (activity_metadata['origin'], written by
    the Celery extraction path for its llm_query activities) wins; otherwise the
    activity name and type heuristics apply. Returns one of: automated_pipeline,
    user_initiated, individual_extraction, algorithmic.
    """
    meta = activity.activity_metadata if isinstance(activity.activity_metadata, dict) else {}
    if meta.get('origin') in ORIGINS:
        return meta['origin']

    name = activity.activity_name or ''

    if 'entities_pass' in name or 'normative_pass' in name or 'temporal_pass' in name:
        return 'automated_pipeline'
    if activity.activity_type in ('composition', 'synthesis', 'analysis'):
        return 'algorithmic'
    if 'dual_' in name or '_extraction' in name:
        return 'user_initiated'
    return 'user_initiated'


# Round storage limits at which a stored prompt or response was once sliced
# (``text[:10000]`` in the step 4 writers until commit 35a80006, 2026-07-11; the larger
# values cover the same pattern at other round sizes). A stored text whose length equals
# one of them is flagged as truncated on the card: the remainder was never kept.
STORED_TEXT_LIMITS = (10000, 20000, 50000)


def truncation_limit(text) -> Optional[int]:
    """The round storage limit a stored text's length equals exactly, or None."""
    if not isinstance(text, str):
        return None
    return len(text) if len(text) in STORED_TEXT_LIMITS else None


def _stored_text_truncation(prompt) -> dict:
    """Truncation flags of an extraction_prompts row: {prompt: limit|None, response: limit|None}."""
    return {
        'prompt': truncation_limit(getattr(prompt, 'prompt_text', None)),
        'response': truncation_limit(getattr(prompt, 'raw_response', None)),
    }


# The largest distance between an activity recorded without a session id and the
# pipeline run it belongs to. Distinct runs of one case are typically days apart.
CONSOLIDATION_RUN_GAP = timedelta(hours=6)


def group_consolidation_by_run(rows, gap: timedelta = CONSOLIDATION_RUN_GAP) -> list:
    """Group consolidation-and-commit activities into pipeline runs.

    ``rows`` are dicts with ``session_id`` (the PipelineRun id the pipeline passes record,
    or None) and ``started_at`` (datetime); other keys pass through. Activities with a
    session id form one run per session. Activities recorded without a session id are
    attached to a run: the extraction-time filter passes (activity_type ``filter``) run
    before the first sessioned pass of their run, so they attach forward to the nearest
    run starting after them; the commit-time passes (edge materialization, guard,
    conformance check, repair) conclude a run, so they attach backward to the nearest run
    ending before them. An activity inside a run's window attaches to it. Activities no
    run lies within ``gap`` of are clustered by ``gap`` into runs of their own (a commit
    made outside a recorded pipeline run).

    Returns runs newest first, each {session_id, started_at, ended_at, activity_count,
    activities} with the activities in chronological order."""
    rows = [r for r in rows if r.get('started_at') is not None]
    chronological = sorted(rows, key=lambda r: r['started_at'])

    runs = {}
    for r in chronological:
        if not r.get('session_id'):
            continue
        run = runs.setdefault(r['session_id'], {
            'session_id': r['session_id'],
            'started_at': r['started_at'],
            'ended_at': r['started_at'],
            'activities': [],
        })
        run['activities'].append(r)
        run['ended_at'] = max(run['ended_at'], r['started_at'])

    leftovers = []
    for r in chronological:
        if r.get('session_id'):
            continue
        t = r['started_at']
        best, best_distance = None, None
        for run in runs.values():
            if run['started_at'] <= t <= run['ended_at']:
                distance = timedelta(0)
            elif r.get('activity_type') == 'filter':
                distance = run['started_at'] - t if t < run['started_at'] else None
            else:
                distance = t - run['ended_at'] if t > run['ended_at'] else None
            if distance is not None and distance <= gap and (best_distance is None or distance < best_distance):
                best, best_distance = run, distance
        if best is None:
            leftovers.append(r)
        else:
            best['activities'].append(r)

    clusters = []
    for r in leftovers:
        if clusters and r['started_at'] - clusters[-1]['ended_at'] <= gap:
            clusters[-1]['activities'].append(r)
            clusters[-1]['ended_at'] = r['started_at']
        else:
            clusters.append({
                'session_id': None,
                'started_at': r['started_at'],
                'ended_at': r['started_at'],
                'activities': [r],
            })

    grouped = []
    for run in list(runs.values()) + clusters:
        activities = sorted(run['activities'], key=lambda r: r['started_at'])
        grouped.append({
            'session_id': run['session_id'],
            'started_at': activities[0]['started_at'],
            'ended_at': activities[-1]['started_at'],
            'activity_count': len(activities),
            'activities': activities,
        })
    grouped.sort(key=lambda g: g['started_at'], reverse=True)
    return grouped
