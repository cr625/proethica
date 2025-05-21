"""
Routes for document structure visualization and section embeddings.
"""

import os
import sys
import json
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from app.models.document import Document
from app.services.section_embedding_service import SectionEmbeddingService

# Create blueprint
doc_structure_bp = Blueprint('doc_structure', __name__, url_prefix='/structure')

@doc_structure_bp.route('/view/<int:id>', methods=['GET'])
def view_structure(id):
    """View document structure for a specific case."""
    # Get the document
    document = Document.query.get_or_404(id)
    
    # Check if it's a case
    if document.document_type not in ['case', 'case_study']:
        flash('The requested document is not a case', 'warning')
        return redirect(url_for('cases.list_cases'))
    
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
                metadata = {}
    
    # Check if document has structure information
    has_structure = False
    document_uri = None
    structure_triples = None
    section_metadata = None
    
    if 'document_structure' in metadata:
        has_structure = True
        document_uri = metadata['document_structure'].get('document_uri')
        structure_triples = metadata['document_structure'].get('structure_triples')
    
    if 'section_embeddings_metadata' in metadata:
        section_metadata = metadata['section_embeddings_metadata']
    
    # Check for section embeddings
    has_section_embeddings = False
    section_embeddings_info = None
    
    if 'document_structure' in metadata and 'section_embeddings' in metadata['document_structure']:
        has_section_embeddings = True
        section_embeddings_info = metadata['document_structure']['section_embeddings']
    
    return render_template('document_structure.html', 
                          document=document,
                          has_structure=has_structure,
                          document_uri=document_uri,
                          structure_triples=structure_triples,
                          section_metadata=section_metadata,
                          has_section_embeddings=has_section_embeddings,
                          section_embeddings_info=section_embeddings_info)

@doc_structure_bp.route('/generate_embeddings/<int:id>', methods=['POST'])
def generate_embeddings(id):
    """Generate section embeddings for a document."""
    # Get the document
    document = Document.query.get_or_404(id)
    
    try:
        # Initialize section embedding service
        section_embedding_service = SectionEmbeddingService()
        
        # Process document sections
        result = section_embedding_service.process_document_sections(document.id)
        
        if result.get('success'):
            flash(f"Successfully generated embeddings for {result.get('sections_embedded')} sections", 'success')
        else:
            flash(f"Error generating embeddings: {result.get('error')}", 'danger')
    
    except Exception as e:
        flash(f"Error processing section embeddings: {str(e)}", 'danger')
    
    return redirect(url_for('doc_structure.view_structure', id=id))

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
