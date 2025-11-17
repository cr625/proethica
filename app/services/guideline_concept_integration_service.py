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
from app.models.ontology_import import OntologyImport
from app.models.entity_triple import EntityTriple
from app.models.guideline import Guideline
from app.services.entity_service import EntityService
from datetime import datetime
from app.utils.label_normalization import ensure_role_suffix, normalize_role_label, make_role_uri_fragment

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
                                guideline_id: int,
                                ontology_domain: str = 'engineering-ethics',
                                commit_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Add guideline concepts to a derived ontology that imports the base engineering-ethics ontology.
        This approach avoids permanently modifying the core .ttl files.
        
        Args:
            concepts: List of concept dictionaries with 'label', 'type', 'description', etc.
            guideline_id: ID of the guideline these concepts are from
            ontology_domain: Domain ID of base ontology (default: 'engineering-ethics')
            commit_message: Optional commit message for ontology version
            
        Returns:
            Dict with success status, results, and any errors
        """
        try:
            logger.info(f"add_concepts_to_ontology called for guideline_id={guideline_id}, ontology_domain={ontology_domain}")
            
            # Get the actual guideline ID from document metadata to retrieve concepts
            actual_guideline_id = cls._get_actual_guideline_id(guideline_id)
            if not actual_guideline_id:
                logger.error(f"No actual guideline ID found for document {guideline_id}")
                return {
                    'success': False,
                    'error': f'No actual guideline ID found for document {guideline_id}',
                    'results': []
                }
            
            logger.info(f"Found actual guideline ID: {actual_guideline_id} for document {guideline_id}")
            
            # If concepts list is empty, retrieve from database using actual guideline ID
            if not concepts:
                concepts = cls.get_concepts_from_guideline(actual_guideline_id)
                if not concepts:
                    logger.warning(f"No concepts found for guideline {actual_guideline_id}")
                    return {
                        'success': False,
                        'error': f'No concepts found for guideline {actual_guideline_id}',
                        'results': []
                    }
            
            logger.info(f"Starting integration of {len(concepts)} concepts from document {guideline_id} (actual guideline {actual_guideline_id})")
            
            # Get or create derived ontology for this guideline (using document ID for naming)
            derived_ontology = cls._get_or_create_derived_ontology(guideline_id, ontology_domain)
            if not derived_ontology:
                return {
                    'success': False,
                    'error': f'Failed to create derived ontology for guideline {guideline_id}',
                    'results': []
                }
            
            # Check for existing entities to avoid duplicates
            existing_entities = cls._get_existing_entity_labels(derived_ontology.id)
            # Precompute normalized labels for duplicate detection on roles
            existing_norm = {normalize_role_label(lbl): lbl for lbl in existing_entities}
            logger.info(f"Found {len(existing_entities)} existing entities in derived ontology")
            
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
                    # Duplicate detection: for roles use normalized, for others case-insensitive
                    if concept_type == 'role':
                        if normalize_role_label(concept_label) in existing_norm:
                            logger.info(f"Skipping duplicate concept (role, normalized): {concept_label}")
                            results.append({
                                'concept': concept_label,
                                'status': 'skipped',
                                'reason': 'Duplicate role (normalized) exists in derived ontology'
                            })
                            skipped_duplicates += 1
                            continue
                    elif any(existing.lower() == concept_label.lower() for existing in existing_entities):
                        logger.info(f"Skipping duplicate concept: {concept_label}")
                        results.append({
                            'concept': concept_label,
                            'status': 'skipped',
                            'reason': 'Duplicate entity already exists in derived ontology'
                        })
                        skipped_duplicates += 1
                        continue
                    
                    # Map to intermediate ontology parent class
                    parent_class = cls.TYPE_TO_PARENT_CLASS_MAP.get(concept_type)
                    # If a role came with suggested parent (professional/participant), use it
                    if concept_type == 'role':
                        suggested_parent = concept.get('suggested_parent_class_uri')
                        role_classification = concept.get('role_classification')
                        if suggested_parent:
                            parent_class = suggested_parent
                        elif role_classification == 'professional':
                            parent_class = 'http://proethica.org/ontology/intermediate#ProfessionalRole'
                        elif role_classification == 'participant':
                            parent_class = 'http://proethica.org/ontology/intermediate#ParticipantRole'
                    if not parent_class:
                        logger.warning(f"Unknown concept type '{concept_type}' for concept '{concept_label}', using generic parent")
                        parent_class = 'http://proethica.org/ontology/intermediate#Entity'
                    
                    # Prepare entity data for EntityService
                    # Enforce Role suffix policy for role labels for consistency
                    label_out = ensure_role_suffix(concept_label) if concept_type == 'role' else concept_label
                    entity_data = {
                        'label': label_out,
                        'description': concept_description,
                        'parent_class': parent_class
                    }
                    
                    # Add semantic metadata if available
                    if semantic_label:
                        entity_data['semantic_category'] = semantic_label
                        if 'description' in entity_data:
                            entity_data['description'] += f" (Semantic category: {semantic_label})"
                    # Preserve role classification hints
                    if concept_type == 'role':
                        if concept.get('role_classification'):
                            entity_data['role_classification'] = concept.get('role_classification')
                        if concept.get('role_signals'):
                            entity_data['role_signals'] = concept.get('role_signals')
                    
                    # Create entity in derived ontology using existing EntityService
                    payload = {
                        'label': label_out,
                        'description': entity_data['description'],
                        'parent_class': entity_data['parent_class']
                    }
                    # Preserve optional metadata
                    for k in ('semantic_category','role_classification','role_signals','capabilities'):
                        if k in entity_data:
                            payload[k] = entity_data[k]
                    # For roles, force Role-suffixed URI fragment
                    if concept_type == 'role':
                        payload['id_fragment'] = make_role_uri_fragment(concept_label)

                    success, result = EntityService.create_entity(
                        ontology_id=derived_ontology.id,
                        entity_type=concept_type,
                        data=payload
                    )
                    
                    if success:
                        logger.info(f"Successfully created entity: {concept_label}")
                        results.append({
                            'concept': label_out,
                            'status': 'created',
                            'entity_type': concept_type,
                            'entity_id': result.get('entity_id'),
                            'semantic_category': semantic_label
                        })
                        successful_additions += 1
                        # Add to existing entities list to prevent duplicates in this batch
                        existing_entities.append(label_out)
                        if concept_type == 'role':
                            existing_norm[normalize_role_label(label_out)] = label_out
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
                'ontology_id': derived_ontology.id,
                'ontology_name': derived_ontology.name,
                'is_derived': True,
                'base_ontology_unchanged': True,
                'summary': {
                    'total_concepts': total_processed,
                    'successful_additions': successful_additions,
                    'skipped_duplicates': skipped_duplicates,
                    'errors': len(errors)
                },
                'results': results,
                'errors': errors,
                'commit_message': commit_message or f"Added {successful_additions} concepts from guideline {guideline_id}"
            }
            
        except Exception as e:
            logger.error(f"Error in add_concepts_to_ontology: {str(e)}")
            return {
                'success': False,
                'error': f"Integration failed: {str(e)}",
                'results': []
            }
    
    @classmethod
    def _get_or_create_derived_ontology(cls, guideline_id: int, base_domain: str = 'engineering-ethics') -> Optional[Ontology]:
        """
        Get or create a derived ontology for the specified guideline.
        This ontology imports the base engineering-ethics ontology and contains only guideline-specific concepts.
        
        Args:
            guideline_id: ID of the guideline
            base_domain: Domain ID of the base ontology to import
            
        Returns:
            Derived ontology or None if creation failed
        """
        try:
            # Check if derived ontology already exists
            derived_domain = f"guideline-{guideline_id}-concepts"
            existing_ontology = Ontology.query.filter_by(domain_id=derived_domain).first()
            
            if existing_ontology:
                logger.info(f"Using existing derived ontology: {existing_ontology.name}")
                return existing_ontology
            
            # Get the base ontology to import
            base_ontology = Ontology.query.filter_by(domain_id=base_domain).first()
            if not base_ontology:
                logger.error(f"Base ontology '{base_domain}' not found")
                return None
            
            # Get guideline information for naming
            # Note: guideline_id here is actually a document_id, so we need to get the actual guideline
            from app.models import Document
            document = Document.query.get(guideline_id)
            guideline_title = f"Document {guideline_id}"
            
            if document:
                guideline_title = document.title[:50] + "..." if len(document.title) > 50 else document.title
                
                # Try to get the actual guideline if it exists
                if document.doc_metadata and 'guideline_id' in document.doc_metadata:
                    actual_guideline_id = document.doc_metadata['guideline_id']
                    guideline = Guideline.query.get(actual_guideline_id)
                    if guideline:
                        guideline_title = guideline.title[:50] + "..." if len(guideline.title) > 50 else guideline.title
            
            # Create derived ontology content that imports the base ontology
            derived_content = cls._create_derived_ontology_content(derived_domain, base_ontology.domain_id, guideline_title)
            
            # Create the derived ontology
            derived_ontology = Ontology(
                name=f"{guideline_title} - Concepts",
                domain_id=derived_domain,
                description=f"Derived ontology containing concepts extracted from guideline: {guideline_title}",
                content=derived_content,
                base_uri=f"http://proethica.org/ontology/{derived_domain}#",
                is_base=False,
                is_editable=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(derived_ontology)
            db.session.flush()  # Get the ID
            
            # Create import relationship
            ontology_import = OntologyImport(
                importing_ontology_id=derived_ontology.id,
                imported_ontology_id=base_ontology.id
            )
            
            db.session.add(ontology_import)
            db.session.commit()
            
            logger.info(f"Created derived ontology '{derived_ontology.name}' (ID: {derived_ontology.id}) importing {base_domain}")
            return derived_ontology
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating derived ontology for guideline {guideline_id}: {str(e)}")
            return None
    
    @classmethod
    def _create_derived_ontology_content(cls, derived_domain: str, base_domain: str, guideline_title: str) -> str:
        """
        Create the initial TTL content for a derived ontology that imports the base ontology.
        
        Args:
            derived_domain: Domain ID of the derived ontology
            base_domain: Domain ID of the base ontology to import  
            guideline_title: Title of the guideline for documentation
            
        Returns:
            TTL content string
        """
        return f"""@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix dc: <http://purl.org/dc/elements/1.1/> .
@prefix derived: <http://proethica.org/ontology/{derived_domain}#> .
@prefix base: <http://proethica.org/ontology/{base_domain}#> .

# Derived ontology containing concepts from guideline: {guideline_title}
<http://proethica.org/ontology/{derived_domain}> rdf:type owl:Ontology ;
    dc:title "Guideline Concepts - {guideline_title}" ;
    dc:description "Derived ontology containing concepts extracted from guideline analysis. Imports the base {base_domain} ontology." ;
    dc:creator "ProEthica Guideline Analysis System" ;
    dc:created "{datetime.utcnow().isoformat()}Z" ;
    owl:imports <http://proethica.org/ontology/{base_domain}> .

# This ontology imports all concepts from the base ontology
# New concepts extracted from guidelines will be added below
"""
    
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
                # Enrich with role classification metadata from description triple if present
                role_meta = cls._get_role_metadata(guideline_id, triple.subject)
                if role_meta:
                    concept.update(role_meta)
                concepts.append(concept)
            
            logger.info(f"Retrieved {len(concepts)} concepts from guideline {guideline_id}")
            return concepts
            
        except Exception as e:
            logger.error(f"Error retrieving concepts from guideline {guideline_id}: {str(e)}")
            return []

    @classmethod
    def _get_role_metadata(cls, guideline_id: int, concept_uri: str) -> Dict[str, Any]:
        """Fetch role-related metadata stored in the description triple."""
        try:
            desc = EntityTriple.query.filter(
                and_(
                    EntityTriple.guideline_id == guideline_id,
                    EntityTriple.subject == concept_uri,
                    EntityTriple.predicate == 'http://purl.org/dc/elements/1.1/description'
                )
            ).first()
            meta = (desc.triple_metadata or {}) if desc else {}
            result: Dict[str, Any] = {}
            for k in ["role_classification", "role_signals", "suggested_parent_class_uri"]:
                if k in meta:
                    result[k] = meta[k]
            return result
        except Exception as e:
            logger.debug(f"No role metadata for {concept_uri}: {e}")
            return {}
    
    @classmethod
    def check_concepts_added_to_ontology(cls, guideline_id: int, ontology_domain: str = 'engineering-ethics') -> Dict[str, Any]:
        """
        Check if concepts from a guideline have already been added to a derived ontology.
        
        Args:
            guideline_id: Document ID of the guideline (used for naming derived ontology)
            ontology_domain: Domain ID of base ontology (default: 'engineering-ethics')
            
        Returns:
            Dict with status information about ontology integration
        """
        try:
            # For consistency, we need to check both:
            # 1. The derived ontology naming (uses document_id: guideline_id parameter)  
            # 2. The actual concepts storage (uses actual guideline_id from metadata)
            
            # Get the actual guideline ID from document metadata to retrieve concepts
            actual_guideline_id = cls._get_actual_guideline_id(guideline_id)
            if not actual_guideline_id:
                return {
                    'exists': False,
                    'error': 'No concepts found for this guideline (no actual guideline ID)',
                    'concepts_in_ontology': 0,
                    'total_concepts': 0
                }
            
            # Get concepts from the actual guideline record
            concepts = cls.get_concepts_from_guideline(actual_guideline_id)
            if not concepts:
                return {
                    'exists': False,
                    'error': 'No concepts found for this guideline',
                    'concepts_in_ontology': 0,
                    'total_concepts': 0
                }
            
            # Check if a derived ontology exists for this guideline
            derived_domain = f"guideline-{guideline_id}-concepts"
            derived_ontology = Ontology.query.filter_by(domain_id=derived_domain).first()
            
            logger.info(f"Checking for derived ontology with domain: {derived_domain}")
            logger.info(f"Found derived ontology: {derived_ontology.name if derived_ontology else 'None'}")
            
            if not derived_ontology:
                # No derived ontology means concepts haven't been added yet
                return {
                    'exists': True,
                    'all_added': False,
                    'some_added': False,
                    'concepts_in_ontology': 0,
                    'total_concepts': len(concepts),
                    'percentage_added': 0,
                    'ready_to_add': True,
                    'ontology_type': 'derived',
                    'derived_ontology_exists': False
                }
            
            # Get existing entities in the derived ontology
            existing_entities = cls._get_existing_entity_labels(derived_ontology.id)
            
            # Check how many guideline concepts already exist in the derived ontology
            concepts_in_ontology = 0
            concept_labels = [concept.get('label', '') for concept in concepts]
            
            for concept_label in concept_labels:
                if any(existing.lower() == concept_label.lower() for existing in existing_entities):
                    concepts_in_ontology += 1
            
            # Determine if concepts have been added
            all_added = concepts_in_ontology == len(concepts)
            some_added = concepts_in_ontology > 0
            
            return {
                'exists': True,
                'all_added': all_added,
                'some_added': some_added,
                'concepts_in_ontology': concepts_in_ontology,
                'total_concepts': len(concepts),
                'percentage_added': round((concepts_in_ontology / len(concepts)) * 100) if concepts else 0,
                'ready_to_add': not all_added and len(concepts) > 0,
                'ontology_type': 'derived',
                'derived_ontology_exists': True,
                'derived_ontology_name': derived_ontology.name,
                'derived_ontology_id': derived_ontology.id
            }
            
        except Exception as e:
            logger.error(f"Error checking if concepts added to ontology: {str(e)}")
            return {
                'exists': False,
                'error': str(e),
                'concepts_in_ontology': 0,
                'total_concepts': 0
            }

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
    
    @classmethod
    def _get_actual_guideline_id(cls, document_id: int) -> Optional[int]:
        """
        Get the actual guideline ID from document metadata, or the document ID itself if it's a guideline.
        
        Args:
            document_id: Document ID (from URL)
            
        Returns:
            Actual guideline ID from metadata, or document_id if it's a guideline document, or None
        """
        try:
            from app.models import Document
            document = Document.query.get(document_id)
            
            if not document:
                logger.warning(f"Document {document_id} not found")
                return None
            
            # Case 1: Document references another guideline via metadata
            if document.doc_metadata and 'guideline_id' in document.doc_metadata:
                return document.doc_metadata['guideline_id']
            
            # Case 2: Document IS a guideline itself (document_type == 'guideline')
            if document.document_type == 'guideline':
                logger.info(f"Document {document_id} is itself a guideline document")
                return document_id
            
            logger.warning(f"Document {document_id} is not a guideline and has no guideline_id in metadata")
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving actual guideline ID for document {document_id}: {str(e)}")
            return None
    
    @classmethod
    def cleanup_conflicting_derived_ontologies(cls, document_id: int) -> Dict[str, Any]:
        """
        Check for and optionally clean up derived ontologies with incorrect IDs.
        
        Args:
            document_id: Document ID (correct ID for naming)
            
        Returns:
            Dict with cleanup information
        """
        try:
            # Get the actual guideline ID from document metadata
            actual_guideline_id = cls._get_actual_guideline_id(document_id)
            if not actual_guideline_id:
                return {'conflicts_found': False, 'message': 'No actual guideline ID found'}
            
            # Check for derived ontologies that might exist with wrong IDs
            correct_domain = f"guideline-{document_id}-concepts"
            incorrect_domain = f"guideline-{actual_guideline_id}-concepts"
            
            correct_ont = Ontology.query.filter_by(domain_id=correct_domain).first()
            incorrect_ont = Ontology.query.filter_by(domain_id=incorrect_domain).first()
            
            conflicts = []
            
            if correct_ont and incorrect_ont:
                conflicts.append(f"Both correct ({correct_domain}) and incorrect ({incorrect_domain}) ontologies exist")
            elif incorrect_ont and not correct_ont:
                conflicts.append(f"Only incorrect ontology exists ({incorrect_domain}), should be ({correct_domain})")
            
            return {
                'conflicts_found': len(conflicts) > 0,
                'conflicts': conflicts,
                'correct_domain': correct_domain,
                'incorrect_domain': incorrect_domain,
                'correct_ontology_exists': correct_ont is not None,
                'incorrect_ontology_exists': incorrect_ont is not None,
                'correct_ontology_id': correct_ont.id if correct_ont else None,
                'incorrect_ontology_id': incorrect_ont.id if incorrect_ont else None
            }
            
        except Exception as e:
            logger.error(f"Error checking for conflicting ontologies: {str(e)}")
            return {'conflicts_found': False, 'error': str(e)}