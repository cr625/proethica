"""
Routes for document structure visualization and section embeddings.
Uses DocumentSection model with pgvector for section embedding storage and retrieval.
"""

import os
import sys
import json
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request, current_app
from flask_sqlalchemy import SQLAlchemy
from app.models.document import Document
from app.models.document_section import DocumentSection
from app.services.section_embedding_service import SectionEmbeddingService
from app.services.case_processing.pipeline_steps.document_structure_annotation_step import DocumentStructureAnnotationStep
from datetime import datetime
from app import db

# Create blueprint
doc_structure_bp = Blueprint('doc_structure', __name__, url_prefix='/structure')

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
    
    # Now check if section_embeddings exists
    if 'document_structure' in metadata and 'section_embeddings' in metadata['document_structure']:
        has_section_embeddings = True
        section_embeddings_info = metadata['document_structure']['section_embeddings']
        current_app.logger.info(f"Section embeddings info: {section_embeddings_info}")
    else:
        current_app.logger.info("No section_embeddings key found in document_structure")
    
    # Add a timestamp query parameter to prevent browser caching
    no_cache = request.args.get('_', '')
    
    return render_template('document_structure.html', 
                          document=document,
                          has_structure=has_structure,
                          document_uri=document_uri,
                          structure_triples=structure_triples,
                          section_metadata=section_metadata,
                          has_section_embeddings=has_section_embeddings,
                          section_embeddings_info=section_embeddings_info,
                          debug_info=debug_info,
                          no_cache=no_cache)

@doc_structure_bp.route('/generate_embeddings/<int:id>', methods=['POST'])
def generate_embeddings(id):
    """Generate section embeddings for a document."""
    # Get the document
    document = Document.query.get_or_404(id)
    
    try:
        # Initialize section embedding service
        section_embedding_service = SectionEmbeddingService()
        
        # Log that we're starting the embedding generation process
        current_app.logger.info(f"Starting section embedding generation for document {id}")
        
        # Log the document metadata structure
        metadata = document.doc_metadata or {}
        current_app.logger.info(f"Document metadata keys: {list(metadata.keys())}")
        if 'document_structure' in metadata:
            current_app.logger.info(f"Document structure keys: {list(metadata['document_structure'].keys())}")
            if 'sections' in metadata['document_structure']:
                current_app.logger.info(f"Found {len(metadata['document_structure']['sections'])} sections in document_structure")
                
                # Log the first section to understand structure
                first_section_id = list(metadata['document_structure']['sections'].keys())[0] if metadata['document_structure']['sections'] else None
                if first_section_id:
                    current_app.logger.info(f"First section ({first_section_id}) keys: {list(metadata['document_structure']['sections'][first_section_id].keys())}")
        
        if 'sections' in metadata:
            current_app.logger.info(f"Top-level sections found: {list(metadata['sections'].keys())}")
        
        if 'section_embeddings_metadata' in metadata:
            current_app.logger.info(f"Section embeddings metadata contains {len(metadata['section_embeddings_metadata'])} sections")
        
        # Process document sections
        result = section_embedding_service.process_document_sections(document.id)
        
        if result.get('success'):
            flash(f"Successfully generated embeddings for {result.get('sections_embedded')} sections", 'success')
            
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
                    sections_with_embeddings = [s for s in metadata['document_structure']['sections'] 
                                             if 'embedding' in metadata['document_structure']['sections'][s]]
                    
                    current_app.logger.info(f"Found {len(sections_with_embeddings)} sections with embeddings after reload")
                    
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
        flash(f"Error processing section embeddings: {str(e)}", 'danger')
    
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
