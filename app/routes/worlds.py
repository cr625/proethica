from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from app import db
from app.models.world import World
from app.models.scenario import Scenario
from app.models.role import Role
from app.models.condition_type import ConditionType
from app.models.resource_type import ResourceType
from app.services.mcp_client import MCPClient

worlds_bp = Blueprint('worlds', __name__, url_prefix='/worlds')

# Get singleton instance of MCPClient
mcp_client = MCPClient.get_instance()

# API endpoints
@worlds_bp.route('/api', methods=['GET'])
def api_get_worlds():
    """API endpoint to get all worlds."""
    worlds = World.query.all()
    return jsonify({
        'success': True,
        'data': [world.to_dict() for world in worlds]
    })

@worlds_bp.route('/api/<int:id>', methods=['GET'])
def api_get_world(id):
    """API endpoint to get a specific world by ID."""
    world = World.query.get_or_404(id)
    return jsonify({
        'success': True,
        'data': world.to_dict()
    })

# Web routes
@worlds_bp.route('/', methods=['GET'])
def list_worlds():
    """Display all worlds."""
    worlds = World.query.all()
    return render_template('worlds.html', worlds=worlds)

@worlds_bp.route('/new', methods=['GET'])
def new_world():
    """Display form to create a new world."""
    return render_template('create_world.html')

@worlds_bp.route('/', methods=['POST'])
def create_world():
    """Create a new world."""
    # Check if the request is JSON or form data
    if request.is_json:
        data = request.json
    else:
        data = request.form
    
    # Create world
    world = World(
        name=data.get('name', ''),
        description=data.get('description', ''),
        ontology_source=data.get('ontology_source', ''),
        metadata={}
    )
    db.session.add(world)
    db.session.commit()
    
    if request.is_json:
        return jsonify({
            'success': True,
            'message': 'World created successfully',
            'data': world.to_dict()
        }), 201
    else:
        flash('World created successfully', 'success')
        return redirect(url_for('worlds.view_world', id=world.id))

@worlds_bp.route('/<int:id>', methods=['GET'])
def view_world(id):
    """Display a specific world."""
    world = World.query.get_or_404(id)
    
    # Get world entities from MCP client if ontology source is specified
    entities = {"entities": {}}  # Initialize with empty entities structure
    if world.ontology_source:
        try:
            result = mcp_client.get_world_entities(world.ontology_source)
            # Check if result already has an 'entities' key
            if 'entities' in result:
                entities = result
            else:
                # If not, wrap it in an 'entities' key
                entities = {"entities": result}
        except Exception as e:
            entities = {"error": str(e)}
            print(f"Error retrieving world entities: {str(e)}")
    
    return render_template('world_detail.html', world=world, entities=entities)

@worlds_bp.route('/<int:id>/edit', methods=['GET'])
def edit_world(id):
    """Display form to edit an existing world."""
    world = World.query.get_or_404(id)
    return render_template('edit_world.html', world=world)

@worlds_bp.route('/<int:id>/edit', methods=['POST'])
def update_world_form(id):
    """Update an existing world from form data."""
    world = World.query.get_or_404(id)
    
    # Update world fields
    world.name = request.form.get('name', '')
    world.description = request.form.get('description', '')
    world.ontology_source = request.form.get('ontology_source', '')
    
    # Handle guidelines file upload
    if 'guidelines_file' in request.files:
        file = request.files['guidelines_file']
        if file and file.filename:
            # Check if file type is allowed
            if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in {'pdf', 'docx', 'txt', 'html', 'htm'}:
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
                from app.models.document import Document
                document = Document(
                    title=request.form.get('guidelines_title', f"Guidelines for {world.name}"),
                    document_type="guideline",
                    world_id=world.id,
                    file_path=file_path,
                    file_type=file_type,
                    doc_metadata={}  # Initialize with empty metadata
                )
                db.session.add(document)
                db.session.commit()
                
                # Process document in background (in a real application, this would be a Celery task)
                # For now, we'll process it synchronously
                from app.services.embedding_service import EmbeddingService
                try:
                    embedding_service = EmbeddingService()
                    embedding_service.process_document(document.id)
                    flash('Guidelines document processed successfully', 'success')
                except Exception as e:
                    flash(f'Error processing guidelines document: {str(e)}', 'error')
            else:
                flash('File type not allowed. Allowed types: pdf, docx, txt, html, htm', 'error')
    
    # Handle guidelines URL
    guidelines_url = request.form.get('guidelines_url', '').strip()
    if guidelines_url:
        # Create document record for URL
        from app.models.document import Document
        from app.services.embedding_service import EmbeddingService
        
        try:
            # Process the URL using the embedding service
            embedding_service = EmbeddingService()
            document_id = embedding_service.process_url(
                guidelines_url,
                request.form.get('guidelines_title', f"Guidelines URL for {world.name}"),
                "guideline",
                world.id
            )
            flash('Guidelines URL processed successfully', 'success')
        except Exception as e:
            flash(f'Error processing guidelines URL: {str(e)}', 'error')
            
            # Create a Document record for the URL without processing
            document = Document(
                title=request.form.get('guidelines_title', f"Guidelines URL for {world.name}"),
                document_type="guideline",
                world_id=world.id,
                source=guidelines_url,
                file_type="url",
                doc_metadata={}
            )
            db.session.add(document)
            db.session.commit()
    
    # Handle guidelines text
    guidelines_text = request.form.get('guidelines_text', '').strip()
    if guidelines_text:
        # Create document record for text
        from app.models.document import Document
        document = Document(
            title=request.form.get('guidelines_title', f"Guidelines Text for {world.name}"),
            document_type="guideline",
            world_id=world.id,
            content=guidelines_text,
            file_type="txt",
            doc_metadata={}
        )
        db.session.add(document)
        db.session.commit()
        
        # Create chunks and embeddings for the document
        from app.services.embedding_service import EmbeddingService
        try:
            embedding_service = EmbeddingService()
            chunks = embedding_service._split_text(guidelines_text)
            embeddings = embedding_service.embed_documents(chunks)
            embedding_service._store_chunks(document.id, chunks, embeddings)
            flash('Guidelines text processed successfully', 'success')
        except Exception as e:
            flash(f'Error processing guidelines text: {str(e)}', 'error')
    
    db.session.commit()
    
    flash('World updated successfully', 'success')
    return redirect(url_for('worlds.view_world', id=world.id))

@worlds_bp.route('/<int:id>', methods=['PUT'])
def update_world(id):
    """Update an existing world via API."""
    world = World.query.get_or_404(id)
    data = request.json
    
    # Update world fields
    if 'name' in data:
        world.name = data['name']
    if 'description' in data:
        world.description = data['description']
    if 'ontology_source' in data:
        world.ontology_source = data['ontology_source']
    if 'metadata' in data:
        world.world_metadata = data['metadata']
    
    # Handle guidelines if provided
    if 'guidelines' in data:
        guidelines = data['guidelines']
        
        # Process guidelines URL
        if 'url' in guidelines and guidelines['url']:
            from app.models.document import Document
            from app.services.embedding_service import EmbeddingService
            
            try:
                # Process the URL using the embedding service
                embedding_service = EmbeddingService()
                document_id = embedding_service.process_url(
                    guidelines['url'],
                    guidelines.get('title', f"Guidelines URL for {world.name}"),
                    "guideline",
                    world.id
                )
            except Exception as e:
                # Create a Document record for the URL without processing
                document = Document(
                    title=guidelines.get('title', f"Guidelines URL for {world.name}"),
                    document_type="guideline",
                    world_id=world.id,
                    source=guidelines['url'],
                    file_type="url",
                    doc_metadata={}
                )
                db.session.add(document)
        
        # Process guidelines text
        if 'text' in guidelines and guidelines['text']:
            from app.models.document import Document
            document = Document(
                title=guidelines.get('title', f"Guidelines Text for {world.name}"),
                document_type="guideline",
                world_id=world.id,
                content=guidelines['text'],
                file_type="txt",
                doc_metadata={}
            )
            db.session.add(document)
            
            # Create chunks and embeddings for the document
            from app.services.embedding_service import EmbeddingService
            try:
                embedding_service = EmbeddingService()
                chunks = embedding_service._split_text(guidelines['text'])
                embeddings = embedding_service.embed_documents(chunks)
                db.session.flush()  # Get document ID
                embedding_service._store_chunks(document.id, chunks, embeddings)
            except Exception:
                pass  # Ignore embedding errors in API
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'World updated successfully',
        'data': world.to_dict()
    })

@worlds_bp.route('/<int:id>', methods=['DELETE'])
def delete_world(id):
    """Delete a world via API."""
    world = World.query.get_or_404(id)
    
    # Delete associated scenarios first
    for scenario in world.scenarios:
        db.session.delete(scenario)
    
    # Then delete the world
    db.session.delete(world)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'World deleted successfully'
    })

@worlds_bp.route('/<int:id>/delete', methods=['POST'])
def delete_world_confirm(id):
    """Delete a world from web form."""
    world = World.query.get_or_404(id)
    
    # Delete associated scenarios first
    for scenario in world.scenarios:
        db.session.delete(scenario)
    
    # Then delete the world
    db.session.delete(world)
    db.session.commit()
    
    flash('World deleted successfully', 'success')
    return redirect(url_for('worlds.list_worlds'))

# Case management routes
@worlds_bp.route('/<int:id>/cases', methods=['POST'])
def add_case(id):
    """Add a case to a world."""
    world = World.query.get_or_404(id)
    data = request.json
    
    # If no cases field exists in metadata, create it
    if not world.metadata:
        world.metadata = {}
    if 'cases' not in world.metadata:
        world.metadata['cases'] = []
    
    # Create case object
    case = {
        'title': data.get('title', ''),
        'description': data.get('description', ''),
        'decision': data.get('decision', ''),
        'outcome': data.get('outcome', ''),
        'ethical_analysis': data.get('ethical_analysis', ''),
        'date': data.get('date') or datetime.now().strftime('%Y-%m-%d')
    }
    
    # Add to metadata
    world.metadata['cases'].append(case)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Case added successfully',
        'data': case
    })

@worlds_bp.route('/<int:id>/cases/<int:case_id>', methods=['DELETE'])
def delete_case(id, case_id):
    """Delete a case from a world."""
    world = World.query.get_or_404(id)
    
    # Check if cases exist in metadata
    if not world.metadata or 'cases' not in world.metadata:
        return jsonify({
            'success': False,
            'message': 'No cases found for this world'
        }), 404
    
    # Check if case_id is valid
    if case_id < 0 or case_id >= len(world.metadata['cases']):
        return jsonify({
            'success': False,
            'message': f'Case with ID {case_id} not found'
        }), 404
    
    # Remove case
    world.metadata['cases'].pop(case_id)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Case deleted successfully'
    })

# Ruleset management routes
@worlds_bp.route('/<int:id>/rulesets', methods=['POST'])
def add_ruleset(id):
    """Add a ruleset to a world."""
    world = World.query.get_or_404(id)
    data = request.json
    
    # If no rulesets field exists in metadata, create it
    if not world.metadata:
        world.metadata = {}
    if 'rulesets' not in world.metadata:
        world.metadata['rulesets'] = []
    
    # Create ruleset object
    ruleset = {
        'name': data.get('name', ''),
        'description': data.get('description', ''),
        'rules': data.get('rules', [])
    }
    
    # Add to metadata
    world.metadata['rulesets'].append(ruleset)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Ruleset added successfully',
        'data': ruleset
    })

@worlds_bp.route('/<int:id>/rulesets/<int:ruleset_id>', methods=['DELETE'])
def delete_ruleset(id, ruleset_id):
    """Delete a ruleset from a world."""
    world = World.query.get_or_404(id)
    
    # Check if rulesets exist in metadata
    if not world.metadata or 'rulesets' not in world.metadata:
        return jsonify({
            'success': False,
            'message': 'No rulesets found for this world'
        }), 404
    
    # Check if ruleset_id is valid
    if ruleset_id < 0 or ruleset_id >= len(world.metadata['rulesets']):
        return jsonify({
            'success': False,
            'message': f'Ruleset with ID {ruleset_id} not found'
        }), 404
    
    # Remove ruleset
    world.metadata['rulesets'].pop(ruleset_id)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Ruleset deleted successfully'
    })

# Guidelines routes
@worlds_bp.route('/<int:id>/guidelines', methods=['GET'])
def world_guidelines(id):
    """Display guidelines for a world."""
    world = World.query.get_or_404(id)
    
    # Get all guidelines documents for this world
    from app.models.document import Document
    guidelines = Document.query.filter_by(world_id=world.id, document_type="guideline").all()
    
    return render_template('guidelines.html', world=world, guidelines=guidelines)

@worlds_bp.route('/<int:id>/guidelines/<int:document_id>/delete', methods=['POST'])
def delete_guideline(id, document_id):
    """Delete a guideline document."""
    world = World.query.get_or_404(id)
    
    from app.models.document import Document
    document = Document.query.get_or_404(document_id)
    
    # Check if document belongs to this world
    if document.world_id != world.id:
        flash('Document does not belong to this world', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Check if document is a guideline
    if document.document_type != "guideline":
        flash('Document is not a guideline', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Delete the file if it exists
    if document.file_path and os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except Exception as e:
            flash(f'Error deleting file: {str(e)}', 'warning')
    
    # Delete the document
    db.session.delete(document)
    db.session.commit()
    
    flash('Guideline deleted successfully', 'success')
    return redirect(url_for('worlds.world_guidelines', id=world.id))

# References routes
@worlds_bp.route('/<int:id>/references', methods=['GET'])
def world_references(id):
    """Display references for a world."""
    world = World.query.get_or_404(id)
    
    # Get search query from request parameters
    query = request.args.get('query', '')
    
    # Get references
    references = None
    try:
        if query:
            # Search with the provided query
            references_data = mcp_client.search_zotero_items(query, limit=10)
            references = {'results': references_data}
        else:
            # Get references based on world content
            references_data = mcp_client.get_references_for_world(world)
            references = {'results': references_data}
    except Exception as e:
        print(f"Error retrieving references: {str(e)}")
        references = {'results': []}
    
    return render_template('world_references.html', world=world, references=references, query=query)
