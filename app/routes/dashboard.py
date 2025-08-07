"""
Unified dashboard for ProEthica ethical decision-making system.

This dashboard provides a comprehensive overview of the system's capabilities,
current data, and workflow status.
"""

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import json
import logging

from app.models import db
from app.models.world import World
from app.models.guideline import Guideline
from app.models.document import Document
from app.models.document_section import DocumentSection
from app.models.entity_triple import EntityTriple
from app.models.ontology import Ontology
from app.models.deconstructed_case import DeconstructedCase
try:
    from app.models.case_guideline_associations import CaseGuidelineAssociation
except ImportError:
    # Create a placeholder for testing if the model doesn't exist yet
    CaseGuidelineAssociation = None
from app.services.ontology_entity_service import OntologyEntityService
from app.services.recommendation_engine import recommendation_engine
from app.services.firac_analysis_service import firac_analysis_service
from app.services.ethics_committee_agent import ethics_committee_agent

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__)

# Setup logging
logger = logging.getLogger(__name__)


@dashboard_bp.route('/')
@login_required
def index():
    """Admin dashboard showing system overview and management tools."""
    
    # Get system statistics
    stats = get_system_statistics()
    
    # Get recent activity
    recent_activity = get_recent_activity()
    
    # Get ontology sync status
    sync_status = get_ontology_sync_status()
    
    # Get simplified system status (MCP server, database)
    system_status = get_simplified_system_status()
    
    return render_template(
        'dashboard/index.html',
        stats=stats,
        recent_activity=recent_activity,
        sync_status=sync_status,
        system_status=system_status
    )


@dashboard_bp.route('/api/stats')
@login_required
def api_system_stats():
    """API endpoint for system statistics."""
    stats = get_system_statistics()
    return jsonify(stats)


@dashboard_bp.route('/api/workflow')
@login_required
def api_workflow_status():
    """API endpoint for workflow status."""
    workflow = get_workflow_status()
    return jsonify(workflow)


@dashboard_bp.route('/api/capabilities')
@login_required
def api_capabilities():
    """API endpoint for capability assessment."""
    capabilities = assess_capabilities()
    return jsonify(capabilities)


@dashboard_bp.route('/api/sync-status')
@login_required
def api_sync_status():
    """API endpoint for ontology sync status."""
    sync_status = get_ontology_sync_status()
    return jsonify(sync_status)


@dashboard_bp.route('/world/<int:world_id>')
@login_required
def world_dashboard(world_id):
    """Detailed dashboard for a specific world."""
    
    world = World.query.get_or_404(world_id)
    
    # Get world-specific statistics
    world_stats = get_world_statistics(world_id)
    
    # Get world analysis status
    analysis_status = get_world_analysis_status(world_id)
    
    # Get recommendations status
    recommendations_status = get_world_recommendations_status(world_id)
    
    return render_template(
        'dashboard/world.html',
        world=world,
        stats=world_stats,
        analysis_status=analysis_status,
        recommendations_status=recommendations_status
    )


@dashboard_bp.route('/case/<int:case_id>/recommendations')
@login_required
def case_recommendations(case_id):
    """Generate and display recommendations for a specific case."""
    
    try:
        # Generate recommendations using the new engine
        recommendations = recommendation_engine.generate_recommendations(case_id)
        
        return render_template(
            'dashboard/recommendations.html',
            recommendations=recommendations
        )
    except Exception as e:
        logger.error(f"Error generating recommendations for case {case_id}: {e}")
        return render_template(
            'dashboard/recommendations_error.html',
            case_id=case_id,
            error=str(e)
        )


@dashboard_bp.route('/api/case/<int:case_id>/recommendations')
@login_required
def api_case_recommendations(case_id):
    """API endpoint for case recommendations."""
    
    try:
        recommendations = recommendation_engine.generate_recommendations(case_id)
        
        # Convert to JSON-serializable format
        return jsonify({
            'status': 'success',
            'case_id': recommendations.case_id,
            'case_title': recommendations.case_title,
            'overall_risk_assessment': recommendations.overall_risk_assessment,
            'key_ethical_themes': recommendations.key_ethical_themes,
            'recommendations': [
                {
                    'id': rec.id,
                    'title': rec.title,
                    'type': rec.recommendation_type,
                    'confidence': rec.confidence,
                    'priority': rec.priority,
                    'summary': rec.summary,
                    'detailed_explanation': rec.detailed_explanation,
                    'ethical_reasoning': rec.ethical_reasoning,
                    'risk_level': rec.risk_level,
                    'predicted_outcome': rec.predicted_outcome,
                    'outcome_confidence': rec.outcome_confidence,
                    'guideline_concepts': rec.guideline_concepts,
                    'similar_cases': rec.similar_cases,
                    'pattern_indicators': rec.pattern_indicators,
                    'stakeholder_considerations': rec.stakeholder_considerations,
                    'implementation_steps': rec.implementation_steps,
                    'potential_challenges': rec.potential_challenges
                }
                for rec in recommendations.recommendations
            ],
            'confidence_overview': recommendations.confidence_overview,
            'processing_metadata': recommendations.processing_metadata
        })
    except Exception as e:
        logger.error(f"Error generating API recommendations for case {case_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@dashboard_bp.route('/recommendations/test')
@login_required
def test_recommendations():
    """Test page for recommendation engine."""
    
    # Get sample cases - if associations exist, get cases with associations, otherwise get any cases
    if CaseGuidelineAssociation is not None:
        try:
            cases_with_associations = db.session.query(Document.id, Document.title)\
                .join(CaseGuidelineAssociation, Document.id == CaseGuidelineAssociation.case_id)\
                .distinct()\
                .limit(5)\
                .all()
        except Exception as e:
            logger.warning(f"Could not query associations: {e}")
            cases_with_associations = []
    else:
        cases_with_associations = []
    
    # If no cases with associations, get any cases that look like NSPE cases
    if not cases_with_associations:
        try:
            cases_with_associations = db.session.query(Document.id, Document.title)\
                .filter(Document.doc_metadata.op('->>')('case_number').isnot(None))\
                .limit(5)\
                .all()
        except Exception as e:
            logger.warning(f"Could not query cases: {e}")
            cases_with_associations = []
    
    return render_template(
        'dashboard/test_recommendations.html',
        cases=cases_with_associations
    )


@dashboard_bp.route('/case/<int:case_id>/firac')
@login_required
def case_firac_analysis(case_id):
    """Generate and display FIRAC analysis for a specific case."""
    
    try:
        # Generate FIRAC analysis
        firac_analysis = firac_analysis_service.analyze_case(case_id)
        
        return render_template(
            'dashboard/firac_analysis.html',
            analysis=firac_analysis
        )
    except Exception as e:
        logger.error(f"Error generating FIRAC analysis for case {case_id}: {e}")
        return render_template(
            'dashboard/firac_error.html',
            case_id=case_id,
            error=str(e)
        )


@dashboard_bp.route('/api/case/<int:case_id>/firac')
@login_required
def api_case_firac_analysis(case_id):
    """API endpoint for FIRAC analysis."""
    
    try:
        firac_analysis = firac_analysis_service.analyze_case(case_id)
        
        # Convert to JSON-serializable format
        return jsonify({
            'status': 'success',
            'case_id': firac_analysis.case_id,
            'case_title': firac_analysis.case_title,
            'facts': {
                'factual_statements': firac_analysis.facts.factual_statements,
                'key_stakeholders': firac_analysis.facts.key_stakeholders,
                'context_description': firac_analysis.facts.context_description,
                'source_sections': firac_analysis.facts.source_sections
            },
            'issues': {
                'primary_ethical_issues': firac_analysis.issues.primary_ethical_issues,
                'secondary_issues': firac_analysis.issues.secondary_issues,
                'ethical_dilemmas': firac_analysis.issues.ethical_dilemmas,
                'stakeholder_conflicts': firac_analysis.issues.stakeholder_conflicts
            },
            'rules': {
                'applicable_guidelines': firac_analysis.rules.applicable_guidelines,
                'ontology_concepts': firac_analysis.rules.ontology_concepts,
                'ethical_principles': firac_analysis.rules.ethical_principles,
                'professional_standards': firac_analysis.rules.professional_standards,
                'confidence_scores': firac_analysis.rules.confidence_scores
            },
            'analysis': {
                'rule_application': firac_analysis.analysis.rule_application,
                'conflict_resolution': firac_analysis.analysis.conflict_resolution,
                'stakeholder_impact': firac_analysis.analysis.stakeholder_impact,
                'precedent_cases': firac_analysis.analysis.precedent_cases,
                'reasoning_chain': firac_analysis.analysis.reasoning_chain
            },
            'conclusion': {
                'recommended_action': firac_analysis.conclusion.recommended_action,
                'implementation_steps': firac_analysis.conclusion.implementation_steps,
                'risk_assessment': firac_analysis.conclusion.risk_assessment,
                'alternative_approaches': firac_analysis.conclusion.alternative_approaches,
                'committee_consultation_needed': firac_analysis.conclusion.committee_consultation_needed
            },
            'confidence_overview': firac_analysis.confidence_overview,
            'processing_metadata': firac_analysis.processing_metadata
        })
    except Exception as e:
        logger.error(f"Error generating API FIRAC analysis for case {case_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@dashboard_bp.route('/case/<int:case_id>/ethics-committee')
@login_required
def case_ethics_committee(case_id):
    """Generate and display ethics committee consultation for a specific case."""
    
    try:
        # First generate FIRAC analysis
        firac_analysis = firac_analysis_service.analyze_case(case_id)
        
        # Then conduct ethics committee consultation
        committee_discussion = ethics_committee_agent.conduct_committee_consultation(firac_analysis)
        
        return render_template(
            'dashboard/ethics_committee.html',
            discussion=committee_discussion,
            firac_analysis=firac_analysis
        )
    except Exception as e:
        logger.error(f"Error generating ethics committee consultation for case {case_id}: {e}")
        return render_template(
            'dashboard/committee_error.html',
            case_id=case_id,
            error=str(e)
        )


@dashboard_bp.route('/api/case/<int:case_id>/ethics-committee')
@login_required
def api_case_ethics_committee(case_id):
    """API endpoint for ethics committee consultation."""
    
    try:
        # Generate FIRAC analysis first
        firac_analysis = firac_analysis_service.analyze_case(case_id)
        
        # Conduct committee consultation
        committee_discussion = ethics_committee_agent.conduct_committee_consultation(firac_analysis)
        
        # Convert to JSON-serializable format
        return jsonify({
            'status': 'success',
            'case_id': committee_discussion.case_id,
            'case_title': committee_discussion.case_title,
            'discussion_phases': committee_discussion.discussion_phases,
            'member_positions': [
                {
                    'member_name': pos.member.name,
                    'member_role': pos.member.role,
                    'expertise': pos.member.expertise,
                    'position': pos.position,
                    'reasoning': pos.reasoning,
                    'supporting_evidence': pos.supporting_evidence,
                    'concerns_raised': pos.concerns_raised,
                    'confidence': pos.confidence
                }
                for pos in committee_discussion.member_positions
            ],
            'areas_of_agreement': committee_discussion.areas_of_agreement,
            'areas_of_disagreement': committee_discussion.areas_of_disagreement,
            'consensus_recommendation': committee_discussion.consensus_recommendation,
            'minority_opinions': committee_discussion.minority_opinions,
            'follow_up_actions': committee_discussion.follow_up_actions,
            'confidence_in_consensus': committee_discussion.confidence_in_consensus
        })
    except Exception as e:
        logger.error(f"Error generating API ethics committee consultation for case {case_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@dashboard_bp.route('/firac/test')
@login_required
def test_firac_analysis():
    """Test page for FIRAC analysis."""
    
    # Get sample cases for testing
    if CaseGuidelineAssociation is not None:
        try:
            cases_with_associations = db.session.query(Document.id, Document.title)\
                .join(CaseGuidelineAssociation, Document.id == CaseGuidelineAssociation.case_id)\
                .distinct()\
                .limit(5)\
                .all()
        except Exception as e:
            logger.warning(f"Could not query associations: {e}")
            cases_with_associations = []
    else:
        cases_with_associations = []
    
    # If no cases with associations, get any cases that look like NSPE cases
    if not cases_with_associations:
        try:
            cases_with_associations = db.session.query(Document.id, Document.title)\
                .filter(Document.doc_metadata.op('->>')('case_number').isnot(None))\
                .limit(5)\
                .all()
        except Exception as e:
            logger.warning(f"Could not query cases: {e}")
            cases_with_associations = []
    
    return render_template(
        'dashboard/test_firac.html',
        cases=cases_with_associations
    )


def get_simplified_system_status():
    """Get simplified system status for admin dashboard."""
    import os
    import requests
    
    status = {
        'mcp_server': False,
        'database': False,
        'mcp_url': os.environ.get('MCP_SERVER_URL', 'http://localhost:5001')
    }
    
    # Check MCP server
    try:
        response = requests.post(
            f"{status['mcp_url']}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "list_tools",
                "params": {},
                "id": 1
            },
            timeout=2
        )
        if response.status_code == 200:
            status['mcp_server'] = True
    except:
        pass
    
    # Check database
    try:
        # Simple query to check database connection
        World.query.limit(1).first()
        status['database'] = True
    except:
        pass
    
    return status


def get_ontology_sync_status():
    """Check synchronization status between TTL files and database."""
    import os
    from datetime import datetime
    import hashlib
    from app.models.ontology_version import OntologyVersion
    
    sync_status = {
        'core_ontologies': [],
        'guideline_ontologies': [],
        'last_sync': None,
        'needs_sync': False
    }
    
    try:
        # Check core ontology files
        core_ontologies = ['bfo', 'proethica-intermediate', 'engineering-ethics']
        for domain in core_ontologies:
            ttl_path = f'ontologies/{domain}.ttl'
            
            logger.info(f"Checking ontology: {domain} at path: {ttl_path}")
            
            if os.path.exists(ttl_path):
                # Get file modification time
                file_mtime = datetime.fromtimestamp(os.path.getmtime(ttl_path))
                
                # Get file content for comparison
                with open(ttl_path, 'r') as f:
                    file_content = f.read()
                
                # Check database version
                ontology = Ontology.query.filter_by(domain_id=domain).first()
                latest_version = None
                db_synced = False
                
                logger.info(f"Found ontology in DB: {ontology is not None}")
                
                if ontology:
                    latest_version = OntologyVersion.query.filter_by(
                        ontology_id=ontology.id
                    ).order_by(OntologyVersion.created_at.desc()).first()
                    
                    # Assume synced if both exist (simplified check)
                    db_synced = True
                    
                    logger.info(f"Latest version exists: {latest_version is not None}")
                
                sync_status['core_ontologies'].append({
                    'domain': domain,
                    'file_exists': True,
                    'file_modified': file_mtime.isoformat(),
                    'db_exists': ontology is not None,
                    'is_synced': db_synced,
                    'last_db_sync': latest_version.created_at.isoformat() if latest_version else None,
                    'has_content': bool(latest_version.content) if latest_version else False,
                    'ontology_id': ontology.id if ontology else None
                })
                
                if not db_synced:
                    sync_status['needs_sync'] = True
            else:
                logger.warning(f"TTL file not found: {ttl_path}")
                # Add entry for missing file
                sync_status['core_ontologies'].append({
                    'domain': domain,
                    'file_exists': False,
                    'file_modified': None,
                    'db_exists': False,
                    'is_synced': False,
                    'last_db_sync': None,
                    'has_content': False,
                    'ontology_id': None
                })
        
        # Count guideline-derived ontologies (database only)
        guideline_ontology_count = Ontology.query.filter(
            Ontology.domain_id.like('%guideline-%')
        ).count()
        
        sync_status['guideline_ontologies'] = {
            'count': guideline_ontology_count,
            'note': 'Guideline ontologies exist only in database (no TTL files)'
        }
        
        # Get last sync time
        last_sync = OntologyVersion.query.order_by(
            OntologyVersion.created_at.desc()
        ).first()
        if last_sync:
            sync_status['last_sync'] = last_sync.created_at.isoformat()
        
        logger.info(f"Sync status generated: {len(sync_status['core_ontologies'])} ontologies")
        
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        # Return a default status to prevent template errors
        sync_status['core_ontologies'] = [
            {'domain': 'bfo', 'file_exists': False, 'db_exists': False, 'is_synced': False, 'ontology_id': None},
            {'domain': 'proethica-intermediate', 'file_exists': False, 'db_exists': False, 'is_synced': False, 'ontology_id': None},
            {'domain': 'engineering-ethics', 'file_exists': False, 'db_exists': False, 'is_synced': False, 'ontology_id': None}
        ]
    
    return sync_status


def get_system_statistics():
    """Get overall system statistics for admin dashboard."""
    
    # Basic counts
    world_count = World.query.count()
    guideline_count = Document.query.filter_by(document_type='guideline').count()
    document_count = Document.query.count()
    case_count = Document.query.filter(
        Document.doc_metadata.op('->>')('case_number').isnot(None)
    ).count()
    
    # Ontology statistics
    ontology_count = Ontology.query.count()
    entity_triple_count = EntityTriple.query.count()
    
    # Document sections with embeddings
    embedded_sections = DocumentSection.query.filter(
        DocumentSection.embedding.isnot(None)
    ).count()
    total_sections = DocumentSection.query.count()
    
    # Processing statistics
    processed_docs = Document.query.filter(
        Document.doc_metadata.op('->>')('document_structure').isnot(None)
    ).count()
    
    # Guideline analysis statistics
    # Count Documents with guideline type that have concept metadata
    analyzed_guidelines = Document.query.filter(
        Document.document_type == 'guideline',
        Document.doc_metadata.op('->>')('concepts_extracted').isnot(None)
    ).count()
    
    # Association statistics
    associations_count = db.session.query(func.count()).select_from(
        db.session.query(EntityTriple.id).filter(
            EntityTriple.entity_type == 'case_guideline_association'
        ).subquery()
    ).scalar() or 0
    
    # Get database table count
    try:
        result = db.session.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
        )
        table_count = result.scalar()
    except:
        table_count = 0
    
    return {
        'overview': {
            'worlds': world_count,
            'guidelines': guideline_count,
            'documents': document_count,
            'cases': case_count,
            'ontologies': ontology_count
        },
        'processing': {
            'total_documents': document_count,
            'processed_documents': processed_docs,
            'structure_percentage': round((processed_docs / document_count * 100) if document_count > 0 else 0),
            'total_sections': total_sections,
            'embedded_sections': embedded_sections,
            'embeddings_percentage': round((embedded_sections / total_sections * 100) if total_sections > 0 else 0)
        },
        'analysis': {
            'total_guidelines': guideline_count,
            'analyzed_guidelines': analyzed_guidelines,
            'analysis_rate': (analyzed_guidelines / guideline_count * 100) if guideline_count > 0 else 0,
            'entity_triples': entity_triple_count,
            'associations': associations_count
        },
        'database': {
            'table_count': table_count
        }
    }


def get_recent_activity():
    """Get recent system activity."""
    
    # Recent documents
    recent_docs = Document.query.order_by(desc(Document.created_at)).limit(5).all()
    
    # Recent guidelines
    recent_guidelines = Document.query.filter_by(document_type='guideline').order_by(desc(Document.created_at)).limit(5).all()
    
    # Recent worlds
    recent_worlds = World.query.order_by(desc(World.created_at)).limit(5).all()
    
    return {
        'documents': [{
            'id': doc.id,
            'title': doc.title,
            'document_type': doc.document_type,
            'created_at': doc.created_at.isoformat() if doc.created_at else None
        } for doc in recent_docs],
        'guidelines': [{
            'id': guideline.id,
            'title': guideline.title,
            'world_id': guideline.world_id,
            'world_name': guideline.world.name if guideline.world else 'Unknown',
            'created_at': guideline.created_at.isoformat() if guideline.created_at else None
        } for guideline in recent_guidelines],
        'worlds': [{
            'id': world.id,
            'name': world.name,
            'description': world.description,
            'created_at': world.created_at.isoformat() if world.created_at else None
        } for world in recent_worlds]
    }


def get_workflow_status():
    """Get the status of the ethical decision-making workflow."""
    
    # Document processing pipeline status
    pipeline_status = {
        'document_import': {
            'name': 'Document Import',
            'status': 'operational',
            'description': 'URL and file upload processing',
            'completion': 100
        },
        'structure_annotation': {
            'name': 'Structure Annotation',
            'status': 'operational',
            'description': 'RDF triple generation and section parsing',
            'completion': 100
        },
        'section_embedding': {
            'name': 'Section Embedding',
            'status': 'operational',
            'description': 'Vector embeddings for semantic search',
            'completion': 100
        },
        'concept_extraction': {
            'name': 'Concept Extraction',
            'status': 'operational',
            'description': 'LLM-powered guideline analysis',
            'completion': 100
        },
        'association_generation': {
            'name': 'Association Generation',
            'status': 'operational',
            'description': 'Case-guideline hybrid associations',
            'completion': 100
        },
        'recommendation_engine': {
            'name': 'Recommendation Engine',
            'status': 'operational',
            'description': 'Synthesize associations into recommendations',
            'completion': 100
        },
        'decision_visualization': {
            'name': 'Decision Visualization',
            'status': 'partial',
            'description': 'Decision trees and confidence displays',
            'completion': 30
        },
        'outcome_tracking': {
            'name': 'Outcome Tracking',
            'status': 'missing',
            'description': 'Track decisions and learn from outcomes',
            'completion': 0
        }
    }
    
    return {
        'pipeline': pipeline_status,
        'overall_completion': sum(step['completion'] for step in pipeline_status.values()) / len(pipeline_status)
    }


def assess_capabilities():
    """Assess current system capabilities."""
    
    capabilities = {
        'document_processing': {
            'name': 'Document Processing',
            'status': 'excellent',
            'features': [
                'URL extraction (NSPE cases)',
                'Document structure annotation',
                'RDF triple generation',
                'Section embeddings',
                'Dual format storage (HTML/text)'
            ],
            'completion': 95
        },
        'ontology_management': {
            'name': 'Ontology Management',
            'status': 'good',
            'features': [
                'Multiple ontology support',
                'Entity browsing',
                'Type management',
                'Concept classification',
                'Triple visualization'
            ],
            'completion': 85
        },
        'guideline_analysis': {
            'name': 'Guideline Analysis',
            'status': 'excellent',
            'features': [
                'LLM concept extraction',
                'Confidence scoring',
                'Type mapping',
                'Duplicate detection',
                'Review workflow'
            ],
            'completion': 90
        },
        'case_analysis': {
            'name': 'Case Analysis',
            'status': 'good',
            'features': [
                'Section parsing',
                'Semantic embedding',
                'Association generation',
                'Pattern recognition',
                'Confidence scoring'
            ],
            'completion': 80
        },
        'semantic_search': {
            'name': 'Semantic Search',
            'status': 'good',
            'features': [
                'Vector similarity search',
                'Cross-document analysis',
                'Related case discovery',
                'Concept-based filtering'
            ],
            'completion': 75
        },
        'decision_support': {
            'name': 'Decision Support',
            'status': 'needs_work',
            'features': [
                'Mock decision engine (placeholder)',
                'Basic scenario creation',
                'Pattern indicators',
                'Association confidence'
            ],
            'completion': 40
        },
        'recommendation_generation': {
            'name': 'Recommendation Generation',
            'status': 'excellent',
            'features': [
                'Recommendation synthesis (operational)',
                'Confidence ranking (operational)',
                'Explanation generation (operational)',
                'Implementation guidance (operational)'
            ],
            'completion': 95
        },
        'outcome_learning': {
            'name': 'Outcome Learning',
            'status': 'missing',
            'features': [
                'Outcome tracking (missing)',
                'Feedback collection (missing)',
                'Pattern learning (missing)',
                'Recommendation improvement (missing)'
            ],
            'completion': 5
        }
    }
    
    return capabilities


def get_world_statistics(world_id):
    """Get statistics for a specific world."""
    
    world = World.query.get(world_id)
    if not world:
        return {}
    
    # Guidelines in this world
    guidelines = Document.query.filter_by(world_id=world_id, document_type='guideline').all()
    
    # Documents/cases in this world
    # This is tricky since documents aren't directly linked to worlds
    # We'll need to infer from guideline associations or other relationships
    
    # Entity triples for this world
    entity_triples = EntityTriple.query.filter_by(world_id=world_id).all()
    
    # Get concept types from entity triples
    concept_types = {}
    for triple in entity_triples:
        if triple.entity_type == 'guideline_concept':
            concept_type = triple.metadata.get('concept_type', 'unknown')
            concept_types[concept_type] = concept_types.get(concept_type, 0) + 1
    
    return {
        'world': {
            'id': world.id,
            'name': world.name,
            'description': world.description,
            'created_at': world.created_at.isoformat() if world.created_at else None
        },
        'content': {
            'guidelines': len(guidelines),
            'entity_triples': len(entity_triples),
            'concept_types': len(concept_types),
            'concepts_by_type': concept_types
        },
        'guidelines': [{
            'id': g.id,
            'title': g.title,
            'created_at': g.created_at.isoformat() if g.created_at else None,
            'has_analysis': bool(g.guideline_metadata.get('concepts'))
        } for g in guidelines]
    }


def get_world_analysis_status(world_id):
    """Get analysis status for a specific world."""
    
    # Count guidelines with concept analysis
    total_guidelines = Document.query.filter_by(world_id=world_id, document_type='guideline').count()
    analyzed_guidelines = Document.query.filter(
        Document.world_id == world_id,
        Document.document_type == 'guideline',
        Document.doc_metadata.op('->>')('concepts_extracted').isnot(None)
    ).count()
    
    # Get entity triples for analysis
    entity_triples = EntityTriple.query.filter_by(world_id=world_id).count()
    
    return {
        'guidelines': {
            'total': total_guidelines,
            'analyzed': analyzed_guidelines,
            'completion_rate': (analyzed_guidelines / total_guidelines * 100) if total_guidelines > 0 else 0
        },
        'entity_triples': entity_triples,
        'status': 'complete' if analyzed_guidelines == total_guidelines else 'partial'
    }


def get_world_recommendations_status(world_id):
    """Get recommendation status for a specific world."""
    
    # Check if we have association data
    if CaseGuidelineAssociation is not None:
        try:
            associations_count = CaseGuidelineAssociation.query.filter_by(world_id=world_id).count()
            if associations_count > 0:
                return {
                    'available': True,
                    'reason': 'Recommendation engine operational with association data',
                    'associations_count': associations_count,
                    'confidence_average': 0.75,  # Placeholder - could calculate real average
                    'status': 'operational'
                }
        except Exception as e:
            logger.warning(f"Could not check associations: {e}")
    
    # Fallback - engine is available but with basic recommendations
    return {
        'available': True,
        'reason': 'Recommendation engine operational (basic recommendations available)',
        'associations_count': 0,
        'confidence_average': 0.8,  # Basic recommendations have 80% confidence
        'status': 'basic_mode'
    }