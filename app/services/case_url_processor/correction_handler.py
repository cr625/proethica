"""
Correction handler for the Case URL Processor.

This module provides functionality for handling user corrections
to automatically processed URL content.
"""

import logging
from typing import Dict, List, Any, Optional

# Set up logging
logger = logging.getLogger(__name__)

class CorrectionHandler:
    """
    Handler for user corrections to automatically processed URL content.
    """
    
    def __init__(self):
        """Initialize the correction handler."""
        pass
    
    def apply_corrections(self, result, corrections, user_id=None):
        """
        Apply user corrections to processing result.
        
        Args:
            result: Original processing result
            corrections: User corrections to apply
            user_id: ID of user making corrections (optional)
            
        Returns:
            Corrected result
        """
        # Create a copy of the original result
        corrected_result = dict(result)
        
        # Mark as manually corrected
        corrected_result['processing_method'] = 'manual_correction'
        corrected_result['corrected_by'] = user_id
        
        # Apply metadata corrections
        if 'metadata' in corrections:
            if 'metadata' not in corrected_result:
                corrected_result['metadata'] = {}
            
            for field, value in corrections['metadata'].items():
                corrected_result['metadata'][field] = value
        
        # Apply content corrections
        if 'content' in corrections:
            corrected_result['content'] = corrections['content']
        
        # Apply title corrections
        if 'title' in corrections:
            corrected_result['title'] = corrections['title']
        
        # Apply triple corrections
        if 'triples' in corrections:
            corrected_result['triples'] = corrections['triples']
            
            # Update database triples if document_id is available
            if 'document_id' in result:
                self._update_database_triples(
                    result['document_id'],
                    corrections['triples']
                )
        
        return corrected_result
    
    def _update_database_triples(self, document_id, triples):
        """
        Update triples in the database for an existing document.
        
        Args:
            document_id: ID of the document
            triples: New triples to update
        """
        try:
            from app.services.entity_triple_service import EntityTripleService
            triple_service = EntityTripleService()
            
            # Get existing triples for the document
            existing_triples = triple_service.get_triples_for_entity('document', document_id)
            
            # Delete existing triples
            for triple in existing_triples:
                triple_service.delete_triple(triple.id)
            
            # Add new triples
            for triple in triples:
                triple_service.create_triple(
                    entity_type='document',
                    entity_id=document_id,
                    predicate=triple['predicate'],
                    object_value=triple['object'],
                    object_type='uri' if not triple.get('is_literal', False) else 'literal'
                )
            
            logger.info(f"Updated triples for document {document_id}: deleted {len(existing_triples)}, added {len(triples)}")
            
        except Exception as e:
            logger.error(f"Error updating database triples: {str(e)}")
            # Don't raise exception, as this is a background task
    
    def get_correction_fields(self, result):
        """
        Get fields available for correction.
        
        Args:
            result: Processing result
            
        Returns:
            Dictionary of field types and current values
        """
        correction_fields = {}
        
        # Add basic fields
        if 'title' in result:
            correction_fields['title'] = result['title']
        
        # Add metadata fields
        if 'metadata' in result:
            correction_fields['metadata'] = {}
            
            for field, value in result['metadata'].items():
                # Skip internal fields
                if field in ['processing_time', 'extraction_method']:
                    continue
                
                correction_fields['metadata'][field] = value
        
        # Add triples information
        if 'triples' in result:
            correction_fields['triples'] = {
                'count': len(result['triples']),
                'sample': result['triples'][:3] if len(result['triples']) > 0 else []
            }
        
        return correction_fields
