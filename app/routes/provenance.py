"""
Provenance viewer routes for PROV-O tracking visualization.
"""

from flask import Blueprint, render_template, jsonify, request
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
from app.services.provenance_service import get_provenance_service
from app.utils.environment_auth import auth_optional

provenance_bp = Blueprint('provenance', __name__)

@provenance_bp.route('/tools/provenance')
@auth_optional
def provenance_viewer():
    """Main provenance viewer page."""
    # Get recent cases with provenance data
    recent_cases = db.session.query(
        Document.id,
        Document.title,
        Document.document_type,
        func.count(ProvenanceActivity.id).label('activity_count'),
        func.max(ProvenanceActivity.created_at).label('last_activity')
    ).outerjoin(
        ProvenanceActivity, ProvenanceActivity.case_id == Document.id
    ).group_by(
        Document.id, Document.title, Document.document_type
    ).having(
        func.count(ProvenanceActivity.id) > 0
    ).order_by(
        desc('last_activity')
    ).limit(20).all()
    
    # Get summary statistics
    stats = {
        'total_activities': ProvenanceActivity.query.count(),
        'total_entities': ProvenanceEntity.query.count(),
        'total_agents': ProvenanceAgent.query.count(),
        'total_cases_tracked': db.session.query(
            func.count(func.distinct(ProvenanceActivity.case_id))
        ).scalar() or 0
    }
    
    return render_template('tools/provenance_viewer.html',
                         recent_cases=recent_cases,
                         stats=stats)

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