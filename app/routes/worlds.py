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
guideline_analysis_service = GuidelineAnalysisService.get_instance()

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
    
    # Analyze guideline
    analysis_result = guideline_analysis_service.analyze_guideline(document_id)
    
    if "error" in analysis_result:
        flash(f'Error analyzing guideline: {analysis_result["error"]}', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Render the review page with extracted concepts
    return render_template('guideline_concepts_review.html', 
                          world=world, 
                          guideline=guideline, 
                          concepts=analysis_result["extracted_concepts"],
                          matched_entities=analysis_result.get("matched_entities", {}))

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
    
    # Get selected concepts
    selected_concept_indices = request.form.getlist('selected_concepts')
    selected_indices = [int(idx) for idx in selected_concept_indices]
    
    # Get analysis result
    analysis_result = guideline_analysis_service.analyze_guideline(document_id)
    
    if "error" in analysis_result or not analysis_result.get("success", False):
        flash(f'Error retrieving guideline analysis: {analysis_result.get("error", "Unknown error")}', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Create triples for selected concepts
    created_triples = guideline_analysis_service.create_triples_for_concepts(
        document_id, 
        analysis_result["extracted_concepts"], 
        selected_indices
    )
    
    # Update document metadata with selected concepts
    guideline.doc_metadata = {
        **(guideline.doc_metadata or {}),
        "analyzed": True,
        "concepts_extracted": len(analysis_result["extracted_concepts"]),
        "concepts_selected": len(selected_indices),
        "triples_created": len(created_triples)
    }
    db.session.commit()
    
    flash(f'Successfully created {len(created_triples)} RDF triples from selected concepts', 'success')
    return redirect(url_for('worlds.world_guidelines', id=world.id))

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
