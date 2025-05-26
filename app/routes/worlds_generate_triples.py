"""
Direct triple generation route for guidelines.
Allows generating triples directly from the guideline view page without going through concept selection.
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

def generate_triples_direct(world_id, document_id):
    """
    Generate triples directly from existing concepts without the selection UI.
    This is called from the guideline view page.
    """
    try:
        # Verify the guideline exists and belongs to this world
        guideline = Document.query.get_or_404(document_id)
        world = World.query.get_or_404(world_id)
        
        if guideline.world_id != world.id:
            flash('Guideline does not belong to this world', 'error')
            return redirect(url_for('worlds.view_guideline', id=world_id, guideline_id=document_id))
        
        # Get existing concepts from entity triples
        existing_triples = EntityTriple.query.filter_by(
            guideline_id=guideline.id,
            world_id=world.id
        ).all()
        
        if not existing_triples:
            flash('No concepts found. Please analyze concepts first.', 'warning')
            return redirect(url_for('worlds.view_guideline', id=world_id, guideline_id=document_id))
        
        # Extract unique concepts from existing triples
        concepts_dict = {}
        for triple in existing_triples:
            subject = triple.subject_label or triple.subject
            if subject not in concepts_dict:
                # Try to reconstruct concept structure from triples
                concepts_dict[subject] = {
                    'id': f'concept_{len(concepts_dict)}',
                    'label': subject,
                    'description': '',
                    'category': 'concept',  # Default category
                    'related_concepts': []
                }
                
                # Look for description in triples
                if triple.predicate and 'description' in triple.predicate.lower():
                    concepts_dict[subject]['description'] = triple.object_literal or ''
                    
                # Look for category/type in triples
                if triple.predicate and ('type' in triple.predicate.lower() or 'category' in triple.predicate.lower()):
                    concepts_dict[subject]['category'] = triple.object_label or triple.object_literal or 'concept'
        
        concepts = list(concepts_dict.values())
        
        if not concepts:
            flash('Could not extract concepts from existing triples.', 'error')
            return redirect(url_for('worlds.view_guideline', id=world_id, guideline_id=document_id))
        
        logger.info(f"Regenerating triples for {len(concepts)} concepts from guideline {document_id}")
        
        # Initialize the guideline analysis service
        guideline_analysis_service = GuidelineAnalysisService()
        
        # Generate triples for all concepts (no selection indices means all)
        selected_indices = list(range(len(concepts)))
        
        # Get ontology source from world
        ontology_source = world.ontology_source if world.ontology_source else 'engineering-ethics'
        
        # Generate new triples
        triples_result = guideline_analysis_service.generate_triples(
            concepts, 
            selected_indices, 
            world_id=world.id,
            ontology_source=ontology_source
        )
        
        if triples_result.get('success'):
            triple_count = triples_result.get('triple_count', 0)
            
            # Delete old triples before saving new ones
            EntityTriple.query.filter_by(
                guideline_id=guideline.id,
                world_id=world.id
            ).delete()
            
            # Save the new triples
            if 'triples' in triples_result:
                for triple_data in triples_result['triples']:
                    entity_triple = EntityTriple(
                        world_id=world.id,
                        guideline_id=guideline.id,
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
            
            db.session.commit()
            flash(f'Successfully regenerated {triple_count} triples for {len(concepts)} concepts', 'success')
        else:
            error_msg = triples_result.get('error', 'Unknown error during triple generation')
            flash(f'Error generating triples: {error_msg}', 'error')
            
    except Exception as e:
        logger.exception(f"Error in generate_triples_direct: {str(e)}")
        flash(f'Unexpected error: {str(e)}', 'error')
    
    return redirect(url_for('worlds.view_guideline', id=world_id, guideline_id=document_id))