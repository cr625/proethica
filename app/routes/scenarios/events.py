"""Event CRUD routes for scenarios."""

import json
import logging
from flask import request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.world import World
from app.services.mcp_client import MCPClient

logger = logging.getLogger(__name__)


def register_event_routes(bp):
    """Register event CRUD routes on the blueprint."""

    @bp.route('/<int:id>/events/new', methods=['GET'])
    @login_required
    def new_event(id):
        """Display form to add an event to a scenario."""
        mcp_client = MCPClient.get_instance()
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
                logger.warning(f"Error retrieving action types from ontology: {str(e)}")

        return render_template('create_event.html', scenario=scenario, action_types=action_types)

    @bp.route('/<int:id>/events/<int:event_id>/edit', methods=['GET'])
    @login_required
    def edit_event(id, event_id):
        """Display form to edit an event."""
        from app.models.event import Event

        mcp_client = MCPClient.get_instance()
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
                logger.warning(f"Error retrieving action types from ontology: {str(e)}")

        return render_template('edit_event.html', scenario=scenario, event=event, action_types=action_types)

    @bp.route('/<int:id>/events/<int:event_id>/update', methods=['POST'])
    @login_required
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
            metadata = data['metadata']
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}
            event.parameters = metadata

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

    @bp.route('/<int:id>/events/<int:event_id>/delete', methods=['POST'])
    @login_required
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
            logger.warning(f"Event {event_id} is linked to action {event.action_id} and cannot be deleted directly")
            flash('This event is linked to an action and cannot be deleted directly. Delete the action instead.', 'warning')
            return redirect(url_for('scenarios.view_scenario', id=scenario.id))

        try:
            # Delete the event
            logger.debug(f"Deleting event {event_id}")
            db.session.delete(event)
            db.session.commit()
            logger.info(f"Event {event_id} deleted successfully")

            flash('Event deleted successfully', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting event {event_id}: {str(e)}")
            flash(f'Error deleting event: {str(e)}', 'danger')

        return redirect(url_for('scenarios.view_scenario', id=scenario.id))

    @bp.route('/<int:id>/events', methods=['POST'])
    @login_required
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

        # Process metadata to ensure it's a Python dictionary
        metadata = data.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}

        # Create event
        event = Event(
            scenario=scenario,
            event_time=event_time,
            description=data['description'],
            character_id=character_id,
            parameters=metadata
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
