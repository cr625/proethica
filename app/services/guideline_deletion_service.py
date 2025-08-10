"""
Guideline Deletion Service

Safely removes guidelines and all associated data including:
- Entity triples (handled by cascade)
- Derived ontologies
- Guideline sections
- Related documents (with document_type='guideline')
- Any cached data
"""

import logging
from typing import Dict, Any, Optional
from app import db
from app.models.guideline import Guideline
from app.models.ontology import Ontology
from app.models.entity_triple import EntityTriple
from app.models.document import Document

logger = logging.getLogger(__name__)

class GuidelineDeletionService:
    """Service for safely deleting guidelines and all associated data"""
    
    @classmethod
    def delete_guideline(cls, guideline_id: int, confirm: bool = False) -> Dict[str, Any]:
        """
        Delete a guideline and all associated data.
        
        Args:
            guideline_id: ID of the guideline to delete
            confirm: Must be True to actually perform deletion
            
        Returns:
            Dict with deletion status and statistics
        """
        try:
            guideline = Guideline.query.get(guideline_id)
            if not guideline:
                return {
                    'success': False,
                    'error': f'Guideline {guideline_id} not found'
                }
            
            # Collect statistics before deletion
            stats = {
                'guideline_title': guideline.title,
                'triple_count': guideline.entity_triples.count(),
                'section_count': guideline.sections.count(),
                'derived_ontologies': [],
                'related_documents': []
            }
            
            # Find derived ontologies for this guideline
            derived_domain = f'engineering-ethics-guideline-{guideline_id}'
            derived_ontologies = Ontology.query.filter(
                Ontology.domain_id.like(f'%guideline-{guideline_id}%')
            ).all()
            
            for ont in derived_ontologies:
                stats['derived_ontologies'].append({
                    'id': ont.id,
                    'domain': ont.domain_id,
                    'name': ont.name
                })
            
            # Find related documents that reference this guideline
            related_documents = Document.query.filter(
                db.and_(
                    Document.document_type == 'guideline',
                    db.or_(
                        Document.doc_metadata.op('->>')('guideline_id') == str(guideline_id),
                        Document.doc_metadata.op('->>')('source_guideline_id') == str(guideline_id)
                    )
                )
            ).all()
            
            for doc in related_documents:
                stats['related_documents'].append({
                    'id': doc.id,
                    'title': doc.title,
                    'document_type': doc.document_type,
                    'created_at': doc.created_at.isoformat() if doc.created_at else None
                })
            
            if not confirm:
                # Dry run - just return what would be deleted
                return {
                    'success': True,
                    'dry_run': True,
                    'message': 'Dry run completed. Set confirm=True to actually delete.',
                    'would_delete': stats
                }
            
            # Perform actual deletion
            logger.info(f"Deleting guideline {guideline_id}: {guideline.title}")
            
            # Delete derived ontologies first
            for ont in derived_ontologies:
                logger.info(f"Deleting derived ontology: {ont.domain_id}")
                db.session.delete(ont)
            
            # Delete related documents
            for doc in related_documents:
                logger.info(f"Deleting related document: {doc.title} (ID: {doc.id})")
                db.session.delete(doc)
            
            # Delete the guideline (cascade will handle triples and sections)
            db.session.delete(guideline)
            db.session.commit()
            
            logger.info(f"Successfully deleted guideline {guideline_id} and all associated data")
            
            return {
                'success': True,
                'message': f'Successfully deleted guideline {guideline_id}',
                'deleted': stats
            }
            
        except Exception as e:
            logger.error(f"Error deleting guideline {guideline_id}: {e}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
    
    @classmethod
    def list_guideline_dependencies(cls, guideline_id: int) -> Dict[str, Any]:
        """
        List all data that would be affected by deleting a guideline.
        
        Args:
            guideline_id: ID of the guideline to check
            
        Returns:
            Dict with detailed dependency information
        """
        try:
            guideline = Guideline.query.get(guideline_id)
            if not guideline:
                return {
                    'success': False,
                    'error': f'Guideline {guideline_id} not found'
                }
            
            # Get all triples grouped by type
            triple_types = db.session.query(
                EntityTriple.primary_type,
                db.func.count(EntityTriple.id).label('count')
            ).filter(
                EntityTriple.guideline_id == guideline_id
            ).group_by(EntityTriple.primary_type).all()
            
            # Get unique concepts
            unique_concepts = db.session.query(
                db.func.count(db.func.distinct(EntityTriple.subject))
            ).filter(
                EntityTriple.guideline_id == guideline_id
            ).scalar()
            
            dependencies = {
                'guideline': {
                    'id': guideline.id,
                    'title': guideline.title,
                    'world_id': guideline.world_id
                },
                'statistics': {
                    'total_triples': guideline.entity_triples.count(),
                    'unique_concepts': unique_concepts,
                    'sections': guideline.sections.count()
                },
                'triple_types': [
                    {'type': t.primary_type or 'untyped', 'count': t.count}
                    for t in triple_types
                ],
                'derived_ontologies': [],
                'related_documents': []
            }
            
            # Check for derived ontologies
            derived_ontologies = Ontology.query.filter(
                Ontology.domain_id.like(f'%guideline-{guideline_id}%')
            ).all()
            
            for ont in derived_ontologies:
                dependencies['derived_ontologies'].append({
                    'id': ont.id,
                    'domain': ont.domain_id,
                    'name': ont.name,
                    'entity_count': ont.entity_count
                })
            
            # Check for related documents
            related_documents = Document.query.filter(
                db.and_(
                    Document.document_type == 'guideline',
                    db.or_(
                        Document.doc_metadata.op('->>')('guideline_id') == str(guideline_id),
                        Document.doc_metadata.op('->>')('source_guideline_id') == str(guideline_id)
                    )
                )
            ).all()
            
            for doc in related_documents:
                dependencies['related_documents'].append({
                    'id': doc.id,
                    'title': doc.title,
                    'document_type': doc.document_type,
                    'created_at': doc.created_at.isoformat() if doc.created_at else None,
                    'guideline_ref': doc.doc_metadata.get('guideline_id') or doc.doc_metadata.get('source_guideline_id')
                })
            
            return {
                'success': True,
                'dependencies': dependencies
            }
            
        except Exception as e:
            logger.error(f"Error listing dependencies for guideline {guideline_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }