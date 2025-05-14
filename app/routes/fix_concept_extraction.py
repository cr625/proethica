"""
This module provides a fix to ensure the concepts extracted from MCP are displayed to users
even when LLM is unavailable for additional processing like matching and triple generation.
"""

from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session, current_app
import json
import traceback
import os

from app.models.world import World
from app.models.document import Document
from app.models.ontology import Ontology
from app.services.guideline_analysis_service import GuidelineAnalysisService

# Create a blueprint for the concept extraction fix
fix_concepts_bp = Blueprint('fix_concepts', __name__)

# Get singleton instance
guideline_analysis_service = GuidelineAnalysisService()

@fix_concepts_bp.route('/worlds/<int:id>/guidelines/<int:document_id>/extract_concepts', methods=['GET'])
def extract_and_display_concepts(id, document_id):
    """Extract concepts from a guideline using MCP server and display them, even if LLM is unavailable."""
    world = World.query.get_or_404(id)
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
    
    # Try to extract concepts using the MCP server
    try:
        # Extract concepts from the guideline content
        concepts_result = guideline_analysis_service.extract_concepts(content, ontology_source)
        
        # Log the result structure for debugging
        print(f"Concepts result keys: {concepts_result.keys()}")
        print(f"Has concepts: {len(concepts_result.get('concepts', []))} concepts found")
        
        # Check if extraction succeeded
        if "error" in concepts_result and "concepts" not in concepts_result:
            flash(f'Error extracting concepts: {concepts_result["error"]}', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))
        
        # Get the extracted concepts, even if there was an error with LLM
        concepts_list = concepts_result.get("concepts", [])
        
        # If no concepts were found, show a warning
        if not concepts_list:
            flash('No concepts were extracted from this guideline', 'warning')
            return redirect(url_for('worlds.world_guidelines', id=world.id))
        
        # If there was an LLM error, show it as a warning
        if "error" in concepts_result and "LLM client not available" in concepts_result["error"]:
            flash('LLM client not available. Showing extracted concepts only.', 'warning')
        
        # Print the template path to verify it exists
        from flask import current_app
        template_path = 'guideline_extracted_concepts.html'
        print(f"Rendering template: {template_path}")
        for template_folder in current_app.jinja_loader.searchpath:
            full_path = os.path.join(template_folder, template_path)
            print(f"Checking if template exists at: {full_path}")
            print(f"Template exists: {os.path.exists(full_path)}")
                
        # Render the concepts template with just the concepts
        return render_template('guideline_extracted_concepts.html', 
                            world=world, 
                            guideline=guideline,
                            concepts=concepts_list,
                            world_id=world.id,
                            document_id=document_id,
                            content=content[:1000] + "..." if len(content) > 1000 else content)
    
    except Exception as e:
        flash(f'Unexpected error extracting concepts: {str(e)}', 'error')
        traceback.print_exc()
        return redirect(url_for('worlds.world_guidelines', id=world.id))

@fix_concepts_bp.route('/worlds/<int:id>/guidelines/<int:document_id>/only_extract', methods=['GET'])
def extract_only_api(id, document_id):
    """API endpoint to extract concepts without requiring LLM for matching or triple generation."""
    world = World.query.get_or_404(id)
    guideline = Document.query.get_or_404(document_id)
    
    # Check if document belongs to this world
    if guideline.world_id != world.id:
        return jsonify({"error": "Document does not belong to this world"}), 403
    
    # Get guideline content
    content = guideline.content
    if not content and guideline.file_path:
        try:
            with open(guideline.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
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
    
    # Extract concepts using MCP server
    try:
        concepts_result = guideline_analysis_service.extract_concepts(content, ontology_source)
        
        return jsonify({
            "success": True,
            "concepts": concepts_result.get("concepts", []),
            "llm_available": not ("error" in concepts_result and "LLM client not available" in concepts_result["error"])
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "concepts": []
        }), 500
