"""
Routes for document structure visualization.
"""

import os
import sys
import json
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify
from app.models.document import Document

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
    
    return render_template('document_structure.html', 
                          document=document,
                          has_structure=has_structure,
                          document_uri=document_uri,
                          structure_triples=structure_triples,
                          section_metadata=section_metadata)
