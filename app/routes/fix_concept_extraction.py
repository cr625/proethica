"""
This module provides a fix to ensure the concepts extracted from MCP are displayed to users
even when LLM is unavailable for additional processing like matching and triple generation.
"""

from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session, current_app
import json
import logging
import traceback
import os
from datetime import datetime

from app.models.world import World
from app.models.document import Document
from app.models.ontology import Ontology
from app.services.guideline_analysis_service import GuidelineAnalysisService
from app import db

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

@fix_concepts_bp.route('/worlds/<int:world_id>/guidelines/<int:document_id>/save_concepts', methods=['POST'])
def save_extracted_concepts(world_id, document_id):
    """Save selected concepts from a guideline document to the ontology database."""
    logger.info(f"Saving guideline concepts for document {document_id} in world {world_id}")
    
    # Debug log all form data
    logger.info("Form data:")
    for key, value in request.form.items():
        if key == 'concepts_data':
            logger.info(f"  {key}: [JSON data of length {len(value)}]")
        else:
            logger.info(f"  {key}: {value}")
    
    world = World.query.get_or_404(world_id)
    
    from app.models.document import Document
    guideline = Document.query.get_or_404(document_id)
    
    # Check if document belongs to this world
    if guideline.world_id != world.id:
        flash('Document does not belong to this world', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Get selected concepts from form
    selected_concept_indices = request.form.getlist('selected_concepts')
    selected_indices = [int(idx) for idx in selected_concept_indices]
    
    logger.info(f"Selected concept indices: {selected_indices}")
    
    if not selected_indices:
        flash('No concepts selected', 'warning')
        return redirect(url_for('fix_concepts.extract_and_display_concepts', id=world_id, document_id=document_id))
    
    try:
        # Get concepts data from the form instead of session
        concepts_data = request.form.get('concepts_data', '[]')
        ontology_source = request.form.get('ontology_source', '')
        
        logger.info(f"Got concepts_data of length {len(concepts_data)} and ontology_source: {ontology_source}")
        
        # Parse the JSON data from the form with better error handling
        try:
            logger.info(f"Parsing concepts_data: First 100 chars: {concepts_data[:100]}...")
            
            # Try various methods to fix malformatted JSON
            try:
                # First try standard JSON parsing
                concepts = json.loads(concepts_data)
                logger.info(f"Standard JSON parsing successful, got {len(concepts) if isinstance(concepts, list) else '?'} items")
            except json.JSONDecodeError as je:
                logger.warning(f"Standard JSON parsing failed: {str(je)}, trying fixes...")
                
                # Try to fix various common JSON formatting issues
                import re
                fixed_data = concepts_data
                
                # 1. Fix missing quotes around property names
                # Example: converts {property: "value"} to {"property": "value"}
                if "{" in fixed_data:
                    logger.info("Attempting to fix missing quotes around property names")
                    
                    # Use regex to identify keys without quotes and add them
                    property_pattern = r'([{,]\s*)([a-zA-Z0-9_]+)(\s*:)'
                    fixed_data = re.sub(property_pattern, r'\1"\2"\3', fixed_data)
                    
                    logger.info(f"After fixing property quotes: {fixed_data[:50]}...")
                
                # 2. Fix single quotes to double quotes
                # Example: converts {'property': 'value'} to {"property": "value"}
                if "'" in fixed_data:
                    logger.info("Attempting to fix single quotes to double quotes")
                    
                    # Use a safer approach to replace single quotes with double quotes
                    fixed_data = fixed_data.replace("'", '"')
                    logger.info(f"After fixing single quotes: {fixed_data[:50]}...")
                
                # 3. Try to use ast.literal_eval for Python-style dictionaries
                try:
                    from ast import literal_eval
                    logger.info("Attempting to parse with ast.literal_eval")
                    python_obj = literal_eval(fixed_data)
                    concepts = python_obj
                    logger.info(f"Fixed JSON using ast.literal_eval, got {len(concepts) if isinstance(concepts, list) else '?'} items")
                except (SyntaxError, ValueError) as e:
                    logger.error(f"Could not parse with ast.literal_eval: {str(e)}")
                    
                    # 4. Last resort: try to parse the fixed data as JSON
                    try:
                        logger.info("Attempting to parse fixed data as JSON")
                        concepts = json.loads(fixed_data)
                        logger.info(f"Fixed JSON parsing successful, got {len(concepts) if isinstance(concepts, list) else '?'} items")
                    except json.JSONDecodeError as je2:
                        # Log original data for debugging
                        logger.error(f"All JSON parsing attempts failed. Original data sample: {concepts_data[:200]}")
                        logger.error(f"Fixed data sample: {fixed_data[:200]}")
                        raise je2
                
            logger.info(f"Parsed concepts data successfully, got {type(concepts)} with {len(concepts) if isinstance(concepts, list) else '?'} items")
        except json.JSONDecodeError as json_error:
            logger.error(f"JSON decode error: {str(json_error)}")
            logger.error(f"First 200 chars of concepts_data: {concepts_data[:200]}")
            flash(f'Error decoding concepts JSON: {str(json_error)}. Check the data format.', 'error')
            return redirect(url_for('fix_concepts.extract_and_display_concepts', id=world_id, document_id=document_id))
        except Exception as json_error:
            logger.error(f"Error parsing concepts JSON: {str(json_error)}")
            flash('Error processing concepts data. Please try again.', 'error')
            return redirect(url_for('fix_concepts.extract_and_display_concepts', id=world_id, document_id=document_id))
        
        if not concepts:
            logger.error("Concepts list is empty after parsing")
            flash('No concepts found in analysis results', 'error')
            return redirect(url_for('fix_concepts.extract_and_display_concepts', id=world_id, document_id=document_id))
        
        logger.info(f"Generating triples for {len(selected_indices)} selected concepts out of {len(concepts)} total concepts")
        
        # Generate triples for selected concepts
        triples_result = guideline_analysis_service.generate_triples(
            concepts, 
            selected_indices, 
            ontology_source
        )
        
        if "error" in triples_result:
            flash(f'Error generating triples: {triples_result["error"]}', 'error')
            return redirect(url_for('fix_concepts.extract_and_display_concepts', id=world_id, document_id=document_id))
        
        # Save the guideline model with the triples
        try:
            # Create guideline record
            from app.models.guideline import Guideline
            new_guideline = Guideline(
                world_id=world_id,
                title=guideline.title,
                content=guideline.content,
                source_url=guideline.source,
                file_path=guideline.file_path,
                file_type=guideline.file_type,
                metadata={
                    "document_id": document_id,
                    "analyzed": True,
                    "concepts_extracted": len(concepts),
                    "concepts_selected": len(selected_indices),
                    "triple_count": triples_result.get("triple_count", 0),
                    "analysis_date": datetime.utcnow().isoformat(),
                    "ontology_source": ontology_source
                }
            )
            db.session.add(new_guideline)
            db.session.flush()  # Get the guideline ID
            
            # Get triples data
            triples_data = triples_result.get("triples", [])
            triple_count = len(triples_data)
            
            if triples_data:
                # Log the number of triples to be saved
                logger.info(f"Saving {triple_count} triples to the database for guideline {new_guideline.id}")
                
                # Bulk insert triples for better performance
                entity_triples = []
                from app.models.entity_triple import EntityTriple
                
                for triple_data in triples_data:
                    # Determine if object is literal or URI
                    is_literal = isinstance(triple_data["object"], str)
                    object_value = triple_data["object"]
                    
                    # Check if the object value isn't a URI - if it starts with http:// or https://, it's a URI
                    if is_literal and (object_value.startswith("http://") or object_value.startswith("https://")):
                        is_literal = False
                    
                    triple = EntityTriple(
                        subject=triple_data["subject"],
                        predicate=triple_data["predicate"],
                        object_literal=object_value if is_literal else None,
                        object_uri=None if is_literal else object_value,
                        is_literal=is_literal,
                        subject_label=triple_data.get("subject_label"),
                        predicate_label=triple_data.get("predicate_label"),
                        object_label=triple_data.get("object_label"),
                        graph=f"guideline_{new_guideline.id}",
                        entity_type="guideline_concept",
                        entity_id=new_guideline.id,
                        world_id=world_id,
                        guideline_id=new_guideline.id,
                        triple_metadata={
                            "source": "guideline_analysis",
                            "confidence": triple_data.get("confidence", 1.0) if "confidence" in triple_data else 1.0,
                            "created_at": datetime.utcnow().isoformat()
                        }
                    )
                    entity_triples.append(triple)
                
                # Add all triples to the session
                db.session.bulk_save_objects(entity_triples)
                
            # Update document metadata
            guideline.doc_metadata = {
                **(guideline.doc_metadata or {}),
                "analyzed": True,
                "guideline_id": new_guideline.id,
                "concepts_extracted": len(concepts),
                "concepts_selected": len(selected_indices),
                "triples_created": triple_count,
                "analysis_date": datetime.utcnow().isoformat()
            }
            db.session.commit()
            
            logger.info(f"Successfully created {triple_count} RDF triples for guideline {new_guideline.id}")
            flash(f'Successfully saved {len(selected_indices)} concepts and created {triple_count} RDF triples', 'success')
            
            # Redirect to the world guidelines page as confirmation of successful saving
            return redirect(url_for('worlds.world_guidelines', id=world_id))
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Error saving triples: {str(e)}\n{error_trace}")
            flash(f'Error saving triples: {str(e)}', 'error')
            return redirect(url_for('fix_concepts.extract_and_display_concepts', id=world_id, document_id=document_id))
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error processing concepts: {str(e)}\n{error_trace}")
        flash(f'Error processing concepts: {str(e)}', 'error')
        return redirect(url_for('fix_concepts.extract_and_display_concepts', id=world_id, document_id=document_id))

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
