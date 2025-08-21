"""
Service for managing temporary concept storage during the guideline extraction workflow.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy import and_, or_

from app.models import db
from app.models.temporary_concept import TemporaryConcept
from app.models.document import Document
from app.models.world import World

logger = logging.getLogger(__name__)


class TemporaryConceptService:
    """
    Service for managing temporary concepts during extraction and review workflow.
    """
    
    @staticmethod
    def create_session_id(document_id: int, world_id: int) -> str:
        """
        Create a unique session ID for a concept extraction session.
        
        Args:
            document_id: ID of the document being processed
            world_id: ID of the world context
            
        Returns:
            Unique session identifier
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        return f"doc{document_id}_world{world_id}_{timestamp}_{unique_id}"
    
    @staticmethod
    def store_concepts(
        concepts: List[Dict[str, Any]], 
        document_id: int,
        world_id: int,
        session_id: Optional[str] = None,
        extraction_method: str = 'llm',
        created_by: Optional[str] = None,
        expires_in_days: int = 7
    ) -> str:
        """
        Store extracted concepts in temporary storage.
        
        Args:
            concepts: List of concept dictionaries
            document_id: ID of the source document
            world_id: ID of the world context
            session_id: Optional session ID (will be generated if not provided)
            extraction_method: Method used for extraction ('llm', 'manual', 'hybrid')
            created_by: User or session identifier
            expires_in_days: Days until auto-cleanup
            
        Returns:
            Session ID for retrieving the concepts
        """
        try:
            # Generate session ID if not provided
            if not session_id:
                session_id = TemporaryConceptService.create_session_id(document_id, world_id)
            
            # Calculate expiration
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
            
            # Store each concept
            stored_concepts = []
            for concept in concepts:
                temp_concept = TemporaryConcept(
                    document_id=document_id,
                    world_id=world_id,
                    session_id=session_id,
                    concept_data=concept,
                    status='pending',
                    extraction_method=extraction_method,
                    expires_at=expires_at,
                    created_by=created_by
                )
                db.session.add(temp_concept)
                stored_concepts.append(temp_concept)
            
            db.session.commit()
            
            logger.info(f"Stored {len(stored_concepts)} concepts with session ID: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Error storing temporary concepts: {str(e)}")
            db.session.rollback()
            raise
    
    @staticmethod
    def get_session_concepts(
        session_id: str, 
        status: Optional[str] = None,
        only_selected: bool = False
    ) -> List[TemporaryConcept]:
        """
        Retrieve concepts for a session.
        
        Args:
            session_id: Session identifier
            status: Optional status filter
            only_selected: If True, only return concepts marked as selected
            
        Returns:
            List of TemporaryConcept objects
        """
        query = TemporaryConcept.query.filter_by(session_id=session_id)
        
        if status:
            query = query.filter_by(status=status)
        
        concepts = query.order_by(TemporaryConcept.id).all()
        
        if only_selected:
            concepts = [c for c in concepts if c.concept_data.get('selected', True)]
        
        return concepts
    
    @staticmethod
    def get_latest_session_for_document(
        document_id: int,
        world_id: Optional[int] = None,
        status: str = 'pending'
    ) -> Optional[str]:
        """
        Get the most recent session ID for a document.
        
        Args:
            document_id: Document ID
            world_id: Optional world ID filter
            status: Status filter
            
        Returns:
            Session ID or None if no sessions found
        """
        query = TemporaryConcept.query.filter_by(
            document_id=document_id,
            status=status
        )
        
        if world_id:
            query = query.filter_by(world_id=world_id)
        
        latest = query.order_by(
            TemporaryConcept.extraction_timestamp.desc()
        ).first()
        
        return latest.session_id if latest else None
    
    @staticmethod
    def update_concept(
        concept_id: int,
        updates: Dict[str, Any],
        modified_by: Optional[str] = None
    ) -> bool:
        """
        Update a temporary concept.
        
        Args:
            concept_id: ID of the concept to update
            updates: Dictionary of updates to apply
            modified_by: User or session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            concept = TemporaryConcept.query.get(concept_id)
            if not concept:
                logger.warning(f"Concept {concept_id} not found")
                return False
            
            # Preserve original data if this is the first edit
            if not concept.concept_data.get('original_data'):
                concept.concept_data = {
                    **concept.concept_data,
                    'original_data': dict(concept.concept_data)
                }
            
            # Apply updates
            concept.concept_data = {
                **concept.concept_data,
                **updates,
                'edited': True
            }
            
            if modified_by:
                concept.modified_by = modified_by
            
            concept.last_modified = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Updated concept {concept_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating concept {concept_id}: {str(e)}")
            db.session.rollback()
            return False
    
    @staticmethod
    def bulk_update_status(
        session_id: str,
        from_status: str,
        to_status: str,
        concept_ids: Optional[List[int]] = None
    ) -> int:
        """
        Update status for multiple concepts.
        
        Args:
            session_id: Session identifier
            from_status: Current status to filter by
            to_status: New status to set
            concept_ids: Optional list of specific concept IDs to update
            
        Returns:
            Number of concepts updated
        """
        try:
            query = TemporaryConcept.query.filter_by(
                session_id=session_id,
                status=from_status
            )
            
            if concept_ids:
                query = query.filter(TemporaryConcept.id.in_(concept_ids))
            
            count = query.update(
                {'status': to_status, 'last_modified': datetime.utcnow()},
                synchronize_session=False
            )
            
            db.session.commit()
            logger.info(f"Updated {count} concepts from {from_status} to {to_status}")
            return count
            
        except Exception as e:
            logger.error(f"Error updating concept statuses: {str(e)}")
            db.session.rollback()
            return 0
    
    @staticmethod
    def mark_session_committed(session_id: str) -> bool:
        """
        Mark all concepts in a session as committed.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful
        """
        count = TemporaryConceptService.bulk_update_status(
            session_id, 'pending', 'committed'
        )
        count += TemporaryConceptService.bulk_update_status(
            session_id, 'reviewed', 'committed'
        )
        return count > 0
    
    @staticmethod
    def cleanup_expired() -> int:
        """
        Remove expired temporary concepts.
        
        Returns:
            Number of concepts removed
        """
        try:
            # Delete concepts past expiration
            expired = TemporaryConcept.query.filter(
                or_(
                    TemporaryConcept.expires_at < datetime.utcnow(),
                    and_(
                        TemporaryConcept.expires_at.is_(None),
                        TemporaryConcept.extraction_timestamp < datetime.utcnow() - timedelta(days=7)
                    )
                )
            ).delete()
            
            db.session.commit()
            logger.info(f"Cleaned up {expired} expired temporary concepts")
            return expired
            
        except Exception as e:
            logger.error(f"Error cleaning up expired concepts: {str(e)}")
            db.session.rollback()
            return 0
    
    @staticmethod
    def get_concept_by_id(concept_id: int) -> Optional[TemporaryConcept]:
        """
        Get a single concept by ID.
        
        Args:
            concept_id: Concept ID
            
        Returns:
            TemporaryConcept object or None
        """
        return TemporaryConcept.query.get(concept_id)
    
    @staticmethod
    def delete_session(session_id: str) -> bool:
        """
        Delete all concepts in a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful
        """
        try:
            count = TemporaryConcept.query.filter_by(
                session_id=session_id
            ).delete()
            
            db.session.commit()
            logger.info(f"Deleted {count} concepts from session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {str(e)}")
            db.session.rollback()
            return False
    
    @staticmethod
    def get_document_sessions(
        document_id: int,
        world_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all extraction sessions for a document.
        
        Args:
            document_id: Document ID
            world_id: Optional world ID filter
            
        Returns:
            List of session summaries
        """
        query = db.session.query(
            TemporaryConcept.session_id,
            TemporaryConcept.status,
            TemporaryConcept.extraction_timestamp,
            TemporaryConcept.extraction_method,
            db.func.count(TemporaryConcept.id).label('concept_count')
        ).filter_by(document_id=document_id)
        
        if world_id:
            query = query.filter_by(world_id=world_id)
        
        sessions = query.group_by(
            TemporaryConcept.session_id,
            TemporaryConcept.status,
            TemporaryConcept.extraction_timestamp,
            TemporaryConcept.extraction_method
        ).order_by(
            TemporaryConcept.extraction_timestamp.desc()
        ).all()
        
        return [
            {
                'session_id': s.session_id,
                'status': s.status,
                'extraction_timestamp': s.extraction_timestamp,
                'extraction_method': s.extraction_method,
                'concept_count': s.concept_count
            }
            for s in sessions
        ]