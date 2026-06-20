"""Section embeddings and similarity search, all built on SectionEmbeddingService. generate_embeddings populates section embeddings; search_similar_sections is the cross-document search form/results; compare_sections finds sections similar to a given section.."""
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
from app.services.embedding.section_embedding_service import SectionEmbeddingService
from app.services.guideline_section_service import GuidelineSectionService 
from app.services.case_processing.pipeline_steps.document_structure_annotation_step import DocumentStructureAnnotationStep
from app.services.structure_triple_formatter import StructureTripleFormatter
from datetime import datetime
from app import db

# Import the section triple association service
from app.services.ttl_triple_association.section_triple_association_service import SectionTripleAssociationService
from app.services.ttl_triple_association.section_triple_association_storage import SectionTripleAssociationStorage

logger = logging.getLogger(__name__)


def register_embedding_routes(bp):
    @bp.route('/generate_embeddings/<int:id>', methods=['POST'])
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
    @bp.route('/search_similar', methods=['GET', 'POST'])
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
    @bp.route('/compare_sections/<int:doc_id>/<section_id>', methods=['GET'])
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
