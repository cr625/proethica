"""
Routes for extracting concepts from guidelines without relying on entity integration.
This provides a direct route to extract concepts from guidelines using the LLM.
"""

from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for, session
from app.services.guideline_analysis_service import GuidelineAnalysisService
from app.models import Document
from app.models.world import World
from app import db
import json
import logging

logger = logging.getLogger(__name__)

worlds_extract_only_bp = Blueprint('worlds_extract_only', __name__)

@worlds_extract_only_bp.route('/worlds/<int:world_id>/guidelines/<int:document_id>/review_concepts_from_temp', methods=['GET'])
def review_concepts_from_temp(world_id, document_id):
    """
    Retrieve and display concepts from temporary storage for review.
    This is used when navigating back from the triples review page.
    """
    try:
        world = World.query.get_or_404(world_id)
        document = Document.query.get_or_404(document_id)
        
        # Check if document belongs to this world
        if document.world_id != world.id:
            flash("Document does not belong to this world", "error")
            return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))
        
        # Get the latest session for this document
        from app.services.temporary_concept_service import TemporaryConceptService
        session_id = TemporaryConceptService.get_latest_session_for_document(
            document_id=document_id,
            world_id=world_id
        )
        
        if not session_id:
            # No temporary concepts found, redirect to extract new concepts
            flash("No temporary concepts found. Please extract concepts first.", "info")
            return redirect(url_for('worlds_extract_only.extract_concepts_direct', 
                                    world_id=world_id, document_id=document_id))
        
        # Retrieve concepts from temporary storage (try different statuses)
        temp_concepts = TemporaryConceptService.get_session_concepts(session_id, status='pending')
        
        # If no pending concepts, try reviewed concepts (they can still be modified)
        if not temp_concepts:
            temp_concepts = TemporaryConceptService.get_session_concepts(session_id, status='reviewed')
            
        # If still no concepts, try any status for this session
        if not temp_concepts:
            temp_concepts = TemporaryConceptService.get_session_concepts(session_id)
        
        if not temp_concepts:
            flash("No concepts found in temporary storage. Please extract concepts first.", "info")
            return redirect(url_for('worlds_extract_only.extract_concepts_direct', 
                                    world_id=world_id, document_id=document_id))
        
        # Convert to the format expected by the template
        concepts_list = [tc.concept_data for tc in temp_concepts]
        
        # Get ontology source for this world (needed by template)
        ontology_source = None
        if world.ontology_source:
            ontology_source = world.ontology_source
        elif world.ontology_id:
            from app.models.ontology import Ontology
            ontology = Ontology.query.get(world.ontology_id)
            if ontology:
                ontology_source = ontology.domain_id
        
        # Prepare stats
        stats = {
            'total_concepts': len(concepts_list),
            'matched_concepts': len([c for c in concepts_list if not c.get('is_new', True)]),
            'new_terms': len([c for c in concepts_list if c.get('is_new', True)]),
            'relationships': 0  # We don't have relationships in temp storage currently
        }
        
        # Show appropriate message based on concept status
        status = temp_concepts[0].status if temp_concepts else 'unknown'
        if status == 'reviewed':
            flash(f"Showing {len(concepts_list)} previously reviewed concepts from temporary storage.", "info")
        elif status == 'committed':
            flash(f"Showing {len(concepts_list)} committed concepts from temporary storage.", "warning")
        else:
            logger.info(f"Retrieved {len(concepts_list)} concepts from temporary storage (session: {session_id}, status: {status})")
        
        # Render the concepts review template
        return render_template('guideline_concepts_review.html', 
                               world=world, 
                               guideline=document,
                               concepts=concepts_list,
                               relationships=[],  # Empty for now
                               term_candidates=[],  # Empty for now
                               stats=stats,
                               session_id=session_id,
                               world_id=world.id,
                               document_id=document.id,
                               ontology_source=ontology_source,
                               matched_entities={})
                               
    except Exception as e:
        logger.error(f"Error retrieving concepts from temporary storage: {str(e)}")
        flash(f"Error retrieving concepts: {str(e)}", "error")
        return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))

@worlds_extract_only_bp.route('/worlds/<int:world_id>/guidelines/<int:document_id>/extract_concepts_direct', methods=['GET', 'POST'])
def extract_concepts_direct(world_id, document_id):
    """
    Extract concepts from a guideline document directly using the LLM-based extraction.
    This bypasses the entity integration and focuses solely on extracting concepts.
    
    Args:
        world_id: ID of the world containing the guideline
        document_id: ID of the guideline document to extract concepts from
        
    Returns:
        JSON response with extracted concepts or redirect to concepts review page
    """
    try:
        world = World.query.get_or_404(world_id)
        document = Document.query.get_or_404(document_id)
        
        # Create analysis service
        analysis_service = GuidelineAnalysisService()
        
        # Check if document belongs to this world
        if document.world_id != world.id:
            flash("Document does not belong to this world", "error")
            return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))
        
        # Check if document is a guideline
        if document.document_type != "guideline":
            flash("Document is not a guideline", "error")
            return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))
        
        # Get document content
        content = document.content
        if not content and document.file_path:
            try:
                with open(document.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                flash(f"Error reading file: {str(e)}", "error")
                return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))
        if not content:
            flash("No content found in the guideline document", "error")
            return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))        
        
        
        # Get ontology source for this world if available
        ontology_source = world.ontology_source
        
        # Extract concepts using the enhanced LLM-based approach
        logger.info(f"Extracting concepts directly from guideline: {document.title}")
        result = analysis_service.extract_concepts(content, document_id, world_id)
        
        if "concepts" in result:
            extracted_concepts = result["concepts"]
            
            # Save the concepts to a JSON file for debugging/review
            try:
                with open('guideline_concepts.json', 'w') as f:
                    json.dump(extracted_concepts, f, indent=2)
            except Exception as e:
                logger.warning(f"Could not save concepts to file: {str(e)}")
            
            # SAVE CONCEPTS TO DATABASE IMMEDIATELY
            from app.services.temporary_concept_service import TemporaryConceptService
            try:
                session_id = TemporaryConceptService.store_concepts(
                    concepts=extracted_concepts,
                    document_id=document_id,
                    world_id=world_id,
                    extraction_method='llm',
                    created_by=session.get('user_id', 'anonymous')
                )
                logger.info(f"Successfully stored {len(extracted_concepts)} concepts in database with session_id: {session_id}")
            except Exception as e:
                logger.error(f"Error storing concepts to database: {str(e)}")
                flash(f"Concepts extracted but could not be saved to database: {str(e)}", "warning")
                # Fall back to showing basic template without database storage
                return render_template('guideline_extracted_concepts.html',
                                     world=world,
                                     guideline=document,
                                     concepts=extracted_concepts,
                                     world_id=world_id,
                                     document_id=document_id)
            
            logger.info(f"Successfully extracted {len(extracted_concepts)} concepts from guideline")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # If AJAX request, return JSON response with session_id
                return jsonify({
                    "success": True, 
                    "concepts": extracted_concepts,
                    "document_id": document_id,
                    "session_id": session_id
                })
            else:
                # Redirect to enhancement/review endpoint instead of showing basic template
                flash(f"Successfully extracted {len(extracted_concepts)} concepts. Loading enhanced review...", "success")
                return redirect(url_for('worlds_extract_only.enhance_and_review_concepts', 
                                      world_id=world_id, 
                                      document_id=document_id, 
                                      session_id=session_id))
        else:
            # Handle error case
            error_message = result.get("error", "Unknown error in concept extraction")
            logger.error(f"Error extracting concepts: {error_message}")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "error": error_message})
            else:
                flash(f"Error extracting concepts: {error_message}", "error")
                # If there are concepts in the result (even with error), show them
                if "concepts" in result and result["concepts"]:
                    return render_template('guideline_extracted_concepts.html',
                                         world=world,
                                         guideline=document,
                                         concepts=result["concepts"],
                                         world_id=world_id,
                                         document_id=document_id,
                                         error=error_message)
                else:
                    return redirect(url_for('worlds.view_guideline', 
                                         id=world_id, 
                                         document_id=document_id))
        
    except Exception as e:
        logger.exception(f"Error in extract_concepts_direct: {str(e)}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "error": str(e)})
        else:
            flash(f"Error extracting concepts: {str(e)}", "error")
            return redirect(url_for('worlds.view_guideline', 
                                   id=world_id, 
                                   document_id=document_id))

@worlds_extract_only_bp.route('/worlds/<int:world_id>/guidelines/<int:document_id>/enhance_and_review/<session_id>', methods=['GET'])
def enhance_and_review_concepts(world_id, document_id, session_id):
    """
    Enhance saved concepts with ontology matching and show the rich review interface.
    This runs the expensive ontology analysis on concepts saved in the database.
    
    Args:
        world_id: ID of the world containing the guideline
        document_id: ID of the guideline document
        session_id: Session ID for the saved concepts
        
    Returns:
        Enhanced review page with ontology matching, relationships, and full UI
    """
    try:
        world = World.query.get_or_404(world_id)
        document = Document.query.get_or_404(document_id)
        
        # Check if document belongs to this world
        if document.world_id != world.id:
            flash("Document does not belong to this world", "error")
            return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))
        
        # Retrieve concepts from database
        from app.services.temporary_concept_service import TemporaryConceptService
        temp_concepts = TemporaryConceptService.get_session_concepts(session_id, status='pending')
        
        if not temp_concepts:
            flash("No concepts found in database. Please extract concepts first.", "error")
            return redirect(url_for('worlds_extract_only.extract_concepts_direct', 
                                  world_id=world_id, document_id=document_id))
        
        # Convert to concept data format
        concepts_list = [tc.concept_data for tc in temp_concepts]
        logger.info(f"Retrieved {len(concepts_list)} concepts from database for enhancement")
        
        # ENHANCE WITH RELATIONSHIPS AND ADVANCED ANALYSIS
        analysis_service = GuidelineAnalysisService()
        enhanced_concepts = concepts_list
        relationships = []  # Initialize relationships array
        
        try:
            logger.info(f"Running relationship discovery on {len(concepts_list)} concepts...")
            
            # Get the original document content for relationship discovery
            content = document.content
            if not content and document.file_path:
                try:
                    with open(document.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read document content for relationship analysis: {str(e)}")
                    content = ""
            
            if content:
                # Discover relationships using the same method as extraction
                relationships = analysis_service._discover_relationships(enhanced_concepts, content)
                logger.info(f"Discovered {len(relationships)} relationships between concepts")
                
                # Add role-specific relationships (like hasObligation, adheresToPrinciple)
                try:
                    role_relationships = analysis_service._discover_role_relationships(enhanced_concepts, content)
                    relationships.extend(role_relationships)
                    logger.info(f"Added {len(role_relationships)} role-specific relationships")
                except Exception as role_err:
                    logger.warning(f"Role relationship discovery failed: {str(role_err)}")
                
                # Add predicates to concepts based on discovered relationships  
                enhanced_concepts = analysis_service._add_predicates_to_concepts(enhanced_concepts, relationships)
                logger.info(f"Enhanced {len(enhanced_concepts)} concepts with suggested predicates from {len(relationships)} total relationships")
            else:
                logger.warning("No document content available for relationship analysis")
                # Add empty relationship structures
                for concept in enhanced_concepts:
                    if 'suggested_predicates' not in concept:
                        concept['suggested_predicates'] = {'as_subject': [], 'as_object': []}
                    if 'suggested_links' not in concept:
                        concept['suggested_links'] = {}
                
        except Exception as e:
            logger.error(f"Error during relationship analysis: {str(e)}")
            flash(f"Relationship analysis failed: {str(e)}", "warning")
            # Add empty structures as fallback
            for concept in enhanced_concepts:
                if 'suggested_predicates' not in concept:
                    concept['suggested_predicates'] = {'as_subject': [], 'as_object': []}
                if 'suggested_links' not in concept:
                    concept['suggested_links'] = {}
        
        # Get ontology source for this world
        ontology_source = None
        if world.ontology_source:
            ontology_source = world.ontology_source
        elif world.ontology_id:
            from app.models.ontology import Ontology
            ontology = Ontology.query.get(world.ontology_id)
            if ontology:
                ontology_source = ontology.domain_id
        
        # Generate preview triples (if available)
        preview_triples = []
        triple_count = 0
        try:
            if hasattr(analysis_service, 'generate_preview_triples'):
                triples_result = analysis_service.generate_preview_triples(enhanced_concepts, world_id)
                if triples_result.get("success", False):
                    preview_triples = triples_result.get("triples", [])
                    triple_count = len(preview_triples)
                    logger.info(f"Generated {triple_count} preview triples")
        except Exception as e:
            logger.warning(f"Could not generate preview triples: {str(e)}")
        
        # Prepare statistics
        stats = {
            'total_concepts': len(enhanced_concepts),
            'matched_concepts': len([c for c in enhanced_concepts if not c.get('is_new', True)]),
            'new_terms': len([c for c in enhanced_concepts if c.get('is_new', True)]),
            'relationships': sum(len(c.get('suggested_predicates', {}).get('as_subject', [])) + 
                               len(c.get('suggested_predicates', {}).get('as_object', [])) 
                               for c in enhanced_concepts)
        }
        
        # Render the ENHANCED review template (the good one!)
        return render_template('guideline_concepts_review.html',
                               world=world,
                               guideline=document,
                               concepts=enhanced_concepts,
                               relationships=relationships,
                               term_candidates=[],
                               stats=stats,
                               session_id=session_id,
                               world_id=world.id,
                               document_id=document.id,
                               ontology_source=ontology_source,
                               matched_entities={},
                               preview_triples=preview_triples,
                               triple_count=triple_count,
                               llm_unavailable=False)
        
    except Exception as e:
        logger.exception(f"Error in enhance_and_review_concepts: {str(e)}")
        flash(f"Error enhancing concepts: {str(e)}", "error")
        return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))

@worlds_extract_only_bp.route('/worlds/<int:world_id>/guidelines/<int:document_id>/load_pending_concepts', methods=['GET'])
def load_pending_concepts(world_id, document_id):
    """
    Load the most recent pending concepts for a document and redirect to enhancement view.
    This is for the "Load Pending Concepts" button functionality.
    
    Args:
        world_id: ID of the world containing the guideline
        document_id: ID of the guideline document
        
    Returns:
        Redirect to enhancement view or error message
    """
    try:
        world = World.query.get_or_404(world_id)
        document = Document.query.get_or_404(document_id)
        
        # Check if document belongs to this world
        if document.world_id != world.id:
            flash("Document does not belong to this world", "error")
            return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))
        
        # Find the latest session for this document
        from app.services.temporary_concept_service import TemporaryConceptService
        session_id = TemporaryConceptService.get_latest_session_for_document(
            document_id=document_id,
            world_id=world_id,
            status='pending'
        )
        
        if not session_id:
            flash("No pending concepts found. Please extract concepts first.", "info")
            return redirect(url_for('worlds_extract_only.extract_concepts_direct', 
                                  world_id=world_id, document_id=document_id))
        
        # Redirect to enhancement view
        return redirect(url_for('worlds_extract_only.enhance_and_review_concepts',
                              world_id=world_id,
                              document_id=document_id,
                              session_id=session_id))
        
    except Exception as e:
        logger.exception(f"Error loading pending concepts: {str(e)}")
        flash(f"Error loading pending concepts: {str(e)}", "error")
        return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))
