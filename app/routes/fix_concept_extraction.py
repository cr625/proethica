"""
This module provides a fix to ensure the concepts extracted from MCP are displayed to users
even when LLM is unavailable for additional processing like matching and triple generation.
"""

from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session, current_app
import json
import logging
import traceback
import os

from app.models.world import World
from app.models.document import Document
from app.models.ontology import Ontology
from app.services.guideline_analysis_service import GuidelineAnalysisService

# Set up logging
logger = logging.getLogger(__name__)

# Create a blueprint for the concept extraction fix
fix_concepts_bp = Blueprint('fix_concepts', __name__)

# Get singleton instance
guideline_analysis_service = GuidelineAnalysisService()

@fix_concepts_bp.route('/worlds/<int:id>/guidelines/<int:document_id>/extract_concepts', methods=['GET'])
def extract_and_display_concepts(id, document_id):
    """Extract concepts from a guideline using MCP server and display them, even if LLM is unavailable."""
    try:
        world = World.query.get_or_404(id)
        
        # Import the direct concept extraction function from worlds_direct_concepts
        from app.routes.worlds_direct_concepts import direct_concept_extraction
        
        logger.info(f"Attempting to extract concepts for world {id}, document {document_id}")
        
        # Call the direct concept extraction function
        return direct_concept_extraction(id, document_id, world, guideline_analysis_service)
        
    except Exception as e:
        logger.exception(f"Error in extract_and_display_concepts for world {id}, document {document_id}: {str(e)}")
        flash(f'Unexpected error extracting concepts: {str(e)}', 'error')
        return redirect(url_for('worlds.world_guidelines', id=id))

@fix_concepts_bp.route('/worlds/<int:id>/guidelines/<int:document_id>/only_extract', methods=['GET'])
def extract_only_api(id, document_id):
    """API endpoint to extract concepts without requiring LLM for matching or triple generation."""
    try:
        world = World.query.get_or_404(id)
        guideline = Document.query.get_or_404(document_id)
        
        logger.info(f"API extraction requested for world {id}, document {document_id}")
        
        # Check if document belongs to this world
        if guideline.world_id != world.id:
            logger.warning(f"Document {document_id} does not belong to world {id}")
            return jsonify({"error": "Document does not belong to this world"}), 403
        
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
            logger.warning(f"No content available for document {document_id}")
            return jsonify({"error": "No content available for analysis"}), 400
        
        # Get ontology source for this world
        ontology_source = None
        if world.ontology_source:
            ontology_source = world.ontology_source
        elif world.ontology_id:
            ontology = Ontology.query.get(world.ontology_id)
            if ontology:
                ontology_source = ontology.domain_id
        
        # Extract concepts using MCP server
        concepts_result = guideline_analysis_service.extract_concepts(content, ontology_source)
        
        # Check if there was an error with LLM availability
        llm_available = True
        if "error" in concepts_result and "LLM client not available" in concepts_result["error"]:
            logger.warning("LLM client not available, using fallback concepts")
            llm_available = False
            
        logger.info(f"Successfully extracted {len(concepts_result.get('concepts', []))} concepts")
            
        return jsonify({
            "success": True,
            "concepts": concepts_result.get("concepts", []),
            "llm_available": llm_available
        })
        
    except Exception as e:
        logger.exception(f"Error in extract_only_api for world {id}, document {document_id}: {str(e)}")
        return jsonify({
            "error": str(e),
            "concepts": []
        }), 500
