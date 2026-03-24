"""Resource CRUD routes for scenarios."""

import logging
from flask import request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.scenario import Scenario
from app.models.resource import Resource
from app.models.resource_type import ResourceType
from app.models.world import World
from app.services.mcp_client import MCPClient

logger = logging.getLogger(__name__)


def register_resource_routes(bp):
    """Register resource CRUD routes on the blueprint."""

    @bp.route('/<int:id>/resources/new', methods=['GET'])
    @login_required
    def new_resource(id):
        """Display form to add a resource to a scenario."""
        mcp_client = MCPClient.get_instance()
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
                logger.warning(f"Error retrieving resource types from ontology: {str(e)}")

        # Debug information
        logger.debug(f"Found {len(resource_types)} database resource types for world_id {scenario.world_id}")
        logger.debug(f"Found {len(ontology_resource_types)} ontology resource types for world_id {scenario.world_id}")

        for rt in resource_types:
            logger.debug(f"DB Resource Type - ID: {rt.id}, Name: {rt.name}, Category: {rt.category}")
            logger.debug(f"Description: {rt.description}")
            logger.debug(f"Ontology URI: {rt.ontology_uri}")
            logger.debug("-" * 50)

        return render_template(
            'create_resource.html',
            scenario=scenario,
            resource_types=resource_types,
            ontology_resource_types=ontology_resource_types
        )

    @bp.route('/<int:id>/resources/<int:resource_id>/edit', methods=['GET'])
    @login_required
    def edit_resource(id, resource_id):
        """Display form to edit a resource."""
        mcp_client = MCPClient.get_instance()
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
                logger.warning(f"Error retrieving resource types from ontology: {str(e)}")

        return render_template(
            'edit_resource.html',
            scenario=scenario,
            resource=resource,
            resource_types=resource_types,
            ontology_resource_types=ontology_resource_types
        )

    @bp.route('/<int:id>/resources/<int:resource_id>/update', methods=['POST'])
    @login_required
    def update_resource(id, resource_id):
        """Update a resource."""
        mcp_client = MCPClient.get_instance()
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
                        logger.warning(f"Error retrieving resource type from ontology: {str(e)}")
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

    @bp.route('/<int:id>/resources/<int:resource_id>/delete', methods=['POST'])
    @login_required
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

    @bp.route('/<int:id>/resources', methods=['POST'])
    @login_required
    def add_resource(id):
        """Add a resource to a scenario."""
        mcp_client = MCPClient.get_instance()
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
                    logger.warning(f"Error retrieving resource type from ontology: {str(e)}")

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
