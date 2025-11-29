"""
Routes for document structure visualization and section embeddings.
Uses DocumentSection model with pgvector for section embedding storage and retrieval.
"""

import os
import sys
import json
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request, current_app, abort
from flask_sqlalchemy import SQLAlchemy
from app.models import Document
from app.models.scenario import Scenario
from app.models.document_section import DocumentSection
from app.models.section_term_link import SectionTermLink
from app.services.section_embedding_service import SectionEmbeddingService
from app.services.guideline_section_service import GuidelineSectionService 
from app.services.case_processing.pipeline_steps.document_structure_annotation_step import DocumentStructureAnnotationStep
from app.services.structure_triple_formatter import StructureTripleFormatter
from app.services.ontology_term_recognition_service import OntologyTermRecognitionService
from datetime import datetime
from app import db

# Import the section triple association service
from ttl_triple_association.section_triple_association_service import SectionTripleAssociationService
from ttl_triple_association.section_triple_association_storage import SectionTripleAssociationStorage

# Create blueprint
doc_structure_bp = Blueprint('doc_structure', __name__, url_prefix='/structure')


def init_doc_structure_csrf_exemption(app):
    """Exempt document structure routes from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        from app.routes.document_structure import generate_structure, generate_embeddings
        app.csrf.exempt(generate_structure)
        app.csrf.exempt(generate_embeddings)


@doc_structure_bp.route('/view/<int:id>', methods=['GET'])
def view_structure(id):
    """View document structure for a specific case."""
    # Force a fresh load from the database to get the latest data
    # This ensures we see any recent updates from the generate_structure route
    db.session.close()
    
    # Get the document with a fresh query
    document = Document.query.get_or_404(id)
    
    # Check if it's a case
    if document.document_type not in ['case', 'case_study']:
        flash('The requested document is not a case', 'warning')
        return redirect(url_for('cases.list_cases'))
    
    # Get document metadata with explicit refresh
    metadata = {}
    if document.doc_metadata:
        if isinstance(document.doc_metadata, dict):
            metadata = document.doc_metadata
        else:
            # If it's not a dict (likely a string), try to parse it
            try:
                metadata = json.loads(document.doc_metadata)
            except:
                flash('Error parsing document metadata', 'warning')
                metadata = {}
    
    # Check if document has structure information
    has_structure = False
    document_uri = None
    structure_triples = None
    section_metadata = None
    debug_info = {}
    
    # Add some debugging information
    debug_info['metadata_keys'] = list(metadata.keys()) if metadata else []
    debug_info['has_document_structure'] = 'document_structure' in metadata
    
    # Check for structure information in different possible locations
    
    # Case 1: Properly structured under document_structure
    if 'document_structure' in metadata:
        doc_struct = metadata['document_structure']
        debug_info['document_structure_keys'] = list(doc_struct.keys()) if doc_struct else []
        
        # Check if it has the essential components
        has_uri = 'document_uri' in doc_struct and doc_struct['document_uri']
        has_triples = 'structure_triples' in doc_struct and doc_struct['structure_triples']
        
        if has_uri and has_triples:
            has_structure = True
            document_uri = doc_struct.get('document_uri')
            structure_triples = doc_struct.get('structure_triples')
        else:
            # Structure data is incomplete
            debug_info['incomplete_structure'] = {
                'has_uri': has_uri,
                'has_triples': has_triples
            }
    
    # Case 2: Structure information at the top level (legacy format)
    elif 'document_uri' in metadata and 'structure_triples' in metadata:
        debug_info['structure_format'] = 'top_level'
        has_structure = True
        document_uri = metadata.get('document_uri')
        structure_triples = metadata.get('structure_triples')
    
    if 'section_embeddings_metadata' in metadata:
        section_metadata = metadata['section_embeddings_metadata']
    
    # Check for section embeddings
    has_section_embeddings = False
    section_embeddings_info = None
    
    # Add detailed logging for debugging section embeddings
    current_app.logger.info(f"Checking for section embeddings in document {id}")
    
    # First, check in document metadata (normal path)
    if 'document_structure' in metadata:
        current_app.logger.info(f"document_structure keys: {list(metadata['document_structure'].keys())}")
        
        # Check if any section has embeddings
        if 'sections' in metadata['document_structure']:
            sections = metadata['document_structure']['sections']
            sections_with_embeddings = [s for s in sections if 'embedding' in sections[s]]
            current_app.logger.info(f"Found {len(sections_with_embeddings)} sections with embeddings")
            
            # If sections have embeddings but section_embeddings key is missing, add it
            if sections_with_embeddings and 'section_embeddings' not in metadata['document_structure']:
                current_app.logger.info("Fixing: Sections have embeddings but section_embeddings key is missing")
                
                # Add the section_embeddings key
                metadata['document_structure']['section_embeddings'] = {
                    'count': len(sections_with_embeddings),
                    'updated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # Save the updated metadata
                document.doc_metadata = metadata
                db.session.commit()
                current_app.logger.info("Added missing section_embeddings key to document metadata")
    
    # Now check if section_embeddings exists in document_structure
    if 'document_structure' in metadata and 'section_embeddings' in metadata['document_structure']:
        has_section_embeddings = True
        section_embeddings_info = metadata['document_structure']['section_embeddings']
        current_app.logger.info(f"Section embeddings info: {section_embeddings_info}")
        
        # Get list of sections with embeddings for display
        embedded_sections = []
        if 'sections' in metadata['document_structure']:
            sections = metadata['document_structure']['sections']
            if isinstance(sections, dict):
                for section_id in sections.keys():
                    embedded_sections.append(section_id)
        
        # If no sections found in metadata, check DocumentSection table
        if not embedded_sections:
            from app.models.document_section import DocumentSection
            db_sections = DocumentSection.query.filter_by(document_id=id).all()
            embedded_sections = [section.section_type for section in db_sections]
        
        section_embeddings_info['sections'] = embedded_sections
    else:
        # Fallback: Check directly in the DocumentSection table
        from app.models.document_section import DocumentSection
        
        # Count sections for this document in the DocumentSection table
        doc_sections_count = DocumentSection.query.filter_by(document_id=id).count()
        current_app.logger.info(f"Fallback check: Found {doc_sections_count} sections in DocumentSection table")
        
        if doc_sections_count > 0:
            # We found sections in the table, but they're not reflected in the metadata
            # Update the document metadata and set has_section_embeddings
            has_section_embeddings = True
            
            # Get section types from database
            db_sections = DocumentSection.query.filter_by(document_id=id).all()
            embedded_sections = [section.section_type for section in db_sections]
            
            # Create section_embeddings_info for the template
            section_embeddings_info = {
                'count': doc_sections_count,
                'updated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'storage_type': 'pgvector',
                'note': 'Detected from database (metadata updated)',
                'sections': embedded_sections
            }
            
            # Update the document metadata if needed
            if 'document_structure' not in metadata:
                metadata['document_structure'] = {}
            
            # Add the section_embeddings info
            metadata['document_structure']['section_embeddings'] = section_embeddings_info
            
            # Save the updated metadata
            try:
                document.doc_metadata = json.loads(json.dumps(metadata))
                db.session.commit()
                current_app.logger.info("Updated document metadata with section embeddings information from database")
            except Exception as e:
                current_app.logger.warning(f"Failed to update metadata with section embeddings info: {str(e)}")
    
    # Check for guideline associations
    has_guideline_associations = False
    section_guideline_associations = None
    
    # Check if document has guideline associations in metadata
    if 'document_structure' in metadata and 'guideline_associations' in metadata['document_structure']:
        has_guideline_associations = True
        guideline_associations_info = metadata['document_structure']['guideline_associations']
        current_app.logger.info(f"Guideline associations info: {guideline_associations_info}")
        
        # Try to load guideline associations
        try:
            guideline_service = GuidelineSectionService()
            guidelines_result = guideline_service.get_document_section_guidelines(id)
            if guidelines_result.get('success') and guidelines_result.get('sections'):
                section_guideline_associations = guidelines_result.get('sections')
                current_app.logger.info(f"Loaded {len(section_guideline_associations)} sections with guideline associations")
        except Exception as e:
            current_app.logger.warning(f"Error loading guideline associations: {str(e)}")
    
    # Always load guideline associations from the service for up-to-date results
    guideline_service = GuidelineSectionService()
    section_guideline_associations = None
    has_guideline_associations = False
    try:
        guidelines_result = guideline_service.get_document_section_guidelines(id)
        if guidelines_result.get('success') and guidelines_result.get('sections'):
            section_guideline_associations = guidelines_result.get('sections')
            has_guideline_associations = True
            current_app.logger.info(f"Loaded {len(section_guideline_associations)} sections with guideline associations (forced refresh)")
    except Exception as e:
        current_app.logger.warning(f"Error loading guideline associations: {str(e)}")
        
    # Check for section-triple associations
    has_triple_associations = False
    section_triple_associations = None
    
    try:
        # Create the triple association storage
        triple_storage = SectionTripleAssociationStorage()
        
        # Get document sections and their associated triples
        document_associations = triple_storage.get_document_associations(id)
        
        if document_associations:
            has_triple_associations = True
            section_triple_associations = document_associations
            current_app.logger.info(f"Loaded section-triple associations for {len(document_associations)} sections")
    except Exception as e:
        current_app.logger.warning(f"Error loading section-triple associations: {str(e)}")

    # Check for enhanced guideline associations
    has_enhanced_associations = False
    enhanced_associations_data = None
    enhanced_associations_stats = None
    
    try:
        # Check if this document has enhanced associations
        from sqlalchemy import text
        with db.engine.connect() as conn:
            query = text("""
                SELECT COUNT(*) as total_associations,
                       AVG(overall_confidence) as avg_confidence,
                       COUNT(CASE WHEN overall_confidence > 0.7 THEN 1 END) as high_confidence_count,
                       section_type,
                       COUNT(*) as section_count,
                       AVG(overall_confidence) as section_avg_confidence
                FROM case_guideline_associations 
                WHERE case_id = :case_id
                GROUP BY section_type
                ORDER BY section_avg_confidence DESC
            """)
            
            result = conn.execute(query, {"case_id": id})
            associations_by_section = result.fetchall()
            
            if associations_by_section:
                has_enhanced_associations = True
                
                # Get overall stats
                query_overall = text("""
                    SELECT COUNT(*) as total,
                           AVG(overall_confidence) as avg_confidence,
                           COUNT(CASE WHEN overall_confidence > 0.7 THEN 1 END) as high_confidence,
                           COUNT(DISTINCT section_type) as sections_processed
                    FROM case_guideline_associations 
                    WHERE case_id = :case_id
                """)
                
                overall_result = conn.execute(query_overall, {"case_id": id})
                overall_stats = overall_result.fetchone()
                
                enhanced_associations_stats = {
                    'total_associations': overall_stats[0],
                    'average_confidence': round(overall_stats[1], 3) if overall_stats[1] else 0,
                    'high_confidence_count': overall_stats[2],
                    'sections_processed': overall_stats[3],
                    'by_section': []
                }
                
                for row in associations_by_section:
                    enhanced_associations_stats['by_section'].append({
                        'section_type': row[3],
                        'count': row[4], 
                        'avg_confidence': round(row[5], 3) if row[5] else 0
                    })
                
                # Get top associations for display
                query_top = text("""
                    SELECT cga.section_type, cga.overall_confidence, cga.semantic_similarity,
                           cga.keyword_overlap, cga.contextual_relevance, cga.association_reasoning,
                           cga.pattern_indicators, et.subject, et.object_literal,
                           cga.llm_semantic_score, cga.llm_reasoning_quality,
                           cga.embedding_reasoning, cga.llm_reasoning, cga.scoring_method
                    FROM case_guideline_associations cga
                    JOIN entity_triples et ON cga.guideline_concept_id = et.id
                    WHERE cga.case_id = :case_id
                    ORDER BY cga.overall_confidence DESC
                    LIMIT 20
                """)
                
                top_result = conn.execute(query_top, {"case_id": id})
                enhanced_associations_data = []
                
                for row in top_result:
                    pattern_indicators = {}
                    if row[6]:  # pattern_indicators
                        try:
                            pattern_indicators = json.loads(row[6]) if isinstance(row[6], str) else row[6]
                        except:
                            pattern_indicators = {}
                    
                    enhanced_associations_data.append({
                        'section_type': row[0],
                        'overall_confidence': row[1],
                        'embedding_similarity': row[2],  # renamed from semantic_similarity
                        'keyword_overlap': row[3],
                        'contextual_relevance': row[4],
                        'reasoning': row[5],  # combined reasoning
                        'pattern_indicators': pattern_indicators,
                        'concept_uri': row[7],
                        'concept_name': row[8] or row[7].split('/')[-1] if row[7] else 'Unknown',
                        'llm_semantic_score': row[9] or 0.0,
                        'llm_reasoning_quality': row[10] or 0.0,
                        'embedding_reasoning': row[11] or 'Not available',
                        'llm_reasoning': row[12] or 'LLM analysis not available',
                        'scoring_method': row[13] or 'hybrid'
                    })
                
                current_app.logger.info(f"Loaded {len(enhanced_associations_data)} enhanced associations")
                
    except Exception as e:
        current_app.logger.warning(f"Error loading enhanced associations: {str(e)}")

    # Check for ontology term links
    has_term_links = False
    section_term_links = None
    
    try:
        # Get term links for this document
        document_term_links = SectionTermLink.get_document_term_links(id)
        
        if document_term_links:
            has_term_links = True
            section_term_links = document_term_links
            total_term_links = sum(len(links) for links in document_term_links.values())
            current_app.logger.info(f"Loaded {total_term_links} term links across {len(document_term_links)} sections")
    except Exception as e:
        current_app.logger.warning(f"Error loading term links: {str(e)}")

    # Format structure triples if available
    structured_triples_data = None
    if has_structure and structure_triples:
        formatter = StructureTripleFormatter()
        structured_triples_data = formatter.parse_triples(structure_triples)
        
        # Add LLM-friendly format
        if 'error' not in structured_triples_data:
            structured_triples_data['llm_format'] = formatter.format_for_llm(structured_triples_data)
    
    # Add a timestamp query parameter to prevent browser caching
    no_cache = request.args.get('_', '')
    
    return render_template('document_structure.html', 
                          document=document,
                          has_structure=has_structure,
                          document_uri=document_uri,
                          structure_triples=structure_triples,
                          structured_triples_data=structured_triples_data,
                          section_metadata=section_metadata,
                          has_section_embeddings=has_section_embeddings,
                          section_embeddings_info=section_embeddings_info,
                          has_guideline_associations=has_guideline_associations,
                          section_guideline_associations=section_guideline_associations,
                          has_triple_associations=has_triple_associations,
                          section_triple_associations=section_triple_associations,
                          has_enhanced_associations=has_enhanced_associations,
                          enhanced_associations_data=enhanced_associations_data,
                          enhanced_associations_stats=enhanced_associations_stats,
                          has_term_links=has_term_links,
                          section_term_links=section_term_links,
                          debug_info=debug_info,
                          no_cache=no_cache)

@doc_structure_bp.route('/generate_embeddings/<int:id>', methods=['POST'])
def generate_embeddings(id):
    """Generate section embeddings for a document."""
    # Get the document
    document = Document.query.get(id)
    if not document:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': 'Document not found'
            }), 404
        else:
            abort(404)
    
    try:
        # Ensure metadata is properly loaded as a dictionary
        if isinstance(document.doc_metadata, str):
            try:
                import json
                document.doc_metadata = json.loads(document.doc_metadata)
            except (json.JSONDecodeError, TypeError) as e:
                current_app.logger.error(f"Failed to parse document metadata: {e}")
                return jsonify({
                    'success': False,
                    'message': 'Invalid document metadata format. Please regenerate document structure.'
                }), 400
        
        metadata = document.doc_metadata or {}
        
        # Check if document has proper structure data
        doc_structure = metadata.get('document_structure', {})
        if not doc_structure:
            return jsonify({
                'success': False,
                'message': 'Document structure not found. Please generate document structure first.'
            }), 400
        
        # Verify we have structure triples for granular processing
        structure_triples = doc_structure.get('structure_triples', '')
        if not structure_triples:
            return jsonify({
                'success': False,
                'message': 'Structure triples not found. Please regenerate document structure.'
            }), 400
        
        # Initialize section embedding service
        section_embedding_service = SectionEmbeddingService()
        
        # Log that we're starting the embedding generation process
        current_app.logger.info(f"Starting section embedding generation for document {id}")
        
        # Log the document metadata structure for debugging
        current_app.logger.info(f"Document metadata keys: {list(metadata.keys())}")
        if 'document_structure' in metadata:
            current_app.logger.info(f"Document structure keys: {list(metadata['document_structure'].keys())}")
            if 'sections' in metadata['document_structure']:
                sections = metadata['document_structure']['sections']
                # Check if sections is a dictionary before trying to access its properties
                if isinstance(sections, dict):
                    current_app.logger.info(f"Found {len(sections)} sections in document_structure")
                    
                    # Log the first section to understand structure
                    if sections:
                        first_section_id = list(sections.keys())[0]
                        if isinstance(sections[first_section_id], dict):
                            current_app.logger.info(f"First section ({first_section_id}) keys: {list(sections[first_section_id].keys())}")
                else:
                    current_app.logger.warning(f"document_structure.sections is not a dictionary, it's a {type(sections)}")
        
        # Process document sections
        result = section_embedding_service.process_document_sections(document.id)
        
        if result.get('success'):
            success_message = f"Successfully generated embeddings for {result.get('sections_embedded')} sections"
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'message': success_message,
                    'sections_embedded': result.get('sections_embedded')
                })
            else:
                flash(success_message, 'success')
            
            # Force reload the document from the database to ensure we have the latest data
            db.session.close()
            document = Document.query.get(id)
            
            # Double-check that the embeddings data was saved correctly
            current_app.logger.info(f"Verifying embeddings were saved - reloaded document from database")
            metadata = document.doc_metadata or {}
            if 'document_structure' in metadata:
                if 'section_embeddings' in metadata['document_structure']:
                    current_app.logger.info(f"Found section_embeddings with count: {metadata['document_structure']['section_embeddings'].get('count')}")
                else:
                    current_app.logger.warning(f"section_embeddings key is still missing after reload!")
                    
                # If there are sections with embeddings but no section_embeddings, fix it
                if 'sections' in metadata['document_structure']:
                    sections = metadata['document_structure']['sections']
                    # Check if sections is a dictionary before iterating
                    if isinstance(sections, dict):
                        sections_with_embeddings = [s for s in sections 
                                                 if isinstance(sections[s], dict) and 'embedding' in sections[s]]
                        
                        current_app.logger.info(f"Found {len(sections_with_embeddings)} sections with embeddings after reload")
                    else:
                        sections_with_embeddings = []
                        current_app.logger.warning(f"sections is not a dictionary after reload, it's a {type(sections)}")
                    
                    if sections_with_embeddings and 'section_embeddings' not in metadata['document_structure']:
                        current_app.logger.info("Still fixing missing section_embeddings key after reload")
                        
                        # Add the section_embeddings key
                        metadata['document_structure']['section_embeddings'] = {
                            'count': len(sections_with_embeddings),
                            'updated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        
                        # Force an explicit update and commit
                        document.doc_metadata = json.loads(json.dumps(metadata))
                        db.session.commit()
                        current_app.logger.info("Fixed missing section_embeddings key and committed changes")
                        
                        # Finally reload the document again to confirm
                        db.session.close()
                        document = Document.query.get(id)
        else:
            error_msg = result.get('error', 'Unknown error')
            current_app.logger.error(f"Error generating embeddings: {error_msg}")
            flash(f"Error generating embeddings: {error_msg}", 'danger')
    
    except Exception as e:
        current_app.logger.exception(f"Exception during section embedding generation: {str(e)}")
        error_message = str(e)
        
        # Provide more helpful error messages for common issues
        if "'str' object has no attribute 'keys'" in error_message:
            error_message = "Document metadata is corrupted. Please regenerate the document structure."
        elif "No section data found" in error_message:
            error_message = "No section data found. Please generate document structure first."
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': error_message
            }), 500
        else:
            flash(f"Error processing section embeddings: {error_message}", 'danger')
    
    # Add timestamp to prevent caching
    return redirect(url_for('doc_structure.view_structure', id=id, _=datetime.utcnow().timestamp()))

@doc_structure_bp.route('/search_similar', methods=['GET', 'POST'])
def search_similar_sections():
    """Search for similar sections across all documents."""
    if request.method == 'POST':
        query_text = request.form.get('query', '')
        section_type = request.form.get('section_type', None)
        limit = int(request.form.get('limit', 5))
        
        if not query_text:
            flash('Please enter a search query', 'warning')
            return render_template('section_search.html', results=None)
        
        try:
            # Initialize section embedding service
            section_embedding_service = SectionEmbeddingService()
            
            # Search for similar sections
            results = section_embedding_service.find_similar_sections(
                query_text=query_text,
                section_type=section_type if section_type else None,
                limit=limit
            )
            
            return render_template('section_search.html', 
                                  results=results, 
                                  query=query_text,
                                  section_type=section_type,
                                  limit=limit)
            
        except Exception as e:
            flash(f"Error searching for similar sections: {str(e)}", 'danger')
            return render_template('section_search.html', results=None)
    
    # GET request - show search form
    return render_template('section_search.html', results=None)

@doc_structure_bp.route('/generate_structure/<int:id>', methods=['POST'])
def generate_structure(id):
    """Generate document structure annotations for a document."""
    # Get the document
    document = Document.query.get_or_404(id)
    
    # Check if document already has structure - check multiple locations
    if document.doc_metadata and isinstance(document.doc_metadata, dict):
        metadata = document.doc_metadata
        
        # Check if properly structured
        if 'document_structure' in metadata and isinstance(metadata['document_structure'], dict) and \
           'document_uri' in metadata['document_structure'] and 'structure_triples' in metadata['document_structure']:
            flash("This document already has structure annotations.", "info")
            return redirect(url_for('doc_structure.view_structure', id=id))
            
        # Check if it has structure at the top level (legacy format)
        elif 'document_uri' in metadata and 'structure_triples' in metadata:
            # If found, organize it properly
            try:
                # Create proper document_structure object
                metadata['document_structure'] = {
                    'document_uri': metadata['document_uri'],
                    'structure_triples': metadata['structure_triples'],
                    'annotation_timestamp': metadata.get('structure_annotation_timestamp', datetime.utcnow().isoformat()),
                    'sections': {}  # Initialize empty sections
                }
                
                # Save reorganized metadata
                document.doc_metadata = json.loads(json.dumps(metadata))
                db.session.commit()
                
                flash("Reorganized existing document structure to standard format.", "info")
                return redirect(url_for('doc_structure.view_structure', id=id))
            except Exception as e:
                current_app.logger.error(f"Error reorganizing structure: {str(e)}")
                # We'll fall through and regenerate the structure
    
    try:
        # Get document metadata
        metadata = {}
        if document.doc_metadata:
            if isinstance(document.doc_metadata, dict):
                metadata = document.doc_metadata
            else:
                # If it's not a dict (likely a string), try to parse it
                try:
                    metadata = json.loads(document.doc_metadata)
                except:
                    flash('Error parsing document metadata', 'warning')
                    return redirect(url_for('doc_structure.view_structure', id=id))
        
        # Check if document has sections data
        if 'sections' not in metadata:
            flash("Document does not have the necessary section data for structure annotation.", "warning")
            return redirect(url_for('doc_structure.view_structure', id=id))
        
        # Prepare input data for document structure annotation step
        input_data = {
            'status': 'success',
            'case_number': metadata.get('case_number', ''),
            'year': metadata.get('year', ''),
            'title': document.title,
            'sections': metadata.get('sections', {}),
            'questions_list': metadata.get('questions_list', []),
            'conclusion_items': metadata.get('conclusion_items', [])
        }
        
        # Create and run document structure annotation step
        structure_step = DocumentStructureAnnotationStep()
        result = structure_step.process(input_data)
        
        if result.get('status') != 'success':
            flash(f"Failed to generate document structure: {result.get('message')}", "danger")
            return redirect(url_for('doc_structure.view_structure', id=id))
        
        # Update document metadata with structure information
        metadata['document_structure'] = {
            'document_uri': result['document_structure']['document_uri'],
            'structure_triples': result['document_structure']['structure_triples'],
            'annotation_timestamp': datetime.utcnow().isoformat(),
            'sections': result['document_structure'].get('sections', {})  # Use the sections from the pipeline result
        }
        
        # Add section embeddings metadata
        metadata['section_embeddings_metadata'] = result['section_embeddings_metadata']

        # Log the resulting structure for debugging
        current_app.logger.info(f"Generated document structure: {list(metadata['document_structure'].keys())}")
        
        # Ensure we're making a deep copy of any nested structures to prevent reference issues
        document.doc_metadata = json.loads(json.dumps(metadata))
        
        # Make sure changes are committed to the database
        db.session.flush()
        db.session.commit()
        
        # Force reload the document to verify changes were saved
        db.session.refresh(document)
        
        # Verify document structure was saved correctly
        if 'document_structure' in document.doc_metadata:
            flash(f"Successfully generated document structure with {len(result['document_structure'].get('graph', []))} triples", "success")
        else:
            flash("Generated document structure, but had issues saving to database. Please try again.", "warning")
    
    except Exception as e:
        flash(f"Error generating document structure: {str(e)}", "danger")
    
    # Force a new database fetch on redirect
    return redirect(url_for('doc_structure.view_structure', id=id, _=datetime.utcnow().timestamp()))

@doc_structure_bp.route('/generate_term_links/<int:id>', methods=['POST'])
def generate_term_links(id):
    """Generate ontology term links for a document."""
    # Get the document
    document = Document.query.get(id)
    if not document:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': 'Document not found'
            }), 404
        else:
            abort(404)
    
    try:
        # Initialize the term recognition service
        recognition_service = OntologyTermRecognitionService()
        
        if not recognition_service.ontology_terms:
            error_msg = "Ontology terms not loaded. Cannot generate term links."
            current_app.logger.error(error_msg)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': error_msg
                }), 500
            else:
                flash(error_msg, 'danger')
                return redirect(url_for('doc_structure.view_structure', id=id))
        
        # Process the document
        result = recognition_service.process_document_sections(id, force_regenerate=True)
        
        if result.get('success'):
            success_message = f"Successfully generated {result.get('term_links_created')} term links across {result.get('sections_processed')} sections"
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'message': success_message,
                    'term_links_created': result.get('term_links_created'),
                    'sections_processed': result.get('sections_processed')
                })
            else:
                flash(success_message, 'success')
        else:
            error_msg = result.get('error', 'Unknown error')
            current_app.logger.error(f"Error generating term links: {error_msg}")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': f"Error generating term links: {error_msg}"
                }), 500
            else:
                flash(f"Error generating term links: {error_msg}", 'danger')
    
    except Exception as e:
        current_app.logger.exception(f"Exception during term link generation: {str(e)}")
        error_message = str(e)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': error_message
            }), 500
        else:
            flash(f"Error processing term links: {error_message}", 'danger')
    
    # Add timestamp to prevent caching
    return redirect(url_for('doc_structure.view_structure', id=id, _=datetime.utcnow().timestamp()))

@doc_structure_bp.route('/associate_guidelines/<int:id>', methods=['POST'])
def associate_guidelines(id):
    """Associate ethical guidelines with document sections."""
    # Get the document
    document = Document.query.get_or_404(id)
    
    try:
        # Create the guideline service
        guideline_service = GuidelineSectionService()
        
        # Process document sections
        result = guideline_service.associate_guidelines_with_sections(document.id)
        
        if result.get('success'):
            flash(f"Successfully created {result.get('associations_created', 0)} guideline associations across {result.get('sections_processed', 0)} sections", 'success')
        else:
            error_msg = result.get('error', 'Unknown error')
            flash(f"Error associating guidelines: {error_msg}", 'danger')
    
    except Exception as e:
        flash(f"Error processing section guideline associations: {str(e)}", 'danger')
    
    # Add timestamp to prevent caching
    return redirect(url_for('doc_structure.view_structure', id=id, _=datetime.utcnow().timestamp()))

@doc_structure_bp.route('/associate_ontology_concepts/<int:id>', methods=['POST'])
def associate_ontology_concepts(id):
    """Associate ontology concepts with document sections using enhanced service."""
    current_app.logger.info(f"🔥 ENHANCED ROUTE HIT: POST to associate_ontology_concepts/{id}")
    current_app.logger.info(f"🔥 Form data: {dict(request.form)}")
    current_app.logger.info(f"🔥 Request method: {request.method}")
    # Try to get the document - could be stored as Document or Scenario
    document = Document.query.get(id)
    if not document:
        # Try as Scenario (cases are sometimes stored as scenarios)
        from app.models.scenario import Scenario
        document = Scenario.query.get_or_404(id)
        # For scenarios, we need to use scenario_metadata instead of doc_metadata
        metadata_field = 'scenario_metadata'
    else:
        metadata_field = 'doc_metadata'
    
    # Get association method from form
    association_method = request.form.get('association_method', 'embedding')
    
    try:
        # Use async processing instead of synchronous
        from app.services.task_queue import BackgroundTaskQueue
        
        task_queue = BackgroundTaskQueue.get_instance()
        
        # Initialize processing status in document metadata
        if not document.doc_metadata:
            document.doc_metadata = {}
        
        # Check if already processing
        current_status = document.doc_metadata.get('association_processing_status')
        if current_status == 'processing':
            flash("Associations are already being processed for this document. Please wait for completion.", "info")
            return redirect(url_for('doc_structure.view_structure', id=id))
        
        # Start async processing
        success = task_queue.process_associations_async(id, association_method)
        
        if success:
            # Initialize status
            document.doc_metadata['association_processing_status'] = 'pending'
            document.doc_metadata['association_processing_progress'] = 0
            document.doc_metadata['association_processing_phase'] = 'initializing'
            db.session.commit()
            
            current_app.logger.info(f"Started async association processing for document {id} with {association_method} method")
            flash(f"Association processing started using {association_method} method. This may take 2-3 minutes. The page will show progress updates.", "info")
        else:
            flash("Failed to start association processing. Please try again.", "error")
            
    except Exception as e:
        current_app.logger.exception(f"Error associating ontology concepts: {str(e)}")
        flash(f"Error associating ontology concepts: {str(e)}", "danger")
    
    # Add timestamp to prevent caching
    return redirect(url_for('doc_structure.view_structure', id=id, _=datetime.utcnow().timestamp()))

@doc_structure_bp.route('/association_progress/<int:id>', methods=['GET'])
def association_progress(id):
    """Get association processing progress for a document."""
    try:
        # Force refresh from database to avoid session isolation issues
        db.session.expire_all()
        document = Document.query.get_or_404(id)
        db.session.refresh(document)
        
        if not document.doc_metadata:
            return jsonify({
                'status': 'not_started',
                'progress': 0,
                'phase': 'none'
            })
        
        status = document.doc_metadata.get('association_processing_status', 'not_started')
        progress = document.doc_metadata.get('association_processing_progress', 0)
        phase = document.doc_metadata.get('association_processing_phase', 'none')
        error = document.doc_metadata.get('association_processing_error')
        results = document.doc_metadata.get('association_results')
        
        # Fallback: Check if associations actually exist (workaround for session isolation issue)
        if status == 'not_started':
            try:
                # Query the associations table directly (using correct column name: case_id)
                from sqlalchemy import text
                result = db.session.execute(
                    text("SELECT COUNT(*) FROM case_guideline_associations WHERE case_id = :case_id"),
                    {"case_id": id}
                ).scalar()
                
                if result and result > 0:
                    status = 'completed'
                    progress = 100
                    phase = 'completed'
                    # Try to get results from associations if not in metadata
                    if not results:
                        results = {
                            'total_associations': result,
                            'method_used': 'hybrid',
                            'processed_at': 'recently'
                        }
            except Exception as e:
                current_app.logger.error(f"Error checking existing associations: {e}")
        
        response = {
            'status': status,
            'progress': progress,
            'phase': phase
        }
        
        if error:
            response['error'] = error
            
        if results:
            response['results'] = results
            
        return jsonify(response)
        
    except Exception as e:
        current_app.logger.error(f"Error getting association progress: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@doc_structure_bp.route('/clear_associations/<int:id>', methods=['POST'])
def clear_associations(id):
    """Clear enhanced guideline associations for a document."""
    current_app.logger.info(f"Clearing enhanced associations for document {id}")
    
    try:
        # Clear from database
        from sqlalchemy import text
        with db.engine.connect() as conn:
            result = conn.execute(
                text("DELETE FROM case_guideline_associations WHERE case_id = :case_id"),
                {"case_id": id}
            )
            deleted_count = result.rowcount
            conn.commit()
        
        # Clear from document metadata if it exists
        document = Document.query.get(id)
        if not document:
            # Try as Scenario
            from app.models.scenario import Scenario
            document = Scenario.query.get(id)
            metadata_field = 'scenario_metadata'
        else:
            metadata_field = 'doc_metadata'
            
        if document:
            metadata = getattr(document, metadata_field) or {}
            if isinstance(metadata, dict):
                if 'document_structure' in metadata and 'enhanced_associations' in metadata['document_structure']:
                    del metadata['document_structure']['enhanced_associations']
                    setattr(document, metadata_field, json.loads(json.dumps(metadata)))
                    db.session.commit()
        
        success_message = f"Cleared {deleted_count} enhanced associations"
        current_app.logger.info(success_message)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': success_message,
                'deleted_count': deleted_count
            })
        else:
            flash(success_message, 'success')
            
    except Exception as e:
        error_message = f"Error clearing associations: {str(e)}"
        current_app.logger.error(error_message)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': error_message
            }), 500
        else:
            flash(error_message, 'danger')
    
    # Add timestamp to prevent caching for clear route
    return redirect(url_for('doc_structure.view_structure', id=id, _=datetime.utcnow().timestamp()))

@doc_structure_bp.route('/compare_sections/<int:doc_id>/<section_id>', methods=['GET'])
def compare_sections(doc_id, section_id):
    """Find sections similar to a specific document section."""
    # Get the document
    document = Document.query.get_or_404(doc_id)
    
    # Get document metadata
    metadata = {}
    if document.doc_metadata and isinstance(document.doc_metadata, dict):
        metadata = document.doc_metadata
    
    # Check if document has structure and the requested section
    if ('document_structure' not in metadata or 
        'sections' not in metadata['document_structure'] or
        section_id not in metadata['document_structure']['sections']):
        flash('Requested section not found', 'warning')
        return redirect(url_for('doc_structure.view_structure', id=doc_id))
    
    # Get section data
    section_data = metadata['document_structure']['sections'][section_id]
    
    if 'content' not in section_data:
        flash('Section has no content for comparison', 'warning')
        return redirect(url_for('doc_structure.view_structure', id=doc_id))
    
    try:
        # Initialize section embedding service
        section_embedding_service = SectionEmbeddingService()
        
        # Search for similar sections
        results = section_embedding_service.find_similar_sections(
            query_text=section_data['content'],
            section_type=section_data.get('type'),
            limit=5
        )
        
        # Remove the section itself from results
        results = [r for r in results if not (r['document_id'] == doc_id and r['section_id'] == section_id)]
        
        return render_template('section_comparison.html',
                              document=document,
                              section_id=section_id,
                              section_data=section_data,
                              results=results)
        
    except Exception as e:
        flash(f"Error comparing sections: {str(e)}", 'danger')
        return redirect(url_for('doc_structure.view_structure', id=doc_id))

@doc_structure_bp.route('/api/term_links/<int:document_id>')
def get_term_links_api(document_id):
    """Get term links for a document as JSON."""
    try:
        # Get the document to verify it exists
        document = Document.query.get(document_id)
        if not document:
            return jsonify({'error': 'Document not found'}), 404
        
        # Get term links using the model's class method
        document_term_links = SectionTermLink.get_document_term_links(document_id)
        
        # Calculate some statistics
        total_links = sum(len(links) for links in document_term_links.values())
        sections_with_links = len(document_term_links)
        
        return jsonify({
            'success': True,
            'document_id': document_id,
            'sections_with_links': sections_with_links,
            'total_term_links': total_links,
            'term_links': document_term_links
        })
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving term links for document {document_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500
