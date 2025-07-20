"""
Guideline Concept Integration Service

Bridges the gap between extracted guideline concepts and ontology entities.
This service takes concepts that have been extracted and saved as EntityTriples
and promotes them to actual entities in the engineering-ethics ontology.

Uses existing infrastructure:
- EntityService.create_entity() for ontology modification
- Automatic versioning via OntologyVersion
- Existing duplicate detection and validation
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import sessionmaker
from sqlalchemy import and_

from app import db
from app.models.ontology import Ontology
from app.models.entity_triple import EntityTriple
from app.models.guideline import Guideline
from ontology_editor.services.entity_service import EntityService

logger = logging.getLogger(__name__)

class GuidelineConceptIntegrationService:
    """Service for integrating guideline concepts into ontologies"""
    
    # Map ontological types to parent classes in intermediate ontology
    TYPE_TO_PARENT_CLASS_MAP = {
        'role': 'http://proethica.org/ontology/intermediate#Role',
        'principle': 'http://proethica.org/ontology/intermediate#Principle', 
        'obligation': 'http://proethica.org/ontology/intermediate#Obligation',
        'state': 'http://proethica.org/ontology/intermediate#State',
        'resource': 'http://proethica.org/ontology/intermediate#Resource',
        'action': 'http://proethica.org/ontology/intermediate#Action',
        'event': 'http://proethica.org/ontology/intermediate#Event',
        'capability': 'http://proethica.org/ontology/intermediate#Capability'
    }
    
    @classmethod
    def add_concepts_to_ontology(cls, 
                                concepts: List[Dict[str, Any]], 
                                ontology_domain: str = 'engineering-ethics',
                                commit_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Add guideline concepts to the specified ontology using existing EntityService.
        
        Args:
            concepts: List of concept dictionaries with 'label', 'type', 'description', etc.
            ontology_domain: Domain ID of target ontology (default: 'engineering-ethics')
            commit_message: Optional commit message for ontology version
            
        Returns:
            Dict with success status, results, and any errors
        """
        try:
            logger.info(f"Starting integration of {len(concepts)} concepts into {ontology_domain} ontology")
            
            # Get the target ontology
            ontology = Ontology.query.filter_by(domain_id=ontology_domain).first()
            if not ontology:
                return {
                    'success': False,
                    'error': f'Ontology with domain_id "{ontology_domain}" not found',
                    'results': []
                }
            
            if not ontology.is_editable:
                return {
                    'success': False,
                    'error': f'Ontology "{ontology_domain}" is not editable',
                    'results': []
                }
            
            # Check for existing entities to avoid duplicates
            existing_entities = cls._get_existing_entity_labels(ontology.id)
            logger.info(f"Found {len(existing_entities)} existing entities in ontology")
            
            results = []
            successful_additions = 0
            skipped_duplicates = 0
            errors = []
            
            for i, concept in enumerate(concepts):
                try:
                    concept_label = concept.get('label', 'Unknown Concept')
                    concept_type = (concept.get('primary_type') or concept.get('type', 'concept')).lower()
                    concept_description = concept.get('description', '')
                    semantic_label = concept.get('semantic_label') or concept.get('category', '')
                    
                    logger.info(f"Processing concept {i+1}/{len(concepts)}: {concept_label} ({concept_type})")
                    
                    # Check for duplicates (case-insensitive)
                    if any(existing.lower() == concept_label.lower() for existing in existing_entities):
                        logger.info(f"Skipping duplicate concept: {concept_label}")
                        results.append({
                            'concept': concept_label,
                            'status': 'skipped',
                            'reason': 'Duplicate entity already exists in ontology'
                        })
                        skipped_duplicates += 1
                        continue
                    
                    # Map to intermediate ontology parent class
                    parent_class = cls.TYPE_TO_PARENT_CLASS_MAP.get(concept_type)
                    if not parent_class:
                        logger.warning(f"Unknown concept type '{concept_type}' for concept '{concept_label}', using generic parent")
                        parent_class = 'http://proethica.org/ontology/intermediate#Entity'
                    
                    # Prepare entity data for EntityService
                    entity_data = {
                        'label': concept_label,
                        'description': concept_description,
                        'parent_class': parent_class
                    }
                    
                    # Add semantic metadata if available
                    if semantic_label:
                        entity_data['semantic_category'] = semantic_label
                        if 'description' in entity_data:
                            entity_data['description'] += f" (Semantic category: {semantic_label})"
                    
                    # Create entity using existing EntityService
                    success, result = EntityService.create_entity(
                        ontology_id=ontology.id,
                        entity_type=concept_type,
                        data=entity_data
                    )
                    
                    if success:
                        logger.info(f"Successfully created entity: {concept_label}")
                        results.append({
                            'concept': concept_label,
                            'status': 'created',
                            'entity_type': concept_type,
                            'entity_id': result.get('entity_id'),
                            'semantic_category': semantic_label
                        })
                        successful_additions += 1
                        # Add to existing entities list to prevent duplicates in this batch
                        existing_entities.append(concept_label)
                    else:
                        error_msg = result.get('error', 'Unknown error occurred')
                        logger.error(f"Failed to create entity '{concept_label}': {error_msg}")
                        results.append({
                            'concept': concept_label,
                            'status': 'error',
                            'error': error_msg
                        })
                        errors.append(f"{concept_label}: {error_msg}")
                
                except Exception as concept_error:
                    error_msg = f"Error processing concept '{concept.get('label', 'Unknown')}': {str(concept_error)}"
                    logger.error(error_msg)
                    results.append({
                        'concept': concept.get('label', 'Unknown'),
                        'status': 'error',
                        'error': str(concept_error)
                    })
                    errors.append(error_msg)
            
            # Generate summary
            total_processed = len(concepts)
            
            logger.info(f"Integration complete: {successful_additions} created, {skipped_duplicates} skipped, {len(errors)} errors")
            
            return {
                'success': len(errors) == 0,  # Success if no errors occurred
                'ontology_domain': ontology_domain,
                'ontology_id': ontology.id,
                'summary': {
                    'total_concepts': total_processed,
                    'successful_additions': successful_additions,
                    'skipped_duplicates': skipped_duplicates,
                    'errors': len(errors)
                },
                'results': results,
                'errors': errors,
                'commit_message': commit_message or f"Added {successful_additions} concepts from guideline analysis"
            }
            
        except Exception as e:
            logger.error(f"Error in add_concepts_to_ontology: {str(e)}")
            return {
                'success': False,
                'error': f"Integration failed: {str(e)}",
                'results': []
            }
    
    @classmethod
    def _get_existing_entity_labels(cls, ontology_id: int) -> List[str]:
        """
        Get list of existing entity labels in the ontology to avoid duplicates.
        
        Args:
            ontology_id: ID of the ontology
            
        Returns:
            List of existing entity labels
        """
        try:
            # Use EntityService to get existing entities
            entities = EntityService.get_entities(ontology_id)
            
            # Extract labels from all entity types
            labels = []
            for entity_type, entity_list in entities.items():
                if isinstance(entity_list, list):
                    for entity in entity_list:
                        if isinstance(entity, dict) and 'label' in entity:
                            labels.append(entity['label'])
            
            return labels
            
        except Exception as e:
            logger.warning(f"Could not retrieve existing entities for duplicate checking: {str(e)}")
            return []
    
    @classmethod
    def get_concepts_from_guideline(cls, guideline_id: int) -> List[Dict[str, Any]]:
        """
        Retrieve concepts that were saved from a specific guideline.
        
        Args:
            guideline_id: ID of the guideline
            
        Returns:
            List of concept dictionaries extracted from EntityTriples
        """
        try:
            # Query EntityTriples for this guideline
            concept_triples = EntityTriple.query.filter(
                and_(
                    EntityTriple.guideline_id == guideline_id,
                    EntityTriple.entity_type == 'guideline_concept',
                    EntityTriple.predicate == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
                )
            ).all()
            
            concepts = []
            for triple in concept_triples:
                # Extract concept information from the triple
                concept = {
                    'label': triple.subject_label or 'Unknown Concept',
                    'type': triple.primary_type or 'concept',
                    'primary_type': triple.primary_type,
                    'semantic_label': triple.semantic_label,
                    'category': triple.semantic_label,  # For backward compatibility
                    'description': cls._get_concept_description(guideline_id, triple.subject),
                    'mapping_source': triple.mapping_source,
                    'confidence': triple.type_mapping_confidence
                }
                concepts.append(concept)
            
            logger.info(f"Retrieved {len(concepts)} concepts from guideline {guideline_id}")
            return concepts
            
        except Exception as e:
            logger.error(f"Error retrieving concepts from guideline {guideline_id}: {str(e)}")
            return []
    
    @classmethod
    def _get_concept_description(cls, guideline_id: int, concept_uri: str) -> str:
        """
        Get the description for a concept from its description triple.
        
        Args:
            guideline_id: ID of the guideline
            concept_uri: URI of the concept
            
        Returns:
            Description text or empty string if not found
        """
        try:
            description_triple = EntityTriple.query.filter(
                and_(
                    EntityTriple.guideline_id == guideline_id,
                    EntityTriple.subject == concept_uri,
                    EntityTriple.predicate == 'http://purl.org/dc/elements/1.1/description'
                )
            ).first()
            
            return description_triple.object_literal if description_triple else ''
            
        except Exception as e:
            logger.warning(f"Could not retrieve description for concept {concept_uri}: {str(e)}")
            return ''