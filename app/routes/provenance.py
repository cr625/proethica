"""
Provenance viewer routes for PROV-O tracking visualization.
"""

from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from sqlalchemy import desc, func
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
            'concepts': ['actions', 'events']
        }
    ],
    'step4_phases': [
        {'phase': '2A', 'name': 'Code Provisions', 'concept_type': 'code_provision_reference'},
        {'phase': '2B-Q', 'name': 'Ethical Questions', 'concept_type': 'ethical_question'},
        {'phase': '2B-C', 'name': 'Ethical Conclusions', 'concept_type': 'ethical_conclusion'},
        {'phase': '2C', 'name': 'Transformation Analysis', 'concept_type': 'transformation_classification'},
        {'phase': '2D', 'name': 'Rich Analysis', 'concept_type': 'rich_analysis'},
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
    'events': '#ffc107'       # Yellow
}

provenance_bp = Blueprint('provenance', __name__)


@provenance_bp.route('/tools/provenance')
@auth_optional
def provenance_hub():
    """Provenance hub - redirects to cases view."""
    return redirect(url_for('provenance.provenance_cases'))


@provenance_bp.route('/tools/provenance/cases')
@auth_optional
def provenance_cases():
    """All cases provenance viewer page with optional case pre-selected."""
    # Get optional selected case_id from query params
    selected_case_id = request.args.get('selected', type=int)
    selected_case = None
    if selected_case_id:
        selected_case = Document.query.get(selected_case_id)

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
    return redirect(url_for('provenance.provenance_cases', selected=case_id))


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

    return jsonify({
        'case': {
            'id': document.id,
            'title': document.title
        },
        'pipeline': pipeline,
        'entity_colors': ENTITY_COLORS
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
            'results_summary': prompt.results_summary
        } if prompt else None,
        'entities': section_entities,
        'entity_count': len(section_entities)
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

    return {
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
            'results_summary': prompt.results_summary if isinstance(prompt.results_summary, dict) else None
        } if prompt else None,
        'entities': entities,
        'entity_count': len(entities)
    }