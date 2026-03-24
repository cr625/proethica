from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.utils.auth_utils import admin_required, data_owner_required
from app.utils.environment_auth import (
    auth_optional,
    auth_required_for_write,
    auth_required_for_llm,
    auth_required_for_create
)
import json
from datetime import datetime
import os
import logging
from werkzeug.utils import secure_filename
from app import db
from app.models.world import World
from app.models.ontology import Ontology
from app.models import Document
from app.services.mcp_client import MCPClient
from app.services.task_queue import BackgroundTaskQueue
from app.services.ontology_entity_service import OntologyEntityService

from app.routes.worlds.helpers import _get_dynamic_entity_type_config

logger = logging.getLogger(__name__)

# Get singleton instances
mcp_client = MCPClient.get_instance()
task_queue = BackgroundTaskQueue.get_instance()
ontology_entity_service = OntologyEntityService.get_instance()


def register_core_routes(bp):
    # API endpoints
    @bp.route('/api', methods=['GET'])
    def api_get_worlds():
        """API endpoint to get all worlds."""
        worlds = World.query.all()
        return jsonify({
            'success': True,
            'data': [world.to_dict() for world in worlds]
        })

    @bp.route('/api/<int:id>', methods=['GET'])
    def api_get_world(id):
        """API endpoint to get a specific world by ID."""
        world = World.query.get_or_404(id)
        return jsonify({
            'success': True,
            'data': world.to_dict()
        })

    # Web routes
    @bp.route('/', methods=['GET'])
    @auth_optional
    def list_worlds():
        """Display all worlds."""
        worlds = World.query.all()
        return render_template('worlds.html', worlds=worlds)

    @bp.route('/new', methods=['GET'])
    @auth_required_for_create
    def new_world():
        """Display form to create a new world - requires login in production."""
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
                logger.warning(f"Error creating BFO ontology: {str(e)}")

        return render_template('create_world.html', ontologies=ontologies)

    @bp.route('/', methods=['POST'])
    @auth_required_for_write
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

    @bp.route('/<int:id>', methods=['GET'])
    def view_world(id):
        """Display a specific world."""
        world = World.query.get_or_404(id)

        # Initialize defaults
        entities = {"entities": {}}  # Initialize with empty entities structure
        ontology_status = 'current'  # Default status
        ontology = None

        # Get ontology details if available
        if world.ontology_id:
            ontology = Ontology.query.get(world.ontology_id)

            try:
                # Get entities using our direct service
                entities = ontology_entity_service.get_entities_for_world(world)

                # Optionally check ontology status from MCP if we have an ontology source
                if world.ontology_source:
                    try:
                        status_result = mcp_client.get_ontology_status(world.ontology_source)
                        ontology_status = status_result.get('status', 'current')
                    except Exception as e:
                        logger.warning(f"Error checking ontology status: {str(e)}")

                # Debug logging
                logger.debug(f"Retrieved entities result: {entities.keys() if isinstance(entities, dict) else 'not a dict'}")
                if isinstance(entities, dict):
                    logger.debug(f"is_mock value: {entities.get('is_mock', 'not found')}")
                if 'entities' in entities:
                    entity_types = entities['entities'].keys() if isinstance(entities['entities'], dict) else 'not a dict'
                    logger.debug(f"Entity types: {entity_types}")

            except Exception as e:
                import traceback
                stack_trace = traceback.format_exc()
                error_message = f"Error retrieving world entities: {str(e)}"
                entities = {"entities": {}, "error": error_message}
                logger.error(error_message)
                logger.debug(stack_trace)

        # Get all guidelines for this world
        from app.models.guideline import Guideline
        guidelines = Guideline.query.filter_by(world_id=world.id).all()

        # Get all cases for this world (both case_study and case types)
        case_studies = Document.query.filter(
            Document.world_id == world.id,
            Document.document_type.in_(['case_study', 'case'])
        ).all()

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

    @bp.route('/<int:id>/edit', methods=['GET'])
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

    @bp.route('/<int:id>/edit', methods=['POST'])
    @auth_required_for_write
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
                    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads')
                    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

                    # Save file
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(file_path)

                    # Get file type
                    file_type = filename.rsplit('.', 1)[1].lower()

                    # Create guideline record
                    from app.models.guideline import Guideline
                    guideline = Guideline(
                        title=request.form.get('guidelines_title', f"Guidelines for {world.name}"),
                        world_id=world.id,
                        file_path=file_path,
                        file_type=file_type,
                        guideline_metadata={},  # Initialize with empty metadata
                        created_by=current_user.id,
                        data_type='user'
                    )
                    db.session.add(guideline)
                    db.session.commit()

                    # Read and store content from file
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            guideline.content = f.read()
                        db.session.commit()
                    except Exception as e:
                        logger.error(f"Error reading guideline file: {e}")

                    flash('Guideline uploaded successfully', 'success')
                else:
                    flash('File type not allowed. Allowed types: pdf, docx, txt, html, htm', 'error')

        # Handle guidelines URL
        guidelines_url = request.form.get('guidelines_url', '').strip()
        if guidelines_url:
            # Create guideline record for URL
            from app.models.guideline import Guideline

            # Create a Guideline record for the URL
            guideline = Guideline(
                title=request.form.get('guidelines_title_url', f"Guidelines URL for {world.name}"),
                world_id=world.id,
                source_url=guidelines_url,
                file_type="url",
                guideline_metadata={},
                created_by=current_user.id,
                data_type='user'
            )
            db.session.add(guideline)
            db.session.commit()

            # Fetch content from URL
            try:
                import requests
                response = requests.get(guidelines_url, timeout=30)
                response.raise_for_status()
                guideline.content = response.text
                db.session.commit()
            except Exception as e:
                logger.error(f"Error fetching guideline from URL: {e}")

            flash('Guideline URL uploaded successfully', 'success')

        # Handle guidelines text
        guidelines_text = request.form.get('guidelines_text', '').strip()
        if guidelines_text:
            # Create document record for text
            from app.models import Document
            from app.models.document import PROCESSING_STATUS
            document = Document(
                title=request.form.get('guidelines_title_text', f"Guidelines Text for {world.name}"),
                document_type="guideline",
                world_id=world.id,
                content=guidelines_text,
                file_type="txt",
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

    @bp.route('/<int:id>', methods=['PUT'])
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
                from app.models import Document
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
                        file_type="url"
                    )
                    db.session.add(document)

            # Process guidelines text
            if 'text' in guidelines and guidelines['text']:
                from app.models import Document
                document = Document(
                    title=guidelines.get('title', f"Guidelines Text for {world.name}"),
                    document_type="guideline",
                    world_id=world.id,
                    content=guidelines['text'],
                    file_type="txt"
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

    @bp.route('/<int:id>', methods=['DELETE'])
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

    @bp.route('/<int:id>/delete', methods=['POST'])
    @auth_required_for_write
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
    @bp.route('/<int:id>/cases', methods=['POST'])
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

    @bp.route('/<int:id>/cases/<int:case_id>', methods=['DELETE'])
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
    @bp.route('/<int:id>/rulesets', methods=['POST'])
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

    @bp.route('/<int:id>/rulesets/<int:ruleset_id>', methods=['DELETE'])
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
