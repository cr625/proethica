"""
Routes for case management, including listing, viewing, and searching cases.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app.models.document import Document
from app.models.world import World
from app.services.embedding_service import EmbeddingService
from app import db
from app.services.entity_triple_service import EntityTripleService

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
            # Extract metadata - ensuring it's a dictionary
            metadata = {}
            if doc.doc_metadata:
                if isinstance(doc.doc_metadata, dict):
                    metadata = doc.doc_metadata
                else:
                    # If it's not a dict (likely a string), initialize as empty dict
                    # and log the issue
                    print(f"Warning: doc_metadata for document {doc.id} is not a dictionary: {type(doc.doc_metadata)}")
            
            # Create case object
            case = {
                'id': doc.id,
                'title': doc.title,
                'description': doc.content[:500] + '...' if doc.content and len(doc.content) > 500 else (doc.content or ''),
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
                # Extract metadata - ensuring it's a dictionary
                metadata = {}
                if document.doc_metadata:
                    if isinstance(document.doc_metadata, dict):
                        metadata = document.doc_metadata
                    else:
                        # If it's not a dict (likely a string), initialize as empty dict
                        # and log the issue
                        print(f"Warning: doc_metadata for document {document.id} is not a dictionary: {type(document.doc_metadata)}")
                
                # Create case object
                case = {
                    'id': document.id,
                    'title': document.title,
                    'description': document.content[:500] + '...' if document.content and len(document.content) > 500 else (document.content or ''),
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
    
    # Extract metadata - ensuring it's a dictionary
    metadata = {}
    if document.doc_metadata:
        if isinstance(document.doc_metadata, dict):
            metadata = document.doc_metadata
        else:
            # If it's not a dict (likely a string), initialize as empty dict
            # and log the issue
            print(f"Warning: doc_metadata for document {document.id} is not a dictionary: {type(document.doc_metadata)}")
    
    # Create case object
    case = {
        'id': document.id,
        'title': document.title,
        'description': document.content or '',
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
    
    # Get entity triples and related cases
    entity_triples = []
    knowledge_graph_connections = {}
    try:
        triple_service = EntityTripleService()
        entity_triples = triple_service.find_triples(entity_type='document', entity_id=document.id)
        
        # Find related cases by triples
        related_cases_data = triple_service.find_related_cases_by_triples(document.id)
        
        # If we have related cases, get their titles and sort by number of shared triples
        if related_cases_data:
            # For each predicate and related case
            for predicate, data in related_cases_data.items():
                for case_info in data['related_cases']:
                    case_id = case_info['entity_id']
                    # Get the document
                    related_doc = Document.query.get(case_id)
                    if related_doc:
                        # Add the title to the case info
                        case_info['title'] = related_doc.title
                
                # Sort related cases by number of shared triples in descending order
                data['related_cases'] = sorted(
                    data['related_cases'], 
                    key=lambda x: len(x['shared_triples']), 
                    reverse=True
                )
            
            # Save the data
            knowledge_graph_connections = related_cases_data
    except Exception as e:
        flash(f"Warning: Could not retrieve entity triples or related cases: {str(e)}", 'warning')
    
    return render_template('case_detail.html', case=case, world=world, 
                          entity_triples=entity_triples, 
                          knowledge_graph_connections=knowledge_graph_connections)

@cases_bp.route('/new', methods=['GET'])
def new_case():
    """Display form to create a new case."""
    # Get all worlds for the dropdown
    worlds = World.query.all()
    
    return render_template('create_case.html', worlds=worlds)

@cases_bp.route('/<int:id>/delete', methods=['POST'])
def delete_case(id):
    """Delete a case by ID."""
    # Try to get the case as a document
    document = Document.query.get_or_404(id)
    
    # Check if it's a case study
    if document.document_type != 'case_study':
        flash('The requested document is not a case study', 'warning')
        return redirect(url_for('cases.list_cases'))
    
    # Get the world ID if applicable
    world_id = document.world_id
    
    # If this is part of a world, remove it from the world's cases list
    if world_id:
        world = World.query.get(world_id)
        if world and world.cases and id in world.cases:
            world.cases.remove(id)
            db.session.add(world)
    
    # Delete any associated entity triples
    try:
        from app.services.entity_triple_service import EntityTripleService
        triple_service = EntityTripleService()
        triple_service.delete_triples_for_entity('document', id)
    except Exception as e:
        flash(f"Warning: Could not delete associated entity triples: {str(e)}", 'warning')
    
    # Delete the document
    db.session.delete(document)
    db.session.commit()
    
    flash(f"Case '{document.title}' deleted successfully", 'success')
    return redirect(url_for('cases.list_cases'))

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
    rdf_metadata = request.form.get('rdf_metadata', '')
    
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
    
    # Initialize metadata
    metadata = {
        'decision': decision,
        'outcome': outcome,
        'ethical_analysis': ethical_analysis
    }
    
    # Process RDF metadata if provided
    if rdf_metadata:
        try:
            import json
            rdf_data = json.loads(rdf_metadata)
            
            # Validate the basic structure
            if 'triples' not in rdf_data:
                rdf_data['triples'] = []
            
            if 'namespaces' not in rdf_data:
                rdf_data['namespaces'] = {}
                
            # Add the RDF data to the metadata
            metadata['rdf_triples'] = rdf_data['triples']
            metadata['rdf_namespaces'] = rdf_data['namespaces']
            
            # Convert to entity triples if possible
            if world_id == 1:  # Engineering world
                from app.services.entity_triple_service import EntityTripleService
                triple_service = EntityTripleService()
                
                try:
                    # Store a reference to process this document's triples later
                    metadata['process_entity_triples'] = True
                except Exception as e:
                    flash(f'Warning: RDF triples could not be converted to entity triples: {str(e)}', 'warning')
        
        except json.JSONDecodeError:
            flash('Warning: RDF metadata is not valid JSON. It will be stored as plain text.', 'warning')
            metadata['rdf_metadata_text'] = rdf_metadata
        except Exception as e:
            flash(f'Warning: Error processing RDF metadata: {str(e)}', 'warning')
            metadata['rdf_metadata_text'] = rdf_metadata
    
    # Create document record
    document = Document(
        title=title,
        content=description,
        document_type='case_study',
        world_id=world_id,
        source=source,
        doc_metadata=metadata
    )
    
    # Add to database
    db.session.add(document)
    db.session.commit()
    
    # Process document for embeddings
    try:
        embedding_service = EmbeddingService()
        embedding_service.process_document(document.id)
        
        # Process entity triples if needed
        if metadata.get('process_entity_triples'):
            try:
                from app.services.entity_triple_service import EntityTripleService
                triple_service = EntityTripleService()
                
                # Get the document with its ID
                doc = Document.query.get(document.id)
                
                # Convert RDF triples to entity triples
                for triple in metadata.get('rdf_triples', []):
                    triple_service.create_triple(
                        entity_type='document',
                        entity_id=document.id,
                        predicate=triple['predicate'],
                        object_value=triple['object'],
                        object_type='uri'
                    )
                
                flash('RDF triples processed successfully', 'success')
            except Exception as e:
                flash(f'Warning: Error processing entity triples: {str(e)}', 'warning')
        
        flash('Case created and processed successfully', 'success')
    except Exception as e:
        flash(f'Case created but error processing embeddings: {str(e)}', 'warning')
    
    return redirect(url_for('cases.view_case', id=document.id))
