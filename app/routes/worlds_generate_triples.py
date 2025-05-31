"""
Ontology alignment triple generation for guidelines.
Generates semantic relationship triples that connect guideline concepts to the engineering-ethics ontology.
This is Stage 2 of the guideline processing - Stage 1 already stored concepts as basic RDF triples.
"""

from flask import redirect, url_for, flash, request
import json
import logging
from app.models import db
from app.models.document import Document
from app.models.entity_triple import EntityTriple
from app.models.world import World
from app.services.guideline_analysis_service import GuidelineAnalysisService

logger = logging.getLogger(__name__)

# Define the relationship predicates we use for ontology alignment
ALIGNMENT_PREDICATES = [
    'http://proethica.org/ontology/alignsWith',
    'http://proethica.org/ontology/relatesTo',
    'http://proethica.org/ontology/implementsPrinciple',
    'http://proethica.org/ontology/emphasizesObligation',
    'http://proethica.org/ontology/definesRole',
    'http://proethica.org/ontology/requiresCapability',
    'http://proethica.org/ontology/addressesCondition',
    'http://proethica.org/ontology/isNewTermCandidate',
    'http://proethica.org/ontology/suggestedParent'
]

def generate_triples_direct(world_id, document_id):
    """
    Generate ontology alignment triples for guideline concepts.
    This adds semantic relationships between concepts and the engineering-ethics ontology.
    Does NOT delete existing basic concept triples (type, label, description).
    """
    try:
        # Verify the guideline exists and belongs to this world
        guideline = Document.query.get_or_404(document_id)
        world = World.query.get_or_404(world_id)
        
        if guideline.world_id != world.id:
            flash('Guideline does not belong to this world', 'error')
            return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))
        
        # First try to get the related Guideline if this is a Document with guideline metadata
        actual_guideline_id = None
        if guideline.doc_metadata and 'guideline_id' in guideline.doc_metadata:
            actual_guideline_id = guideline.doc_metadata['guideline_id']
            logger.info(f"Document {document_id} is associated with Guideline {actual_guideline_id}")
        
        # Get existing concepts from entity triples
        if actual_guideline_id:
            # If we have an associated guideline, look for its triples
            existing_triples = EntityTriple.query.filter_by(
                guideline_id=actual_guideline_id,
                entity_type="guideline_concept"
            ).all()
        else:
            # Otherwise look for triples associated with this document
            existing_triples = EntityTriple.query.filter_by(
                guideline_id=guideline.id,
                world_id=world.id
            ).all()
        
        # If no triples found, try to extract concepts from metadata
        if not existing_triples and guideline.doc_metadata:
            # Check if we have extracted concepts in metadata
            extracted_concepts = guideline.doc_metadata.get('extracted_concepts', [])
            selected_concepts = guideline.doc_metadata.get('selected_concepts', [])
            
            if extracted_concepts or selected_concepts:
                # Use selected concepts if available, otherwise all extracted
                concepts_to_use = selected_concepts if selected_concepts else extracted_concepts
                
                # Format concepts for triple generation
                concepts = []
                for i, concept in enumerate(concepts_to_use):
                    if isinstance(concept, dict):
                        concepts.append(concept)
                    else:
                        # Handle simple string concepts
                        concepts.append({
                            'id': f'concept_{i}',
                            'label': str(concept),
                            'description': '',
                            'category': 'concept'
                        })
                
                if concepts:
                    logger.info(f"Found {len(concepts)} concepts in document metadata")
                    # Skip to triple generation
                    logger.info(f"Generating ontology alignment triples for {len(concepts)} concepts from guideline {document_id}")
                    
                    # Initialize the guideline analysis service
                    guideline_analysis_service = GuidelineAnalysisService()
                    
                    # Generate triples for all concepts
                    selected_indices = list(range(len(concepts)))
                    
                    # Get ontology source from world
                    ontology_source = world.ontology_source if world.ontology_source else 'engineering-ethics'
                    
                    # Extract ontology terms from guideline text (not from concepts)
                    triples_result = guideline_analysis_service.extract_ontology_terms_from_text(
                        guideline_text=guideline.content,
                        world_id=world.id,
                        guideline_id=actual_guideline_id or guideline.id,
                        ontology_source=ontology_source
                    )
                    
                    if triples_result.get('success'):
                        triple_count = triples_result.get('triple_count', 0)
                        
                        # Delete old triples before saving new ones
                        if actual_guideline_id:
                            EntityTriple.query.filter_by(
                                guideline_id=actual_guideline_id,
                                entity_type="guideline_concept"
                            ).delete()
                        else:
                            EntityTriple.query.filter_by(
                                guideline_id=guideline.id,
                                world_id=world.id
                            ).delete()
                        
                        # Save the new triples
                        if 'triples' in triples_result:
                            for triple_data in triples_result['triples']:
                                entity_triple = EntityTriple(
                                    world_id=world.id,
                                    guideline_id=actual_guideline_id or guideline.id,
                                    entity_type="guideline_concept" if actual_guideline_id else None,
                                    subject=triple_data.get('subject', ''),
                                    subject_label=triple_data.get('subject_label', ''),
                                    predicate=triple_data.get('predicate', ''),
                                    predicate_label=triple_data.get('predicate_label', ''),
                                    object_uri=triple_data.get('object_uri'),
                                    object_literal=triple_data.get('object_literal'),
                                    object_label=triple_data.get('object_label'),
                                    confidence=triple_data.get('confidence', 1.0)
                                )
                                db.session.add(entity_triple)
                        
                        # Update document metadata
                        if not guideline.doc_metadata:
                            guideline.doc_metadata = {}
                        guideline.doc_metadata['triples_created'] = triple_count
                        guideline.doc_metadata['triples_generated'] = True
                        
                        db.session.commit()
                        term_count = triples_result.get('term_count', triple_count // 2)
                        flash(f'Successfully extracted {term_count} ontology terms from text ({triple_count} triples)', 'success')
                        return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))
                    else:
                        error_msg = triples_result.get('error', 'Unknown error during triple generation')
                        flash(f'Error generating triples: {error_msg}', 'error')
                        return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))
        
        # Removed concept check - Stage 2 works directly with text
        
        logger.info(f"Extracting ontology terms from guideline {document_id} text")
        
        # Initialize the guideline analysis service
        guideline_analysis_service = GuidelineAnalysisService()
        
        # Get ontology source from world
        ontology_source = world.ontology_source if world.ontology_source else 'engineering-ethics'
        
        # Extract ontology terms from guideline text (not from concepts)
        # This is completely separate from the concept extraction
        triples_result = guideline_analysis_service.extract_ontology_terms_from_text(
            guideline_text=guideline.content,
            world_id=world.id,
            guideline_id=actual_guideline_id or guideline.id,
            ontology_source=ontology_source
        )
        
        if triples_result.get('success'):
            triple_count = triples_result.get('triple_count', 0)
            
            # Delete only old alignment triples, not basic concept triples
            if actual_guideline_id:
                logger.info(f"Deleting old alignment triples for guideline {actual_guideline_id}")
                deleted_count = EntityTriple.query.filter(
                    EntityTriple.guideline_id == actual_guideline_id,
                    EntityTriple.entity_type == "guideline_concept",
                    EntityTriple.predicate.in_(ALIGNMENT_PREDICATES)
                ).delete(synchronize_session=False)
                logger.info(f"Deleted {deleted_count} old alignment triples")
            else:
                logger.info(f"Deleting old alignment triples for document {guideline.id}")
                deleted_count = EntityTriple.query.filter(
                    EntityTriple.guideline_id == guideline.id,
                    EntityTriple.world_id == world.id,
                    EntityTriple.predicate.in_(ALIGNMENT_PREDICATES)
                ).delete(synchronize_session=False)
                logger.info(f"Deleted {deleted_count} old alignment triples")
            
            # Save only unique triples (skip duplicates)
            if 'triples' in triples_result:
                unique_triples = triples_result.get('unique_triples', triples_result['triples'])
                duplicate_count = triples_result.get('duplicate_count', 0)
                
                logger.info(f"Saving {len(unique_triples)} unique triples (skipping {duplicate_count} duplicates)")
                
                for triple_data in unique_triples:
                    # Handle confidence in metadata since EntityTriple doesn't have a confidence field
                    metadata = {}
                    if 'confidence' in triple_data:
                        metadata['confidence'] = triple_data['confidence']
                    
                    # Skip if marked as duplicate
                    if triple_data.get('duplicate_check_result', {}).get('is_duplicate', False):
                        logger.debug(f"Skipping duplicate triple: {triple_data.get('subject_label', 'Unknown')} -> {triple_data.get('predicate_label', 'Unknown')}")
                        continue
                    
                    entity_triple = EntityTriple(
                        world_id=world.id,
                        guideline_id=actual_guideline_id or guideline.id,
                        entity_id=actual_guideline_id or guideline.id,  # entity_id is required
                        entity_type="guideline_concept",
                        subject=triple_data.get('subject', ''),
                        subject_label=triple_data.get('subject_label', ''),
                        predicate=triple_data.get('predicate', ''),
                        predicate_label=triple_data.get('predicate_label', ''),
                        object_uri=triple_data.get('object_uri'),
                        object_literal=triple_data.get('object_literal'),
                        object_label=triple_data.get('object_label'),
                        is_literal=bool(triple_data.get('object_literal')),
                        triple_metadata=metadata
                    )
                    db.session.add(entity_triple)
                logger.info(f"Added {len(unique_triples)} unique triples to session")
            
            db.session.commit()
            term_count = triples_result.get('term_count', triple_count // 2)
            unique_count = len(unique_triples)
            
            if duplicate_count > 0:
                flash(f'Successfully extracted {term_count} ontology terms ({unique_count} new triples, {duplicate_count} duplicates skipped)', 'success')
            else:
                flash(f'Successfully extracted {term_count} ontology terms ({unique_count} triples)', 'success')
        else:
            error_msg = triples_result.get('error', 'Unknown error during triple generation')
            flash(f'Error generating triples: {error_msg}', 'error')
            
    except Exception as e:
        logger.exception(f"Error in generate_triples_direct: {str(e)}")
        flash(f'Unexpected error: {str(e)}', 'error')
    
    return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))