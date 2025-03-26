"""
Routes for case management, including listing, viewing, and searching cases.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app.models.document import Document
from app.models.world import World
from app.services.embedding_service import EmbeddingService
from app import db

# Create blueprints
cases_bp = Blueprint('cases', __name__, url_prefix='/cases')

@cases_bp.route('/', methods=['GET'])
def list_cases():
    """Display all cases."""
    # Get world filter from query parameters
    world_id = request.args.get('world_id', type=int)
    
    # Get search query from request parameters
    query = request.args.get('query', '')
    
    # Initialize variables
    cases = []
    error = None
    
    try:
        # Filter cases by world if specified
        if world_id:
            # Get document-based cases for the specified world
            document_cases = Document.query.filter_by(
                world_id=world_id,
                document_type='case_study'
            ).all()
        else:
            # Get all document-based cases
            document_cases = Document.query.filter_by(
                document_type='case_study'
            ).all()
        
        # Convert documents to case format
        for doc in document_cases:
            # Extract metadata
            metadata = doc.doc_metadata or {}
            
            # Create case object
            case = {
                'id': doc.id,
                'title': doc.title,
                'description': doc.content[:500] + '...' if len(doc.content) > 500 else doc.content,
                'decision': metadata.get('decision', ''),
                'outcome': metadata.get('outcome', ''),
                'ethical_analysis': metadata.get('ethical_analysis', ''),
                'source': doc.source,
                'document_id': doc.id,
                'is_document': True
            }
            
            cases.append(case)
    
    except Exception as e:
        error = str(e)
    
    # Get all worlds for the filter dropdown
    worlds = World.query.all()
    
    return render_template(
        'cases.html',
        cases=cases,
        worlds=worlds,
        selected_world_id=world_id,
        query=query,
        error=error
    )

@cases_bp.route('/search', methods=['GET'])
def search_cases():
    """Search for cases based on a query."""
    # Get search query from request parameters
    query = request.args.get('query', '')
    
    # Get world filter from query parameters
    world_id = request.args.get('world_id', type=int)
    
    # Initialize variables
    cases = []
    error = None
    
    if not query:
        return redirect(url_for('cases.list_cases', world_id=world_id))
    
    try:
        # Use the embedding service to search for similar cases
        embedding_service = EmbeddingService()
        
        # Search for similar chunks
        similar_chunks = embedding_service.search_similar_chunks(
            query=query,
            k=10,
            world_id=world_id,
            document_type='case_study'
        )
        
        # Get the full documents for each chunk
        seen_doc_ids = set()
        
        for chunk in similar_chunks:
            # Get the document ID from the chunk
            document_id = chunk.get('document_id')
            
            # Skip if we've already seen this document
            if document_id in seen_doc_ids:
                continue
            
            # Get the document
            document = Document.query.get(document_id)
            if document:
                # Extract metadata
                metadata = document.doc_metadata or {}
                
                # Create case object
                case = {
                    'id': document.id,
                    'title': document.title,
                    'description': document.content[:500] + '...' if len(document.content) > 500 else document.content,
                    'decision': metadata.get('decision', ''),
                    'outcome': metadata.get('outcome', ''),
                    'ethical_analysis': metadata.get('ethical_analysis', ''),
                    'source': document.source,
                    'document_id': document.id,
                    'is_document': True,
                    'similarity_score': 1.0 - chunk.get('distance', 0.0),
                    'matching_chunk': chunk.get('chunk_text', '')
                }
                
                cases.append(case)
                seen_doc_ids.add(document_id)
    
    except Exception as e:
        error = str(e)
    
    # Get all worlds for the filter dropdown
    worlds = World.query.all()
    
    return render_template(
        'cases.html',
        cases=cases,
        worlds=worlds,
        selected_world_id=world_id,
        query=query,
        error=error
    )

@cases_bp.route('/<int:id>', methods=['GET'])
def view_case(id):
    """Display a specific case."""
    # Try to get the case as a document
    document = Document.query.get_or_404(id)
    
    # Check if it's a case study
    if document.document_type != 'case_study':
        flash('The requested document is not a case study', 'warning')
        return redirect(url_for('cases.list_cases'))
    
    # Extract metadata
    metadata = document.doc_metadata or {}
    
    # Create case object
    case = {
        'id': document.id,
        'title': document.title,
        'description': document.content,
        'decision': metadata.get('decision', ''),
        'outcome': metadata.get('outcome', ''),
        'ethical_analysis': metadata.get('ethical_analysis', ''),
        'source': document.source,
        'document_id': document.id,
        'is_document': True,
        'case_number': metadata.get('case_number', ''),
        'year': metadata.get('year', ''),
        'world_id': document.world_id
    }
    
    # Get the world
    world = World.query.get(document.world_id) if document.world_id else None
    
    return render_template('case_detail.html', case=case, world=world)

@cases_bp.route('/new', methods=['GET'])
def new_case():
    """Display form to create a new case."""
    # Get all worlds for the dropdown
    worlds = World.query.all()
    
    return render_template('create_case.html', worlds=worlds)

@cases_bp.route('/new', methods=['POST'])
def create_case():
    """Create a new case."""
    # Get form data
    title = request.form.get('title')
    description = request.form.get('description')
    decision = request.form.get('decision')
    outcome = request.form.get('outcome')
    ethical_analysis = request.form.get('ethical_analysis')
    source = request.form.get('source')
    world_id = request.form.get('world_id', type=int)
    
    # Validate required fields
    if not title:
        flash('Title is required', 'danger')
        return redirect(url_for('cases.new_case'))
    
    if not description:
        flash('Description is required', 'danger')
        return redirect(url_for('cases.new_case'))
    
    # Validate world_id if provided
    if world_id:
        world = World.query.get(world_id)
        if not world:
            flash(f'World with ID {world_id} not found', 'danger')
            return redirect(url_for('cases.new_case'))
    
    # Create document record
    document = Document(
        title=title,
        content=description,
        document_type='case_study',
        world_id=world_id,
        source=source,
        doc_metadata={
            'decision': decision,
            'outcome': outcome,
            'ethical_analysis': ethical_analysis
        }
    )
    
    # Add to database
    db.session.add(document)
    db.session.commit()
    
    # Process document for embeddings
    try:
        embedding_service = EmbeddingService()
        embedding_service.process_document(document.id)
        flash('Case created and processed successfully', 'success')
    except Exception as e:
        flash(f'Case created but error processing embeddings: {str(e)}', 'warning')
    
    return redirect(url_for('cases.view_case', id=document.id))
