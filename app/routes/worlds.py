from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.utils.auth_utils import admin_required, data_owner_required
import json
import ast
import re
from datetime import datetime
import os
import logging
from werkzeug.utils import secure_filename
import rdflib
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
from app.services.guideline_concept_integration_service import GuidelineConceptIntegrationService
from app.models.entity_triple import EntityTriple
from app.services.role_property_suggestions import RolePropertySuggestionsService

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
            if isinstance(entities, dict):
                print(f"is_mock value: {entities.get('is_mock', 'not found')}")
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
    
    # Prepare entity types for dynamic tabs
    # Get dynamic entity type configuration from proethica-intermediate ontology
    entity_type_config = _get_dynamic_entity_type_config(world)
    
    # Build dynamic entity tabs - include all tabs from ontology configuration
    entity_tabs = []
    if 'entities' in entities and isinstance(entities['entities'], dict):
        for entity_key, display_name, description in entity_type_config:
            # Get entities for this type, or empty list if none exist
            entity_list = entities['entities'].get(entity_key, [])
            entity_tabs.append({
                'key': entity_key,
                'name': display_name,
                'description': description,
                'count': len(entity_list),
                'entities': entity_list
            })
    
    return render_template('world_detail_dynamic.html', world=world, entities=entities, 
                           entity_tabs=entity_tabs, guidelines=guidelines,
                           case_studies=case_studies, ontology_status=ontology_status, 
                           ontology=ontology, all_ontologies=all_ontologies)

@worlds_bp.route('/<int:id>/edit', methods=['GET'])
@login_required
def edit_world(id):
    """Display form to edit an existing world."""
    world = World.query.get_or_404(id)
    
    # Check if user can edit this world
    if not world.can_edit(current_user):
        flash('You do not have permission to edit this world.', 'error')
        return redirect(url_for('worlds.view_world', id=id))
    
    # Fetch all available ontologies for the dropdown
    ontologies = Ontology.query.all()
    
    return render_template('edit_world.html', world=world, ontologies=ontologies)

@worlds_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
def update_world_form(id):
    """Update an existing world from form data."""
    world = World.query.get_or_404(id)
    
    # Check if user can edit this world
    if not world.can_edit(current_user):
        flash('You do not have permission to edit this world.', 'error')
        return redirect(url_for('worlds.view_world', id=id))
    
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
@login_required
def delete_world(id):
    """Delete a world via API."""
    world = World.query.get_or_404(id)
    
    # Check if user can delete this world
    if not world.can_delete(current_user):
        return jsonify({'error': 'You do not have permission to delete this world'}), 403
    
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
@login_required
def delete_world_confirm(id):
    """Delete a world from web form."""
    world = World.query.get_or_404(id)
    
    # Check if user can delete this world
    if not world.can_delete(current_user):
        flash('You do not have permission to delete this world.', 'error')
        return redirect(url_for('worlds.view_world', id=id))
    
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
    from app.models.ontology import Ontology
    guidelines = Document.query.filter_by(world_id=world.id, document_type="guideline").all()
    
    # Check for derived ontologies for each guideline
    guideline_ontologies = {}
    for guideline in guidelines:
        derived_domain = f"guideline-{guideline.id}-concepts"
        derived_ontology = Ontology.query.filter_by(domain_id=derived_domain).first()
        if derived_ontology:
            guideline_ontologies[guideline.id] = {
                'exists': True,
                'id': derived_ontology.id,
                'name': derived_ontology.name
            }
    
    return render_template('guidelines.html', world=world, guidelines=guidelines, guideline_ontologies=guideline_ontologies)

@worlds_bp.route('/<int:id>/guidelines/<int:document_id>/sections')
def view_guideline_sections(id, document_id):
    """Display extracted sections from a guideline document."""
    logger.info(f"Accessing guideline sections route: world_id={id}, document_id={document_id}")
    
    world = World.query.get_or_404(id)
    
    from app.models.document import Document
    from app.models.guideline_section import GuidelineSection
    
    document = Document.query.get_or_404(document_id)
    logger.info(f"Found document: {document.title}, type: {document.document_type}")
    
    # Check if document belongs to this world
    if document.world_id != world.id:
        flash('Document does not belong to this world', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Check if document is a guideline
    if document.document_type != "guideline":
        flash('Document is not a guideline', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Get the associated guideline ID if exists
    actual_guideline_id = None
    logger.info(f"Document metadata keys: {list(document.doc_metadata.keys()) if document.doc_metadata else 'No metadata'}")
    
    if document.doc_metadata and 'guideline_structure' in document.doc_metadata:
        guideline_structure = document.doc_metadata['guideline_structure']
        logger.info(f"Guideline structure keys: {list(guideline_structure.keys())}")
        actual_guideline_id = guideline_structure.get('guideline_id')
        logger.info(f"Found guideline_id: {actual_guideline_id}")
    else:
        logger.info("No guideline_structure found in metadata")
    
    # Get guideline sections
    sections = []
    if actual_guideline_id:
        sections = GuidelineSection.query.filter_by(guideline_id=actual_guideline_id).order_by(GuidelineSection.section_code).all()
        logger.info(f"Found {len(sections)} sections for guideline_id {actual_guideline_id}")
    else:
        # Fallback: check if there are sections for any guideline
        all_sections = GuidelineSection.query.all()
        logger.info(f"No guideline_id found. Total sections in DB: {len(all_sections)}")
        if all_sections:
            available_guideline_ids = list(set([s.guideline_id for s in all_sections]))
            logger.info(f"Available guideline IDs: {available_guideline_ids}")
            # Use the most recent guideline ID as fallback
            if available_guideline_ids:
                fallback_guideline_id = max(available_guideline_ids)
                logger.info(f"Using fallback guideline_id: {fallback_guideline_id}")
                sections = GuidelineSection.query.filter_by(guideline_id=fallback_guideline_id).order_by(GuidelineSection.section_code).all()
                actual_guideline_id = fallback_guideline_id
    
    # Group sections by category
    sections_by_category = {}
    for section in sections:
        category = section.section_category
        if category not in sections_by_category:
            sections_by_category[category] = []
        sections_by_category[category].append(section)
    
    return render_template('guideline_sections_view.html', 
                         world=world, 
                         document=document,
                         sections=sections,
                         sections_by_category=sections_by_category,
                         guideline_id=actual_guideline_id)

@worlds_bp.route('/<int:id>/guidelines/<int:document_id>/sections/regenerate', methods=['POST'])
@login_required
def regenerate_guideline_sections(id, document_id):
    """Regenerate extracted sections for a guideline document via background processing."""
    world = World.query.get_or_404(id)

    from app.models.document import Document
    document = Document.query.get_or_404(document_id)

    # Validate ownership and type
    if document.world_id != world.id:
        flash('Document does not belong to this world', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    if document.document_type != 'guideline':
        flash('Document is not a guideline', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))

    try:
        from app.services.task_queue import BackgroundTaskQueue
        task_queue = BackgroundTaskQueue.get_instance()
        # Re-run processing which includes guideline structure annotation when content exists
        task_queue.process_document_async(document.id)
        flash('Section regeneration started. This may take a moment; refresh to see results.', 'info')
    except Exception as e:
        logger.error(f"Error starting section regeneration: {e}")
        flash(f'Error starting section regeneration: {str(e)}', 'error')

    return redirect(url_for('worlds.view_guideline_sections', id=world.id, document_id=document.id))

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
                
                # Get concepts from guideline metadata if available
                concepts = []
                if related_guideline.guideline_metadata and 'concepts' in related_guideline.guideline_metadata:
                    concepts = related_guideline.guideline_metadata['concepts']
                    logger.info(f"Retrieved {len(concepts)} concepts from guideline metadata")
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
    
    # Check if concepts have been added to the ontology
    # Use document_id for consistent naming/linking with derived ontologies
    ontology_status = {'ready_to_add': False}
    if related_guideline:
        try:
            ontology_status = GuidelineConceptIntegrationService.check_concepts_added_to_ontology(
                guideline_id=document_id,  # Use document ID that matches the URL
                ontology_domain='engineering-ethics'
            )
        except Exception as e:
            logger.warning(f"Could not check ontology status: {str(e)}")
    
    return render_template('guideline_content.html', 
                          world=world, 
                          guideline=guideline, 
                          triple_count=triple_count, 
                          concept_count=concept_count, 
                          triples=triples, 
                          concepts=concepts,
                          ontology_status=ontology_status)

@worlds_bp.route('/<int:world_id>/guidelines/<int:document_id>/generate_triples', methods=['POST'])
def generate_triples_direct(world_id, document_id):
    """Generate triples directly from the guideline view page."""
    from app.routes.worlds_generate_triples import generate_triples_direct as generate_triples_impl
    return generate_triples_impl(world_id, document_id)

@worlds_bp.route('/<int:world_id>/guidelines/<int:guideline_id>/manage_triples', methods=['GET'])
def manage_guideline_triples(world_id, guideline_id):
    """Display and manage triples for a guideline."""
    world = World.query.get_or_404(world_id)

    from app.models.document import Document
    from app.models.guideline import Guideline
    guideline = Document.query.get_or_404(guideline_id)

    # Cleanup: remove triples pointing to deleted guidelines (orphan records)
    try:
        from sqlalchemy import text as _text
        del_sql = _text(
                        """
                        DELETE FROM entity_triples et
                        WHERE et.entity_type = 'guideline_concept'
                            AND et.guideline_id IS NOT NULL
                            AND NOT EXISTS (
                                SELECT 1 FROM guidelines g WHERE g.id = et.guideline_id
                            )
                        """
        )
        res = db.session.execute(del_sql)
        if res.rowcount and res.rowcount > 0:
            logger.info(f"Cleanup removed {res.rowcount} orphan guideline triples")
        db.session.commit()
    except Exception as _cleanup_err:
        logger.debug(f"Guideline triple cleanup skipped/failed: {_cleanup_err}")
    
    # Check if document belongs to this world
    if guideline.world_id != world.id:
        flash('Document does not belong to this world', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Get the actual guideline ID if this is a Document with guideline metadata
    actual_guideline_id = None
    if guideline.doc_metadata and 'guideline_id' in guideline.doc_metadata:
        actual_guideline_id = guideline.doc_metadata['guideline_id']
    
    # Get all triples for this guideline (with proper world filtering)
    from app.models.entity_triple import EntityTriple
    if actual_guideline_id:
        triples = EntityTriple.query.filter_by(
            guideline_id=actual_guideline_id,
            world_id=world.id
        ).all()
    else:
        triples = EntityTriple.query.filter_by(
            guideline_id=guideline.id,
            world_id=world.id
        ).all()
    
    # Add ontology status to each triple with enhanced categorization
    from app.services.triple_duplicate_detection_service import get_duplicate_detection_service
    duplicate_service = get_duplicate_detection_service()
    
    core_ontology_terms = []      # In actual ontology files
    other_guidelines_terms = []   # From different guidelines
    same_guideline_old_terms = [] # Old runs of same guideline
    orphaned_terms = []          # No clear source
    guideline_specific_terms = [] # New unique terms
    
    # Optional: ignore duplicates sourced from configured guideline IDs (comma-separated env)
    import os
    ignore_ids_env = os.getenv('IGNORE_DUPLICATE_GUIDELINE_IDS', '').strip()
    ignore_guideline_ids = set()
    if ignore_ids_env:
        try:
            ignore_guideline_ids = {int(x) for x in ignore_ids_env.split(',') if x.strip().isdigit()}
        except Exception:
            ignore_guideline_ids = set()

    for triple in triples:
        # Check if this triple exists in ontology or database
        object_value = triple.object_uri if triple.object_uri else triple.object_literal
        
        # Skip triples with no object value
        if object_value is None:
            logger.warning(f"Skipping triple with None object value: {triple.subject} {triple.predicate}")
            continue
            
        duplicate_result = duplicate_service.check_duplicate_with_details(
            triple.subject,
            triple.predicate,
            object_value,
            triple.is_literal,
            exclude_guideline_id=triple.guideline_id
        )

        # Apply ignore filter: if duplicate is only due to an existing triple from an ignored guideline, treat as non-duplicate
        try:
            existing = duplicate_result.get('existing_triple') if isinstance(duplicate_result, dict) else None
            if existing and getattr(existing, 'guideline_id', None) in ignore_guideline_ids:
                duplicate_result['is_duplicate'] = False
                duplicate_result['in_database'] = False
                duplicate_result['details'] = f"Ignoring duplicate from guideline {existing.guideline_id} by config"
                duplicate_result['existing_triple'] = None
        except Exception:
            pass
        
        # Add the duplicate check result to the triple
        triple.ontology_status = duplicate_result

        # Also annotate whether subject/object concepts already exist independently
        try:
            subj_presence = duplicate_service.check_concept_presence(triple.subject)
        except Exception:
            subj_presence = {'in_ontology': False, 'in_database': False}
        try:
            obj_uri = None if triple.is_literal else (triple.object_uri or getattr(triple, 'object', None))
            obj_presence = duplicate_service.check_concept_presence(obj_uri) if obj_uri else {'in_ontology': False, 'in_database': False}
        except Exception:
            obj_presence = {'in_ontology': False, 'in_database': False}
        # Attach lightweight flags for template use
        triple.subject_known = subj_presence
        triple.object_known = obj_presence
        
        # Enhanced categorization logic
        if duplicate_result['in_ontology']:
            # Found in actual ontology files (engineering-ethics.ttl, etc.)
            core_ontology_terms.append(triple)
        elif duplicate_result['in_database'] and duplicate_result['existing_triple']:
            existing_triple = duplicate_result['existing_triple']
            # Check if it's from the same guideline (old run) vs different guideline
            if existing_triple.guideline_id == triple.guideline_id:
                # Same guideline - this is from an old run, probably should be cleaned up
                same_guideline_old_terms.append(triple)
            elif existing_triple.guideline_id and existing_triple.guideline_id != triple.guideline_id:
                # Different guideline - this is a shared concept
                other_guidelines_terms.append(triple)
            else:
                # No clear guideline association - orphaned
                orphaned_terms.append(triple)
        else:
            # No duplicates found - this is a new guideline-specific term
            guideline_specific_terms.append(triple)
    
    # Group triples by predicate type for easier management
    def group_triples_by_predicate(triple_list, prefix=""):
        groups = {}
        for triple in triple_list:
            predicate = triple.predicate_label or triple.predicate
            if predicate not in groups:
                groups[predicate] = {
                    'predicate': predicate,
                    'predicate_uri': triple.predicate,
                    'triples': [],
                    'count': 0
                }
            groups[predicate]['triples'].append(triple)
            groups[predicate]['count'] += 1
        return sorted(groups.values(), key=lambda x: x['count'], reverse=True)
    
    # NEW: Group triples by subject (extracted concept/term) for organized view
    def group_triples_by_subject(triple_list):
        """Group triples by their subject (extracted concept), showing all predicates for each concept."""
        groups = {}
        for triple in triple_list:
            subject_key = triple.subject_label or triple.subject
            if subject_key not in groups:
                groups[subject_key] = {
                    'subject': subject_key,
                    'subject_uri': triple.subject,
                    'triples': [],
                    'predicates': {},  # Track predicates for this subject
                    'count': 0,
                    'concept_type': None,  # Will detect from rdf:type or similar
                    'ontology_relationships': [],  # Semantic relationships from ontology
                    'is_in_ontology': False  # Whether this concept exists in ontology
                }
            
            groups[subject_key]['triples'].append(triple)
            groups[subject_key]['count'] += 1
            
            # Track predicate types for this concept
            predicate = triple.predicate_label or triple.predicate
            if predicate not in groups[subject_key]['predicates']:
                groups[subject_key]['predicates'][predicate] = []
            groups[subject_key]['predicates'][predicate].append(triple)
            
            # Try to detect concept type from rdf:type or proethica-intermediate predicates
            if 'type' in predicate.lower() and not triple.is_literal:
                object_value = triple.object_label or triple.object_uri or str(triple.object_literal)
                if 'Role' in object_value:
                    groups[subject_key]['concept_type'] = 'Role'
                elif 'Principle' in object_value:
                    groups[subject_key]['concept_type'] = 'Principle'
                elif 'Obligation' in object_value:
                    groups[subject_key]['concept_type'] = 'Obligation'
                elif any(t in object_value for t in ['State', 'Resource', 'Action', 'Event', 'Capability', 'Constraint']):
                    for t in ['State', 'Resource', 'Action', 'Event', 'Capability', 'Constraint']:
                        if t in object_value:
                            groups[subject_key]['concept_type'] = t
                            break
        
        # Check for ontology relationships for each concept
        for subject_key, group in groups.items():
            ontology_rels = get_ontology_relationships_for_concept(subject_key, group.get('concept_type'))
            if ontology_rels:
                group['ontology_relationships'] = ontology_rels
                group['is_in_ontology'] = True
        
        # Sort by count (most triples first) and then alphabetically
        return sorted(groups.values(), key=lambda x: (-x['count'], x['subject']))
    
    def get_ontology_relationships_for_concept(concept_label, concept_type):
        """Get semantic relationships from the ontology for a concept that matches an existing entity."""
        # Map common concept labels to ontology entities
        concept_mappings = {
            # Roles
            'engineer role': ':Engineer',
            'professional engineer role': ':Engineer', 
            'structural engineer role': ':StructuralEngineerRole',
            'electrical engineer role': ':ElectricalEngineerRole',
            'mechanical engineer role': ':MechanicalEngineerRole',
            'client representative role': ':ClientRepresentativeRole',
            'project manager role': ':ProjectManagerRole',
            'public official role': ':PublicOfficialRole',
            
            # Principles  
            'public safety principle': ':PublicSafetyPrinciple',
            'professional integrity principle': ':ProfessionalIntegrityPrinciple',
            'competence principle': ':CompetencePrinciple',
            'sustainability principle': ':SustainabilityPrinciple',
            
            # Obligations
            'public welfare obligation': ':PublicWelfareObligation',
            'honest service obligation': ':HonestServiceObligation',
            'continuous learning obligation': ':ContinuousLearningObligation',
            
            # States
            'professional competence state': ':ProfessionalCompetenceState',
            'conflict of interest state': ':ConflictOfInterestState',
            'ethical dilemma state': ':EthicalDilemmaState',
            'compliance state': ':ComplianceState',
            'risk state': ':RiskState'
        }
        
        # Known semantic relationships for key entities from engineering-ethics.ttl
        ontology_relationships = {
            ':Engineer': [
                {'predicate': 'hasObligation', 'objects': ['Public Welfare Obligation', 'Honest Service Obligation', 'Continuous Learning Obligation'], 'source': 'engineering-ethics.ttl:406'},
                {'predicate': 'adheresToPrinciple', 'objects': ['Public Safety Principle', 'Professional Integrity Principle', 'Competence Principle'], 'source': 'engineering-ethics.ttl:407'},
                {'predicate': 'pursuesEnd', 'objects': ['Protect Public Safety, Health, and Welfare', 'Truthful and Objective Public Communication'], 'source': 'engineering-ethics.ttl:408'},
                {'predicate': 'governedByCode', 'objects': ['NSPE Code of Ethics'], 'source': 'engineering-ethics.ttl:409'}
            ],
            ':PublicSafetyPrinciple': [
                {'predicate': 'isAdheredToBy', 'objects': ['Engineer Role'], 'source': 'Inferred from engineering-ethics.ttl:407'},
                {'predicate': 'isPrimaryPrinciple', 'objects': ['true'], 'source': 'NSPE Code Section I.1'},
                {'predicate': 'sourceDocument', 'objects': ['NSPE Code of Ethics Section I.1'], 'source': 'engineering-ethics.ttl:171'}
            ],
            ':PublicWelfareObligation': [
                {'predicate': 'isObligationOf', 'objects': ['Engineer Role'], 'source': 'Inferred from engineering-ethics.ttl:406'},
                {'predicate': 'isPrimaryObligation', 'objects': ['true'], 'source': 'engineering-ethics.ttl:340'},
                {'predicate': 'supersedesOtherDuties', 'objects': ['true'], 'source': 'NSPE Code I.1 fundamental canon'}
            ],
            ':CompetencePrinciple': [
                {'predicate': 'isAdheredToBy', 'objects': ['Engineer Role'], 'source': 'Inferred from engineering-ethics.ttl:407'},
                {'predicate': 'requiresAction', 'objects': ['Continuous Learning Obligation'], 'source': 'Professional competency requirements'},
                {'predicate': 'sourceDocument', 'objects': ['NSPE Code of Ethics Section I.2'], 'source': 'engineering-ethics.ttl:193'}
            ]
        }
        
        # Check if concept matches an ontology entity (case insensitive)
        concept_key = concept_label.lower() if concept_label else ''
        ontology_entity = concept_mappings.get(concept_key)
        
        if ontology_entity and ontology_entity in ontology_relationships:
            return ontology_relationships[ontology_entity]
        
        return []
    
    # Create grouped data for each category (by predicate - original view)
    core_ontology_groups = group_triples_by_predicate(core_ontology_terms)
    other_guidelines_groups = group_triples_by_predicate(other_guidelines_terms)
    same_guideline_old_groups = group_triples_by_predicate(same_guideline_old_terms)
    orphaned_groups = group_triples_by_predicate(orphaned_terms)
    guideline_specific_groups = group_triples_by_predicate(guideline_specific_terms)
    
    # NEW: Create subject-based groupings (by extracted concept/term)
    core_ontology_subjects = group_triples_by_subject(core_ontology_terms)
    other_guidelines_subjects = group_triples_by_subject(other_guidelines_terms)
    same_guideline_old_subjects = group_triples_by_subject(same_guideline_old_terms)
    orphaned_subjects = group_triples_by_subject(orphaned_terms)
    guideline_specific_subjects = group_triples_by_subject(guideline_specific_terms)
    
    # All triples subject-based grouping
    all_subjects = group_triples_by_subject(triples)
    
    # Also create the original combined grouping for backward compatibility
    triple_groups = {}
    for triple in triples:
        predicate = triple.predicate_label or triple.predicate
        if predicate not in triple_groups:
            triple_groups[predicate] = {
                'predicate': predicate,
                'predicate_uri': triple.predicate,
                'triples': [],
                'count': 0
            }
        triple_groups[predicate]['triples'].append(triple)
        triple_groups[predicate]['count'] += 1
    
    # Sort groups by count (descending)
    sorted_groups = sorted(triple_groups.values(), key=lambda x: x['count'], reverse=True)
    
    return render_template('manage_guideline_triples.html',
                          world=world,
                          guideline=guideline,
                          triple_groups=sorted_groups,
                          core_ontology_groups=core_ontology_groups,
                          other_guidelines_groups=other_guidelines_groups,
                          same_guideline_old_groups=same_guideline_old_groups,
                          orphaned_groups=orphaned_groups,
                          guideline_specific_groups=guideline_specific_groups,
                          # NEW: Subject-based groupings (organized by extracted concept/term)
                          all_subjects=all_subjects,
                          core_ontology_subjects=core_ontology_subjects,
                          other_guidelines_subjects=other_guidelines_subjects,
                          same_guideline_old_subjects=same_guideline_old_subjects,
                          orphaned_subjects=orphaned_subjects,
                          guideline_specific_subjects=guideline_specific_subjects,
                          total_triples=len(triples),
                          core_ontology_count=len(core_ontology_terms),
                          other_guidelines_count=len(other_guidelines_terms),
                          same_guideline_old_count=len(same_guideline_old_terms),
                          orphaned_count=len(orphaned_terms),
                          guideline_specific_count=len(guideline_specific_terms))

@worlds_bp.route('/<int:world_id>/guidelines/<int:guideline_id>/delete_triples', methods=['POST'])
def delete_guideline_triples(world_id, guideline_id):
    """Delete selected triples for a guideline."""
    try:
        data = request.get_json()
        triple_ids = data.get('triple_ids', [])
        
        if not triple_ids:
            return jsonify({'success': False, 'message': 'No triples selected'}), 400
        
        # Verify world and guideline
        world = World.query.get_or_404(world_id)
        from app.models.document import Document
        guideline = Document.query.get_or_404(guideline_id)
        
        if guideline.world_id != world.id:
            return jsonify({'success': False, 'message': 'Invalid guideline'}), 403
        
        # Delete the triples
        from app.models.entity_triple import EntityTriple
        deleted_count = 0
        
        for triple_id in triple_ids:
            triple = EntityTriple.query.get(triple_id)
            if triple:
                # Verify the triple belongs to this guideline
                if (triple.guideline_id == guideline_id or 
                    (guideline.doc_metadata and 
                     triple.guideline_id == guideline.doc_metadata.get('guideline_id'))):
                    db.session.delete(triple)
                    deleted_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Successfully deleted {deleted_count} triples',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        logger.error(f"Error deleting triples: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@worlds_bp.route('/<int:id>/guidelines/add', methods=['GET'])
@login_required
def add_guideline_form(id):
    """Display form to add a guideline to a world."""
    world = World.query.get_or_404(id)
    
    # Get referrer URL for redirect after submission
    referrer = request.referrer or url_for('worlds.world_guidelines', id=world.id)
    
    return render_template('add_guideline.html', world=world, referrer=referrer)

@worlds_bp.route('/<int:id>/guidelines/add', methods=['POST'])
@login_required
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
                    processing_status=PROCESSING_STATUS['PENDING'],
                    created_by=current_user.id,
                    data_type='user'
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
                processing_status=PROCESSING_STATUS['PENDING'],
                created_by=current_user.id,
                data_type='user'
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
                processing_status=PROCESSING_STATUS['PENDING'],
                created_by=current_user.id,
                data_type='user'
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
    from app.services.role_property_suggestions import RolePropertySuggestionsService
    
    # Get world object
    world = World.query.get_or_404(id)
    
    # Call the direct extraction function
    return direct_concept_extraction(id, document_id, world, guideline_analysis_service)

@worlds_bp.route('/<int:id>/guidelines/<int:document_id>/match_existing_concepts', methods=['GET'])
def match_existing_concepts(id, document_id):
    """Match guideline concepts to existing engineering-ethics ontology entities."""
    try:
        # Get world and guideline
        world = World.query.get_or_404(id)
        guideline = Document.query.get_or_404(document_id)
        
        # Check if document belongs to this world and is a guideline
        if guideline.world_id != world.id:
            flash('Document does not belong to this world', 'error')
            return redirect(url_for('worlds.view_world', id=world.id))
        
        if guideline.document_type != "guideline":
            flash('Document is not a guideline', 'error') 
            return redirect(url_for('worlds.view_world', id=world.id))
        
        # Get guideline content
        content = guideline.content
        if not content and guideline.file_path:
            try:
                with open(guideline.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                flash(f'Error reading guideline file: {str(e)}', 'error')
                return redirect(url_for('worlds.view_world', id=world.id))
        
        if not content:
            flash('No content available for analysis', 'error')
            return redirect(url_for('worlds.view_world', id=world.id))
        
        # Initialize services
        from app.services.guideline_analysis_service import GuidelineAnalysisService
        from app.services.mcp_client import MCPClient
        
        analysis_service = GuidelineAnalysisService()
        mcp_client = MCPClient.get_instance()
        
        # Step 1: Extract concepts from guideline text
        logger.info(f"Extracting concepts from guideline: {guideline.title}")
        extraction_result = analysis_service.extract_concepts(content, document_id, id)
        
        if 'error' in extraction_result:
            flash(f'Error extracting concepts: {extraction_result["error"]}', 'error')
            return redirect(url_for('worlds.view_world', id=world.id))
        
        extracted_concepts = extraction_result.get('concepts', [])
        logger.info(f"Extracted {len(extracted_concepts)} concepts")
        
        # Step 2: Get existing ontology entities via MCP
        logger.info("Fetching existing ontology entities from MCP server")
        try:
            entities_response = mcp_client.get_ontology_entities('engineering-ethics')
            existing_entities = entities_response.get('entities', []) if entities_response else []
            logger.info(f"Retrieved {len(existing_entities)} existing ontology entities")
        except Exception as e:
            logger.error(f"Error fetching ontology entities: {e}")
            existing_entities = []
        
        # Step 3: Focus on roles and match to existing ontology
        role_concepts = [c for c in extracted_concepts if c.get('type', '').lower() == 'role']
        existing_roles = [e for e in existing_entities if e.get('type', '').lower() == 'role']
        
        # Build lookup for existing roles
        role_lookup = {}
        for role in existing_roles:
            label = role.get('label', '').lower().strip()
            role_lookup[label] = role
            # Also try without " role" suffix
            if label.endswith(' role'):
                role_lookup[label[:-5].strip()] = role
        
        # Match extracted roles to existing ontology
        matched_roles = []
        unmatched_roles = []
        
        for concept in role_concepts:
            concept_label = concept.get('label', '').lower().strip()
            
            # Try exact match
            if concept_label in role_lookup:
                matched_entity = role_lookup[concept_label]
                concept['ontology_match'] = {
                    'found': True,
                    'entity': matched_entity,
                    'match_type': 'exact'
                }
                matched_roles.append(concept)
            # Try without "role" suffix  
            elif concept_label.endswith(' role') and concept_label[:-5].strip() in role_lookup:
                matched_entity = role_lookup[concept_label[:-5].strip()]
                concept['ontology_match'] = {
                    'found': True,
                    'entity': matched_entity,
                    'match_type': 'without_suffix'
                }
                matched_roles.append(concept)
            else:
                concept['ontology_match'] = {'found': False}
                unmatched_roles.append(concept)
        
        logger.info(f"Role matching results: {len(matched_roles)} matched, {len(unmatched_roles)} unmatched")
        
        return render_template('existing_concept_matches.html',
                             world=world,
                             guideline=guideline,
                             matched_roles=matched_roles,
                             unmatched_roles=unmatched_roles,
                             total_roles=len(role_concepts),
                             total_existing_roles=len(existing_roles))
        
    except Exception as e:
        logger.error(f"Error in match_existing_concepts: {str(e)}")
        flash(f'Error matching concepts: {str(e)}', 'error')
        return redirect(url_for('worlds.view_world', id=id))

@worlds_bp.route('/<int:id>/guidelines/<int:document_id>/extract_concepts', methods=['GET'])
def extract_and_display_concepts(id, document_id):
    """Extract concepts from a guideline using MCP server and display them."""
    try:
        # Import the direct concept extraction function
        from app.routes.worlds_direct_concepts import direct_concept_extraction
        # Reset any failed transaction state before starting DB work
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass

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

def _get_dynamic_entity_type_config(world):
    """
    Get dynamic entity type configuration from the proethica-intermediate ontology.
    
    Args:
        world: World model instance
        
    Returns:
        List of tuples (entity_key, display_name, description)
    """
    try:
        # Get the proethica-intermediate ontology from database
        proethica_ontology = Ontology.query.filter_by(domain_id='proethica-intermediate').first()
        if not proethica_ontology:
            logger.warning("proethica-intermediate ontology not found, using fallback config")
            return _get_fallback_entity_type_config()
        
        # Parse the ontology to extract GuidelineConceptTypes
        from rdflib import Graph, Namespace, RDF, RDFS
        proeth_namespace = Namespace("http://proethica.org/ontology/intermediate#")
        
        g = Graph()
        g.parse(data=proethica_ontology.content, format="turtle")
        
        # Extract GuidelineConceptTypes with their labels and descriptions
        concept_types = []
        for concept_type in g.subjects(RDF.type, proeth_namespace.GuidelineConceptType):
            label = next(g.objects(concept_type, RDFS.label), None)
            description = next(g.objects(concept_type, RDFS.comment), None)
            
            if label:
                concept_name = str(label)
                entity_key = concept_name.lower()
                
                # Handle special mappings for legacy compatibility
                if concept_name == "State":
                    entity_key = "state"  # Use "state" instead of legacy "conditions"
                
                # Create friendly descriptions
                desc = str(description) if description else _get_default_description(concept_name)
                
                # Smart pluralization
                display_name = _pluralize(concept_name)
                
                concept_types.append((entity_key, display_name, desc))
        
        # Sort by a preferred order if possible
        preferred_order = ["role", "principle", "obligation", "state", "resource", "action", "event", "capability"]
        def sort_key(item):
            try:
                return preferred_order.index(item[0])
            except ValueError:
                return len(preferred_order)  # Put unknown types at the end
        
        concept_types.sort(key=sort_key)
        
        logger.info(f"Found {len(concept_types)} GuidelineConceptTypes: {[ct[0] for ct in concept_types]}")
        return concept_types
        
    except Exception as e:
        logger.error(f"Error extracting dynamic entity types: {e}")
        return _get_fallback_entity_type_config()

def _get_fallback_entity_type_config():
    """
    Fallback entity type configuration if dynamic extraction fails.
    
    Returns:
        List of tuples (entity_key, display_name, description)
    """
    return [
        ('role', 'Roles', 'Users and their responsibilities'),
        ('principle', 'Principles', 'Fundamental ethical values that guide professional conduct'),
        ('obligation', 'Obligations', 'Professional duties that must be fulfilled'),
        ('state', 'States', 'Conditions that provide context for ethical decision-making'),
        ('resource', 'Resources', 'Physical or informational entities used in ethical scenarios'),
        ('action', 'Actions', 'Intentional activities performed by agents'),
        ('event', 'Events', 'Occurrences or happenings in ethical scenarios'),
        ('capability', 'Capabilities', 'Skills and abilities that can be realized')
    ]

def _pluralize(word):
    """
    Smart pluralization for entity type names.
    
    Args:
        word: Singular word to pluralize
        
    Returns:
        Pluralized word
    """
    # Handle special cases
    pluralization_rules = {
        "Capability": "Capabilities",
        "Activity": "Activities",
        "Entity": "Entities"
    }
    
    if word in pluralization_rules:
        return pluralization_rules[word]
    
    # General rules
    if word.endswith('y') and len(word) > 1 and word[-2] not in 'aeiou':
        return word[:-1] + 'ies'
    elif word.endswith(('s', 'sh', 'ch', 'x', 'z')):
        return word + 'es'
    else:
        return word + 's'

def _get_default_description(concept_name):
    """
    Get default description for a GuidelineConceptType.
    
    Args:
        concept_name: Name of the concept type
        
    Returns:
        Default description string
    """
    descriptions = {
        "Role": "Professional positions with associated responsibilities",
        "Principle": "Fundamental ethical values that guide conduct",
        "Obligation": "Professional duties that must be fulfilled",
        "State": "Conditions that provide context for decision-making",
        "Resource": "Physical or informational entities used in scenarios",
        "Action": "Intentional activities performed by agents",
        "Event": "Occurrences or happenings in scenarios",
        "Capability": "Skills and abilities that can be realized"
    }
    return descriptions.get(concept_name, f"{concept_name} entities")

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
@worlds_bp.route('/<int:world_id>/roles/property_suggestions', methods=['GET'])
def world_role_property_suggestions(world_id):
    """Return aggregated role property suggestions for a world as JSON."""
    try:
        world = World.query.get_or_404(world_id)
        data = RolePropertySuggestionsService.build_for_world(world.id)
        return jsonify(data)
    except Exception as e:
        logger.exception(f"Error building role property suggestions: {e}")
        return jsonify({"error": str(e)}), 500

@worlds_bp.route('/<int:world_id>/roles/backfill_triples', methods=['POST'])
def world_backfill_triples(world_id):
    """Backfill guideline_semantic_triples from cached relationships for this world."""
    try:
        world = World.query.get_or_404(world_id)
        from app.services.role_property_suggestions import RolePropertySuggestionsService
        result = RolePropertySuggestionsService.backfill_triples_from_cache(world.id)
        return jsonify({ 'success': True, **result })
    except Exception as e:
        logger.exception(f"Error backfilling triples: {e}")
        return jsonify({ 'success': False, 'error': str(e) }), 500

@worlds_bp.route('/<int:world_id>/guidelines/<int:document_id>/generate_triples', methods=['POST'])
def generate_guideline_triples(world_id, document_id):
    """Extract ontology terms from guideline text (same as direct extraction button)."""
    logger.info(f"Extracting ontology terms for document {document_id} in world {world_id}")
    
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
        
        # Extract ontology terms directly from guideline text (same as direct extraction)
        logger.info(f"Extracting ontology terms from guideline text (concept-based workflow)")
        
        # Get the actual guideline ID if available
        actual_guideline_id = None
        if guideline.doc_metadata and 'guideline_id' in guideline.doc_metadata:
            actual_guideline_id = guideline.doc_metadata['guideline_id']
        
        # Extract ontology terms from guideline text (same as direct method)
        triples_result = guideline_analysis_service.extract_ontology_terms_from_text(
            guideline_text=guideline.content,
            world_id=world.id,
            guideline_id=actual_guideline_id or guideline.id,
            ontology_source=ontology_source
        )
        
        if "error" in triples_result:
            logger.error(f"Error in ontology term extraction: {triples_result['error']}")
            return redirect(url_for('worlds.guideline_processing_error', 
                                    world_id=world.id, 
                                    document_id=document_id,
                                    error_title='Ontology Term Extraction Error',
                                    error_message=triples_result['error']))
        
        # Get the triples for review
        triples = triples_result.get("triples", [])
        if not triples:
            flash('No ontology terms were extracted from the guideline text', 'warning')
            return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))
        
        # Prepare data for the template
        triples_json = json.dumps(triples)
        # For consistency with template expectations, pass empty concept data
        selected_concepts_json = json.dumps([])
        selected_concept_indices_str = ''
        
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
        # Get concepts data from the form - try different methods
        concepts_data = request.form.get('concepts_data', '[]')
        ontology_source = request.form.get('ontology_source', '')
        
        # Debug logging
        logger.info(f"Received concepts_data length: {len(concepts_data)}")
        logger.info(f"Full concepts_data: {concepts_data}")
        logger.info(f"Selected concept indices: {selected_indices}")
        
        # FIXED: Improved form data validation to avoid unnecessary LLM re-extraction
        # Check if concepts_data is valid JSON or a special cached reference
        parsed_concepts = None
        
        if concepts_data == "cached_in_session":
            # Template is using the new lightweight approach - get from cache
            logger.info("Form indicates concepts are cached, retrieving from session/database")
            parsed_concepts = None  # Will trigger cache lookup below
        else:
            # Try to parse JSON from form data (legacy approach)
            try:
                if concepts_data and concepts_data.strip():
                    parsed_concepts = robust_json_parse(concepts_data)
                    if parsed_concepts and isinstance(parsed_concepts, list) and len(parsed_concepts) > 0:
                        logger.info(f"Successfully parsed {len(parsed_concepts)} concepts from form data")
                        concepts = parsed_concepts
                    else:
                        logger.warning("Form data parsed but contains no valid concepts")
                        parsed_concepts = None
                else:
                    logger.warning("No concepts_data in form submission")
            except Exception as parse_error:
                logger.warning(f"Failed to parse form concepts_data: {parse_error}")
                parsed_concepts = None
        
        # Only re-extract if form data is completely invalid AND we have no cached data
        if parsed_concepts is None:
            # Get fresh data from database to avoid stale cache
            from app import db
            db.session.refresh(guideline)
            
            # Try multiple sources for cached concepts with detailed logging
            cached_concepts = None
            
            # Debug current document state
            logger.info(f"Document {document_id} metadata keys: {list(guideline.doc_metadata.keys()) if guideline.doc_metadata else 'None'}")
            
            # Check document metadata (primary source now)
            if hasattr(guideline, 'doc_metadata') and guideline.doc_metadata:
                if 'extracted_concepts' in guideline.doc_metadata:
                    cached_concepts = guideline.doc_metadata.get('extracted_concepts', [])
                    logger.info(f"Found {len(cached_concepts)} cached concepts in document metadata")
                    # Log timestamp for debugging
                    timestamp = guideline.doc_metadata.get('extraction_timestamp', 'unknown')
                    logger.info(f"Concepts cached at: {timestamp}")
                else:
                    logger.warning("'extracted_concepts' key not found in doc_metadata")
            else:
                logger.warning("No doc_metadata found in guideline")
            
            # Fallback: Check Flask session (though it may be truncated)
            if not cached_concepts:
                session_key = f'concepts_{document_id}'
                if session_key in session:
                    cached_concepts = session.get(session_key, [])
                    logger.info(f"Fallback: Found {len(cached_concepts)} cached concepts in Flask session")
                else:
                    logger.warning(f"No concepts found in session key: {session_key}")
                    logger.info(f"Available session keys: {list(session.keys())}")
            
            if cached_concepts and len(cached_concepts) > 0:
                # Use cached concepts and filter to selected indices
                concepts = [cached_concepts[i] for i in selected_indices if i < len(cached_concepts)]
                logger.info(f"Using {len(concepts)} cached concepts from {len(cached_concepts)} total (avoiding LLM re-extraction)")
            else:
                # Only as last resort, if no cached data exists, inform user instead of re-extracting
                logger.error("No valid form data and no cached concepts - asking user to retry analysis")
                logger.error(f"Debug info - Document metadata: {guideline.doc_metadata}")
                logger.error(f"Debug info - Session keys: {list(session.keys())}")
                return redirect(url_for('worlds.guideline_processing_error', 
                                      world_id=world_id, 
                                      document_id=document_id,
                                      error_title='Concepts Data Lost',
                                      error_message='The extracted concepts were lost during form submission. Please click "Analyze Concepts" again and then "Save Concepts".',
                                      error_details='This can happen if the browser session expires or the form data is corrupted.'))
        
        # concepts variable should already be set by the logic above
            
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
                
                # Check for manual type override
                if concept.get("manually_edited") and concept.get("manual_type_override"):
                    concept_type = concept.get("manual_type_override")
                    # Update the mapping metadata to reflect manual override
                    concept["mapping_source"] = "manual"
                    concept["mapping_justification"] = "Manually corrected by user"
                    concept["type_mapping_confidence"] = 1.0
                    concept["needs_type_review"] = False
                else:
                    concept_type = concept.get("type", "concept")
                
                # Create concept URI
                concept_uri = f"{namespace}{concept_label.lower().replace(' ', '_')}"
                
                # Create basic triples for this concept
                # 1. Type triple (with two-tier type mapping metadata)
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
                    graph=f"guideline_{new_guideline.id}",
                    # Store type mapping metadata from GuidelineAnalysisService
                    original_llm_type=concept.get("original_llm_type"),
                    type_mapping_confidence=concept.get("type_mapping_confidence"),
                    needs_type_review=concept.get("needs_type_review", False),
                    mapping_justification=concept.get("mapping_justification"),
                    # Two-tier concept type storage
                    semantic_label=concept.get("semantic_label", concept.get("category", concept.get("type", ""))),
                    primary_type=concept_type,
                    mapping_source=concept.get("mapping_source", "legacy")
                )
                db.session.add(type_triple)
                created_triple_count += 1
                
                # Persist role classification metadata in description triple metadata for later integration
                role_meta = {}
                if (concept.get("type", "").lower() == "role"):
                    if concept.get("role_classification"):
                        role_meta["role_classification"] = concept.get("role_classification")
                    if concept.get("role_signals"):
                        role_meta["role_signals"] = concept.get("role_signals")
                    if concept.get("suggested_parent_class_uri"):
                        role_meta["suggested_parent_class_uri"] = concept.get("suggested_parent_class_uri")

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
            graph=f"guideline_{new_guideline.id}",
            triple_metadata=role_meta or None
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
        
        # Store the selected concepts in guideline metadata
        selected_concepts_for_storage = []
        for idx in selected_indices:
            if idx < len(concepts):
                concept = concepts[idx]
                selected_concepts_for_storage.append({
                    'label': concept.get('label', 'Unknown Concept'),
                    'type': concept.get('type', 'concept'),
                    'category': concept.get('type', 'concept'),  # Use the basic type (role, principle, etc.)
                    'description': concept.get('description', 'No description available')
                })
        
        # Update the guideline_metadata with concepts and triple count
        new_guideline.guideline_metadata = {
            **(new_guideline.guideline_metadata or {}),
            "triple_count": created_triple_count,
            "concepts": selected_concepts_for_storage,
            "concepts_selected": len(selected_indices)
        }
        
        db.session.commit()
        
        logger.info(f"Successfully saved {len(selected_indices)} concepts for guideline {new_guideline.id}")
        
        # Automatically add concepts to the derived ontology attached to this guideline document
        integration_result = None
        try:
            commit_msg = f"Auto-added {len(selected_indices)} concepts from guideline analysis"
            from app.services.guideline_concept_integration_service import GuidelineConceptIntegrationService
            integration_result = GuidelineConceptIntegrationService.add_concepts_to_ontology(
                concepts=[],  # service will retrieve from DB using document metadata
                guideline_id=document_id,  # use document id; service resolves actual guideline id
                ontology_domain='engineering-ethics',
                commit_message=commit_msg
            )
            if integration_result.get('success'):
                summary = integration_result.get('summary', {})
                added = summary.get('successful_additions', 0)
                skipped = summary.get('skipped_duplicates', 0)
                if added or skipped:
                    flash(f"Derived ontology updated: {added} added, {skipped} skipped as duplicates.", 'success')
                else:
                    flash("No new concepts were added to the derived ontology (all duplicates).", 'info')
            else:
                flash(f"Concepts saved, but ontology integration failed: {integration_result.get('error','unknown error')}", 'warning')
        except Exception as integ_err:
            logger.error(f"Auto-integration error: {integ_err}")
            flash("Concepts saved, but automatic ontology integration encountered an error.", 'warning')
        
        # Prepare selected concepts for display
        selected_concepts = [concepts[i] for i in selected_indices if i < len(concepts)]
        concepts_json = json.dumps(selected_concepts)
        
        # Count any existing semantic relationship triples for this document
        try:
            from app.models.guideline_semantic_triple import GuidelineSemanticTriple
            existing_semantic_triples = GuidelineSemanticTriple.get_by_guideline(document_id, approved_only=False)
            semantic_triple_count = len(existing_semantic_triples)
        except Exception:
            semantic_triple_count = 0

        # Show Saved Concepts page with auto-added status
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
                               ontology_source=ontology_source,
                               auto_added=True,
                               integration_result=integration_result,
                               semantic_triple_count=semantic_triple_count)
        
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
        
        # Check for duplicates before saving
        from app.services.triple_duplicate_detection_service import get_duplicate_detection_service
        duplicate_service = get_duplicate_detection_service()
        
        # Save the selected triples to the database
        saved_triples = []
        skipped_duplicates = []
        
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
                object_value = object_literal
            else:
                object_literal = None
                object_uri = triple_data.get('object', '')
                object_value = object_uri
            
            # Check for duplicates before saving
            duplicate_result = duplicate_service.check_duplicate_with_details(
                triple_data.get('subject', ''),
                triple_data.get('predicate', ''),
                object_value,
                is_literal,
                exclude_guideline_id=guideline_record.id
            )
            
            if duplicate_result['is_duplicate']:
                logger.info(f"Skipping duplicate triple: {duplicate_result['details']}")
                skipped_duplicates.append({
                    'triple': triple_data,
                    'reason': duplicate_result['details']
                })
                continue
            
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
        
        logger.info(f"Successfully saved {len(saved_triples)} triples for guideline {guideline_record.id} (skipped {len(skipped_duplicates)} duplicates)")
        
        # Add flash message with duplicate info
        if skipped_duplicates:
            flash(f'Successfully saved {len(saved_triples)} triples. Skipped {len(skipped_duplicates)} duplicates.', 'success')
        else:
            flash(f'Successfully saved {len(saved_triples)} triples.', 'success')
        
        # Return the success page
        return render_template('guideline_triples_saved.html',
                               world=world,
                               guideline=guideline,
                               saved_triples=saved_triples,
                               skipped_duplicates=skipped_duplicates,
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
@login_required
def delete_guideline(id, document_id):
    """Delete a guideline document and all associated data."""
    world = World.query.get_or_404(id)
    
    from app.models.document import Document
    from app.models.guideline import Guideline
    from app.models.entity_triple import EntityTriple
    
    document = Document.query.get_or_404(document_id)
    
    # Check if document belongs to this world
    if document.world_id != world.id:
        flash('Document does not belong to this world', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Check if document is a guideline
    if document.document_type != "guideline":
        flash('Document is not a guideline', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    # Check if user can delete this document
    if not document.can_delete(current_user):
        flash('You do not have permission to delete this guideline.', 'error')
        return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))
    
    # User option: delete associated derived ontology too
    delete_derived = request.form.get('delete_derived_ontology') in ('on', 'true', '1')
    derived_ontology_id = request.form.get('derived_ontology_id')

    # Get the associated guideline ID if exists
    actual_guideline_id = None
    if document.doc_metadata and 'guideline_id' in document.doc_metadata:
        actual_guideline_id = document.doc_metadata['guideline_id']
        logger.info(f"Deleting document {document_id} with associated guideline {actual_guideline_id}")
    
    # Delete associated data in order (due to foreign key constraints)
    deleted_counts = {
        'triples': 0,
        'guideline': 0
    }
    
    try:
        # Use no_autoflush to prevent premature queries to related tables
        with db.session.no_autoflush:
            # 1. Delete entity triples associated with the guideline
            if actual_guideline_id:
                deleted_counts['triples'] = EntityTriple.query.filter_by(
                    guideline_id=actual_guideline_id
                ).delete(synchronize_session=False)
                logger.info(f"Deleted {deleted_counts['triples']} triples for guideline {actual_guideline_id}")
                
                # 2. Delete the guideline entry
                guideline = Guideline.query.get(actual_guideline_id)
                if guideline:
                    db.session.delete(guideline)
                    deleted_counts['guideline'] = 1
                    logger.info(f"Deleted guideline {actual_guideline_id}")
            
            # Optionally delete derived ontology first to avoid orphan
            if delete_derived and derived_ontology_id:
                try:
                    from app.models.ontology import Ontology
                    derived_ont = Ontology.query.get(int(derived_ontology_id))
                    if derived_ont:
                        logger.info(f"Deleting derived ontology {derived_ontology_id} as requested")
                        db.session.delete(derived_ont)
                except Exception as e:
                    logger.warning(f"Could not delete derived ontology {derived_ontology_id}: {e}")

            # 3. Delete document chunks first (due to NOT NULL constraint on document_id)
            from app.models.document import DocumentChunk
            deleted_chunks = DocumentChunk.query.filter_by(document_id=document.id).delete(synchronize_session=False)
            if deleted_chunks > 0:
                logger.info(f"Deleted {deleted_chunks} document chunks for document {document.id}")
            
            # 4. Delete the file if it exists
            if document.file_path and os.path.exists(document.file_path):
                try:
                    os.remove(document.file_path)
                    logger.info(f"Deleted file {document.file_path}")
                except Exception as e:
                    flash(f'Error deleting file: {str(e)}', 'warning')
            
            # 5. Delete the document
            db.session.delete(document)
        
        # Commit all deletions
        db.session.commit()
        
        # Provide detailed feedback
        if deleted_counts['triples'] > 0:
            flash(f'Guideline deleted successfully along with {deleted_counts["triples"]} associated triples', 'success')
        else:
            flash('Guideline deleted successfully', 'success')
        if delete_derived and derived_ontology_id:
            flash('Derived ontology deleted as well.', 'info')
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting guideline: {str(e)}")
        flash(f'Error deleting guideline: {str(e)}', 'error')
        return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))
    
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

# Scenarios routes
@worlds_bp.route('/<int:id>/scenarios', methods=['GET'])
def world_scenarios(id):
    """Display scenarios for a specific world."""
    world = World.query.get_or_404(id)
    
    # Get scenarios for this world
    scenarios = Scenario.query.filter_by(world_id=world.id).all()
    
    return render_template('world_scenarios.html', world=world, scenarios=scenarios)

@worlds_bp.route('/<int:world_id>/guidelines/<int:document_id>/add_concepts_to_ontology', methods=['POST'])
def add_concepts_to_ontology(world_id, document_id):
    """Add extracted guideline concepts directly to the engineering-ethics ontology."""
    logger.info(f"Adding concepts to ontology for document {document_id} in world {world_id}")
    
    world = World.query.get_or_404(world_id)
    
    from app.models.document import Document
    guideline = Document.query.get_or_404(document_id)
    
    # Check if document belongs to this world
    if guideline.world_id != world.id:
        flash('Document does not belong to this world', 'error')
        return redirect(url_for('worlds.world_guidelines', id=world.id))
    
    try:
        # Get commit message if provided
        commit_message = request.form.get('commit_message', '').strip()
        
        # Get the guideline ID from metadata if available
        actual_guideline_id = None
        if guideline.doc_metadata and 'guideline_id' in guideline.doc_metadata:
            actual_guideline_id = guideline.doc_metadata['guideline_id']
        
        if not actual_guideline_id:
            flash('No guideline concepts found to add to ontology', 'warning')
            return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))
        
        # Use the integration service to add concepts to derived ontology (avoids modifying core .ttl files)
        # Pass document_id for consistent naming/linking - service will handle concept retrieval
        result = GuidelineConceptIntegrationService.add_concepts_to_ontology(
            concepts=[],  # Service will retrieve concepts internally
            guideline_id=document_id,  # Use document ID that matches the URL
            ontology_domain='engineering-ethics',
            commit_message=commit_message or f"Added concepts from guideline analysis"
        )
        
        if result['success']:
            summary = result['summary']
            
            # Create success message based on results
            success_parts = []
            if summary['successful_additions'] > 0:
                success_parts.append(f"{summary['successful_additions']} concepts added")
            if summary['skipped_duplicates'] > 0:
                success_parts.append(f"{summary['skipped_duplicates']} duplicates skipped")
            
            if success_parts:
                flash(f"Ontology updated successfully: {', '.join(success_parts)}", 'success')
            else:
                flash('No new concepts were added (all were duplicates)', 'info')
            
            # Get concepts from result for template
            actual_guideline_id = GuidelineConceptIntegrationService._get_actual_guideline_id(document_id)
            concepts = GuidelineConceptIntegrationService.get_concepts_from_guideline(actual_guideline_id) if actual_guideline_id else []
            
            # Render success template with results
            return render_template('guideline_ontology_success.html',
                                  world=world,
                                  guideline=guideline,
                                  result=result,
                                  concepts=concepts,
                                  world_id=world_id,
                                  document_id=document_id)
        else:
            # Handle errors
            error_message = result.get('error', 'Unknown error occurred')
            errors = result.get('errors', [])
            
            flash(f'Error adding concepts to ontology: {error_message}', 'error')
            
            if errors:
                for error in errors[:5]:  # Show first 5 errors
                    flash(f'Detail: {error}', 'warning')
            
            return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error adding concepts to ontology: {str(e)}\n{error_trace}")
        flash(f'Unexpected error: {str(e)}', 'error')
        return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))


@worlds_bp.route('/<int:id>/guidelines/<int:document_id>/concepts', methods=['DELETE'])
@login_required

def remove_extracted_concepts(id, document_id):
    """Remove extracted concepts from a guideline and associated ontology entries."""
    from flask import jsonify, request
    from app.models.document import Document
    from app.models.guideline import Guideline
    from app.models.ontology import Ontology
    from app.models.ontology_version import OntologyVersion
    from app.models.ontology_import import OntologyImport
    try:
        # Get the world and guideline document
        world = World.query.get_or_404(id)
        guideline = Document.query.get_or_404(document_id)
        # Check if document belongs to this world
        if guideline.world_id != world.id:
            return jsonify({'error': 'Document does not belong to this world'}), 403
        # Check if document is a guideline
        if guideline.document_type != "guideline":
            return jsonify({'error': 'Document is not a guideline'}), 400
        # Check permissions: allow if user can edit the document OR the world OR is admin
        try:
            can_edit_doc = guideline.can_edit(current_user)
        except Exception:
            can_edit_doc = False
        try:
            can_edit_world = world.can_edit(current_user)
        except Exception:
            can_edit_world = False
        is_admin = getattr(current_user, 'is_admin', False)
        if not (can_edit_doc or can_edit_world or is_admin):
            logger.warning(f"Permission denied: user {getattr(current_user, 'id', '?')} remove concepts from guideline {document_id}")
            return jsonify({'error': 'Permission denied'}), 403
        logger.info(f"User {current_user.id} removing extracted concepts from guideline document {document_id}")

        # Determine associated Guideline record (Stage 1 saved concepts)
        associated_guideline_id = None
        if guideline.doc_metadata and 'guideline_id' in guideline.doc_metadata:
            associated_guideline_id = guideline.doc_metadata.get('guideline_id')

        concepts_removed = 0
        triples_removed = 0
        derived_ontology_deleted = False

        # 1) Remove EntityTriples associated with this guideline extraction (both basic + alignment)
        from app.models.entity_triple import EntityTriple
        if associated_guideline_id:
            triples_removed = EntityTriple.query.filter(
                EntityTriple.guideline_id == associated_guideline_id,
                EntityTriple.entity_type == 'guideline_concept'
            ).delete(synchronize_session=False)
        else:
            # Fallback: delete any alignment triples linked directly to this document id
            triples_removed = EntityTriple.query.filter(
                EntityTriple.entity_id == guideline.id,
                EntityTriple.entity_type == 'guideline_concept',
                EntityTriple.world_id == world.id
            ).delete(synchronize_session=False)

        # 2) Remove the Guideline record created during save_concepts, if present
        removed_guideline = 0
        if associated_guideline_id:
            related = Guideline.query.get(associated_guideline_id)
            if related:
                # Count concepts saved in metadata for reporting
                if related.guideline_metadata and 'concepts' in related.guideline_metadata:
                    try:
                        concepts_removed = len(related.guideline_metadata['concepts'])
                    except Exception:
                        concepts_removed = 0
                db.session.delete(related)
                removed_guideline = 1

        # 3) Clean document metadata flags and linkage
        if hasattr(guideline, 'doc_metadata') and isinstance(guideline.doc_metadata, dict):
            for key in [
                'guideline_id', 'analyzed', 'concepts_extracted', 'concepts_selected',
                'triples_created', 'triples_saved', 'triples_generated', 'analysis_date'
            ]:
                guideline.doc_metadata.pop(key, None)
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(guideline, 'doc_metadata')

        # Delete the derived ontology for this document by default to prevent stale conflicts
        # Opt-out is available via either delete_derived_ontology=false or keep_derived_ontology=true
        try:
            raw_delete = request.args.get('delete_derived_ontology')
            raw_keep = request.args.get('keep_derived_ontology')
            if raw_keep is not None and str(raw_keep).lower() in ('1', 'true', 'yes', 'on'):
                delete_derived = False
            elif raw_delete is None:
                # Default behavior: delete derived ontology if flag not provided
                delete_derived = True
            else:
                delete_derived = str(raw_delete).lower() in ('1', 'true', 'yes', 'on')
        except Exception:
            delete_derived = True

        if delete_derived:
            try:
                derived_domain = f"guideline-{document_id}-concepts"
                derived = Ontology.query.filter_by(domain_id=derived_domain).first()
                if derived:
                    OntologyImport.query.filter(
                        db.or_(
                            OntologyImport.importing_ontology_id == derived.id,
                            OntologyImport.imported_ontology_id == derived.id
                        )
                    ).delete(synchronize_session=False)
                    OntologyVersion.query.filter_by(ontology_id=derived.id).delete(synchronize_session=False)
                    db.session.delete(derived)
                    derived_ontology_deleted = True
            except Exception as del_err:
                logger.warning(f"Failed to delete derived ontology for document {document_id}: {del_err}")

        db.session.commit()

        logger.info(
            f"Removed {triples_removed} triples and {removed_guideline} associated guideline(s) for document {document_id}"
        )
        return jsonify({
            'success': True,
            'message': 'Extracted concepts and triples removed',
            'concepts_removed': concepts_removed,
            'triples_removed': int(triples_removed),
            'guideline_removed': bool(removed_guideline),
            'derived_ontology_deleted': derived_ontology_deleted
        }), 200
        
    except Exception as e:
        db.session.rollback()
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error removing concepts from guideline {document_id}: {str(e)}\n{error_trace}")
        
        return jsonify({
            'error': f'Failed to remove concepts: {str(e)}'
        }), 500
