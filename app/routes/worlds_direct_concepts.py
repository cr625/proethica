"""
Direct concept extraction route for guidelines without requiring LLM.
This provides a simpler version that just shows the extracted concepts immediately 
without trying to match them to the ontology or generate triples.
"""

from flask import render_template, flash, redirect, url_for, jsonify, session
from slugify import slugify
import traceback
import json
import logging
from datetime import datetime

from app.models.document import Document
from app.models.ontology import Ontology
from app.services.guideline_analysis_service_v2 import GuidelineAnalysisServiceV2

logger = logging.getLogger(__name__)

def direct_concept_extraction(id, document_id, world, guideline_analysis_service):
    """
    Direct implementation to extract and display concepts only.
    This bypasses the matching and triples generation steps to just show what was extracted.
    """
    try:
        # Make sure no stale aborted transaction is lingering from a prior op in this request
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass
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
        
        # Use main service (contains former V2 functionality) - no more V1/V2 confusion
        logger.info("Using GuidelineAnalysisService (former V2) directly")
        
        # Import main service (now contains V2 functionality)
        from app.services.guideline_analysis_service import GuidelineAnalysisService
        service = GuidelineAnalysisService()
        
        # Extract concepts using main service
        concepts_result = service.extract_concepts(
            content=content,
            guideline_id=document_id, 
            world_id=id
        )
        logger.info(f"V2 extraction result keys: {list(concepts_result.keys())}")
        
        if "error" in concepts_result:
            logger.warning(f"Error during concept extraction: {concepts_result['error']}")
            # Check if we still have concepts despite the error
            if "concepts" not in concepts_result or not concepts_result["concepts"]:
                return redirect(url_for('worlds.guideline_processing_error', 
                                       world_id=world.id, 
                                       document_id=document_id,
                                       error_title='Concept Extraction Error',
                                       error_message=f'Error extracting concepts: {concepts_result["error"]}'))
        
        # Get the extracted concepts with match information
        concepts_list = concepts_result.get("concepts", [])
        relationships = concepts_result.get("relationships", [])
        term_candidates = concepts_result.get("term_candidates", [])
        stats = concepts_result.get("stats", {})
        
        # Log matching results
        if stats:
            logger.info(f"Concept extraction stats: {stats}")
            logger.info(f"Found {stats.get('matched_concepts', 0)} existing ontology matches")
            logger.info(f"Identified {stats.get('new_terms', 0)} new term candidates")
        
        # Enrich concepts with suggested links (for roles)
        try:
            def gen_uri(label: str) -> str:
                return f"http://proethica.ai/ontology#{slugify(label or '', separator='_')}"

            # Map URIs to labels/types from the concept list
            uri_to_info = {}
            for c in concepts_list:
                uri = (c.get('ontology_match') or {}).get('uri') or gen_uri(c.get('label', ''))
                uri_to_info[uri] = {
                    'label': c.get('label', uri.split('#')[-1]),
                    'type': (c.get('type') or c.get('primary_type') or '').lower() or 'concept'
                }

            # Aggregate suggestions by subject
            by_subject = {}
            for r in relationships or []:
                subj = r.get('subject') or r.get('subject_uri')
                obj = r.get('object') or r.get('object_uri')
                pred = r.get('predicate', '')
                if not subj or not obj or not pred:
                    continue
                by_subject.setdefault(subj, {'obligations': [], 'principles': [], 'ends': [], 'codes': []})
                bucket = None
                if pred.endswith('#hasObligation'):
                    bucket = 'obligations'
                elif pred.endswith('#adheresToPrinciple'):
                    bucket = 'principles'
                elif pred.endswith('#pursuesEnd'):
                    bucket = 'ends'
                elif pred.endswith('#governedByCode'):
                    bucket = 'codes'
                if bucket:
                    info = uri_to_info.get(obj, {'label': obj.split('#')[-1], 'type': 'concept'})
                    by_subject[subj][bucket].append({
                        'label': info['label'], 'uri': obj, 'type': info['type'], 'confidence': r.get('confidence')
                    })

            for c in concepts_list:
                if (c.get('type') or c.get('primary_type') or '').lower() == 'role':
                    uri = (c.get('ontology_match') or {}).get('uri') or gen_uri(c.get('label', ''))
                    c['suggested_links'] = by_subject.get(uri)
        except Exception as enrich_err:
            logger.warning(f"Could not enrich concepts with suggested links: {enrich_err}")

        # Log warning if concepts are missing enhanced fields but don't modify them
        for concept in concepts_list:
            if 'is_new' not in concept and 'ontology_match' not in concept:
                logger.error(f"CRITICAL: Concept '{concept.get('label', 'Unknown')}' missing enhanced match fields - V2 service not working properly!")
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
            
        # No caching - always extract fresh for testing simplicity
        logger.info("Skipping caching for testing simplicity - always extracting fresh")
        
        # Also prepare JSON for form submission as backup
        concepts_json = json.dumps(concepts_list)
        
        logger.info(f"Successfully extracted {len(concepts_list)} concepts")
        
        # Use the primary template - no fallbacks
        logger.info(f"Passing {len(concepts_list)} concepts to template guideline_concepts_review.html")
        
        # Render the enhanced concepts review template with match information
        return render_template('guideline_concepts_review.html', 
                               world=world, 
                               guideline=guideline,
                               concepts=concepts_list,
                               relationships=relationships,
                               term_candidates=term_candidates,
                               stats=stats,
                               world_id=world.id,
                               document_id=document_id,
                               ontology_source=ontology_source,
                               matched_entities={})  # Add empty matched_entities to fix any missing variable issues
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
        
        # Extract concepts using main service
        concepts_result = guideline_analysis_service.extract_concepts(content, document_id, id)
        
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
