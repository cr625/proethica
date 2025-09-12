"""
Provenance-aware extraction wrapper for ProEthica extractors.

This module wraps the existing extraction services (RolesExtractor, ResourcesExtractor)
with PROV-O provenance tracking, implementing the pattern described in the OntExtract paper.
"""

import json
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.services.extraction.roles import RolesExtractor
from app.services.extraction.resources import ResourcesExtractor
from app.services.extraction.base import ConceptCandidate
from app.services.provenance_service import get_provenance_service
from app.models import db
import logging

logger = logging.getLogger(__name__)


class ProvenanceAwareExtractor:
    """
    Wrapper that adds PROV-O provenance tracking to any extractor.
    
    This implements the provenance pattern from OntExtract:
    - Tracks the LLM agent performing extraction
    - Records prompts sent to the LLM
    - Records responses received
    - Links extracted concepts to their source prompts/responses
    - Maintains complete audit trail
    """
    
    def __init__(self, base_extractor, extractor_name: str):
        """
        Initialize provenance-aware wrapper.
        
        Args:
            base_extractor: The underlying extractor (RolesExtractor, ResourcesExtractor, etc.)
            extractor_name: Name for provenance tracking (e.g., 'RolesExtractor')
        """
        self.base_extractor = base_extractor
        self.extractor_name = extractor_name
        self.provenance = get_provenance_service()
        self.session_id = str(uuid.uuid4())  # Session for grouping related extractions
        
    def extract_with_provenance(self, text: str, 
                               case_id: Optional[int] = None,
                               guideline_id: Optional[int] = None,
                               world_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Perform extraction with full PROV-O provenance tracking.
        
        Args:
            text: Text to extract from
            case_id: Case/document ID for provenance
            guideline_id: Guideline ID (legacy, maps to case_id)
            world_id: World context ID
            
        Returns:
            Dictionary containing:
                - candidates: List of extracted ConceptCandidates
                - provenance_id: ID of the provenance activity
                - prompt_entity_id: ID of the prompt entity
                - response_entity_id: ID of the response entity
                - extraction_entity_id: ID of the extraction results entity
        """
        # Use guideline_id as case_id if case_id not provided
        case_id = case_id or guideline_id
        
        # Start provenance tracking
        with self.provenance.track_activity(
            activity_type='extraction',
            activity_name=f'{self.extractor_name}_extraction',
            case_id=case_id,
            session_id=self.session_id,
            agent_type='extraction_service',
            agent_name=self.extractor_name,
            execution_plan={
                'world_id': world_id,
                'extractor_type': self.base_extractor.concept_type,
                'mcp_enabled': self._is_mcp_enabled()
            }
        ) as activity:
            
            # Get the prompt that will be sent to the LLM
            prompt_text = self._get_prompt_preview(text)
            
            # Record the prompt as an entity
            prompt_entity = self.provenance.record_prompt(
                prompt_text=prompt_text,
                activity=activity,
                entity_name=f"{self.extractor_name}_prompt",
                metadata={
                    'extractor': self.extractor_name,
                    'concept_type': self.base_extractor.concept_type,
                    'text_length': len(text),
                    'mcp_context_included': self._is_mcp_enabled()
                }
            )
            
            # Perform the actual extraction
            try:
                candidates = self.base_extractor.extract(
                    text, 
                    world_id=world_id, 
                    guideline_id=guideline_id
                )
                
                # Get the raw LLM response if available
                response_text = self._get_last_llm_response()
                
                # Record the response as an entity
                response_entity = None
                if response_text:
                    response_entity = self.provenance.record_response(
                        response_text=response_text,
                        activity=activity,
                        derived_from=prompt_entity,
                        entity_name=f"{self.extractor_name}_response",
                        metadata={
                            'extractor': self.extractor_name,
                            'candidates_count': len(candidates)
                        }
                    )
                
                # Convert candidates to serializable format
                serializable_candidates = self._serialize_candidates(candidates)
                
                # Record extraction results as an entity
                extraction_entity = self.provenance.record_extraction_results(
                    results=serializable_candidates,
                    activity=activity,
                    entity_type=f'extracted_{self.base_extractor.concept_type}s',
                    derived_from=[response_entity] if response_entity else [prompt_entity],
                    metadata={
                        'extractor': self.extractor_name,
                        'concept_type': self.base_extractor.concept_type,
                        'count': len(candidates),
                        'enhanced_fields_present': self._check_enhanced_fields(candidates)
                    }
                )
                
                # Commit provenance records
                db.session.commit()
                
                return {
                    'candidates': candidates,
                    'provenance_id': activity.id,
                    'prompt_entity_id': prompt_entity.id,
                    'response_entity_id': response_entity.id if response_entity else None,
                    'extraction_entity_id': extraction_entity.id,
                    'session_id': self.session_id
                }
                
            except Exception as e:
                logger.error(f"Extraction failed with provenance tracking: {e}")
                db.session.rollback()
                raise
    
    def _get_prompt_preview(self, text: str) -> str:
        """Get the prompt that will be sent to the LLM."""
        if hasattr(self.base_extractor, '_get_prompt_for_preview'):
            return self.base_extractor._get_prompt_for_preview(text)
        elif hasattr(self.base_extractor, '_create_prompt'):
            return self.base_extractor._create_prompt(text)
        else:
            return f"[Prompt preview not available for {self.extractor_name}]"
    
    def _get_last_llm_response(self) -> Optional[str]:
        """
        Attempt to get the last LLM response.
        This is a placeholder - would need to be implemented based on how
        the extractors store/return raw responses.
        """
        # For now, return None - this would need to be enhanced
        # to capture the actual LLM response from the extractor
        return None
    
    def _is_mcp_enabled(self) -> bool:
        """Check if MCP context is enabled."""
        import os
        return True
    
    def _serialize_candidates(self, candidates: List[ConceptCandidate]) -> List[Dict]:
        """Convert ConceptCandidate objects to serializable dictionaries."""
        return [
            {
                'label': c.label,
                'description': c.description,
                'primary_type': c.primary_type,
                'category': c.category,
                'confidence': c.confidence,
                'debug': c.debug,
                'notes': c.notes
            }
            for c in candidates
        ]
    
    def _check_enhanced_fields(self, candidates: List[ConceptCandidate]) -> Dict[str, bool]:
        """Check which enhanced fields are present in the candidates."""
        if not candidates:
            return {}
        
        # Check first candidate's debug field for enhanced fields
        first_debug = candidates[0].debug if candidates else {}
        
        return {
            'role_category': 'role_category' in first_debug,
            'resource_category': 'resource_category' in first_debug,
            'is_existing': 'is_existing' in first_debug,
            'ontology_match_reasoning': 'ontology_match_reasoning' in first_debug,
            'theoretical_grounding': 'theoretical_grounding' in first_debug,
            'raw_llm_data': 'raw_llm_data' in first_debug
        }


class ProvenanceAwareRolesExtractor(ProvenanceAwareExtractor):
    """Provenance-aware wrapper for RolesExtractor."""
    
    def __init__(self, provider: Optional[str] = None):
        base_extractor = RolesExtractor(provider)
        super().__init__(base_extractor, 'RolesExtractor')
    
    def extract(self, text: str, **kwargs) -> List[ConceptCandidate]:
        """Extract with provenance tracking, returning just the candidates for compatibility."""
        result = self.extract_with_provenance(text, **kwargs)
        # Store provenance IDs in a class variable for later retrieval if needed
        self.last_provenance = {
            'provenance_id': result['provenance_id'],
            'prompt_entity_id': result['prompt_entity_id'],
            'response_entity_id': result['response_entity_id'],
            'extraction_entity_id': result['extraction_entity_id'],
            'session_id': result['session_id']
        }
        return result['candidates']


class ProvenanceAwareResourcesExtractor(ProvenanceAwareExtractor):
    """Provenance-aware wrapper for ResourcesExtractor."""
    
    def __init__(self, provider: Optional[str] = None):
        base_extractor = ResourcesExtractor(provider)
        super().__init__(base_extractor, 'ResourcesExtractor')
    
    def extract(self, text: str, **kwargs) -> List[ConceptCandidate]:
        """Extract with provenance tracking, returning just the candidates for compatibility."""
        result = self.extract_with_provenance(text, **kwargs)
        # Store provenance IDs in a class variable for later retrieval if needed
        self.last_provenance = {
            'provenance_id': result['provenance_id'],
            'prompt_entity_id': result['prompt_entity_id'],
            'response_entity_id': result['response_entity_id'],
            'extraction_entity_id': result['extraction_entity_id'],
            'session_id': result['session_id']
        }
        return result['candidates']


def create_provenance_aware_entities_pass(case_id: int, section_text: str) -> Dict[str, Any]:
    """
    Perform entities pass with complete PROV-O provenance tracking.
    
    This demonstrates how to use provenance tracking for a complete
    extraction workflow, linking multiple extraction activities together.
    
    Args:
        case_id: The case/document ID
        section_text: The text to extract from
        
    Returns:
        Dictionary with extraction results and provenance information
    """
    provenance = get_provenance_service()
    session_id = str(uuid.uuid4())
    
    # Create a bundle for the entire entities pass
    bundle = provenance.create_bundle(
        bundle_name=f"entities_pass_{case_id}",
        bundle_type='extraction_workflow',
        case_id=case_id,
        session_id=session_id,
        metadata={'pass_type': 'entities', 'pass_number': 1}
    )
    
    # Extract roles with provenance
    roles_extractor = ProvenanceAwareRolesExtractor()
    roles_result = roles_extractor.extract_with_provenance(
        section_text,
        case_id=case_id
    )
    
    # Extract resources with provenance
    resources_extractor = ProvenanceAwareResourcesExtractor()
    resources_result = resources_extractor.extract_with_provenance(
        section_text,
        case_id=case_id
    )
    
    # Link the two extraction activities (resources extraction informed by roles)
    if roles_result['provenance_id'] and resources_result['provenance_id']:
        roles_activity = provenance.session.query(ProvenanceActivity).get(roles_result['provenance_id'])
        resources_activity = provenance.session.query(ProvenanceActivity).get(resources_result['provenance_id'])
        
        if roles_activity and resources_activity:
            provenance.link_activities(
                informed=resources_activity,
                informing=roles_activity,
                communication_type='sequence'
            )
    
    # Update bundle end time
    bundle.ended_at = datetime.utcnow()
    db.session.commit()
    
    return {
        'roles': roles_result['candidates'],
        'resources': resources_result['candidates'],
        'provenance': {
            'bundle_id': bundle.id,
            'session_id': session_id,
            'roles_provenance': {
                'activity_id': roles_result['provenance_id'],
                'prompt_entity_id': roles_result['prompt_entity_id'],
                'response_entity_id': roles_result['response_entity_id'],
                'extraction_entity_id': roles_result['extraction_entity_id']
            },
            'resources_provenance': {
                'activity_id': resources_result['provenance_id'],
                'prompt_entity_id': resources_result['prompt_entity_id'],
                'response_entity_id': resources_result['response_entity_id'],
                'extraction_entity_id': resources_result['extraction_entity_id']
            }
        }
    }