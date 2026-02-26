"""
Provenance viewer routes for PROV-O tracking visualization.
"""

from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from sqlalchemy import desc, func, text
import json
from datetime import datetime

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

# Mapping from concept_type to provenance activity_name patterns
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

# Pipeline structure definition with colors
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
    'passes': ['facts', 'discussion']
}

# Entity type colors from color-scheme.md
ENTITY_COLORS = {
    'roles': '#0d6efd',       # Blue
    'states': '#6f42c1',      # Purple
    'resources': '#20c997',   # Teal
    'principles': '#fd7e14',  # Orange
    'obligations': '#dc3545', # Red
    'constraints': '#6c757d', # Gray
    'capabilities': '#0dcaf0',# Cyan
    'actions': '#198754',     # Green
    'events': '#ffc107',      # Yellow/Amber
    'causal_chains': '#dc3545',  # Red
    'allen_relations': '#6f42c1', # Purple
    'timeline': '#0dcaf0'     # Cyan
}

provenance_bp = Blueprint('provenance', __name__)


def init_provenance_csrf_exemption(app):
    """Exempt API endpoints from CSRF for programmatic access."""
    app.csrf.exempt(run_qc_audit_api)


@provenance_bp.route('/api/qc/audit/<int:case_id>', methods=['POST'])
@auth_optional
def run_qc_audit_api(case_id):
    """Run V0-V9 QC audit for a case and store results."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'scripts'))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'scripts', 'analysis'))
    try:
        from run_qc_audit import run_audit, store_audit
        audit = run_audit(case_id)
        store_audit(audit)
        return jsonify({'success': True, 'audit': audit})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@provenance_bp.route('/tools/provenance')
@auth_optional
def provenance_hub():
    """Provenance hub - redirects to cases view."""
    return redirect(url_for('provenance.provenance_cases'))


@provenance_bp.route('/tools/provenance/cases')
@auth_optional
def provenance_cases():
    """All cases provenance viewer page with optional case pre-selected."""
    # Redirect to unified view when a specific case is selected
    selected_case_id = request.args.get('selected', type=int)
    if selected_case_id:
        return redirect(url_for('provenance.case_provenance', case_id=selected_case_id))

    selected_case = None

    # Get all cases with optional provenance activity counts
    all_cases = db.session.query(
        Document.id,
        Document.title,
        func.count(ProvenanceActivity.id).label('activity_count'),
        func.max(ProvenanceActivity.created_at).label('last_activity')
    ).outerjoin(
        ProvenanceActivity, ProvenanceActivity.case_id == Document.id
    ).group_by(
        Document.id, Document.title
    ).order_by(
        Document.id
    ).all()

    # Get summary statistics
    stats = {
        'total_cases_tracked': db.session.query(
            func.count(func.distinct(ProvenanceActivity.case_id))
        ).scalar() or 0,
        'total_activities': ProvenanceActivity.query.count(),
        'total_entities': ProvenanceEntity.query.count(),
        'total_agents': ProvenanceAgent.query.count()
    }

    return render_template('tools/provenance_viewer.html',
                         all_cases=all_cases,
                         stats=stats,
                         selected_case_id=selected_case_id,
                         selected_case=selected_case)


@provenance_bp.route('/tools/provenance/cases/<int:case_id>')
@auth_optional
def provenance_case(case_id):
    """Redirect to unified provenance view with case selected."""
    return redirect(url_for('provenance.case_provenance', case_id=case_id))


@provenance_bp.route('/scenario_pipeline/case/<int:case_id>/provenance')
@auth_optional
def case_provenance(case_id):
    """Unified provenance view for a single case."""
    document = Document.query.get_or_404(case_id)

    initial_step = request.args.get('step', type=int)
    initial_section = request.args.get('section')
    initial_concept = request.args.get('concept')

    return render_template('scenarios/provenance.html',
                           case=document,
                           initial_step=initial_step,
                           initial_section=initial_section,
                           initial_concept=initial_concept)


@provenance_bp.route('/api/provenance/case/<int:case_id>')
@auth_optional
def get_case_provenance(case_id):
    """Get provenance data for a specific case."""
    # Get the document
    document = Document.query.get_or_404(case_id)
    
    # Get all activities for this case
    activities = ProvenanceActivity.query.filter_by(
        case_id=case_id
    ).order_by(ProvenanceActivity.started_at).all()
    
    # Get all entities for this case
    entities = ProvenanceEntity.query.filter_by(
        case_id=case_id
    ).order_by(ProvenanceEntity.created_at).all()
    
    # Build timeline data
    timeline = []
    for activity in activities:
        timeline.append({
            'id': activity.id,
            'type': 'activity',
            'activity_type': activity.activity_type,
            'name': activity.activity_name,
            'status': activity.status,
            'started_at': activity.started_at.isoformat() if activity.started_at else None,
            'ended_at': activity.ended_at.isoformat() if activity.ended_at else None,
            'duration_ms': activity.duration_ms,
            'agent': {
                'name': activity.agent.agent_name,
                'type': activity.agent.agent_type
            } if activity.agent else None
        })
    
    # Build entity list
    entity_list = []
    for entity in entities:
        entity_data = {
            'id': entity.id,
            'type': entity.entity_type,
            'name': entity.entity_name,
            'size': entity.content_size,
            'confidence': entity.confidence_score,
            'created_at': entity.generation_time.isoformat() if entity.generation_time else None,
            'generating_activity_id': entity.generating_activity_id
        }
        
        # Add preview of content based on type
        if entity.entity_type == 'prompt':
            entity_data['preview'] = entity.content[:200] + '...' if len(entity.content) > 200 else entity.content
        elif entity.entity_type == 'response':
            entity_data['preview'] = entity.content[:200] + '...' if len(entity.content) > 200 else entity.content
        elif entity.entity_type in ['extracted_roles', 'extracted_resources']:
            try:
                content_json = json.loads(entity.content)
                entity_data['preview'] = f"Extracted {len(content_json)} items"
                entity_data['items'] = content_json[:5]  # First 5 items
            except:
                entity_data['preview'] = 'Extraction results'
        
        entity_list.append(entity_data)
    
    # Get provenance graph
    prov_service = get_provenance_service()
    graph = prov_service.get_provenance_graph(case_id)
    
    return jsonify({
        'document': {
            'id': document.id,
            'title': document.title,
            'type': document.document_type
        },
        'timeline': timeline,
        'entities': entity_list,
        'graph': graph,
        'stats': {
            'total_activities': len(activities),
            'total_entities': len(entities),
            'successful_activities': sum(1 for a in activities if a.status == 'completed'),
            'failed_activities': sum(1 for a in activities if a.status == 'failed')
        }
    })

@provenance_bp.route('/api/provenance/entity/<int:entity_id>')
@auth_optional
def get_entity_details(entity_id):
    """Get detailed information about a specific entity."""
    entity = ProvenanceEntity.query.get_or_404(entity_id)
    
    # Get derivations
    derived_from = ProvenanceDerivation.query.filter_by(
        derived_entity_id=entity_id
    ).all()
    
    derives = ProvenanceDerivation.query.filter_by(
        source_entity_id=entity_id
    ).all()
    
    # Get usage information
    used_by = ProvenanceUsage.query.filter_by(
        entity_id=entity_id
    ).all()
    
    return jsonify({
        'entity': {
            'id': entity.id,
            'type': entity.entity_type,
            'name': entity.entity_name,
            'content': entity.content,
            'content_hash': entity.content_hash,
            'content_size': entity.content_size,
            'confidence_score': entity.confidence_score,
            'quality_metrics': entity.quality_metrics,
            'metadata': entity.entity_metadata,
            'created_at': entity.created_at.isoformat() if entity.created_at else None,
            'generation_time': entity.generation_time.isoformat() if entity.generation_time else None
        },
        'derived_from': [
            {
                'entity_id': d.source_entity_id,
                'entity_name': d.source_entity.entity_name if d.source_entity else None,
                'derivation_type': d.derivation_type
            }
            for d in derived_from
        ],
        'derives': [
            {
                'entity_id': d.derived_entity_id,
                'entity_name': d.derived_entity.entity_name if d.derived_entity else None,
                'derivation_type': d.derivation_type
            }
            for d in derives
        ],
        'used_by': [
            {
                'activity_id': u.activity_id,
                'activity_name': u.activity.activity_name if u.activity else None,
                'usage_role': u.usage_role,
                'used_at': u.used_at.isoformat() if u.used_at else None
            }
            for u in used_by
        ]
    })

@provenance_bp.route('/api/provenance/activity/<int:activity_id>')
@auth_optional
def get_activity_details(activity_id):
    """Get detailed information about a specific activity."""
    activity = ProvenanceActivity.query.get_or_404(activity_id)
    
    # Get entities generated by this activity
    generated_entities = ProvenanceEntity.query.filter_by(
        generating_activity_id=activity_id
    ).all()
    
    # Get entities used by this activity
    used_entities = ProvenanceUsage.query.filter_by(
        activity_id=activity_id
    ).all()
    
    # Get communication relationships
    informed_by = ProvenanceCommunication.query.filter_by(
        informed_activity_id=activity_id
    ).all()
    
    informs = ProvenanceCommunication.query.filter_by(
        informing_activity_id=activity_id
    ).all()
    
    return jsonify({
        'activity': {
            'id': activity.id,
            'type': activity.activity_type,
            'name': activity.activity_name,
            'status': activity.status,
            'started_at': activity.started_at.isoformat() if activity.started_at else None,
            'ended_at': activity.ended_at.isoformat() if activity.ended_at else None,
            'duration_ms': activity.duration_ms,
            'error_message': activity.error_message,
            'execution_plan': activity.execution_plan,
            'metadata': activity.activity_metadata
        },
        'agent': {
            'id': activity.agent.id,
            'name': activity.agent.agent_name,
            'type': activity.agent.agent_type,
            'version': activity.agent.agent_version
        } if activity.agent else None,
        'generated': [
            {
                'entity_id': e.id,
                'entity_type': e.entity_type,
                'entity_name': e.entity_name
            }
            for e in generated_entities
        ],
        'used': [
            {
                'entity_id': u.entity.id if u.entity else None,
                'entity_name': u.entity.entity_name if u.entity else None,
                'usage_role': u.usage_role
            }
            for u in used_entities
        ],
        'informed_by': [
            {
                'activity_id': c.informing_activity_id,
                'activity_name': c.informing_activity.activity_name if c.informing_activity else None,
                'communication_type': c.communication_type
            }
            for c in informed_by
        ],
        'informs': [
            {
                'activity_id': c.informed_activity_id,
                'activity_name': c.informed_activity.activity_name if c.informed_activity else None,
                'communication_type': c.communication_type
            }
            for c in informs
        ]
    })

@provenance_bp.route('/api/provenance/search')
@auth_optional
def search_provenance():
    """Search provenance records."""
    query_type = request.args.get('type', 'all')
    search_term = request.args.get('q', '')
    limit = min(int(request.args.get('limit', 50)), 100)
    
    results = {
        'activities': [],
        'entities': [],
        'agents': []
    }
    
    if query_type in ['all', 'activities']:
        activities = ProvenanceActivity.query.filter(
            ProvenanceActivity.activity_name.ilike(f'%{search_term}%')
        ).limit(limit).all()
        
        results['activities'] = [
            {
                'id': a.id,
                'name': a.activity_name,
                'type': a.activity_type,
                'case_id': a.case_id,
                'status': a.status,
                'created_at': a.created_at.isoformat() if a.created_at else None
            }
            for a in activities
        ]
    
    if query_type in ['all', 'entities']:
        entities = ProvenanceEntity.query.filter(
            ProvenanceEntity.entity_name.ilike(f'%{search_term}%')
        ).limit(limit).all()
        
        results['entities'] = [
            {
                'id': e.id,
                'name': e.entity_name,
                'type': e.entity_type,
                'case_id': e.case_id,
                'created_at': e.created_at.isoformat() if e.created_at else None
            }
            for e in entities
        ]
    
    if query_type in ['all', 'agents']:
        agents = ProvenanceAgent.query.filter(
            ProvenanceAgent.agent_name.ilike(f'%{search_term}%')
        ).limit(limit).all()
        
        results['agents'] = [
            {
                'id': ag.id,
                'name': ag.agent_name,
                'type': ag.agent_type,
                'version': ag.agent_version
            }
            for ag in agents
        ]
    
    return jsonify(results)


@provenance_bp.route('/api/provenance/case/<int:case_id>/pipeline')
@auth_optional
def get_case_pipeline(case_id):
    """
    Get structured pipeline data for vertical timeline view.
    Returns all extraction prompts and entities organized by step/pass/concept.
    """
    document = Document.query.get_or_404(case_id)

    # Build pipeline data structure
    pipeline = []

    # Steps 1-3: Entity extraction
    for step_def in PIPELINE_STRUCTURE['steps']:
        step_data = {
            'step': step_def['step'],
            'name': step_def['name'],
            'color': step_def['color'],
            'passes': []
        }

        if step_def['step'] == 3:
            # Step 3 uses a single LangGraph extraction (not per-section passes)
            pass_data = {
                'name': 'Temporal Dynamics',
                'section_type': 'facts',
                'extractions': []
            }
            for concept in step_def['concepts']:
                extraction_data = _get_temporal_extraction_data(case_id, concept)
                pass_data['extractions'].append(extraction_data)
            step_data['passes'].append(pass_data)
        else:
            for section_type in PIPELINE_STRUCTURE['passes']:
                pass_name = 'Pass 1 (Facts)' if section_type == 'facts' else 'Pass 2 (Discussion)'
                pass_data = {
                    'name': pass_name,
                    'section_type': section_type,
                    'extractions': []
                }

                for concept in step_def['concepts']:
                    extraction_data = _get_extraction_data(
                        case_id,
                        step_def['step'],
                        section_type,
                        concept
                    )
                    pass_data['extractions'].append(extraction_data)

                step_data['passes'].append(pass_data)

        pipeline.append(step_data)

    # Step 4: Synthesis phases
    step4_data = {
        'step': 4,
        'name': 'Synthesis & Analysis',
        'color': PIPELINE_STRUCTURE['step4_color'],
        'phases': []
    }

    for phase_def in PIPELINE_STRUCTURE['step4_phases']:
        phase_data = _get_step4_phase_data(case_id, phase_def)
        step4_data['phases'].append(phase_data)

    pipeline.append(step4_data)

    # QC verification results (latest audit for this case)
    qc_result = None
    qc_row = db.session.execute(text("""
        SELECT verification_date, protocol_version, overall_status,
               entity_count_total, extraction_types_count,
               critical_count, warning_count, info_count, check_results
        FROM case_verification_results
        WHERE case_id = :case_id
        ORDER BY verification_date DESC LIMIT 1
    """), {'case_id': case_id}).fetchone()
    if qc_row:
        qc_result = {
            'verification_date': qc_row[0].isoformat() if qc_row[0] else None,
            'protocol_version': qc_row[1],
            'overall_status': qc_row[2],
            'entity_count_total': qc_row[3],
            'extraction_types_count': qc_row[4],
            'critical_count': qc_row[5],
            'warning_count': qc_row[6],
            'info_count': qc_row[7],
            'check_results': json.loads(qc_row[8]) if isinstance(qc_row[8], str) else qc_row[8],
        }

    return jsonify({
        'case': {
            'id': document.id,
            'title': document.title
        },
        'pipeline': pipeline,
        'entity_colors': ENTITY_COLORS,
        'qc_verification': qc_result
    })


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
                'color': ENTITY_COLORS.get(concept_type, '#6c757d')
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
            'session_id': prompt.extraction_session_id
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
        'color': ENTITY_COLORS.get(concept_type, '#6c757d')
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
            'is_published': e.is_published
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
            'rdf_data': dp.rdf_json_ld
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
        'has_data': prompt is not None,
        'prompt': {
            'id': prompt.id,
            'text': prompt.prompt_text,
            'response': prompt.raw_response,
            'model': prompt.llm_model,
            'created_at': prompt.created_at.isoformat() if prompt.created_at else None,
            'results_summary': prompt.results_summary if isinstance(prompt.results_summary, dict) else None,
            'session_id': prompt.extraction_session_id
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
    """Look up W3C provenance metadata for an extraction prompt.

    Matches via session_id + activity_name pattern. Falls back to
    case_id + activity_name when session_id is unavailable.
    """
    if not prompt:
        return None

    activity_name = CONCEPT_ACTIVITY_MAP.get(concept_type)

    activity = None
    if prompt.extraction_session_id and activity_name:
        # Primary match: session_id + concept-specific activity
        activity = ProvenanceActivity.query.filter_by(
            case_id=case_id,
            session_id=prompt.extraction_session_id,
            activity_name=activity_name
        ).order_by(ProvenanceActivity.started_at.desc()).first()

    if not activity and prompt.extraction_session_id:
        # Fallback: any activity in this session for this case
        activity = ProvenanceActivity.query.filter_by(
            case_id=case_id,
            session_id=prompt.extraction_session_id
        ).order_by(ProvenanceActivity.started_at.desc()).first()

    if not activity and activity_name:
        # Last resort: match by case + activity name, closest to prompt timestamp
        activity = ProvenanceActivity.query.filter_by(
            case_id=case_id,
            activity_name=activity_name
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


def _determine_origin(activity):
    """Classify extraction origin from activity metadata.

    Returns one of: automated_pipeline, user_initiated,
    individual_extraction, algorithmic.
    """
    name = activity.activity_name or ''

    if 'entities_pass' in name or 'normative_pass' in name or 'temporal_pass' in name:
        return 'automated_pipeline'
    if activity.activity_type in ('composition', 'synthesis', 'analysis'):
        return 'algorithmic'
    if 'dual_' in name or '_extraction' in name:
        return 'user_initiated'
    return 'user_initiated'