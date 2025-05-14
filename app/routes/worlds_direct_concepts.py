"""
Direct concept extraction route for guidelines without requiring LLM.
This provides a simpler version that just shows the extracted concepts immediately 
without trying to match them to the ontology or generate triples.
"""

from flask import render_template, flash, redirect, url_for, jsonify
import traceback
import json

from app.models.document import Document
from app.models.ontology import Ontology

def direct_concept_extraction(id, document_id, world, guideline_analysis_service):
    """
    Direct implementation to extract and display concepts only.
    This bypasses the matching and triples generation steps to just show what was extracted.
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
        flash(f'Error extracting concepts: {concepts_result["error"]}', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Get the extracted concepts
    concepts_list = concepts_result.get("concepts", [])
    if not concepts_list:
        flash('No concepts were extracted from this guideline', 'warning')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
        
    # Render the concepts review template with just the concepts
    return render_template('guideline_extracted_concepts.html', 
                          world=world, 
                          guideline=guideline,
                          concepts=concepts_list,
                          world_id=world.id,
                          document_id=document_id,
                          content=content[:1000] + "..." if len(content) > 1000 else content)

def get_extracted_concepts_json(id, document_id, world, guideline_analysis_service):
    """JSON endpoint to get extracted concepts for a guideline."""
    from app.models.document import Document
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
    try:
        concepts_result = guideline_analysis_service.extract_concepts(content, ontology_source)
        
        if "error" in concepts_result:
            return jsonify({
                "error": concepts_result["error"],
                "concepts": []
            }), 400
        
        return jsonify({
            "success": True,
            "concepts": concepts_result.get("concepts", [])
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "concepts": []
        }), 500
