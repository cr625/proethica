"""Dashboard data/status helper functions."""
from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import json
import logging

from app.models import db
from app.models.world import World
from app.models.guideline import Guideline
from app.models import Document
from app.models.document_section import DocumentSection
from app.models.entity_triple import EntityTriple
from app.models.ontology import Ontology
from app.models.deconstructed_case import DeconstructedCase
try:
    from app.models.case_guideline_associations import CaseGuidelineAssociation
except ImportError:
    # Create a placeholder for testing if the model doesn't exist yet
    CaseGuidelineAssociation = None
try:
    from app.models.temporary_concept import TemporaryConcept
except ImportError:
    # Create a placeholder for testing if the model doesn't exist yet
    TemporaryConcept = None
from app.services.step4_synthesis.firac_analysis_service import firac_analysis_service
from app.services.ethics_committee_agent import ethics_committee_agent
logger = logging.getLogger(__name__)


def get_simplified_system_status():
    """Get simplified system status for admin dashboard."""
    import os
    import requests
    
    status = {
        'mcp_server': False,
        'database': False,
        'mcp_url': current_app.config.get('ONTSERVE_MCP_URL', 'http://localhost:8082')
    }
    
    # Check MCP server
    try:
        response = requests.get(f"{status['mcp_url']}/health", timeout=2)
        if response.status_code == 200:
            status['mcp_server'] = True
    except Exception:
        logger.debug("MCP server health check failed", exc_info=True)
    
    # Check database
    try:
        # Simple query to check database connection
        World.query.limit(1).first()
        status['database'] = True
    except Exception:
        logger.warning("Database connection check failed", exc_info=True)
    
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
        'cases_ontologies': [],
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
        
        # Get detailed guideline-derived ontologies (database only)
        guideline_ontologies = Ontology.query.filter(
            Ontology.domain_id.like('%guideline-%')
        ).all()
        
        guideline_ontology_list = []
        for ont in guideline_ontologies:
            # Extract document ID from domain (e.g., "guideline-27-concepts" -> 27)
            try:
                doc_id = int(ont.domain_id.split('guideline-')[1].split('-')[0])
                # Get related document for guideline title
                from app.models import Document
                doc = Document.query.get(doc_id)
                related_guideline_title = doc.title if doc else f"Document {doc_id}"
                related_document_id = doc_id if doc else None
                related_world_id = doc.world_id if doc else None
            except (ValueError, IndexError):
                related_guideline_title = "Unknown Guideline"
                related_document_id = None
                related_world_id = None
            
            guideline_ontology_list.append({
                'id': ont.id,
                'name': ont.name,
                'domain_id': ont.domain_id,
                'related_guideline_title': related_guideline_title,
                'related_document_id': related_document_id,
                'related_world_id': related_world_id,
                'created_at': ont.created_at
            })
        
        sync_status['guideline_ontologies'] = {
            'count': len(guideline_ontologies),
            'list': guideline_ontology_list,
            'note': 'Guideline ontologies exist only in database (no TTL files)'
        }
        
        # Collect per-world cases ontologies stored in DB
        cases_ontologies = Ontology.query.filter(
            Ontology.domain_id.like('world-cases-%')
        ).all()

        cases_ontology_list = []
        for ont in cases_ontologies:
            # Extract world_id from domain_id pattern 'world-cases-<id>'
            related_world_id = None
            related_world_name = None
            try:
                related_world_id = int(ont.domain_id.split('world-cases-')[1].split('-')[0])
                world = World.query.get(related_world_id)
                if world:
                    related_world_name = world.name
            except Exception:
                pass

            cases_ontology_list.append({
                'id': ont.id,
                'name': ont.name,
                'domain_id': ont.domain_id,
                'related_world_id': related_world_id,
                'related_world_name': related_world_name,
                'created_at': ont.created_at
            })

        sync_status['cases_ontologies'] = {
            'count': len(cases_ontologies),
            'list': cases_ontology_list,
            'note': 'Per-world editable ontologies for scenario/case concepts'
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
        sync_status['guideline_ontologies'] = {
            'count': 0,
            'list': [],
            'note': 'Guideline ontologies exist only in database (no TTL files)'
        }
        sync_status['cases_ontologies'] = {
            'count': 0,
            'list': [],
            'note': 'Per-world editable ontologies for scenario/case concepts'
        }
        sync_status['last_sync'] = None
        sync_status['needs_sync'] = False
    
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
    
    # Temporary concept statistics
    pending_concepts_count = 0
    pending_sessions_count = 0
    if TemporaryConcept:
        try:
            pending_concepts_count = TemporaryConcept.query.filter_by(status='pending').count()
            pending_sessions_count = db.session.query(func.count(func.distinct(TemporaryConcept.session_id))).filter_by(status='pending').scalar() or 0
        except Exception as e:
            logger.warning(f"Could not query temporary concepts: {e}")
    
    # Get database table count
    try:
        result = db.session.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
        )
        table_count = result.scalar()
    except Exception:
        logger.warning("Failed to query database table count", exc_info=True)
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
            'associations': associations_count,
            'pending_concepts': pending_concepts_count,
            'pending_sessions': pending_sessions_count
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


