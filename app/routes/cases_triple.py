"""
Routes for case management with RDF triple support.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime

from app import db
from app.models.document import Document, PROCESSING_STATUS
from app.models.world import World
from app.models.entity_triple import EntityTriple
from app.services.embedding_service import EmbeddingService
from app.services.entity_triple_service import EntityTripleService

# Create blueprint
cases_triple_bp = Blueprint('cases_triple', __name__, url_prefix='/cases/triple')

# Get services
triple_service = EntityTripleService()
embedding_service = EmbeddingService()

@cases_triple_bp.route('/new', methods=['GET'])
def new_case_triple():
    """Display form to create a new triple-based case."""
    # Get all worlds for the dropdown
    worlds = World.query.all()
    
    return render_template('create_case_triple.html', worlds=worlds)

@cases_triple_bp.route('/new', methods=['POST'])
def create_case_triple():
    """Create a new case using RDF triples approach."""
    source_type = request.form.get('source_type', 'manual')
    
    # Get common form data
    title = request.form.get('title')
    world_id = request.form.get('world_id', type=int)
    source = request.form.get('source', '')
    
    # Validate required fields
    if not title:
        flash('Title is required', 'danger')
        return redirect(url_for('cases_triple.new_case_triple'))
    
    if not world_id:
        flash('World is required', 'danger')
        return redirect(url_for('cases_triple.new_case_triple'))
    
    # Check if world exists
    world = World.query.get(world_id)
    if not world:
        flash(f'World with ID {world_id} not found', 'danger')
        return redirect(url_for('cases_triple.new_case_triple'))
    
    # Handle different source types
    if source_type == 'manual':
        # Get description
        description = request.form.get('description', '')
        
        # Get triple data
        subjects = request.form.getlist('subjects[]')
        predicates = request.form.getlist('predicates[]')
        objects = request.form.getlist('objects[]')
        is_literals = request.form.getlist('is_literals[]')
        
        # Get namespace data
        prefixes = request.form.getlist('prefixes[]')
        uris = request.form.getlist('uris[]')
        
        # Create namespaces dictionary
        namespaces = {}
        for i in range(min(len(prefixes), len(uris))):
            if prefixes[i] and uris[i]:
                namespaces[prefixes[i]] = uris[i]
        
        # Create triples list
        triples = []
        for i in range(min(len(subjects), len(predicates), len(objects), len(is_literals))):
            if subjects[i] and predicates[i] and objects[i]:
                triples.append({
                    "subject": subjects[i],
                    "predicate": predicates[i],
                    "object": objects[i],
                    "is_literal": is_literals[i] == 'true'
                })
        
        # Create document record with metadata
        metadata = {
            "rdf_triples": triples,
            "rdf_namespaces": namespaces,
            "process_entity_triples": True
        }
        
        # Create document
        document = Document(
            title=title,
            content=description,
            document_type='case_study',
            world_id=world_id,
            source=source,
            doc_metadata=metadata,
            processing_status=PROCESSING_STATUS['COMPLETED']
        )
        
        # Add to database
        db.session.add(document)
        db.session.commit()
        
        # Process entity triples
        try:
            for triple in triples:
                # Convert to entity triple
                triple_service.create_triple(
                    entity_type='document',
                    entity_id=document.id,
                    subject=triple['subject'],
                    predicate=triple['predicate'],
                    object_value=triple['object'],
                    is_literal=triple['is_literal'],
                    graph=f"case:{document.id}"
                )
            
            flash('Case created with RDF triples successfully', 'success')
        except Exception as e:
            flash(f'Case created but error processing entity triples: {str(e)}', 'warning')
        
        return redirect(url_for('cases.view_case', id=document.id))
    
    elif source_type == 'file':
        # Check if file is provided
        if 'case_file' not in request.files:
            flash('No file provided', 'danger')
            return redirect(url_for('cases_triple.new_case_triple'))
        
        file = request.files['case_file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('cases_triple.new_case_triple'))
        
        # Check if file type is allowed
        allowed_extensions = {'pdf', 'docx', 'txt', 'html', 'htm'}
        if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            flash(f'File type not allowed. Allowed types: {", ".join(allowed_extensions)}', 'danger')
            return redirect(url_for('cases_triple.new_case_triple'))
        
        # Configure upload folder
        UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Save file
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        # Get file type
        file_type = filename.rsplit('.', 1)[1].lower()
        
        # Create document record
        document = Document(
            title=title,
            document_type='case_study',
            world_id=world_id,
            source=source,
            file_path=file_path,
            file_type=file_type,
            doc_metadata={},
            processing_status=PROCESSING_STATUS['PENDING']
        )
        
        db.session.add(document)
        db.session.commit()
        
        # Process document in background
        embedding_service.process_document(document.id)
        
        flash('Document uploaded and processing started. You will be able to add triples once processing completes.', 'success')
        return redirect(url_for('cases.dummy_edit_triples', id=document.id))
    
    elif source_type == 'url':
        # Get URL
        case_url = request.form.get('case_url')
        if not case_url:
            flash('URL is required', 'danger')
            return redirect(url_for('cases_triple.new_case_triple'))
        
        # Process URL
        try:
            document_id = embedding_service.process_url(
                url=case_url,
                title=title,
                document_type='case_study',
                world_id=world_id
            )
            
            # Update document source
            document = Document.query.get(document_id)
            if document:
                document.source = source or case_url
                db.session.commit()
            
            flash('URL processed successfully. You will be able to add triples once processing completes.', 'success')
            return redirect(url_for('cases.dummy_edit_triples', id=document_id))
        except Exception as e:
            flash(f'Error processing URL: {str(e)}', 'danger')
            return redirect(url_for('cases_triple.new_case_triple'))
    
    # If we get here, the source type is not valid
    flash(f'Invalid source type: {source_type}', 'danger')
    return redirect(url_for('cases_triple.new_case_triple'))

@cases_triple_bp.route('/<int:id>/edit', methods=['GET'])
def edit_triples(id):
    """Display page to edit triples for an existing case."""
    # Get document
    document = Document.query.get_or_404(id)
    
    # Get world
    world = World.query.get(document.world_id) if document.world_id else None
    
    # Get existing triples
    existing_triples = []
    triples_from_doc = document.doc_metadata.get('rdf_triples', []) if document.doc_metadata else []
    namespaces_from_doc = document.doc_metadata.get('rdf_namespaces', {}) if document.doc_metadata else {}
    
    # Get entity triples from database
    entity_triples = EntityTriple.query.filter_by(
        entity_type='document',
        entity_id=document.id
    ).all()
    
    # Convert entity triples to format needed by template
    for triple in entity_triples:
        existing_triples.append({
            'subject': triple.subject,
            'predicate': triple.predicate,
            'object': triple.object_literal if triple.is_literal else triple.object_uri,
            'is_literal': triple.is_literal
        })
    
    # If no entity triples but doc_metadata has triples, use those
    if not existing_triples and triples_from_doc:
        existing_triples = triples_from_doc
    
    # Get all possible worlds for dropdown
    worlds = World.query.all()
    
    return render_template(
        'edit_case_triples.html',
        document=document,
        world=world,
        worlds=worlds,
        existing_triples=existing_triples,
        existing_namespaces=namespaces_from_doc
    )

@cases_triple_bp.route('/<int:id>/edit', methods=['POST'])
def update_triples(id):
    """Update triples for an existing case."""
    # Get document
    document = Document.query.get_or_404(id)
    
    # Get triple data
    subjects = request.form.getlist('subjects[]')
    predicates = request.form.getlist('predicates[]')
    objects = request.form.getlist('objects[]')
    is_literals = request.form.getlist('is_literals[]')
    
    # Get namespace data
    prefixes = request.form.getlist('prefixes[]')
    uris = request.form.getlist('uris[]')
    
    # Create namespaces dictionary
    namespaces = {}
    for i in range(min(len(prefixes), len(uris))):
        if prefixes[i] and uris[i]:
            namespaces[prefixes[i]] = uris[i]
    
    # Create triples list
    triples = []
    for i in range(min(len(subjects), len(predicates), len(objects), len(is_literals))):
        if subjects[i] and predicates[i] and objects[i]:
            triples.append({
                "subject": subjects[i],
                "predicate": predicates[i],
                "object": objects[i],
                "is_literal": is_literals[i] == 'true'
            })
    
    # Update document metadata
    if not document.doc_metadata:
        document.doc_metadata = {}
    document.doc_metadata['rdf_triples'] = triples
    document.doc_metadata['rdf_namespaces'] = namespaces
    
    # Update document
    db.session.commit()
    
    # Clear existing entity triples
    existing_triples = EntityTriple.query.filter_by(
        entity_type='document',
        entity_id=document.id
    ).delete()
    
    # Create new entity triples
    try:
        for triple in triples:
            # Convert to entity triple
            triple_service.create_triple(
                entity_type='document',
                entity_id=document.id,
                subject=triple['subject'],
                predicate=triple['predicate'],
                object_value=triple['object'],
                is_literal=triple['is_literal'],
                graph=f"case:{document.id}"
            )
        
        flash('Case triples updated successfully', 'success')
    except Exception as e:
        flash(f'Error updating triples: {str(e)}', 'warning')
    
    return redirect(url_for('cases.view_case', id=document.id))

@cases_triple_bp.route('/api/triples/<int:document_id>', methods=['GET'])
def get_triples(document_id):
    """API endpoint to get triples for a document."""
    # Get document
    document = Document.query.get_or_404(document_id)
    
    # Get entity triples from database
    entity_triples = EntityTriple.query.filter_by(
        entity_type='document',
        entity_id=document.id
    ).all()
    
    # Convert to dictionary
    triples = [triple.to_dict() for triple in entity_triples]
    
    # Get namespaces from document metadata
    namespaces = document.doc_metadata.get('rdf_namespaces', {}) if document.doc_metadata else {}
    
    return jsonify({
        'triples': triples,
        'namespaces': namespaces
    })

@cases_triple_bp.route('/api/document-status/<int:document_id>', methods=['GET'])
def check_document_status(document_id):
    """API endpoint to check the processing status of a document."""
    document = Document.query.get_or_404(document_id)
    
    return jsonify({
        'id': document.id,
        'status': document.processing_status,
        'progress': document.processing_progress or 0,
        'phase': document.processing_phase,
        'has_content': bool(document.content),
        'title': document.title
    })

@cases_triple_bp.route('/api/update-title/<int:id>', methods=['POST'])
def update_document_title(id):
    """API endpoint to update a document's title."""
    # Get document
    document = Document.query.get_or_404(id)
    
    # Get new title from request data
    data = request.json
    new_title = data.get('title')
    
    # Validate title
    if not new_title or not new_title.strip():
        return jsonify({'error': 'Title cannot be empty'}), 400
    
    # Update document title
    document.title = new_title.strip()
    
    # Save changes
    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'id': document.id,
            'title': document.title
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
