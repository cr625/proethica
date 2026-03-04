"""Action CRUD routes for scenarios."""

import json
from flask import request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.world import World
from app.services.mcp_client import MCPClient


def register_action_routes(bp):
    """Register action CRUD routes on the blueprint."""

    @bp.route('/<int:id>/actions/new', methods=['GET'])
    @login_required
    def new_action(id):
        """Display form to add an action to a scenario."""
        mcp_client = MCPClient.get_instance()
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

    @bp.route('/<int:id>/actions/<int:action_id>/edit', methods=['GET'])
    @login_required
    def edit_action(id, action_id):
        """Display form to edit an action."""
        from app.models.event import Action

        mcp_client = MCPClient.get_instance()
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

    @bp.route('/<int:id>/actions/<int:action_id>/update', methods=['POST'])
    @login_required
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
            parameters = data['parameters']
            if isinstance(parameters, str):
                try:
                    parameters = json.loads(parameters)
                except json.JSONDecodeError:
                    parameters = {}
            action.parameters = parameters

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

    @bp.route('/<int:id>/actions/<int:action_id>/delete', methods=['POST'])
    @login_required
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

    @bp.route('/<int:id>/actions', methods=['POST'])
    @login_required
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

        # Process parameters to ensure they're a Python dictionary
        parameters = data.get('parameters', {})
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                parameters = {}

        # Create action
        action = Action(
            name=data['name'],
            description=data['description'],
            scenario=scenario,
            character_id=character_id,
            action_time=action_time,
            action_type=data.get('action_type'),
            parameters=parameters,
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
