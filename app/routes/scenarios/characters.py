"""Character CRUD routes for scenarios."""

import json
import logging
from flask import request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.condition import Condition
from app.models.condition_type import ConditionType
from app.models.world import World
from app.models.role import Role
from app.services.mcp_client import MCPClient

logger = logging.getLogger(__name__)


def register_character_routes(bp):
    """Register character CRUD routes on the blueprint."""

    @bp.route('/<int:id>/characters/new', methods=['GET'])
    @login_required
    def new_character(id):
        """Display form to add a character to a scenario."""
        mcp_client = MCPClient.get_instance()
        scenario = Scenario.query.get_or_404(id)
        world = World.query.get(scenario.world_id)

        # Get roles for the scenario's world from the database
        db_roles = Role.query.filter_by(world_id=scenario.world_id).all()

        # Get condition types for the scenario's world
        condition_types = ConditionType.query.filter_by(world_id=scenario.world_id).all()

        # Get roles and condition types from the ontology if the world has an ontology source
        ontology_roles = []
        ontology_condition_types = []

        if world and world.ontology_source:
            try:
                # Get all entity types from ontology in one request
                entities = mcp_client.get_world_entities(world.ontology_source)
                logger.debug(f"Retrieved entities result: {entities.keys() if isinstance(entities, dict) else 'not a dict'}")
                if isinstance(entities, dict):
                    logger.debug(f"is_mock value: {entities.get('is_mock', 'not found')}")

                if entities and 'entities' in entities:
                    logger.debug(f"Final entities structure: {entities.keys()}")
                    entity_dict = entities['entities']
                    logger.debug(f"Entity types: {entity_dict.keys() if isinstance(entity_dict, dict) else 'not a dict'}")

                    # Extract roles if available
                    if 'roles' in entity_dict:
                        ontology_roles = entity_dict['roles']

                    # Extract condition types if available
                    if 'conditions' in entity_dict:
                        ontology_condition_types = entity_dict['conditions']
            except Exception as e:
                logger.warning(f"Error retrieving entities from ontology: {str(e)}")

        # Debug information
        logger.debug(f"Found {len(db_roles)} database roles for world_id {scenario.world_id}")
        logger.debug(f"Found {len(ontology_roles)} ontology roles for world_id {scenario.world_id}")

        logger.debug(f"Found {len(condition_types)} database condition types for world_id {scenario.world_id}")
        logger.debug(f"Found {len(ontology_condition_types)} ontology condition types for world_id {scenario.world_id}")

        return render_template(
            'create_character.html',
            scenario=scenario,
            roles=db_roles,
            ontology_roles=ontology_roles,
            condition_types=condition_types,
            ontology_condition_types=ontology_condition_types
        )

    @bp.route('/<int:id>/characters', methods=['POST'])
    @login_required
    def add_character(id):
        """Add a character to a scenario."""
        mcp_client = MCPClient.get_instance()
        scenario = Scenario.query.get_or_404(id)
        data = request.json

        # Validate required role
        role_id = data.get('role_id')
        if not role_id:
            return jsonify({
                'success': False,
                'message': 'A role must be selected for the character'
            }), 400

        # Initialize variables for role information
        role_name = None
        role_description = None

        if role_id and isinstance(role_id, str) and role_id.startswith('http'):
            # This is an ontology role
            # Get the role name and description from the ontology
            world = World.query.get(scenario.world_id)
            if world and world.ontology_source:
                try:
                    entities = mcp_client.get_world_entities(world.ontology_source, entity_type="roles")
                    if entities and 'entities' in entities and 'roles' in entities['entities']:
                        for role in entities['entities']['roles']:
                            if role['id'] == role_id:
                                role_name = role['label']
                                role_description = role['description']
                                break
                except Exception as e:
                    logger.warning(f"Error retrieving role from ontology: {str(e)}")

            # Create or find a role in the database to associate with this character
            db_role = Role.query.filter_by(ontology_uri=role_id, world_id=scenario.world_id).first()
            if not db_role and role_name:
                # Create a new role in the database
                db_role = Role(
                    name=role_name,
                    description=role_description,
                    world_id=scenario.world_id,
                    ontology_uri=role_id
                )
                db.session.add(db_role)
                db.session.flush()  # Get the ID without committing

            # Use the database role ID if available
            if db_role:
                role_id = db_role.id

        # Create character - ensure attributes is a Python dictionary
        attributes = data.get('attributes', {})
        if isinstance(attributes, str):
            try:
                attributes = json.loads(attributes)
            except json.JSONDecodeError:
                attributes = {}

        # Convert empty string role_id to None
        if role_id == '':
            role_id = None

        character = Character(
            scenario=scenario,
            name=data['name'],
            role_id=role_id,
            attributes=attributes
        )

        # Set the role name for backward compatibility
        if character.role_id:
            if role_name:  # We already have the name from the ontology
                character.role = role_name
            else:
                # Get the role name from the database
                role = Role.query.get(character.role_id)
                if role:
                    character.role = role.name

        db.session.add(character)

        # Add conditions if provided
        for cond_data in data.get('conditions', []):
            condition_type_id = cond_data.get('condition_type_id')
            condition_name = cond_data['name']
            condition_description = cond_data.get('description', '')

            # Check if the condition_type_id is an ontology URI (starts with http)
            if condition_type_id and isinstance(condition_type_id, str) and condition_type_id.startswith('http'):
                # This is an ontology condition type
                # Get the condition type details from the ontology
                world = World.query.get(scenario.world_id)
                if world and world.ontology_source:
                    try:
                        entities = mcp_client.get_world_entities(world.ontology_source, entity_type="conditions")
                        if entities and 'entities' in entities and 'conditions' in entities['entities']:
                            for cond_type in entities['entities']['conditions']:
                                if cond_type['id'] == condition_type_id:
                                    # Create or find a condition type in the database
                                    db_cond_type = ConditionType.query.filter_by(ontology_uri=condition_type_id, world_id=scenario.world_id).first()
                                    if not db_cond_type:
                                        # Create a new condition type in the database
                                        db_cond_type = ConditionType(
                                            name=cond_type['label'],
                                            description=cond_type['description'],
                                            world_id=scenario.world_id,
                                            category=cond_type.get('type', ''),
                                            ontology_uri=condition_type_id
                                        )
                                        db.session.add(db_cond_type)
                                        db.session.flush()  # Get the ID without committing

                                    # Use the database condition type ID
                                    condition_type_id = db_cond_type.id
                                    break
                    except Exception as e:
                        logger.warning(f"Error retrieving condition type from ontology: {str(e)}")

            # Create condition
            condition = Condition(
                character=character,
                name=condition_name,
                description=condition_description,
                severity=cond_data.get('severity', 1),
                condition_type_id=condition_type_id
            )
            db.session.add(condition)

        db.session.commit()

        # Synchronize the new character with the RDF triple store
        from app.services.rdf_service import RDFService
        rdf_service = RDFService()
        try:
            logger.info(f"Syncing new character {character.id} ({character.name}) to RDF triple store")
            rdf_service.sync_character(character)
            logger.info(f"Character {character.id} successfully synced with RDF triple store")
        except Exception as e:
            logger.warning(f"Error syncing character with RDF triple store: {str(e)}")

        return jsonify({
            'success': True,
            'message': 'Character added successfully',
            'data': {
                'id': character.id,
                'name': character.name,
                'role': character.role
            }
        })

    @bp.route('/<int:id>/characters/<int:character_id>/edit', methods=['GET'])
    @login_required
    def edit_character(id, character_id):
        """Display form to edit a character."""
        mcp_client = MCPClient.get_instance()
        scenario = Scenario.query.get_or_404(id)
        character = Character.query.get_or_404(character_id)

        # Ensure the character belongs to the scenario
        if character.scenario_id != scenario.id:
            flash('Character does not belong to this scenario', 'danger')
            return redirect(url_for('scenarios.view_scenario', id=scenario.id))

        world = World.query.get(scenario.world_id)

        # Get roles for the scenario's world from the database
        db_roles = Role.query.filter_by(world_id=scenario.world_id).all()

        # Get condition types for the scenario's world
        condition_types = ConditionType.query.filter_by(world_id=scenario.world_id).all()

        # Get roles and condition types from the ontology if the world has an ontology source
        ontology_roles = []
        ontology_condition_types = []

        # Get ontology URI if the character has a database role with an ontology reference
        ontology_role_uri = None
        if character.role_id:
            if character.role_from_role and character.role_from_role.ontology_uri:
                ontology_role_uri = character.role_from_role.ontology_uri
                logger.debug(f"Character's role has ontology URI: {ontology_role_uri}")

        if world and world.ontology_source:
            try:
                # Get all entity types from ontology in one request
                entities = mcp_client.get_world_entities(world.ontology_source)

                if entities and 'entities' in entities:
                    entity_dict = entities['entities']

                    # Extract roles if available
                    if 'roles' in entity_dict:
                        ontology_roles = entity_dict['roles']

                        # Mark selected role in ontology roles
                        if ontology_role_uri:
                            for role in ontology_roles:
                                if role['id'] == ontology_role_uri:
                                    role['selected'] = True
                                    logger.debug(f"Marked ontology role {role['label']} as selected")

                    # Extract condition types if available
                    if 'conditions' in entity_dict:
                        ontology_condition_types = entity_dict['conditions']
            except Exception as e:
                logger.warning(f"Error retrieving entities from ontology: {str(e)}")

        # If role is unmatched, generate a suggested description to prefill
        suggested_role_description = None
        if not character.matched_ontology_role_id and (character.original_llm_role or character.role):
            try:
                from app.services.role_description_service import RoleDescriptionService
                rds = RoleDescriptionService()
                world_obj = World.query.get(scenario.world_id)
                desc_payload = rds.generate(character.original_llm_role or character.role, world=world_obj)
                suggested_role_description = desc_payload.get('description')
            except Exception as e:
                logger.warning(f"Role description suggestion failed: {e}")

        return render_template(
            'edit_character.html',
            scenario=scenario,
            character=character,
            roles=db_roles,
            ontology_roles=ontology_roles,
            condition_types=condition_types,
            ontology_condition_types=ontology_condition_types,
            ontology_role_uri=ontology_role_uri,
            suggested_role_description=suggested_role_description
        )

    @bp.route('/<int:id>/characters/<int:character_id>/update', methods=['POST'])
    @login_required
    def update_character(id, character_id):
        """Update a character."""
        from app.services.rdf_service import RDFService
        from app.services.cases_ontology_service import CasesOntologyService

        mcp_client = MCPClient.get_instance()
        scenario = Scenario.query.get_or_404(id)
        character = Character.query.get_or_404(character_id)

        # Ensure the character belongs to the scenario
        if character.scenario_id != scenario.id:
            return jsonify({
                'success': False,
                'message': 'Character does not belong to this scenario'
            }), 403

        data = request.json

        # Update character fields
        if 'name' in data:
            character.name = data['name']

        # Handle attributes if provided
        if 'attributes' in data:
            attributes = data['attributes']
            if isinstance(attributes, str):
                try:
                    attributes = json.loads(attributes)
                except json.JSONDecodeError:
                    attributes = {}
            character.attributes = attributes

        # Always update role if provided in the request
        role_assigned = False
        proposed_selected = False
        if 'role_id' in data:
            role_id = data['role_id']

            # Treat empty string or None as no selection
            if not role_id:
                pass
            elif isinstance(role_id, str) and role_id == '__proposed__':
                # User wants to keep proposed for potential add-to-ontology
                proposed_selected = True
            elif isinstance(role_id, str) and role_id.startswith('http'):
                # This is an ontology role
                # Get the role name and description from the ontology
                world = World.query.get(scenario.world_id)
                if world and world.ontology_source:
                    try:
                        entities = mcp_client.get_world_entities(world.ontology_source, entity_type="roles")
                        if entities and 'entities' in entities and 'roles' in entities['entities']:
                            for role in entities['entities']['roles']:
                                if role['id'] == role_id:
                                    role_name = role['label']
                                    role_description = role['description']

                                    # Create or find a role in the database
                                    db_role = Role.query.filter_by(ontology_uri=role_id, world_id=scenario.world_id).first()
                                    if not db_role:
                                        # Create a new role in the database
                                        db_role = Role(
                                            name=role_name,
                                            description=role_description,
                                            world_id=scenario.world_id,
                                            category=role.get('type', ''),
                                            ontology_uri=role_id
                                        )
                                        db.session.add(db_role)
                                        db.session.flush()  # Get the ID without committing

                                    # Update both role_id and legacy role field
                                    character.role_id = db_role.id
                                    character.role = role_name  # Update the legacy role field
                                    role_assigned = True
                                    logger.info(f"Updated character role to ontology role: {role_name} (ID: {db_role.id})")
                                    break
                    except Exception as e:
                        logger.warning(f"Error retrieving role from ontology: {str(e)}")
            else:
                # This is a database role ID - convert to integer
                try:
                    role_int = int(role_id)
                    # Update role_id
                    character.role_id = role_int

                    # Always update the legacy role field when role_id changes
                    role = Role.query.get(role_int)
                    if role:
                        character.role = role.name
                        role_assigned = True
                        logger.info(f"Updated character role to database role: {role.name} (ID: {role_int})")
                    else:
                        logger.warning(f"Role with ID {role_int} not found in database")
                except ValueError:
                    # Ignore invalid special strings
                    logger.warning(f"Invalid role_id format: {role_id}")

        # Optionally add suggested role to cases ontology when unmatched
        if data.get('add_to_cases_ontology'):
            suggested_name = (data.get('suggested_role_name') or '').strip()
            if suggested_name:
                world = World.query.get(scenario.world_id)
                svc = CasesOntologyService()
                try:
                    ontology_uri, role_row = svc.add_role_to_cases_ontology(
                        world=world,
                        label=suggested_name,
                        description=(data.get('suggested_role_description') or '').strip()
                    )
                    # Set the character's role to the newly created role only if no explicit role was chosen
                    # or the user explicitly selected the proposed option
                    if not role_assigned or proposed_selected:
                        character.role_id = role_row.id
                        character.role = role_row.name
                        character.matched_ontology_role_id = ontology_uri
                        character.matching_confidence = 1.0
                        character.matching_method = 'user_add_cases_ontology'
                        character.matching_reasoning = 'User accepted LLM suggestion and added role to cases ontology.'
                except Exception as e:
                    logger.warning(f"Error adding role to cases ontology: {e}")

        # Update conditions
        # First, handle existing conditions that were updated
        existing_condition_ids = set()
        for cond_data in data.get('conditions', []):
            if 'id' in cond_data:
                condition_id = cond_data['id']
                existing_condition_ids.add(condition_id)

                # Find the condition
                condition = Condition.query.get(condition_id)
                if condition and condition.character_id == character.id:
                    # Update condition fields
                    condition.name = cond_data['name']
                    condition.description = cond_data.get('description', '')
                    condition.severity = cond_data.get('severity', 1)

                    # Update condition type if provided
                    condition_type_id = cond_data.get('condition_type_id')
                    if condition_type_id:
                        # Check if the condition_type_id is an ontology URI (starts with http)
                        if isinstance(condition_type_id, str) and condition_type_id.startswith('http'):
                            # This is an ontology condition type
                            # Get the condition type details from the ontology
                            world = World.query.get(scenario.world_id)
                            if world and world.ontology_source:
                                try:
                                    entities = mcp_client.get_world_entities(world.ontology_source, entity_type="conditions")
                                    if entities and 'entities' in entities and 'conditions' in entities['entities']:
                                        for cond_type in entities['entities']['conditions']:
                                            if cond_type['id'] == condition_type_id:
                                                # Create or find a condition type in the database
                                                db_cond_type = ConditionType.query.filter_by(ontology_uri=condition_type_id, world_id=scenario.world_id).first()
                                                if not db_cond_type:
                                                    # Create a new condition type in the database
                                                    db_cond_type = ConditionType(
                                                        name=cond_type['label'],
                                                        description=cond_type['description'],
                                                        world_id=scenario.world_id,
                                                        category=cond_type.get('type', ''),
                                                        ontology_uri=condition_type_id
                                                    )
                                                    db.session.add(db_cond_type)
                                                    db.session.flush()  # Get the ID without committing

                                                # Use the database condition type ID
                                                condition.condition_type_id = db_cond_type.id
                                                break
                                except Exception as e:
                                    logger.warning(f"Error retrieving condition type from ontology: {str(e)}")
                        else:
                            # This is a database condition type ID
                            condition.condition_type_id = condition_type_id

        # Next, add new conditions
        for cond_data in data.get('conditions', []):
            if 'id' not in cond_data:
                condition_type_id = cond_data.get('condition_type_id')
                condition_name = cond_data['name']
                condition_description = cond_data.get('description', '')

                # Check if the condition_type_id is an ontology URI (starts with http)
                if condition_type_id and isinstance(condition_type_id, str) and condition_type_id.startswith('http'):
                    # This is an ontology condition type
                    # Get the condition type details from the ontology
                    world = World.query.get(scenario.world_id)
                    if world and world.ontology_source:
                        try:
                            # Use the singleton instance
                            entities = mcp_client.get_world_entities(world.ontology_source, entity_type="conditions")
                            if entities and 'entities' in entities and 'conditions' in entities['entities']:
                                for cond_type in entities['entities']['conditions']:
                                    if cond_type['id'] == condition_type_id:
                                        # Create or find a condition type in the database
                                        db_cond_type = ConditionType.query.filter_by(ontology_uri=condition_type_id, world_id=scenario.world_id).first()
                                        if not db_cond_type:
                                            # Create a new condition type in the database
                                            db_cond_type = ConditionType(
                                                name=cond_type['label'],
                                                description=cond_type['description'],
                                                world_id=scenario.world_id,
                                                category=cond_type.get('type', ''),
                                                ontology_uri=condition_type_id
                                            )
                                            db.session.add(db_cond_type)
                                            db.session.flush()  # Get the ID without committing

                                        # Use the database condition type ID
                                        condition_type_id = db_cond_type.id
                                        break
                        except Exception as e:
                            logger.warning(f"Error retrieving condition type from ontology: {str(e)}")

                # Create condition
                condition = Condition(
                    character=character,
                    name=condition_name,
                    description=condition_description,
                    severity=cond_data.get('severity', 1),
                    condition_type_id=condition_type_id
                )
                db.session.add(condition)

        # Finally, delete conditions that were removed
        for condition_id in data.get('removed_condition_ids', []):
            condition = Condition.query.get(condition_id)
            if condition and condition.character_id == character.id:
                db.session.delete(condition)

        db.session.commit()

        # Synchronize the character with the RDF triple store
        rdf_service = RDFService()
        try:
            # Sync will delete existing triples and create new ones based on current character state
            logger.info(f"Syncing character {character.id} ({character.name}) to RDF triple store")
            rdf_service.sync_character(character)
            logger.info(f"Character {character.id} successfully synced with RDF triple store")
        except Exception as e:
            logger.warning(f"Error syncing character with RDF triple store: {str(e)}")

        return jsonify({
            'success': True,
            'message': 'Character updated successfully',
            'data': {
                'id': character.id,
                'name': character.name,
                'role': character.role
            }
        })

    @bp.route('/<int:id>/characters/<int:character_id>/delete', methods=['POST'])
    @login_required
    def delete_character(id, character_id):
        """Delete a character and its associated actions."""
        from app.models.event import Action, Event
        from app.services.rdf_service import RDFService

        scenario = Scenario.query.get_or_404(id)
        character = Character.query.get_or_404(character_id)

        # Ensure the character belongs to the scenario
        if character.scenario_id != scenario.id:
            flash('Character does not belong to this scenario', 'danger')
            return redirect(url_for('scenarios.view_scenario', id=scenario.id))

        # Delete character triples from the RDF store
        try:
            rdf_service = RDFService()
            logger.info(f"Deleting RDF triples for character {character_id} ({character.name})")
            deleted_count = rdf_service.delete_triples(character_id=character_id)
            logger.info(f"Deleted {deleted_count} RDF triples for character {character_id}")
        except Exception as e:
            logger.warning(f"Error deleting RDF triples for character {character_id}: {str(e)}")

        # First, find all actions associated with this character
        actions = Action.query.filter_by(character_id=character_id).all()

        # For each action, delete associated events
        for action in actions:
            events = Event.query.filter_by(action_id=action.id).all()
            for event in events:
                db.session.delete(event)

            # Then delete the action
            db.session.delete(action)

        # Now delete the character (conditions will be deleted automatically due to cascade)
        db.session.delete(character)
        db.session.commit()

        flash('Character and associated actions deleted successfully', 'success')
        return redirect(url_for('scenarios.view_scenario', id=scenario.id))
