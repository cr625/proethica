"""
Direct concept extraction route for guidelines without requiring LLM.
This provides a simpler version that just shows the extracted concepts immediately 
without trying to match them to the ontology or generate triples.
"""

from flask import render_template, flash, redirect, url_for, jsonify, session
import traceback
import json
import logging

from app.models.document import Document
from app.models.ontology import Ontology

logger = logging.getLogger(__name__)

def direct_concept_extraction(id, document_id, world, guideline_analysis_service):
    """
    Direct implementation to extract and display concepts only.
    This bypasses the matching and triples generation steps to just show what was extracted.
    """
    try:
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
                logger.error(f"Error reading file {guideline.file_path}: {str(e)}")
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
        
        logger.info(f"Extracting concepts for guideline {guideline.title} with world {world.name}")
        
        # Extract concepts from the guideline content
        concepts_result = guideline_analysis_service.extract_concepts(content, ontology_source)
        
        if "error" in concepts_result:
            logger.warning(f"Error during concept extraction: {concepts_result['error']}")
            # Check if we still have concepts despite the error
            if "concepts" not in concepts_result or not concepts_result["concepts"]:
                flash(f'Error extracting concepts: {concepts_result["error"]}', 'error')
                return redirect(url_for('worlds.world_guidelines', id=world.id))
        
        # Get the extracted concepts
        concepts_list = concepts_result.get("concepts", [])
        if not concepts_list:
            flash('No concepts were extracted from this guideline', 'warning')
            return redirect(url_for('worlds.world_guidelines', id=world.id))
            
        # Don't store concepts in session, we'll include them in the form as hidden fields
        # and pass them directly through the form submission
        concepts_json = json.dumps(concepts_list)
        
        logger.info(f"Successfully extracted {len(concepts_list)} concepts")
        
        # Try to use the guideline_concepts_review.html template, which is more robust
        # than guideline_extracted_concepts.html and has proper URL routing
        try:
            # First try the better template
            return render_template('guideline_concepts_review.html', 
                               world=world, 
                               guideline=guideline,
                               concepts=concepts_list,
                               world_id=world.id,
                               document_id=document_id)
        except Exception as template_error:
            # Fall back to the original template if needed
            logger.warning(f"Error using guideline_concepts_review.html template: {str(template_error)}. Falling back to guideline_extracted_concepts.html")
            try:
                # Fallback template
                return render_template('guideline_extracted_concepts.html', 
                                    world=world, 
                                    guideline=guideline,
                                    concepts=concepts_list,
                                    world_id=world.id,
                                    document_id=document_id)
            except Exception as fallback_error:
                # If both templates fail, redirect back to the guideline
                logger.error(f"Both templates failed. Error: {str(fallback_error)}")
                flash("Successfully extracted concepts, but encountered an error displaying them.", "warning")
                return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))
    except Exception as e:
        logger.exception(f"Error in direct_concept_extraction: {str(e)}")
        flash(f'Unexpected error during concept extraction: {str(e)}', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))

def get_extracted_concepts_json(id, document_id, world, guideline_analysis_service):
    """JSON endpoint to get extracted concepts for a guideline."""
    try:
        guideline = Document.query.get_or_404(document_id)
        
        # Check if document belongs to this world
        if guideline.world_id != world.id:
            return jsonify({"error": "Document does not belong to this world"}), 403
        
        # Check if document is a guideline
        if guideline.document_type != "guideline":
            return jsonify({"error": "Document is not a guideline"}), 400
        
        # Get guideline content
        content = guideline.content
        if not content and guideline.file_path:
            try:
                with open(guideline.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"Error reading file {guideline.file_path}: {str(e)}")
                return jsonify({"error": f"Error reading guideline file: {str(e)}"}), 500
        
        if not content:
            return jsonify({"error": "No content available for analysis"}), 400
        
        # Get ontology source for this world
        ontology_source = None
        if world.ontology_source:
            ontology_source = world.ontology_source
        elif world.ontology_id:
            ontology = Ontology.query.get(world.ontology_id)
            if ontology:
                ontology_source = ontology.domain_id
        
        # Extract concepts
        concepts_result = guideline_analysis_service.extract_concepts(content, ontology_source)
        
        if "error" in concepts_result:
            logger.warning(f"Error during concept extraction API call: {concepts_result['error']}")
            return jsonify({
                "error": concepts_result["error"],
                "concepts": concepts_result.get("concepts", [])
            })
        
        return jsonify({
            "success": True,
            "concepts": concepts_result.get("concepts", [])
        })
        
    except Exception as e:
        logger.exception(f"Error in get_extracted_concepts_json: {str(e)}")
        return jsonify({
            "error": str(e),
            "concepts": []
        }), 500
