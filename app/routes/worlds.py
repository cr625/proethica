from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
import json
import ast
import re
from datetime import datetime
import os
import logging
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
from app.models.entity_triple import EntityTriple

# Set up logger
logger = logging.getLogger(__name__)

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
                if related_guideline.guideline_metadata and 'concepts_selected' in related_guideline.guideline_metadata:
                    concept_count = related_guideline.guideline_metadata['concepts_selected']
                
                # Extract concepts from triples to display in the UI
                concepts = []
                # Group triples by subject to form concept objects
                subject_groups = {}
                for triple in triples:
                    if triple.subject not in subject_groups:
                        subject_groups[triple.subject] = {
                            'subject': triple.subject,
                            'subject_label': triple.subject_label or triple.subject.split('/')[-1],
                            'description': None,
                            'type_label': None
                        }
                    
                    # Check for rdf:type predicates to get concept type
                    if triple.predicate.endswith('#type') or triple.predicate.endswith('/type'):
                        subject_groups[triple.subject]['type_label'] = triple.object_label or (triple.object_uri and triple.object_uri.split('/')[-1]) or "Concept"
                    
                    # Check for description predicates
                    if triple.predicate.endswith('#comment') or triple.predicate.endswith('/comment') or 'description' in triple.predicate or 'definition' in triple.predicate:
                        subject_groups[triple.subject]['description'] = triple.object_literal or triple.object_uri
                
                # Convert grouped data to list of concepts
                concepts = list(subject_groups.values())
                logger.info(f"Extracted {len(concepts)} concepts from {triple_count} triples for display")
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(f'Error retrieving guideline data: {str(e)}')
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

@worlds_bp.route('/<int:world_id>/guidelines/<int:document_id>/generate_triples', methods=['POST'])
def generate_triples_direct(world_id, document_id):
    """Generate triples directly from the guideline view page."""
    from app.routes.worlds_generate_triples import generate_triples_direct as generate_triples_impl
    return generate_triples_impl(world_id, document_id)

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
    # Import the direct extraction function
    from app.routes.worlds_direct_concepts import direct_concept_extraction
    
    # Get world object
    world = World.query.get_or_404(id)
    
    # Call the direct extraction function
    return direct_concept_extraction(id, document_id, world, guideline_analysis_service)

@worlds_bp.route('/<int:id>/guidelines/<int:document_id>/extract_concepts', methods=['GET'])
def extract_and_display_concepts(id, document_id):
    """Extract concepts from a guideline using MCP server and display them."""
    try:
        # Import the direct concept extraction function
        from app.routes.worlds_direct_concepts import direct_concept_extraction
        
        world = World.query.get_or_404(id)
        
        logger.info(f"Attempting to extract concepts for world {id}, document {document_id}")
        
        # Call the direct concept extraction function
        return direct_concept_extraction(id, document_id, world, guideline_analysis_service)
        
    except Exception as e:
        logger.exception(f"Error in extract_and_display_concepts for world {id}, document {document_id}: {str(e)}")
        flash(f'Unexpected error extracting concepts: {str(e)}', 'error')
        return redirect(url_for('worlds.world_guidelines', id=id))

@worlds_bp.route('/<int:id>/guidelines/<int:document_id>/analyze_legacy', methods=['POST'])
def analyze_guideline_legacy(id, document_id):
    """Legacy analyze route that uses the direct LLM-based concept extraction."""
    from app.routes.worlds_extract_only import extract_concepts_direct
    
    # Log that legacy route is being used
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Using legacy direct concept extraction for world {id}, document {document_id}")
    
    # Call the direct extraction function
    return extract_concepts_direct(id, document_id)

# Utility function for robust JSON parsing
def robust_json_parse(json_str):
    """Parse JSON with fallback methods for common syntax issues."""
    try:
        # Try standard JSON parsing first
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.info(f"Standard JSON parsing failed, attempting recovery: {str(e)}")
        
        # Debugging: log the problematic JSON string (truncated if large)
        max_log_len = 200  # Only log first 200 chars for debugging
        log_str = json_str[:max_log_len] + "..." if len(json_str) > max_log_len else json_str
        logger.info(f"Problematic JSON string (truncated): {log_str}")
        
        # If JSON has single quotes instead of double quotes, try to fix it
        try:
            if "'" in json_str:
                # Replace single quotes with double quotes, but be careful with nested quotes
                logger.info("Attempting to fix single quotes in JSON")
                # This approach handles single quotes better by first going through ast.literal_eval
                try:
                    python_obj = ast.literal_eval(json_str)
                    return python_obj
                except Exception:
                    # Fallback to simple replacement if ast.literal_eval fails
                    fixed_json = json_str.replace("'", '"')
                    return json.loads(fixed_json)
        except Exception as e:
            logger.info(f"Single quote fix failed: {str(e)}")
            pass
            
        # Try using ast.literal_eval for Python-style dictionaries
        try:
            logger.info("Attempting ast.literal_eval")
            return ast.literal_eval(json_str)
        except Exception as e:
            logger.info(f"ast.literal_eval failed: {str(e)}")
            pass
            
        # Try to fix missing quotes around property names
        try:
            logger.info("Attempting regex fix for property names")
            # Use regex to find and fix common JSON errors
            fixed_json = re.sub(r'(\w+):', r'"\1":', json_str)
            return json.loads(fixed_json)
        except Exception as e:
            logger.info(f"Regex fix failed: {str(e)}")
            pass
            
        # Try handling JavaScript objects with undefined values
        try:
            logger.info("Attempting to fix undefined values")
            fixed_json = json_str.replace('undefined', 'null')
            return json.loads(fixed_json)
        except Exception:
            pass
            
        # If all else fails, raise the original error
        logger.error(f"All JSON parsing recovery methods failed for: {log_str}")
        raise

# Comprehensive error handling for guideline processing
@worlds_bp.route('/<int:world_id>/guidelines/<int:document_id>/error', methods=['GET'])
def guideline_processing_error(world_id, document_id):
    """Display error page for guideline processing problems."""
    try:
        world = World.query.get_or_404(world_id)
        
        from app.models.document import Document
        guideline = Document.query.get_or_404(document_id)
        
        # Check if document belongs to this world
        if guideline.world_id != world.id:
            flash('Document does not belong to this world', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))
        
        # Get error details from query parameters
        error_title = request.args.get('error_title', 'Processing Error')
        error_message = request.args.get('error_message', 'An error occurred while processing the guideline concepts.')
        error_details = request.args.get('error_details', '')
        
        # Log the error for debugging purposes
        logger.error(f"Guideline processing error: {error_title} - {error_message}")
        if error_details:
            logger.debug(f"Error details: {error_details[:500]}..." if len(error_details) > 500 else error_details)
        
        return render_template('guideline_processing_error.html', 
                              world=world, 
                              guideline=guideline,
                              error_title=error_title,
                              error_message=error_message,
                              error_details=error_details)
    except Exception as e:
        # Fallback error handling if the error page itself has an error
        logger.exception(f"Error in error handler: {str(e)}")
        flash(f"An unexpected error occurred: {str(e)}", "error")
        return redirect(url_for('worlds.list_worlds'))

@worlds_bp.route('/<int:world_id>/guidelines/<int:document_id>/generate_triples', methods=['POST'])
def generate_guideline_triples(world_id, document_id):
    """Generate triples from selected concepts but don't save them yet."""
    logger.info(f"Generating triples for document {document_id} in world {world_id}")
    
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
        return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))
    
    try:
        # Get concepts data from the form
        concepts_data = request.form.get('concepts_data', '[]')
        ontology_source = request.form.get('ontology_source', '')
        
        try:
            # Parse the JSON data from the form with our robust parser
            concepts = robust_json_parse(concepts_data)
        except Exception as json_error:
            logger.error(f"Error parsing concepts JSON: {str(json_error)}")
            return redirect(url_for('worlds.guideline_processing_error', 
                                    world_id=world.id, 
                                    document_id=document_id,
                                    error_title='JSON Parsing Error',
                                    error_message='Could not parse the concept data from the form submission.',
                                    error_details=str(json_error)))
        
        if not concepts:
            logger.error("No concepts found in parsed data")
            return redirect(url_for('worlds.guideline_processing_error', 
                                    world_id=world.id, 
                                    document_id=document_id,
                                    error_title='No Concepts Found',
                                    error_message='No concepts were found in the analysis results.'))
        
        # Get only the selected concepts
        selected_concepts = [concepts[i] for i in selected_indices if i < len(concepts)]
        logger.info(f"Generating triples for {len(selected_indices)} selected concepts out of {len(concepts)} total concepts")
        
        # Generate triples for selected concepts
        triples_result = guideline_analysis_service.generate_triples(
            concepts, 
            selected_indices, 
            ontology_source
        )
        
        if "error" in triples_result:
            logger.error(f"Error in triple generation: {triples_result['error']}")
            return redirect(url_for('worlds.guideline_processing_error', 
                                    world_id=world.id, 
                                    document_id=document_id,
                                    error_title='Triple Generation Error',
                                    error_message=triples_result['error']))
        
        # Get the triples for review
        triples = triples_result.get("triples", [])
        if not triples:
            flash('No triples were generated from the selected concepts', 'warning')
            return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))
        
        # Prepare data for the template
        triples_json = json.dumps(triples)
        selected_concepts_json = json.dumps(selected_concepts)
        selected_concept_indices_str = ','.join(str(idx) for idx in selected_indices)
        
        # Render the triples review template
        return render_template('guideline_triples_review.html',
                              world=world,
                              guideline=guideline,
                              triples=triples,
                              triples_json=triples_json,
                              concepts_json=concepts_data,
                              selected_concepts_json=selected_concepts_json,
                              selected_concept_indices=selected_concept_indices_str,
                              world_id=world.id,
                              document_id=document_id,
                              ontology_source=ontology_source)
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error generating triples: {str(e)}\n{error_trace}")
        return redirect(url_for('worlds.guideline_processing_error', 
                               world_id=world.id, 
                               document_id=document_id,
                               error_title='Unexpected Error',
                               error_message=f'Error generating triples: {str(e)}',
                               error_details=error_trace))

@worlds_bp.route('/<int:world_id>/guidelines/<int:document_id>/save_concepts', methods=['POST'])
def save_guideline_concepts(world_id, document_id):
    """Save selected triples from a guideline document to the ontology database."""
    logger.info(f"Saving guideline triples for document {document_id} in world {world_id}")
    
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
        return redirect(url_for('worlds.guideline_processing_error', 
                                world_id=world_id, 
                                document_id=document_id,
                                error_title='No Concepts Selected',
                                error_message='You must select at least one concept to save to the ontology.'))
    
    try:
        # Get concepts data from the form instead of session
        concepts_data = request.form.get('concepts_data', '[]')
        ontology_source = request.form.get('ontology_source', '')
        
        try:
            # Parse the JSON data from the form with our robust parser
            concepts = robust_json_parse(concepts_data)
        except Exception as json_error:
            logger.error(f"Error parsing concepts JSON: {str(json_error)}")
            return redirect(url_for('worlds.guideline_processing_error', 
                                    world_id=world_id, 
                                    document_id=document_id,
                                    error_title='JSON Parsing Error',
                                    error_message='Could not parse the concept data from the form submission.',
                                    error_details=str(json_error)))
        
        if not concepts:
            logger.error("No concepts found in parsed data")
            return redirect(url_for('worlds.guideline_processing_error', 
                                    world_id=world_id, 
                                    document_id=document_id,
                                    error_title='No Concepts Found',
                                    error_message='No concepts were found in the analysis results.'))
        
        logger.info(f"Generating triples for {len(selected_indices)} selected concepts out of {len(concepts)} total concepts")
        
        # At this stage, we're just saving the concepts, not generating or saving triples yet
        # No triples data is needed here
        
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
                guideline_metadata={
                    "document_id": document_id,
                    "analyzed": True,
                    "concepts_extracted": len(concepts),
                    "concepts_selected": len(selected_indices),
                    "triple_count": 0,  # No triples yet
                    "analysis_date": datetime.utcnow().isoformat(),
                "ontology_source": ontology_source
                }
            )
            db.session.add(new_guideline)
            db.session.flush()  # Get the guideline ID
            
            # Create basic entity triples for each selected concept
            # These are minimal triples just to represent the concepts, not the full semantic relationships
            created_triple_count = 0
            namespace = "http://proethica.org/guidelines/"
            
            for idx in selected_indices:
                if idx < len(concepts):
                    concept = concepts[idx]
                    concept_label = concept.get("label", "Unknown Concept")
                    concept_description = concept.get("description", "")
                    concept_type = concept.get("type", "concept")
                    
                    # Create concept URI
                    concept_uri = f"{namespace}{concept_label.lower().replace(' ', '_')}"
                    
                    # Create basic triples for this concept
                    # 1. Type triple
                    type_triple = EntityTriple(
                        subject=concept_uri,
                        subject_label=concept_label,
                        predicate="http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                        predicate_label="is a",
                        object_uri=f"http://proethica.org/ontology/{concept_type}",
                        object_label=concept_type.title(),
                        is_literal=False,
                        entity_type="guideline_concept",
                        entity_id=new_guideline.id,
                        guideline_id=new_guideline.id,
                        world_id=world_id,
                        graph=f"guideline_{new_guideline.id}"
                    )
                    db.session.add(type_triple)
                    created_triple_count += 1
                    
                    # 2. Label triple
                    label_triple = EntityTriple(
                        subject=concept_uri,
                        subject_label=concept_label,
                        predicate="http://www.w3.org/2000/01/rdf-schema#label",
                        predicate_label="label",
                        object_literal=concept_label,
                        object_label=concept_label,
                        is_literal=True,
                        entity_type="guideline_concept",
                        entity_id=new_guideline.id,
                        guideline_id=new_guideline.id,
                        world_id=world_id,
                        graph=f"guideline_{new_guideline.id}"
                    )
                    db.session.add(label_triple)
                    created_triple_count += 1
                    
                    # 3. Description triple if available
                    if concept_description:
                        description_triple = EntityTriple(
                            subject=concept_uri,
                            subject_label=concept_label,
                            predicate="http://purl.org/dc/elements/1.1/description",
                            predicate_label="has description",
                            object_literal=concept_description,
                            object_label=concept_description[:50] + "..." if len(concept_description) > 50 else concept_description,
                            is_literal=True,
                            entity_type="guideline_concept",
                            entity_id=new_guideline.id,
                            guideline_id=new_guideline.id,
                            world_id=world_id,
                            graph=f"guideline_{new_guideline.id}"
                        )
                        db.session.add(description_triple)
                        created_triple_count += 1
            
            # Update document metadata
            guideline.doc_metadata = {
                **(guideline.doc_metadata or {}),
                "analyzed": True,
                "guideline_id": new_guideline.id,
                "concepts_extracted": len(concepts),
                "concepts_selected": len(selected_indices),
                "triples_created": created_triple_count,  # Update with the number of created triples
                "analysis_date": datetime.utcnow().isoformat()
            }
            
            # Also update the guideline_metadata with the triple count
            new_guideline.guideline_metadata = {
                **(new_guideline.guideline_metadata or {}),
                "triple_count": created_triple_count
            }
            
            db.session.commit()
            
            logger.info(f"Successfully saved {len(selected_indices)} concepts for guideline {new_guideline.id}")
            
            # Get the selected concepts for display in the template
            selected_concepts = [concepts[i] for i in selected_indices if i < len(concepts)]
            
            # Convert to JSON for passing to the template
            concepts_json = json.dumps(selected_concepts)
            
            # Render the intermediate page showing saved concepts with a Generate Triples button
            return render_template('guideline_saved_concepts.html',
                                  world=world,
                                  guideline=guideline,
                                  concepts=selected_concepts,
                                  concepts_json=concepts_json,
                                  selected_indices=selected_indices,
                                  concept_count=len(selected_indices),
                                  guideline_id=new_guideline.id,
                                  world_id=world_id,
                                  document_id=document_id,
                                  ontology_source=ontology_source)
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Error saving concepts: {str(e)}\n{error_trace}")
            return redirect(url_for('worlds.guideline_processing_error', 
                                   world_id=world_id, 
                                   document_id=document_id,
                                   error_title='Database Error',
                                   error_message=f'Error saving concepts: {str(e)}',
                                   error_details=error_trace))
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error processing concepts: {str(e)}\n{error_trace}")
        return redirect(url_for('worlds.guideline_processing_error', 
                               world_id=world_id, 
                               document_id=document_id,
                               error_title='Unexpected Error',
                               error_message=f'Error processing concepts: {str(e)}',
                               error_details=error_trace))

@worlds_bp.route('/<int:world_id>/guidelines/<int:document_id>/save_triples', methods=['POST'])
def save_guideline_triples(world_id, document_id):
    """Save the selected RDF triples to the database."""
    logger.info(f"Saving selected RDF triples for guideline document {document_id} in world {world_id}")
    
    world = World.query.get_or_404(world_id)
    
    from app.models.document import Document
    from app.models.guideline import Guideline
    guideline = Document.query.get_or_404(document_id)
    
    # Check if document belongs to this world
    if guideline.world_id != world.id:
        flash('Document does not belong to this world', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    try:
        # Get the selected triple indices from the form
        selected_triple_indices = request.form.getlist('selected_triples')
        
        if not selected_triple_indices:
            flash('No triples selected for saving', 'warning')
            return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))
        
        # Convert to integers
        selected_indices = [int(idx) for idx in selected_triple_indices]
        
        # Get triples data from the form
        triples_data = request.form.get('triples_data', '[]')
        ontology_source = request.form.get('ontology_source', '')
        
        try:
            # First try direct JSON parsing
            try:
                all_triples = json.loads(triples_data)
            except json.JSONDecodeError:
                # Fall back to robust parsing only if needed
                logger.warning("Standard JSON parsing failed, falling back to robust parser")
                all_triples = robust_json_parse(triples_data)
        except Exception as json_error:
            logger.error(f"Error parsing triples JSON: {str(json_error)}")
            return redirect(url_for('worlds.guideline_processing_error', 
                                    world_id=world_id, 
                                    document_id=document_id,
                                    error_title='JSON Parsing Error',
                                    error_message='Could not parse the triple data from the form submission.',
                                    error_details=str(json_error)))
        
        if not all_triples:
            logger.error("No triples found in parsed data")
            return redirect(url_for('worlds.guideline_processing_error', 
                                    world_id=world_id, 
                                    document_id=document_id,
                                    error_title='No Triples Found',
                                    error_message='No triples were found in the data.'))
        
        # Get only the selected triples
        selected_triples = [all_triples[idx] for idx in selected_indices if idx < len(all_triples)]
        
        logger.info(f"Saving {len(selected_triples)} selected triples out of {len(all_triples)} total")
        
        # Get the related guideline record
        guideline_id = None
        if guideline.doc_metadata and 'guideline_id' in guideline.doc_metadata:
            guideline_id = guideline.doc_metadata['guideline_id']
        
        if not guideline_id:
            logger.error("No guideline_id found in document metadata")
            return redirect(url_for('worlds.guideline_processing_error', 
                                    world_id=world_id, 
                                    document_id=document_id,
                                    error_title='Missing Guideline Record',
                                    error_message='The related guideline record was not found. Please extract and save concepts first.'))
        
        guideline_record = Guideline.query.get(guideline_id)
        
        if not guideline_record:
            logger.error(f"Guideline record with ID {guideline_id} not found")
            return redirect(url_for('worlds.guideline_processing_error', 
                                    world_id=world_id, 
                                    document_id=document_id,
                                    error_title='Missing Guideline Record',
                                    error_message=f'The related guideline record with ID {guideline_id} was not found.'))
        
        # Save the selected triples to the database
        saved_triples = []
        
        for triple_data in selected_triples:
            # Check if triple has all required fields
            if not all(key in triple_data for key in ['subject', 'predicate']):
                logger.warning(f"Skipping triple due to missing required fields: {triple_data}")
                continue
            
            # Determine if this is a literal or URI object
            is_literal = triple_data.get('is_literal', False)
            
            if is_literal or 'object_literal' in triple_data:
                object_literal = triple_data.get('object_literal', triple_data.get('object', ''))
                object_uri = None
            else:
                object_literal = None
                object_uri = triple_data.get('object', '')
            
            # Create the triple
            triple = EntityTriple(
                subject=triple_data.get('subject', ''),
                subject_label=triple_data.get('subject_label', ''),
                predicate=triple_data.get('predicate', ''),
                predicate_label=triple_data.get('predicate_label', ''),
                object_literal=object_literal,
                object_uri=object_uri,
                object_label=triple_data.get('object_label', ''),
                is_literal=is_literal,
                entity_type="guideline_concept",
                entity_id=guideline_record.id,
                guideline_id=guideline_record.id,
                world_id=world_id,
                graph=f"guideline_{guideline_record.id}"
            )
            
            db.session.add(triple)
            saved_triples.append(triple_data)
        
        # Update the guideline metadata
        guideline_record.guideline_metadata = {
            **(guideline_record.guideline_metadata or {}),
            "ontology_source": ontology_source,
            "updated_at": datetime.utcnow().isoformat(),
            "triples_saved": len(saved_triples)
        }
        
        # Update document metadata
        guideline.doc_metadata = {
            **(guideline.doc_metadata or {}),
            "guideline_id": guideline_record.id,
            "triples_saved": len(saved_triples),
            "triples_generated": len(all_triples)
        }
        
        # Commit changes
        db.session.commit()
        
        logger.info(f"Successfully saved {len(saved_triples)} triples for guideline {guideline_record.id}")
        
        # Return the success page
        return render_template('guideline_triples_saved.html',
                               world=world,
                               guideline=guideline,
                               saved_triples=saved_triples,
                               triple_count=len(saved_triples),
                               world_id=world_id,
                               document_id=document_id)
        
    except Exception as e:
        db.session.rollback()
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error saving triples: {str(e)}\n{error_trace}")
        return redirect(url_for('worlds.guideline_processing_error', 
                              world_id=world_id, 
                              document_id=document_id,
                              error_title='Unexpected Error',
                              error_message=f'Error saving triples: {str(e)}',
                              error_details=error_trace))

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
