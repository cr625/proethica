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
            return redirect(url_for('worlds.guideline_processing_error', 
                                   world_id=world.id, 
                                   document_id=document_id,
                                   error_title='Access Error',
                                   error_message='Document does not belong to this world'))
        
        # Check if document is a guideline
        if guideline.document_type != "guideline":
            return redirect(url_for('worlds.guideline_processing_error', 
                                   world_id=world.id, 
                                   document_id=document_id,
                                   error_title='Document Type Error',
                                   error_message='Document is not a guideline'))
        
        # Get guideline content - prefer content field but fall back to file content
        content = guideline.content
        if not content and guideline.file_path:
            try:
                with open(guideline.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"Error reading file {guideline.file_path}: {str(e)}")
                error_details = traceback.format_exc()
                return redirect(url_for('worlds.guideline_processing_error', 
                                       world_id=world.id, 
                                       document_id=document_id,
                                       error_title='File Reading Error',
                                       error_message=f'Error reading guideline file: {str(e)}',
                                       error_details=error_details))
        
        if not content:
            return redirect(url_for('worlds.guideline_processing_error', 
                                   world_id=world.id, 
                                   document_id=document_id,
                                   error_title='Empty Content Error',
                                   error_message='No content available for analysis'))
        
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
                return redirect(url_for('worlds.guideline_processing_error', 
                                       world_id=world.id, 
                                       document_id=document_id,
                                       error_title='Concept Extraction Error',
                                       error_message=f'Error extracting concepts: {concepts_result["error"]}'))
        
        # Get the extracted concepts
        concepts_list = concepts_result.get("concepts", [])
        if not concepts_list:
            # Check if this is an MCP server issue
            error_message = 'No concepts were extracted from this guideline'
            if concepts_result.get("using_fallback"):
                error_message = 'The MCP server did not return any concepts. Please check the MCP server logs.'
            elif "error" in concepts_result:
                error_message = f'Extraction error: {concepts_result["error"]}'
                
            return redirect(url_for('worlds.guideline_processing_error', 
                                   world_id=world.id, 
                                   document_id=document_id,
                                   error_title='No Concepts Found',
                                   error_message=error_message))
            
        # Don't store concepts in session, we'll include them in the form as hidden fields
        # and pass them directly through the form submission
        concepts_json = json.dumps(concepts_list)
        
        logger.info(f"Successfully extracted {len(concepts_list)} concepts")
        
        # Try to use the guideline_concepts_review.html template, which is more robust
        # than guideline_extracted_concepts.html and has proper URL routing
        try:
            # Debug log the concepts list to help with troubleshooting
            logger.info(f"Passing {len(concepts_list)} concepts to template guideline_concepts_review.html")
            
            # First try the better template with additional logging
            return render_template('guideline_concepts_review.html', 
                               world=world, 
                               guideline=guideline,
                               concepts=concepts_list,
                               world_id=world.id,
                               document_id=document_id,
                               ontology_source=ontology_source)  # Pass ontology_source explicitly
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
                # If both templates fail, redirect to error page
                logger.error(f"Both templates failed. Error: {str(fallback_error)}")
                error_details = traceback.format_exc()
                return redirect(url_for('worlds.guideline_processing_error', 
                                       world_id=world.id, 
                                       document_id=document_id,
                                       error_title='Template Rendering Error',
                                       error_message='Successfully extracted concepts, but encountered an error displaying them.',
                                       error_details=error_details))
    except Exception as e:
        logger.exception(f"Error in direct_concept_extraction: {str(e)}")
        error_details = traceback.format_exc()
        return redirect(url_for('worlds.guideline_processing_error', 
                               world_id=world.id, 
                               document_id=document_id,
                               error_title='Unexpected Error',
                               error_message=f'Unexpected error during concept extraction: {str(e)}',
                               error_details=error_details))

def get_extracted_concepts_json(id, document_id, world, guideline_analysis_service):
    """JSON endpoint to get extracted concepts for a guideline."""
    try:
        guideline = Document.query.get_or_404(document_id)
        
        # Check if document belongs to this world
        if guideline.world_id != world.id:
            return jsonify({
                "error": "Document does not belong to this world",
                "error_type": "access_error",
                "error_title": "Access Error"
            }), 403
        
        # Check if document is a guideline
        if guideline.document_type != "guideline":
            return jsonify({
                "error": "Document is not a guideline",
                "error_type": "document_type_error",
                "error_title": "Document Type Error"
            }), 400
        
        # Get guideline content
        content = guideline.content
        if not content and guideline.file_path:
            try:
                with open(guideline.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"Error reading file {guideline.file_path}: {str(e)}")
                error_details = traceback.format_exc()
                return jsonify({
                    "error": f"Error reading guideline file: {str(e)}",
                    "error_type": "file_reading_error",
                    "error_title": "File Reading Error",
                    "error_details": error_details
                }), 500
        
        if not content:
            return jsonify({
                "error": "No content available for analysis",
                "error_type": "empty_content_error",
                "error_title": "Empty Content Error"
            }), 400
        
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
                "error_type": "concept_extraction_error",
                "error_title": "Concept Extraction Error",
                "concepts": concepts_result.get("concepts", [])
            })
        
        return jsonify({
            "success": True,
            "concepts": concepts_result.get("concepts", [])
        })
        
    except Exception as e:
        logger.exception(f"Error in get_extracted_concepts_json: {str(e)}")
        error_details = traceback.format_exc()
        return jsonify({
            "error": str(e),
            "error_type": "unexpected_error",
            "error_title": "Unexpected Error",
            "error_details": error_details,
            "concepts": []
        }), 500
