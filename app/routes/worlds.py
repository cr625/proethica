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
from app.models.ontology import Ontology
from app.services.mcp_client import MCPClient
from app.services.task_queue import BackgroundTaskQueue
from app.services.ontology_entity_service import OntologyEntityService
from app.services.guideline_analysis_service import GuidelineAnalysisService

worlds_bp = Blueprint('worlds', __name__, url_prefix='/worlds')

# Get singleton instances
mcp_client = MCPClient.get_instance()
task_queue = BackgroundTaskQueue.get_instance()
ontology_entity_service = OntologyEntityService.get_instance()
guideline_analysis_service = GuidelineAnalysisService()

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
    # Fetch all available ontologies for the dropdown
    ontologies = Ontology.query.all()
    
    # Check if we have a BFO ontology
    bfo_exists = False
    for ontology in ontologies:
        if "bfo" in ontology.name.lower() or "basic formal ontology" in ontology.name.lower():
            bfo_exists = True
            break
    
    if not bfo_exists and not ontologies:
        # Add a basic BFO ontology if none exists and no other ontologies exist
        try:
            bfo_ontology = Ontology(
                name="Basic Formal Ontology (BFO)",
                description="A small, upper level ontology that is designed for use in supporting information retrieval, analysis and integration in scientific and other domains.",
                domain_id="bfo",
                content="# Basic Formal Ontology placeholder content"
            )
            db.session.add(bfo_ontology)
            db.session.commit()
            ontologies = [bfo_ontology]
        except Exception as e:
            print(f"Error creating BFO ontology: {str(e)}")
            
    return render_template('create_world.html', ontologies=ontologies)

@worlds_bp.route('/', methods=['POST'])
def create_world():
    """Create a new world."""
    # Check if the request is JSON or form data
    if request.is_json:
        data = request.json
    else:
        data = request.form
    
    # Process ontology selection
    ontology_id = data.get('ontology_id')
    ontology_source = data.get('ontology_source', '')
    
    # If ontology_id is 'new', we'll redirect to create a new ontology after world creation
    create_new_ontology = (ontology_id == 'new')
    
    # If ontology_id is provided and not 'new', get the ontology source from it
    if ontology_id and not create_new_ontology and ontology_id != '':
        try:
            ontology = Ontology.query.get(int(ontology_id))
            if ontology:
                ontology_source = ontology.domain_id
        except (ValueError, TypeError):
            # If conversion fails, just use the provided ontology_source
            pass
    
    # Create world with the determined values
    world = World(
        name=data.get('name', ''),
        description=data.get('description', ''),
        ontology_source=ontology_source,
        ontology_id=int(ontology_id) if ontology_id and not create_new_ontology and ontology_id != '' else None,
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
    
    # Get ontology details if available
    ontology = None
    if world.ontology_id:
        ontology = Ontology.query.get(world.ontology_id)
    
        # Get world entities directly from the database
        entities = {"entities": {}}  # Initialize with empty entities structure
        ontology_status = 'current'  # Default status
        
        try:
            # Get entities using our direct service
            entities = ontology_entity_service.get_entities_for_world(world)
            
            # Optionally check ontology status from MCP if we have an ontology source
            if world.ontology_source:
                try:
                    status_result = mcp_client.get_ontology_status(world.ontology_source)
                    ontology_status = status_result.get('status', 'current')
                except Exception as e:
                    print(f"Error checking ontology status: {str(e)}")
            
            # Debug logging
            print(f"Retrieved entities result: {entities.keys() if isinstance(entities, dict) else 'not a dict'}")
            if 'entities' in entities:
                entity_types = entities['entities'].keys() if isinstance(entities['entities'], dict) else 'not a dict'
                print(f"Entity types: {entity_types}")
                
        except Exception as e:
            import traceback
            stack_trace = traceback.format_exc()
            error_message = f"Error retrieving world entities: {str(e)}"
            entities = {"entities": {}, "error": error_message}
            print(error_message)
            print(stack_trace)
    
    # Get all guidelines documents for this world
    from app.models.document import Document
    guidelines = Document.query.filter_by(world_id=world.id, document_type="guideline").all()
    
    # Get all case studies for this world
    case_studies = Document.query.filter_by(world_id=world.id, document_type="case_study").all()
    
    # Fetch all ontologies for the dropdown
    all_ontologies = Ontology.query.all()
    
    return render_template('world_detail.html', world=world, entities=entities, guidelines=guidelines,
                           case_studies=case_studies, ontology_status=ontology_status, 
                           ontology=ontology, all_ontologies=all_ontologies)

@worlds_bp.route('/<int:id>/edit', methods=['GET'])
def edit_world(id):
    """Display form to edit an existing world."""
    world = World.query.get_or_404(id)
    
    # Fetch all available ontologies for the dropdown
    ontologies = Ontology.query.all()
    
    return render_template('edit_world.html', world=world, ontologies=ontologies)

@worlds_bp.route('/<int:id>/edit', methods=['POST'])
def update_world_form(id):
    """Update an existing world from form data."""
    world = World.query.get_or_404(id)
    
    # Update world fields
    world.name = request.form.get('name', '')
    world.description = request.form.get('description', '')
    
    # Process ontology selection
    ontology_id = request.form.get('ontology_id')
    ontology_source = request.form.get('ontology_source', '')
    
    # If ontology_id is 'new', we'll redirect to create a new ontology after saving
    create_new_ontology = (ontology_id == 'new')
    
    # If ontology_id is provided and not 'new', get the ontology source from it
    if ontology_id and not create_new_ontology and ontology_id != '':
        try:
            ontology = Ontology.query.get(int(ontology_id))
            if ontology:
                ontology_source = ontology.domain_id
                world.ontology_id = int(ontology_id)
                world.ontology_source = ontology_source
        except (ValueError, TypeError):
            # If conversion fails, just use the provided ontology_source
            world.ontology_source = ontology_source
    else:
        world.ontology_source = ontology_source
    
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
                from app.models.document import Document, PROCESSING_STATUS
                document = Document(
                    title=request.form.get('guidelines_title', f"Guidelines for {world.name}"),
                    document_type="guideline",
                    world_id=world.id,
                    file_path=file_path,
                    file_type=file_type,
                    doc_metadata={},  # Initialize with empty metadata
                    processing_status=PROCESSING_STATUS['PENDING']
                )
                db.session.add(document)
                db.session.commit()
                
                # Process document asynchronously
                task_queue.process_document_async(document.id)
                flash('Guidelines document uploaded and processing started', 'success')
            else:
                flash('File type not allowed. Allowed types: pdf, docx, txt, html, htm', 'error')
    
    # Handle guidelines URL
    guidelines_url = request.form.get('guidelines_url', '').strip()
    if guidelines_url:
        # Create document record for URL
        from app.models.document import Document, PROCESSING_STATUS
        
        # Create a Document record for the URL
        document = Document(
            title=request.form.get('guidelines_title_url', f"Guidelines URL for {world.name}"),
            document_type="guideline",
            world_id=world.id,
            source=guidelines_url,
            file_type="url",
            doc_metadata={},
            processing_status=PROCESSING_STATUS['PENDING']
        )
        db.session.add(document)
        db.session.commit()
        
        # Process document asynchronously
        task_queue.process_document_async(document.id)
        flash('Guidelines URL uploaded and processing started', 'success')
    
    # Handle guidelines text
    guidelines_text = request.form.get('guidelines_text', '').strip()
    if guidelines_text:
        # Create document record for text
        from app.models.document import Document, PROCESSING_STATUS
        document = Document(
            title=request.form.get('guidelines_title_text', f"Guidelines Text for {world.name}"),
            document_type="guideline",
            world_id=world.id,
            content=guidelines_text,
            file_type="txt",
            doc_metadata={},
            processing_status=PROCESSING_STATUS['PENDING']
        )
        db.session.add(document)
        db.session.commit()
        
        # Process document asynchronously
        task_queue.process_document_async(document.id)
        flash('Guidelines text uploaded and processing started', 'success')
    
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
    
    # Handle ontology reference
    if 'ontology_id' in data:
        try:
            ontology_id = int(data['ontology_id'])
            ontology = Ontology.query.get(ontology_id)
            if ontology:
                world.ontology_id = ontology_id
                world.ontology_source = ontology.domain_id
        except (ValueError, TypeError):
            # If conversion fails, just ignore
            pass
    elif 'ontology_source' in data:
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

@worlds_bp.route('/<int:id>/guidelines/<int:document_id>', methods=['GET'])
def view_guideline(id, document_id):
    """Display a specific guideline document."""
    world = World.query.get_or_404(id)
    
    from app.models.document import Document
    guideline = Document.query.get_or_404(document_id)
    
    # Check if document belongs to this world
    if guideline.world_id != world.id:
        flash('Document does not belong to this world', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Check if document is a guideline
    if guideline.document_type != "guideline":
        flash('Document is not a guideline', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Get associated concepts and triples
    from app.models.entity_triple import EntityTriple
    from app.models.guideline import Guideline
    
    # Initialize variables with default values
    triple_count = 0
    concept_count = 0
    triples = []
    concepts = []
    
    # Try to get related guideline if exists
    related_guideline = None
    if guideline.doc_metadata and 'guideline_id' in guideline.doc_metadata:
        try:
            guideline_id = guideline.doc_metadata['guideline_id']
            related_guideline = Guideline.query.get(guideline_id)
            
            # If related guideline exists, get its triples
            if related_guideline:
                triples = EntityTriple.query.filter_by(
                    guideline_id=related_guideline.id,
                    entity_type="guideline_concept"
                ).all()
                triple_count = len(triples)
                
                # Get concept count from metadata if available
                if related_guideline.metadata and 'concepts_selected' in related_guideline.metadata:
                    concept_count = related_guideline.metadata['concepts_selected']
        except Exception as e:
            import traceback
            traceback.print_exc()
            flash(f'Error retrieving guideline data: {str(e)}', 'warning')
    
    # If no related guideline or metadata available, try to get counts from document metadata
    if triple_count == 0 and guideline.doc_metadata:
        if 'triples_created' in guideline.doc_metadata:
            triple_count = guideline.doc_metadata['triples_created']
        if 'concepts_selected' in guideline.doc_metadata:
            concept_count = guideline.doc_metadata['concepts_selected']
        elif 'concepts_extracted' in guideline.doc_metadata:
            concept_count = guideline.doc_metadata['concepts_extracted']
    
    return render_template('guideline_content.html', 
                          world=world, 
                          guideline=guideline, 
                          triple_count=triple_count, 
                          concept_count=concept_count, 
                          triples=triples, 
                          concepts=concepts)

@worlds_bp.route('/<int:id>/guidelines/add', methods=['GET'])
def add_guideline_form(id):
    """Display form to add a guideline to a world."""
    world = World.query.get_or_404(id)
    
    # Get referrer URL for redirect after submission
    referrer = request.referrer or url_for('worlds.world_guidelines', id=world.id)
    
    return render_template('add_guideline.html', world=world, referrer=referrer)

@worlds_bp.route('/<int:id>/guidelines/add', methods=['POST'])
def add_guideline(id):
    """Process form submission to add a guideline to a world."""
    world = World.query.get_or_404(id)
    
    # Get form data
    title = request.form.get('guidelines_title', f"Guidelines for {world.name}")
    input_type = request.form.get('input_type')
    
    # Import Document model and task queue
    from app.models.document import Document, PROCESSING_STATUS
    from app.services.task_queue import BackgroundTaskQueue
    task_queue = BackgroundTaskQueue.get_instance()
    
    # Process based on input type
    if input_type == 'file' and 'guidelines_file' in request.files:
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
                document = Document(
                    title=title,
                    document_type="guideline",
                    world_id=world.id,
                    file_path=file_path,
                    file_type=file_type,
                    doc_metadata={},
                    processing_status=PROCESSING_STATUS['PENDING']
                )
                db.session.add(document)
                db.session.commit()
                
                # Process document asynchronously
                task_queue.process_document_async(document.id)
                flash('Guidelines document uploaded and processing started', 'success')
            else:
                flash('File type not allowed. Allowed types: pdf, docx, txt, html, htm', 'error')
                return redirect(url_for('worlds.add_guideline_form', id=world.id))
    
    elif input_type == 'url':
        guidelines_url = request.form.get('guidelines_url', '').strip()
        if guidelines_url:
            # Create document record for URL
            document = Document(
                title=title,
                document_type="guideline",
                world_id=world.id,
                source=guidelines_url,
                file_type="url",
                doc_metadata={},
                processing_status=PROCESSING_STATUS['PENDING']
            )
            db.session.add(document)
            db.session.commit()
            
            # Process document asynchronously
            task_queue.process_document_async(document.id)
            flash('Guidelines URL uploaded and processing started', 'success')
        else:
            flash('URL is required', 'error')
            return redirect(url_for('worlds.add_guideline_form', id=world.id))
    
    elif input_type == 'text':
        guidelines_text = request.form.get('guidelines_text', '').strip()
        if guidelines_text:
            # Create document record for text
            document = Document(
                title=title,
                document_type="guideline",
                world_id=world.id,
                content=guidelines_text,
                file_type="txt",
                doc_metadata={},
                processing_status=PROCESSING_STATUS['PENDING']
            )
            db.session.add(document)
            db.session.commit()
            
            # Process document asynchronously
            task_queue.process_document_async(document.id)
            flash('Guidelines text uploaded and processing started', 'success')
        else:
            flash('Text is required', 'error')
            return redirect(url_for('worlds.add_guideline_form', id=world.id))
    
    else:
        flash('No guideline content provided', 'error')
        return redirect(url_for('worlds.add_guideline_form', id=world.id))
    
    # Always redirect to the guidelines page
    return redirect(url_for('worlds.world_guidelines', id=world.id))

@worlds_bp.route('/<int:id>/guidelines/<int:document_id>/analyze', methods=['GET', 'POST'])
def analyze_guideline(id, document_id):
    """Analyze a guideline document and extract ontology concepts."""
    world = World.query.get_or_404(id)
    
    # Import the direct concept extraction and extract-only implementations
    from app.routes.worlds_direct_concepts import direct_concept_extraction
    from app.routes.worlds_extract_only import extract_only_analyze_guideline
    
    try:
        # First try to get the document and content
        from app.models.document import Document
        guideline = Document.query.get_or_404(document_id)
        
        # Check if document belongs to this world
        if guideline.world_id != world.id:
            flash('Document does not belong to this world', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))
        
        # Check if document is a guideline
        if guideline.document_type != "guideline":
            flash('Document is not a guideline', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))
        
        # Get guideline content - prefer content field but fall back to file content
        content = guideline.content
        if not content and guideline.file_path:
            try:
                with open(guideline.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                flash(f'Error reading guideline file: {str(e)}', 'error')
                return redirect(url_for('worlds.world_guidelines', id=world.id))
        
        if not content:
            flash('No content available for analysis', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))
        
        # Get ontology source for this world
        ontology_source = None
        if world.ontology_source:
            ontology_source = world.ontology_source
        elif world.ontology_id:
            ontology = Ontology.query.get(world.ontology_id)
            if ontology:
                ontology_source = ontology.domain_id
        
        # Extract concepts from the guideline content
        concepts_result = guideline_analysis_service.extract_concepts(content, ontology_source)
        
        # Check for various outcomes:
        
        # CASE 1: Extraction failed completely
        if "error" in concepts_result and "concepts" not in concepts_result:
            flash(f'Error analyzing guideline: {concepts_result["error"]}', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))
        
        # CASE 2: MCP extraction succeeded but LLM is unavailable 
        if (concepts_result.get("concepts", []) and 
            ("error" in concepts_result and "LLM client not available" in concepts_result["error"])):
            # Simply show the concepts that were extracted since that part worked
            return direct_concept_extraction(id, document_id, world, guideline_analysis_service)
        
        # CASE 3: No concepts were found
        if not concepts_result.get("concepts", []):
            flash('No concepts were found in this guideline', 'warning')
            return redirect(url_for('worlds.world_guidelines', id=world.id))
        
        # CASE 4: Try the full analysis flow with matching and triple generation
        try:
            # Match concepts to ontology entities
            matched_result = guideline_analysis_service.match_concepts(
                concepts_result.get("concepts", []), 
                ontology_source
            )
            
            # Check if matching failed - if so, just show the concepts
            if "error" in matched_result and "LLM client not available" in matched_result["error"]:
                return direct_concept_extraction(id, document_id, world, guideline_analysis_service)
            
            # Generate preview triples for all concepts
            concepts_list = concepts_result.get("concepts", [])
            preview_indices = list(range(len(concepts_list)))
            preview_triples = []
            triple_count = 0
            
            if preview_indices:
                preview_triples_result = guideline_analysis_service.generate_triples(
                    concepts_list,
                    preview_indices,
                    ontology_source
                )
                
                # Check if triple generation failed - if so, just show the concepts
                if "error" in preview_triples_result and "LLM client not available" in preview_triples_result["error"]:
                    return direct_concept_extraction(id, document_id, world, guideline_analysis_service)
                
                preview_triples = preview_triples_result.get("triples", [])
                triple_count = len(preview_triples)
            
            # Manually limit preview triples to 100 max for display
            limited_preview_triples = preview_triples[:100] if len(preview_triples) > 100 else preview_triples
            
            # Store analysis results in session for the review page
            from flask import session
            session[f'guideline_analysis_{document_id}'] = {
                'concepts': concepts_list,
                'matched_entities': matched_result.get("matches", {}),
                'ontology_source': ontology_source
            }
            
            # Full analysis worked - render the complete review page
            return render_template('guideline_concepts_review.html', 
                                world=world, 
                                guideline=guideline, 
                                concepts=concepts_list,
                                matched_entities=matched_result.get("matches", {}),
                                preview_triples=limited_preview_triples,
                                triple_count=triple_count)
        except Exception as e:
            # If any part of the matching/triples flow fails, just show the concepts
            import traceback
            traceback.print_exc()
            return direct_concept_extraction(id, document_id, world, guideline_analysis_service)
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        # If any exception occurs, try the extract-only implementation as fallback
        try:
            return extract_only_analyze_guideline(id, document_id, world, guideline_analysis_service)
        except Exception as inner_e:
            # If even the fallback fails, show the original error
            flash(f'Error analyzing guideline: {str(e)}', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))

@worlds_bp.route('/<int:world_id>/guidelines/<int:document_id>/save_concepts', methods=['POST'])
def save_guideline_concepts(world_id, document_id):
    """Save selected concepts from a guideline document."""
    world = World.query.get_or_404(world_id)
    
    from app.models.document import Document
    guideline = Document.query.get_or_404(document_id)
    
    # Check if document belongs to this world
    if guideline.world_id != world.id:
        flash('Document does not belong to this world', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Get selected concepts from form
    selected_concept_indices = request.form.getlist('selected_concepts')
    selected_indices = [int(idx) for idx in selected_concept_indices]
    
    if not selected_indices:
        flash('No concepts selected', 'warning')
        return redirect(url_for('worlds.analyze_guideline', id=world_id, document_id=document_id))
    
    try:
        # Get analysis result from session
        from flask import session
        analysis_key = f'guideline_analysis_{document_id}'
        if analysis_key not in session:
            flash('Analysis results not found. Please analyze the guideline again.', 'error')
            return redirect(url_for('worlds.analyze_guideline', id=world_id, document_id=document_id))
        
        analysis_data = session[analysis_key]
        concepts = analysis_data.get('concepts', [])
        ontology_source = analysis_data.get('ontology_source')
        
        if not concepts:
            flash('No concepts found in analysis results', 'error')
            return redirect(url_for('worlds.analyze_guideline', id=world_id, document_id=document_id))
        
        # Generate triples for selected concepts
        triples_result = guideline_analysis_service.generate_triples(
            concepts, 
            selected_indices, 
            ontology_source
        )
        
        if "error" in triples_result:
            flash(f'Error generating triples: {triples_result["error"]}', 'error')
            return redirect(url_for('worlds.analyze_guideline', id=world_id, document_id=document_id))
        
        # Save the guideline model with the triples
        try:
            # Create guideline record
            from app.models.guideline import Guideline
            new_guideline = Guideline(
                world_id=world_id,
                title=guideline.title,
                content=guideline.content,
                source_url=guideline.source,
                file_path=guideline.file_path,
                file_type=guideline.file_type,
                metadata={
                    "document_id": document_id,
                    "analyzed": True,
                    "concepts_extracted": len(concepts),
                    "concepts_selected": len(selected_indices),
                    "triple_count": triples_result.get("triple_count", 0)
                }
            )
            db.session.add(new_guideline)
            db.session.flush()  # Get the guideline ID
            
            # Save triples
            triples_data = triples_result.get("triples", [])
            if triples_data:
                from app.models.entity_triple import EntityTriple
                for triple_data in triples_data:
                    triple = EntityTriple(
                        subject=triple_data["subject"],
                        predicate=triple_data["predicate"],
                        object_literal=triple_data["object"] if isinstance(triple_data["object"], str) else None,
                        object_uri=None if isinstance(triple_data["object"], str) else triple_data["object"],
                        is_literal=isinstance(triple_data["object"], str),
                        subject_label=triple_data.get("subject_label"),
                        predicate_label=triple_data.get("predicate_label"),
                        object_label=triple_data.get("object_label"),
                        graph=f"guideline_{new_guideline.id}",
                        entity_type="guideline_concept",
                        entity_id=new_guideline.id,
                        world_id=world_id,
                        guideline_id=new_guideline.id
                    )
                    db.session.add(triple)
                
            # Update document metadata
            guideline.doc_metadata = {
                **(guideline.doc_metadata or {}),
                "analyzed": True,
                "guideline_id": new_guideline.id,
                "concepts_extracted": len(concepts),
                "concepts_selected": len(selected_indices),
                "triples_created": triples_result.get("triple_count", 0)
            }
            db.session.commit()
            
            # Remove analysis data from session
            session.pop(analysis_key, None)
            
            flash(f'Successfully created {triples_result.get("triple_count", 0)} RDF triples from selected concepts', 'success')
        except Exception as e:
            db.session.rollback()
            import traceback
            traceback.print_exc()
            flash(f'Error saving triples: {str(e)}', 'error')
            return redirect(url_for('worlds.analyze_guideline', id=world_id, document_id=document_id))
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Error processing concepts: {str(e)}', 'error')
        
    return redirect(url_for('worlds.world_guidelines', id=world_id))

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
