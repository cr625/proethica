"""
Service for managing draft ontologies in OntServe as replacement for TemporaryConcept.

This service uses OntServe's draft ontology system to store extracted concepts
for review and editing, replacing the previous TemporaryConcept database table.
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

from app.clients.ontserve_rest_client import get_ontserve_rest_client
from app.models.document import Document
from app.models.world import World

logger = logging.getLogger(__name__)


class DraftOntologyService:
    """
    Service for managing draft ontologies in OntServe during extraction and review workflow.
    Replaces TemporaryConceptService with OntServe-based storage.
    """
    
    @staticmethod
    def create_draft_name(document_id: int, world_id: int) -> str:
        """
        Create a unique draft ontology name for a document/world combination.
        
        Args:
            document_id: ID of the document being processed
            world_id: ID of the world context
            
        Returns:
            Draft ontology name
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return f"extracted_doc{document_id}_world{world_id}_{timestamp}"
    
    @staticmethod
    async def store_concepts(
        concepts: List[Dict[str, Any]], 
        document_id: int,
        world_id: int,
        draft_name: Optional[str] = None,
        extraction_method: str = 'llm',
        created_by: Optional[str] = None,
        base_imports: List[str] = None
    ) -> Optional[str]:
        """
        Store extracted concepts as a draft ontology in OntServe.
        
        Args:
            concepts: List of concept dictionaries
            document_id: ID of the source document
            world_id: ID of the world context
            draft_name: Optional draft name (will be generated if not provided)
            extraction_method: Method used for extraction ('llm', 'manual', 'hybrid')
            created_by: User or session identifier
            base_imports: Base ontologies to import (e.g., ["prov-o-base"])
            
        Returns:
            Draft ontology name for retrieving the concepts, or None if failed
        """
        try:
            # Generate draft name if not provided
            if not draft_name:
                draft_name = DraftOntologyService.create_draft_name(document_id, world_id)
            
            # Get document title for better change summary
            document = Document.query.get(document_id)
            doc_title = document.title if document else f"Document {document_id}"
            
            # Get world name for context
            world = World.query.get(world_id)
            world_name = world.name if world else f"World {world_id}"
            
            change_summary = f"Extracted {len(concepts)} concepts from {doc_title} in {world_name} using {extraction_method}"
            if created_by:
                change_summary += f" by {created_by}"
            
            # Convert concepts to OntServe format
            ont_concepts = []
            for concept in concepts:
                ont_concept = {
                    "uri": concept.get("uri", concept.get("id", "")),
                    "label": concept.get("label", concept.get("name", "")),
                    "type": concept.get("type", concept.get("category", "concept")),
                    "description": concept.get("description", concept.get("comment", "")),
                    "metadata": {
                        "document_id": document_id,
                        "world_id": world_id,
                        "extraction_method": extraction_method,
                        "created_by": created_by,
                        "extracted_at": datetime.utcnow().isoformat(),
                        "original_data": concept  # Preserve full original concept
                    }
                }
                
                # Add any additional properties
                for key, value in concept.items():
                    if key not in ["uri", "label", "type", "description", "id", "name", "category", "comment"]:
                        ont_concept[key] = value
                
                ont_concepts.append(ont_concept)
            
            # Store in OntServe
            client = get_ontserve_rest_client()
            result = await client.create_draft_ontology(
                ontology_name=draft_name,
                concepts=ont_concepts,
                base_imports=base_imports or ["prov-o-base"],
                change_summary=change_summary,
                created_by=created_by or "ProEthica"
            )
            
            if result.get("success", True):  # Default to True if not specified
                logger.info(f"Stored {len(ont_concepts)} concepts as draft ontology: {draft_name}")
                return draft_name
            else:
                logger.error(f"Failed to store concepts as draft ontology: {result.get('error', 'Unknown error')}")
                return None
                
        except Exception as e:
            logger.error(f"Error storing concepts as draft ontology: {str(e)}")
            return None
    
    @staticmethod
    async def get_draft_concepts(draft_name: str) -> List[Dict[str, Any]]:
        """
        Retrieve concepts from a draft ontology.
        
        Args:
            draft_name: Name of the draft ontology
            
        Returns:
            List of concept dictionaries
        """
        try:
            client = get_ontserve_rest_client()
            draft_data = await client.get_draft_ontology(draft_name)
            
            if not draft_data:
                logger.warning(f"No draft found with name: {draft_name}")
                return []
            
            # Extract concepts from the draft
            concepts = []
            version_data = draft_data.get("version", {})
            
            # Parse RDF content to extract concepts would go here
            # For now, return metadata-based approach
            metadata = version_data.get("metadata", {})
            if "concepts" in metadata:
                concepts = metadata["concepts"]
            
            logger.info(f"Retrieved {len(concepts)} concepts from draft ontology: {draft_name}")
            return concepts
            
        except Exception as e:
            logger.error(f"Error retrieving concepts from draft ontology {draft_name}: {str(e)}")
            return []
    
    @staticmethod
    async def get_latest_draft_for_document(
        document_id: int,
        world_id: Optional[int] = None
    ) -> Optional[str]:
        """
        Get the most recent draft ontology name for a document.
        
        Args:
            document_id: Document ID
            world_id: Optional world ID filter
            
        Returns:
            Draft ontology name or None if no drafts found
        """
        # This would require a new OntServe API endpoint to list drafts by metadata
        # For now, we'll use a naming convention approach
        try:
            base_pattern = f"extracted_doc{document_id}"
            if world_id:
                base_pattern += f"_world{world_id}"
            
            # Would need to implement search in OntServe
            # For now, return None and let the caller handle appropriately
            logger.warning(f"get_latest_draft_for_document not fully implemented yet")
            return None
            
        except Exception as e:
            logger.error(f"Error finding latest draft for document {document_id}: {str(e)}")
            return None
    
    @staticmethod
    async def update_draft_concept(
        draft_name: str,
        concept_uri: str,
        updates: Dict[str, Any],
        modified_by: Optional[str] = None
    ) -> bool:
        """
        Update a concept within a draft ontology.
        
        Args:
            draft_name: Name of the draft ontology
            concept_uri: URI of the concept to update
            updates: Dictionary of updates to apply
            modified_by: User or session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current draft
            concepts = await DraftOntologyService.get_draft_concepts(draft_name)
            
            # Find and update the concept
            updated = False
            for concept in concepts:
                if concept.get("uri") == concept_uri:
                    # Preserve original data if this is the first edit
                    if "original_data" not in concept.get("metadata", {}):
                        concept.setdefault("metadata", {})["original_data"] = dict(concept)
                    
                    # Apply updates
                    concept.update(updates)
                    concept.setdefault("metadata", {})["edited"] = True
                    concept.setdefault("metadata", {})["modified_by"] = modified_by
                    concept.setdefault("metadata", {})["last_modified"] = datetime.utcnow().isoformat()
                    updated = True
                    break
            
            if not updated:
                logger.warning(f"Concept {concept_uri} not found in draft {draft_name}")
                return False
            
            # Re-store the updated draft
            # This would require re-creating the draft with updated concepts
            logger.warning(f"update_draft_concept requires re-implementation with updated OntServe API")
            return False  # Not fully implemented yet
            
        except Exception as e:
            logger.error(f"Error updating concept {concept_uri} in draft {draft_name}: {str(e)}")
            return False
    
    @staticmethod
    async def delete_draft(draft_name: str) -> bool:
        """
        Delete a draft ontology.
        
        Args:
            draft_name: Name of the draft ontology
            
        Returns:
            True if successful
        """
        try:
            client = get_ontserve_rest_client()
            success = await client.delete_draft_ontology(draft_name)
            
            if success:
                logger.info(f"Deleted draft ontology: {draft_name}")
            else:
                logger.warning(f"Failed to delete draft ontology: {draft_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting draft ontology {draft_name}: {str(e)}")
            return False
    
    @staticmethod
    def sync_store_concepts(
        concepts: List[Dict[str, Any]], 
        document_id: int,
        world_id: int,
        **kwargs
    ) -> Optional[str]:
        """
        Synchronous wrapper for store_concepts.
        
        Args:
            concepts: List of concept dictionaries
            document_id: ID of the source document
            world_id: ID of the world context
            **kwargs: Additional arguments passed to store_concepts
            
        Returns:
            Draft ontology name or None if failed
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            return loop.run_until_complete(
                DraftOntologyService.store_concepts(concepts, document_id, world_id, **kwargs)
            )
        except Exception as e:
            logger.error(f"Error in sync_store_concepts: {e}")
            return None
    
    @staticmethod
    def sync_delete_draft(draft_name: str) -> bool:
        """
        Synchronous wrapper for delete_draft.
        
        Args:
            draft_name: Name of the draft ontology
            
        Returns:
            True if successful
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            return loop.run_until_complete(
                DraftOntologyService.delete_draft(draft_name)
            )
        except Exception as e:
            logger.error(f"Error in sync_delete_draft: {e}")
            return False


# Compatibility wrapper functions to match TemporaryConceptService interface
class TemporaryConceptCompatibilityService:
    """
    Compatibility wrapper to ease migration from TemporaryConcept to draft ontologies.
    Provides the same interface but uses OntServe draft ontologies internally.
    """
    
    @staticmethod
    def store_concepts(
        concepts: List[Dict[str, Any]], 
        document_id: int,
        world_id: int,
        session_id: Optional[str] = None,
        extraction_method: str = 'llm',
        created_by: Optional[str] = None,
        expires_in_days: int = 7  # Ignored for draft ontologies
    ) -> str:
        """
        Store extracted concepts using OntServe draft ontologies.
        Returns session_id for compatibility (actually draft_name).
        """
        draft_name = session_id or DraftOntologyService.create_draft_name(document_id, world_id)
        
        result = DraftOntologyService.sync_store_concepts(
            concepts=concepts,
            document_id=document_id,
            world_id=world_id,
            draft_name=draft_name,
            extraction_method=extraction_method,
            created_by=created_by
        )
        
        return result or draft_name
    
    @staticmethod
    def delete_session(session_id: str) -> bool:
        """Delete all concepts in a session (draft ontology)."""
        return DraftOntologyService.sync_delete_draft(session_id)
    
    @staticmethod
    def clear_session(session_id: str) -> bool:
        """Clear all concepts in a session (alias for delete_session)."""
        return TemporaryConceptCompatibilityService.delete_session(session_id)