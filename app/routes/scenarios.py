from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from app import db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.condition import Condition
from app.models.condition_type import ConditionType
from app.models.resource import Resource
from app.models.resource_type import ResourceType
from app.models.domain import Domain
from app.models.world import World
from app.models.role import Role
from app.services import EventEngine, DecisionEngine
from app.services.mcp_client import MCPClient

scenarios_bp = Blueprint('scenarios', __name__, url_prefix='/scenarios')

# Get singleton instance of MCPClient
mcp_client = MCPClient.get_instance()

# API endpoints
@scenarios_bp.route('/api', methods=['GET'])
def api_get_scenarios():
    """API endpoint to get all scenarios."""
    scenarios = Scenario.query.all()
    return jsonify({
        'success': True,
        'data': [scenario.to_dict() for scenario in scenarios]
    })

@scenarios_bp.route('/api/<int:id>', methods=['GET'])
def api_get_scenario(id):
    """API endpoint to get a specific scenario by ID."""
    scenario = Scenario.query.get_or_404(id)
    return jsonify({
        'success': True,
        'data': scenario.to_dict()
    })

# Web routes
@scenarios_bp.route('/', methods=['GET'])
def list_scenarios():
    """Display all scenarios."""
    # Get world filter from query parameters
    world_id = request.args.get('world_id', type=int)
    
    # Filter scenarios by world if specified
    if world_id:
        scenarios = Scenario.query.filter_by(world_id=world_id).all()
    else:
        scenarios = Scenario.query.all()
    
    worlds = World.query.all()
    return render_template('scenarios.html', scenarios=scenarios, worlds=worlds, selected_world_id=world_id)

@scenarios_bp.route('/new', methods=['GET'])
def new_scenario():
    """Display form to create a new scenario."""
    worlds = World.query.all()
    world_id = request.args.get('world_id', type=int)
    world = None
    if world_id:
        world = World.query.get(world_id)
    return render_template('create_scenario.html', worlds=worlds, world=world)

@scenarios_bp.route('/<int:id>', methods=['GET'])
def view_scenario(id):
    """Display a specific scenario."""
    scenario = Scenario.query.get_or_404(id)
    return render_template('scenario_detail.html', scenario=scenario)

@scenarios_bp.route('/<int:id>/edit', methods=['GET'])
def edit_scenario(id):
    """Display form to edit an existing scenario."""
    scenario = Scenario.query.get_or_404(id)
    worlds = World.query.all()
    return render_template('edit_scenario.html', scenario=scenario, worlds=worlds)

@scenarios_bp.route('/<int:id>/edit', methods=['POST'])
def update_scenario_form(id):
    """Update an existing scenario from form data."""
    scenario = Scenario.query.get_or_404(id)
    
    # Get world (required)
    world_id = request.form.get('world_id')
    if not world_id:
        flash('World ID is required', 'danger')
        return redirect(url_for('scenarios.edit_scenario', id=scenario.id))
    
    try:
        world_id = int(world_id)
        world = World.query.get(world_id)
        if not world:
            flash(f'World with ID {world_id} not found', 'danger')
            return redirect(url_for('scenarios.edit_scenario', id=scenario.id))
    except ValueError:
        flash('Invalid world ID', 'danger')
        return redirect(url_for('scenarios.edit_scenario', id=scenario.id))
    
    # Update scenario fields
    scenario.name = request.form.get('name', '')
    scenario.description = request.form.get('description', '')
    scenario.world_id = world_id
    
    db.session.commit()
    
    flash('Scenario updated successfully', 'success')
    return redirect(url_for('scenarios.view_scenario', id=scenario.id))

# Character routes
@scenarios_bp.route('/<int:id>/characters/new', methods=['GET'])
def new_character(id):
    """Display form to add a character to a scenario."""
    scenario = Scenario.query.get_or_404(id)
    world = World.query.get(scenario.world_id)
    
    # Get roles for the scenario's world from the database
    db_roles = Role.query.filter_by(world_id=scenario.world_id).all()
    
    # Get condition types for the scenario's world
    condition_types = ConditionType.query.filter_by(world_id=scenario.world_id).all()
    
    # Get roles from the ontology if the world has an ontology source
    ontology_roles = []
    # Get condition types from the ontology if the world has an ontology source
    ontology_condition_types = []
    
    if world and world.ontology_source:
        try:
            # Get roles from ontology
            entities = mcp_client.get_world_entities(world.ontology_source, entity_type="roles")
            if entities and 'entities' in entities and 'roles' in entities['entities']:
                ontology_roles = entities['entities']['roles']
                
            # Get condition types from ontology
            entities = mcp_client.get_world_entities(world.ontology_source, entity_type="conditions")
            if entities and 'entities' in entities and 'conditions' in entities['entities']:
                ontology_condition_types = entities['entities']['conditions']
        except Exception as e:
            print(f"Error retrieving entities from ontology: {str(e)}")
    
    # Debug information
    print(f"Found {len(db_roles)} database roles for world_id {scenario.world_id}")
    print(f"Found {len(ontology_roles)} ontology roles for world_id {scenario.world_id}")
    
    print(f"Found {len(condition_types)} database condition types for world_id {scenario.world_id}")
    print(f"Found {len(ontology_condition_types)} ontology condition types for world_id {scenario.world_id}")
    
    return render_template(
        'create_character.html', 
        scenario=scenario, 
        roles=db_roles, 
        ontology_roles=ontology_roles,
        condition_types=condition_types,
        ontology_condition_types=ontology_condition_types
    )

@scenarios_bp.route('/<int:id>/characters', methods=['POST'])
def add_character(id):
    """Add a character to a scenario."""
    scenario = Scenario.query.get_or_404(id)
    data = request.json
    
    # Check if the role_id is an ontology URI (starts with http)
    role_id = data.get('role_id')
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
                print(f"Error retrieving role from ontology: {str(e)}")
        
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
    
    # Create character
    character = Character(
        scenario=scenario,
        name=data['name'],
        role_id=role_id,
        attributes=data.get('attributes', {})
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
                    print(f"Error retrieving condition type from ontology: {str(e)}")
        
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
    
    return jsonify({
        'success': True,
        'message': 'Character added successfully',
        'data': {
            'id': character.id,
            'name': character.name,
            'role': character.role
        }
    })

@scenarios_bp.route('/<int:id>/characters/<int:character_id>/edit', methods=['GET'])
def edit_character(id, character_id):
    """Display form to edit a character."""
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
    
    # Get roles from the ontology if the world has an ontology source
    ontology_roles = []
    # Get condition types from the ontology if the world has an ontology source
    ontology_condition_types = []
    
    if world and world.ontology_source:
        try:
            # Get roles from ontology
            entities = mcp_client.get_world_entities(world.ontology_source, entity_type="roles")
            if entities and 'entities' in entities and 'roles' in entities['entities']:
                ontology_roles = entities['entities']['roles']
                
            # Get condition types from ontology
            entities = mcp_client.get_world_entities(world.ontology_source, entity_type="conditions")
            if entities and 'entities' in entities and 'conditions' in entities['entities']:
                ontology_condition_types = entities['entities']['conditions']
        except Exception as e:
            print(f"Error retrieving entities from ontology: {str(e)}")
    
    return render_template(
        'edit_character.html', 
        scenario=scenario,
        character=character,
        roles=db_roles, 
        ontology_roles=ontology_roles,
        condition_types=condition_types,
        ontology_condition_types=ontology_condition_types
    )

@scenarios_bp.route('/<int:id>/characters/<int:character_id>/update', methods=['POST'])
def update_character(id, character_id):
    """Update a character."""
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
    
    # Update role if provided
    if 'role_id' in data and data['role_id']:
        role_id = data['role_id']
        
        # Check if the role_id is an ontology URI (starts with http)
        if isinstance(role_id, str) and role_id.startswith('http'):
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
                                
                                # Use the database role ID
                                character.role_id = db_role.id
                                character.role = role_name  # Update the role field for backward compatibility
                                break
                except Exception as e:
                    print(f"Error retrieving role from ontology: {str(e)}")
        else:
            # This is a database role ID
            character.role_id = role_id
            
            # Update the role field for backward compatibility
            role = Role.query.get(role_id)
            if role:
                character.role = role.name
    
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
                                print(f"Error retrieving condition type from ontology: {str(e)}")
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
                        print(f"Error retrieving condition type from ontology: {str(e)}")
            
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
    
    return jsonify({
        'success': True,
        'message': 'Character updated successfully',
        'data': {
            'id': character.id,
            'name': character.name,
            'role': character.role
        }
    })

@scenarios_bp.route('/<int:id>/characters/<int:character_id>/delete', methods=['POST'])
def delete_character(id, character_id):
    """Delete a character and its associated actions."""
    from app.models.event import Action, Event
    
    scenario = Scenario.query.get_or_404(id)
    character = Character.query.get_or_404(character_id)
    
    # Ensure the character belongs to the scenario
    if character.scenario_id != scenario.id:
        flash('Character does not belong to this scenario', 'danger')
        return redirect(url_for('scenarios.view_scenario', id=scenario.id))
    
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

# Resource routes
@scenarios_bp.route('/<int:id>/resources/new', methods=['GET'])
def new_resource(id):
    """Display form to add a resource to a scenario."""
    scenario = Scenario.query.get_or_404(id)
    world = World.query.get(scenario.world_id)
    
    # Get resource types for the scenario's world from the database
    resource_types = ResourceType.query.filter_by(world_id=scenario.world_id).all()
    
    # Get resource types from the ontology if the world has an ontology source
    ontology_resource_types = []
    if world and world.ontology_source:
        try:
            entities = mcp_client.get_world_entities(world.ontology_source, entity_type="resources")
            if entities and 'entities' in entities and 'resources' in entities['entities']:
                ontology_resource_types = entities['entities']['resources']
        except Exception as e:
            print(f"Error retrieving resource types from ontology: {str(e)}")
    
    # Debug information
    print(f"Found {len(resource_types)} database resource types for world_id {scenario.world_id}")
    print(f"Found {len(ontology_resource_types)} ontology resource types for world_id {scenario.world_id}")
    
    for rt in resource_types:
        print(f"DB Resource Type - ID: {rt.id}, Name: {rt.name}, Category: {rt.category}")
        print(f"Description: {rt.description}")
        print(f"Ontology URI: {rt.ontology_uri}")
        print("-" * 50)
    
    return render_template(
        'create_resource.html', 
        scenario=scenario, 
        resource_types=resource_types,
        ontology_resource_types=ontology_resource_types
    )

@scenarios_bp.route('/<int:id>/resources/<int:resource_id>/edit', methods=['GET'])
def edit_resource(id, resource_id):
    """Display form to edit a resource."""
    scenario = Scenario.query.get_or_404(id)
    resource = Resource.query.get_or_404(resource_id)
    
    # Ensure the resource belongs to the scenario
    if resource.scenario_id != scenario.id:
        flash('Resource does not belong to this scenario', 'danger')
        return redirect(url_for('scenarios.view_scenario', id=scenario.id))
    
    world = World.query.get(scenario.world_id)
    
    # Get resource types for the scenario's world from the database
    resource_types = ResourceType.query.filter_by(world_id=scenario.world_id).all()
    
    # Get resource types from the ontology if the world has an ontology source
    ontology_resource_types = []
    if world and world.ontology_source:
        try:
            entities = mcp_client.get_world_entities(world.ontology_source, entity_type="resources")
            if entities and 'entities' in entities and 'resources' in entities['entities']:
                ontology_resource_types = entities['entities']['resources']
        except Exception as e:
            print(f"Error retrieving resource types from ontology: {str(e)}")
    
    return render_template(
        'edit_resource.html', 
        scenario=scenario,
        resource=resource,
        resource_types=resource_types,
        ontology_resource_types=ontology_resource_types
    )

@scenarios_bp.route('/<int:id>/resources/<int:resource_id>/update', methods=['POST'])
def update_resource(id, resource_id):
    """Update a resource."""
    scenario = Scenario.query.get_or_404(id)
    resource = Resource.query.get_or_404(resource_id)
    
    # Ensure the resource belongs to the scenario
    if resource.scenario_id != scenario.id:
        return jsonify({
            'success': False,
            'message': 'Resource does not belong to this scenario'
        }), 403
    
    data = request.json
    
    # Update resource fields
    if 'name' in data:
        resource.name = data['name']
    if 'quantity' in data:
        resource.quantity = data['quantity']
    if 'description' in data:
        resource.description = data['description']
    
    # Update resource type if provided
    if 'resource_type_id' in data and data['resource_type_id']:
        resource_type_id = data['resource_type_id']
        
        # Check if the resource_type_id is an ontology URI (starts with http)
        if isinstance(resource_type_id, str) and resource_type_id.startswith('http'):
            # This is an ontology resource type
            # Get the resource type details from the ontology
            world = World.query.get(scenario.world_id)
            if world and world.ontology_source:
                try:
                    entities = mcp_client.get_world_entities(world.ontology_source, entity_type="resources")
                    if entities and 'entities' in entities and 'resources' in entities['entities']:
                        for res_type in entities['entities']['resources']:
                            if res_type['id'] == resource_type_id:
                                resource_type_name = res_type['label']
                                
                                # Create or find a resource type in the database
                                db_res_type = ResourceType.query.filter_by(ontology_uri=resource_type_id, world_id=scenario.world_id).first()
                                if not db_res_type:
                                    # Create a new resource type in the database
                                    db_res_type = ResourceType(
                                        name=res_type['label'],
                                        description=res_type['description'],
                                        world_id=scenario.world_id,
                                        category=res_type.get('type', ''),
                                        ontology_uri=resource_type_id
                                    )
                                    db.session.add(db_res_type)
                                    db.session.flush()  # Get the ID without committing
                                
                                # Use the database resource type ID
                                resource.resource_type_id = db_res_type.id
                                resource.type = resource_type_name  # Update the type field for backward compatibility
                                break
                except Exception as e:
                    print(f"Error retrieving resource type from ontology: {str(e)}")
        else:
            # This is a database resource type ID
            resource.resource_type_id = resource_type_id
            
            # Update the type field for backward compatibility
            res_type = ResourceType.query.get(resource_type_id)
            if res_type:
                resource.type = res_type.name
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Resource updated successfully',
        'data': {
            'id': resource.id,
            'name': resource.name,
            'type': resource.type,
            'quantity': resource.quantity
        }
    })

@scenarios_bp.route('/<int:id>/resources/<int:resource_id>/delete', methods=['POST'])
def delete_resource(id, resource_id):
    """Delete a resource."""
    scenario = Scenario.query.get_or_404(id)
    resource = Resource.query.get_or_404(resource_id)
    
    # Ensure the resource belongs to the scenario
    if resource.scenario_id != scenario.id:
        flash('Resource does not belong to this scenario', 'danger')
        return redirect(url_for('scenarios.view_scenario', id=scenario.id))
    
    # Delete the resource
    db.session.delete(resource)
    db.session.commit()
    
    flash('Resource deleted successfully', 'success')
    return redirect(url_for('scenarios.view_scenario', id=scenario.id))

@scenarios_bp.route('/<int:id>/resources', methods=['POST'])
def add_resource(id):
    """Add a resource to a scenario."""
    scenario = Scenario.query.get_or_404(id)
    data = request.json
    
    # Check if the resource_type_id is an ontology URI (starts with http)
    resource_type_id = data.get('resource_type_id')
    resource_type_name = None
    
    if resource_type_id and isinstance(resource_type_id, str) and resource_type_id.startswith('http'):
        # This is an ontology resource type
        # Get the resource type details from the ontology
        world = World.query.get(scenario.world_id)
        if world and world.ontology_source:
            try:
                # Use the singleton instance
                entities = mcp_client.get_world_entities(world.ontology_source, entity_type="resources")
                if entities and 'entities' in entities and 'resources' in entities['entities']:
                    for res_type in entities['entities']['resources']:
                        if res_type['id'] == resource_type_id:
                            resource_type_name = res_type['label']
                            
                            # Create or find a resource type in the database
                            db_res_type = ResourceType.query.filter_by(ontology_uri=resource_type_id, world_id=scenario.world_id).first()
                            if not db_res_type:
                                # Create a new resource type in the database
                                db_res_type = ResourceType(
                                    name=res_type['label'],
                                    description=res_type['description'],
                                    world_id=scenario.world_id,
                                    category=res_type.get('type', ''),
                                    ontology_uri=resource_type_id
                                )
                                db.session.add(db_res_type)
                                db.session.flush()  # Get the ID without committing
                            
                            # Use the database resource type ID
                            resource_type_id = db_res_type.id
                            break
            except Exception as e:
                print(f"Error retrieving resource type from ontology: {str(e)}")
    
    # Create resource
    resource = Resource(
        scenario=scenario,
        name=data['name'],
        resource_type_id=resource_type_id,
        quantity=data.get('quantity', 1),
        description=data.get('description', '')
    )
    
    # Set the type field for backward compatibility
    if resource.resource_type_id:
        if resource_type_name:  # We already have the name from the ontology
            resource.type = resource_type_name
        else:
            # Get the resource type name from the database
            res_type = ResourceType.query.get(resource.resource_type_id)
            if res_type:
                resource.type = res_type.name
    else:
        # Use the type field if provided
        resource.type = data.get('type', '')
    
    db.session.add(resource)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Resource added successfully',
        'data': {
            'id': resource.id,
            'name': resource.name,
            'type': resource.type,
            'quantity': resource.quantity
        }
    })

# Action routes
@scenarios_bp.route('/<int:id>/actions/new', methods=['GET'])
def new_action(id):
    """Display form to add an action to a scenario."""
    scenario = Scenario.query.get_or_404(id)
    world = World.query.get(scenario.world_id)
    
    # Get action types from the ontology if the world has an ontology source
    action_types = []
    if world and world.ontology_source:
        try:
            entities = mcp_client.get_world_entities(world.ontology_source, entity_type="actions")
            if entities and 'entities' in entities and 'actions' in entities['entities']:
                action_types = entities['entities']['actions']
        except Exception as e:
            print(f"Error retrieving action types from ontology: {str(e)}")
    
    return render_template('create_action.html', scenario=scenario, action_types=action_types)

@scenarios_bp.route('/<int:id>/actions/<int:action_id>/edit', methods=['GET'])
def edit_action(id, action_id):
    """Display form to edit an action."""
    from app.models.event import Action
    
    scenario = Scenario.query.get_or_404(id)
    action = Action.query.get_or_404(action_id)
    
    # Ensure the action belongs to the scenario
    if action.scenario_id != scenario.id:
        flash('Action does not belong to this scenario', 'danger')
        return redirect(url_for('scenarios.view_scenario', id=scenario.id))
    
    world = World.query.get(scenario.world_id)
    
    # Get action types from the ontology if the world has an ontology source
    action_types = []
    if world and world.ontology_source:
        try:
            entities = mcp_client.get_world_entities(world.ontology_source, entity_type="actions")
            if entities and 'entities' in entities and 'actions' in entities['entities']:
                action_types = entities['entities']['actions']
        except Exception as e:
            print(f"Error retrieving action types from ontology: {str(e)}")
    
    return render_template('edit_action.html', scenario=scenario, action=action, action_types=action_types)

@scenarios_bp.route('/<int:id>/actions/<int:action_id>/update', methods=['POST'])
def update_action(id, action_id):
    """Update an action."""
    from app.models.event import Action
    from datetime import datetime
    
    scenario = Scenario.query.get_or_404(id)
    action = Action.query.get_or_404(action_id)
    
    # Ensure the action belongs to the scenario
    if action.scenario_id != scenario.id:
        return jsonify({
            'success': False,
            'message': 'Action does not belong to this scenario'
        }), 403
    
    data = request.json
    
    # Update action fields
    if 'name' in data:
        action.name = data['name']
    if 'description' in data:
        action.description = data['description']
    if 'action_time' in data:
        # Parse action_time if it's a string
        action_time = data['action_time']
        if isinstance(action_time, str):
            try:
                # Try to parse ISO format first
                action_time = datetime.fromisoformat(action_time.replace('Z', '+00:00'))
            except ValueError:
                try:
                    # Try to parse common datetime formats
                    action_time = datetime.strptime(action_time, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        action_time = datetime.strptime(action_time, '%Y-%m-%d')
                    except ValueError:
                        # Default to current time if parsing fails
                        action_time = datetime.now()
        action.action_time = action_time
    if 'character_id' in data:
        action.character_id = data['character_id']
    if 'action_type' in data:
        action.action_type = data['action_type']
    if 'parameters' in data:
        action.parameters = data['parameters']
    
    # Update decision-specific fields
    if 'is_decision' in data:
        action.is_decision = data['is_decision']
        if action.is_decision and 'options' in data:
            action.options = data['options']
    
    db.session.commit()
    
    # Update related event if this is a decision
    if action.is_decision:
        from app.models.event import Event
        event = Event.query.filter_by(action_id=action.id).first()
        if event:
            event.event_time = action.action_time
            event.description = f"Decision point: {action.name}"
            event.character_id = action.character_id
            event.parameters = action.parameters
            db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Action updated successfully',
        'data': {
            'id': action.id,
            'name': action.name,
            'action_time': action.action_time.isoformat(),
            'description': action.description,
            'is_decision': action.is_decision
        }
    })

@scenarios_bp.route('/<int:id>/actions/<int:action_id>/delete', methods=['POST'])
def delete_action(id, action_id):
    """Delete an action."""
    from app.models.event import Action, Event
    
    scenario = Scenario.query.get_or_404(id)
    action = Action.query.get_or_404(action_id)
    
    # Ensure the action belongs to the scenario
    if action.scenario_id != scenario.id:
        flash('Action does not belong to this scenario', 'danger')
        return redirect(url_for('scenarios.view_scenario', id=scenario.id))
    
    try:
        # Delete related events
        events = Event.query.filter_by(action_id=action.id).all()
        print(f"Found {len(events)} events to delete for action {action_id}")
        for event in events:
            print(f"Deleting event {event.id}")
            db.session.delete(event)
        
        # Delete the action
        print(f"Deleting action {action_id}")
        db.session.delete(action)
        db.session.commit()
        print(f"Action {action_id} and related events deleted successfully")
        
        flash('Action deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting action {action_id}: {str(e)}")
        flash(f'Error deleting action: {str(e)}', 'danger')
    
    return redirect(url_for('scenarios.view_scenario', id=scenario.id))

@scenarios_bp.route('/<int:id>/actions', methods=['POST'])
def add_action(id):
    """Add an action to a scenario."""
    from app.models.event import Action
    from datetime import datetime
    
    scenario = Scenario.query.get_or_404(id)
    data = request.json
    
    # Get character if provided
    character_id = data.get('character_id')
    character = None
    if character_id:
        character = Character.query.get(character_id)
    
    # Parse action_time if it's a string
    action_time = data['action_time']
    if isinstance(action_time, str):
        try:
            # Try to parse ISO format first
            action_time = datetime.fromisoformat(action_time.replace('Z', '+00:00'))
        except ValueError:
            try:
                # Try to parse common datetime formats
                action_time = datetime.strptime(action_time, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    action_time = datetime.strptime(action_time, '%Y-%m-%d')
                except ValueError:
                    # Default to current time if parsing fails
                    action_time = datetime.now()
    
    # Create action
    action = Action(
        name=data['name'],
        description=data['description'],
        scenario=scenario,
        character_id=character_id,
        action_time=action_time,
        action_type=data.get('action_type'),
        parameters=data.get('parameters', {}),
        is_decision=data.get('is_decision', False),
        options=data.get('options', []) if data.get('is_decision', False) else None
    )
    db.session.add(action)
    db.session.commit()
    
    # If this is a decision, we might want to create an event for it as well
    if action.is_decision:
        from app.models.event import Event
        event = Event(
            scenario=scenario,
            event_time=action_time,
            description=f"Decision point: {data['name']}",
            character_id=character_id,
            action=action,
            parameters=data.get('parameters', {})
        )
        db.session.add(event)
        db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Action added successfully',
        'data': {
            'id': action.id,
            'name': action.name,
            'action_time': action.action_time.isoformat(),
            'description': action.description,
            'is_decision': action.is_decision
        }
    })

# Event routes
@scenarios_bp.route('/<int:id>/events/new', methods=['GET'])
def new_event(id):
    """Display form to add an event to a scenario."""
    scenario = Scenario.query.get_or_404(id)
    world = World.query.get(scenario.world_id)
    
    # Get action types from the ontology if the world has an ontology source
    action_types = []
    if world and world.ontology_source:
        try:
            # Use the singleton instance
            entities = mcp_client.get_world_entities(world.ontology_source, entity_type="actions")
            if entities and 'entities' in entities and 'actions' in entities['entities']:
                action_types = entities['entities']['actions']
        except Exception as e:
            print(f"Error retrieving action types from ontology: {str(e)}")
    
    return render_template('create_event.html', scenario=scenario, action_types=action_types)

@scenarios_bp.route('/<int:id>/events/<int:event_id>/edit', methods=['GET'])
def edit_event(id, event_id):
    """Display form to edit an event."""
    from app.models.event import Event
    
    scenario = Scenario.query.get_or_404(id)
    event = Event.query.get_or_404(event_id)
    
    # Ensure the event belongs to the scenario
    if event.scenario_id != scenario.id:
        flash('Event does not belong to this scenario', 'danger')
        return redirect(url_for('scenarios.view_scenario', id=scenario.id))
    
    world = World.query.get(scenario.world_id)
    
    # Get action types from the ontology if the world has an ontology source
    action_types = []
    if world and world.ontology_source:
        try:
            # Use the singleton instance
            entities = mcp_client.get_world_entities(world.ontology_source, entity_type="actions")
            if entities and 'entities' in entities and 'actions' in entities['entities']:
                action_types = entities['entities']['actions']
        except Exception as e:
            print(f"Error retrieving action types from ontology: {str(e)}")
    
    return render_template('edit_event.html', scenario=scenario, event=event, action_types=action_types)

@scenarios_bp.route('/<int:id>/events/<int:event_id>/update', methods=['POST'])
def update_event(id, event_id):
    """Update an event."""
    from app.models.event import Event
    from datetime import datetime
    
    scenario = Scenario.query.get_or_404(id)
    event = Event.query.get_or_404(event_id)
    
    # Ensure the event belongs to the scenario
    if event.scenario_id != scenario.id:
        return jsonify({
            'success': False,
            'message': 'Event does not belong to this scenario'
        }), 403
    
    data = request.json
    
    # Update event fields
    if 'description' in data:
        event.description = data['description']
    if 'event_time' in data:
        # Parse event_time if it's a string
        event_time = data['event_time']
        if isinstance(event_time, str):
            try:
                # Try to parse ISO format first
                event_time = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
            except ValueError:
                try:
                    # Try to parse common datetime formats
                    event_time = datetime.strptime(event_time, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        event_time = datetime.strptime(event_time, '%Y-%m-%d')
                    except ValueError:
                        # Default to current time if parsing fails
                        event_time = datetime.now()
        event.event_time = event_time
    if 'character_id' in data:
        event.character_id = data['character_id']
    if 'metadata' in data:
        event.parameters = data['metadata']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Event updated successfully',
        'data': {
            'id': event.id,
            'event_time': event.event_time.isoformat(),
            'description': event.description
        }
    })

@scenarios_bp.route('/<int:id>/events/<int:event_id>/delete', methods=['POST'])
def delete_event(id, event_id):
    """Delete an event."""
    from app.models.event import Event
    
    scenario = Scenario.query.get_or_404(id)
    event = Event.query.get_or_404(event_id)
    
    # Ensure the event belongs to the scenario
    if event.scenario_id != scenario.id:
        flash('Event does not belong to this scenario', 'danger')
        return redirect(url_for('scenarios.view_scenario', id=scenario.id))
    
    # Check if this event is linked to an action
    if event.action_id:
        print(f"Event {event_id} is linked to action {event.action_id} and cannot be deleted directly")
        flash('This event is linked to an action and cannot be deleted directly. Delete the action instead.', 'warning')
        return redirect(url_for('scenarios.view_scenario', id=scenario.id))
    
    try:
        # Delete the event
        print(f"Deleting event {event_id}")
        db.session.delete(event)
        db.session.commit()
        print(f"Event {event_id} deleted successfully")
        
        flash('Event deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting event {event_id}: {str(e)}")
        flash(f'Error deleting event: {str(e)}', 'danger')
    
    return redirect(url_for('scenarios.view_scenario', id=scenario.id))

@scenarios_bp.route('/<int:id>/events', methods=['POST'])
def add_event(id):
    """Add an event to a scenario."""
    from app.models.event import Event
    from datetime import datetime
    
    scenario = Scenario.query.get_or_404(id)
    data = request.json
    
    # Get character if provided
    character_id = data.get('character_id')
    character = None
    if character_id:
        character = Character.query.get(character_id)
    
    # Parse event_time if it's a string
    event_time = data['event_time']
    if isinstance(event_time, str):
        try:
            # Try to parse ISO format first
            event_time = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
        except ValueError:
            try:
                # Try to parse common datetime formats
                event_time = datetime.strptime(event_time, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    event_time = datetime.strptime(event_time, '%Y-%m-%d')
                except ValueError:
                    # Default to current time if parsing fails
                    event_time = datetime.now()
    
    # Create event
    event = Event(
        scenario=scenario,
        event_time=event_time,
        description=data['description'],
        character_id=character_id,
        parameters=data.get('metadata', {})
    )
    db.session.add(event)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Event added successfully',
        'data': {
            'id': event.id,
            'event_time': event.event_time.isoformat(),
            'description': event.description
        }
    })

# Decision routes
@scenarios_bp.route('/<int:id>/decisions/new', methods=['GET'])
def new_decision(id):
    """Display form to add a decision to a scenario."""
    scenario = Scenario.query.get_or_404(id)
    return render_template('create_decision.html', scenario=scenario)

@scenarios_bp.route('/<int:id>/decisions', methods=['POST'])
def add_decision(id):
    """Add a decision to a scenario."""
    from app.models.decision import Decision
    
    scenario = Scenario.query.get_or_404(id)
    data = request.json
    
    # Get character if provided
    character_id = data.get('character_id')
    character = None
    if character_id:
        character = Character.query.get(character_id)
    
    # Create decision
    decision = Decision(
        scenario=scenario,
        decision_time=data['decision_time'],
        description=data['description'],
        options=data['options'],
        character_id=character_id,
        context=data.get('context', '')
    )
    db.session.add(decision)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Decision added successfully',
        'data': {
            'id': decision.id,
            'decision_time': decision.decision_time.isoformat(),
            'description': decision.description,
            'options': decision.options
        }
    })

@scenarios_bp.route('/', methods=['POST'])
def create_scenario():
    """Create a new scenario."""
    # Check if the request is JSON or form data
    if request.is_json:
        data = request.json
    else:
        data = request.form
    
    # Get world (required)
    world_id = data.get('world_id')
    if not world_id:
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'World ID is required'
            }), 400
        else:
            flash('World ID is required', 'danger')
            return redirect(url_for('scenarios.new_scenario'))
    
    try:
        world_id = int(world_id)
        world = World.query.get(world_id)
        if not world:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': f'World with ID {world_id} not found'
                }), 404
            else:
                flash(f'World with ID {world_id} not found', 'danger')
                return redirect(url_for('scenarios.new_scenario'))
    except ValueError:
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Invalid world ID'
            }), 400
        else:
            flash('Invalid world ID', 'danger')
            return redirect(url_for('scenarios.new_scenario'))
    
    # Create scenario
    scenario = Scenario(
        name=data.get('name', ''),
        description=data.get('description', ''),
        metadata={},
        world_id=world_id
    )
    db.session.add(scenario)
    
    # Add characters if provided (JSON only)
    if request.is_json:
        for char_data in data.get('characters', []):
            character = Character(
                scenario=scenario,
                name=char_data['name'],
                role=char_data.get('role', ''),
                attributes=char_data.get('attributes', {})
            )
            db.session.add(character)
            
            # Add conditions if provided
            for cond_data in char_data.get('conditions', []):
                condition = Condition(
                    character=character,
                    name=cond_data['name'],
                    description=cond_data.get('description', ''),
                    severity=cond_data.get('severity', 1)
                )
                db.session.add(condition)
        
        # Add resources if provided
        for res_data in data.get('resources', []):
            resource = Resource(
                scenario=scenario,
                name=res_data['name'],
                type=res_data.get('type', ''),
                quantity=res_data.get('quantity', 1),
                description=res_data.get('description', '')
            )
            db.session.add(resource)
    
    db.session.commit()
    
    if request.is_json:
        return jsonify({
            'success': True,
            'message': 'Scenario created successfully',
            'data': scenario.to_dict()
        }), 201
    else:
        flash('Scenario created successfully', 'success')
        return redirect(url_for('scenarios.view_scenario', id=scenario.id))

@scenarios_bp.route('/<int:id>', methods=['PUT'])
def update_scenario(id):
    """Update an existing scenario."""
    scenario = Scenario.query.get_or_404(id)
    data = request.json
    
    # Update scenario fields
    if 'name' in data:
        scenario.name = data['name']
    if 'description' in data:
        scenario.description = data['description']
    if 'metadata' in data:
        scenario.metadata = data['metadata']
    
    # Update world if provided
    if 'world_id' in data:
        world = World.query.get(data['world_id'])
        if not world:
            return jsonify({
                'success': False,
                'message': f'World with ID {data["world_id"]} not found'
            }), 404
        scenario.world_id = world.id
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Scenario updated successfully',
        'data': scenario.to_dict()
    })

@scenarios_bp.route('/<int:id>', methods=['DELETE'])
def delete_scenario(id):
    """Delete a scenario via API."""
    scenario = Scenario.query.get_or_404(id)
    db.session.delete(scenario)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Scenario deleted successfully'
    })

@scenarios_bp.route('/<int:id>/delete', methods=['POST'])
def delete_scenario_form(id):
    """Delete a scenario from web form."""
    scenario = Scenario.query.get_or_404(id)
    db.session.delete(scenario)
    db.session.commit()
    
    flash('Scenario deleted successfully', 'success')
    return redirect(url_for('scenarios.list_scenarios'))

# References routes
@scenarios_bp.route('/<int:id>/references', methods=['GET'])
def scenario_references(id):
    """Display references for a scenario."""
    scenario = Scenario.query.get_or_404(id)
    
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
            # Get references based on scenario content
            references_data = mcp_client.get_references_for_scenario(scenario)
            references = {'results': references_data}
    except Exception as e:
        print(f"Error retrieving references: {str(e)}")
        references = {'results': []}
    
    return render_template('scenario_references.html', scenario=scenario, references=references, query=query)

@scenarios_bp.route('/<int:id>/references/<item_key>/citation', methods=['GET'])
def get_reference_citation(id, item_key):
    """Get citation for a reference."""
    scenario = Scenario.query.get_or_404(id)
    style = request.args.get('style', 'apa')
    
    # Get citation
    try:
        # Get a fresh instance of MCPClient to ensure we're using the most up-to-date instance
        # This is important for testing where we might be mocking the client
        mcp_client_instance = MCPClient.get_instance()
        citation = mcp_client_instance.get_zotero_citation(item_key, style)
        return jsonify({
            'success': True,
            'citation': citation
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@scenarios_bp.route('/<int:id>/references/add', methods=['POST'])
def add_reference(id):
    """Add a reference to the Zotero library."""
    scenario = Scenario.query.get_or_404(id)
    data = request.json
    
    # Add reference
    try:
        result = mcp_client.add_zotero_item(
            item_type=data.get('item_type', 'journalArticle'),
            title=data.get('title', ''),
            creators=data.get('creators', []),
            additional_fields=data.get('additional_fields', {})
        )
        
        return jsonify({
            'success': True,
            'message': 'Reference added successfully',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Simulation route
@scenarios_bp.route('/<int:id>/simulate', methods=['GET'])
def simulate_scenario(id):
    """Display simulation coming soon page."""
    scenario = Scenario.query.get_or_404(id)
    return render_template('simulate_coming_soon.html', scenario=scenario)
