"""
Modified worlds routes that support concept-only extraction without requiring LLM.
This adds a specialized route for showing only extracted concepts without requiring match/triples.
"""

from flask import render_template, flash, redirect, url_for, session
import traceback

from app.models.document import Document
from app.models.ontology import Ontology

def extract_only_analyze_guideline(id, document_id, world, guideline_analysis_service):
    """
    Special implementation of analyze_guideline that only requires concept extraction
    to succeed, and does not require the matching and triple generation steps.
    
    This allows users to see extracted concepts even when LLM is unavailable.
    """
    from app.models.document import Document
    guideline = Document.query.get_or_404(document_id)
    
    # Check if document belongs to this world
    if guideline.world_id != world.id:
        flash('Document does not belong to this world', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Check if document is a guideline
    if guideline.document_type != "guideline":
        flash('Document is not a guideline', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Get guideline content - prefer content field but fall back to file content
    content = guideline.content
    if not content and guideline.file_path:
        try:
            with open(guideline.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            flash(f'Error reading guideline file: {str(e)}', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    if not content:
        flash('No content available for analysis', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Get ontology source for this world
    ontology_source = None
    if world.ontology_source:
        ontology_source = world.ontology_source
    elif world.ontology_id:
        ontology = Ontology.query.get(world.ontology_id)
        if ontology:
            ontology_source = ontology.domain_id
    
    # Extract concepts from the guideline content
    concepts_result = guideline_analysis_service.extract_concepts(content, ontology_source)
    
    if "error" in concepts_result:
        flash(f'Error analyzing guideline: {concepts_result["error"]}', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Initialize empty values for optional components
    matched_entities = {}
    preview_triples = []
    triple_count = 0
    concepts_list = concepts_result.get("concepts", [])
    
    # Try to match concepts to ontology entities if possible
    # But continue even if this fails
    try:
        matched_result = guideline_analysis_service.match_concepts(concepts_list, ontology_source)
        if not "error" in matched_result:
            matched_entities = matched_result.get("matches", {})
        else:
            flash(f'Warning: Unable to match concepts to ontology: {matched_result["error"]}', 'warning')
    except Exception as e:
        flash(f'Warning: Unable to match concepts to ontology: {str(e)}', 'warning')
    
    # Try to generate preview triples if possible
    # But continue even if this fails
    try:
        preview_indices = list(range(len(concepts_list)))
        if preview_indices:
            preview_triples_result = guideline_analysis_service.generate_triples(
                concepts_list,
                preview_indices,
                ontology_source
            )
            if not "error" in preview_triples_result:
                preview_triples = preview_triples_result.get("triples", [])
                triple_count = len(preview_triples)
                # Manually limit preview triples to 100 max for display
                preview_triples = preview_triples[:100] if len(preview_triples) > 100 else preview_triples
            else:
                flash(f'Warning: Unable to generate triple previews: {preview_triples_result["error"]}', 'warning')
    except Exception as e:
        flash(f'Warning: Unable to generate triple previews: {str(e)}', 'warning')
    
    # Store analysis results in session for the review page
    from flask import session
    session[f'guideline_analysis_{document_id}'] = {
        'concepts': concepts_list,
        'matched_entities': matched_entities,
        'ontology_source': ontology_source
    }
    
    # Render the review page with extracted concepts
    # This will work even if matching or triples failed
    return render_template('guideline_concepts_review.html', 
                        world=world, 
                        guideline=guideline, 
                        concepts=concepts_list,
                        matched_entities=matched_entities,
                        preview_triples=preview_triples,
                        triple_count=triple_count,
                        world_id=world.id,
                        document_id=document_id)
