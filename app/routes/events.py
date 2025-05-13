"""
Routes for managing events.

This module provides routes for managing events and actions in the application.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.event import Event, Action
from app.models.scenario import Scenario
from app.models import db

# Create a blueprint for the events routes
events_bp = Blueprint('events', __name__)

@events_bp.route('/')
def list_events():
    """
    List all events.
    
    Returns:
        Rendered template with events
    """
    try:
        events = Event.query.all()
        return render_template('events/list.html', events=events)
    except Exception:
        # Fallback if events functionality is not fully implemented
        flash('Events functionality is not fully implemented yet', 'warning')
        return redirect(url_for('index.index'))

@events_bp.route('/create', methods=['GET', 'POST'])
def create_event():
    """
    Create a new event.
    
    Returns:
        Rendered template or redirect
    """
    if request.method == 'POST':
        try:
            # Extract data from form
            name = request.form.get('name')
            description = request.form.get('description', '')
            scenario_id = request.form.get('scenario_id')
            event_type = request.form.get('event_type', 'event')
            
            # Create new event
            if event_type == 'action':
                event = Action(
                    name=name, 
                    description=description,
                    scenario_id=scenario_id
                )
            else:
                event = Event(
                    name=name, 
                    description=description,
                    scenario_id=scenario_id
                )
                
            db.session.add(event)
            db.session.commit()
            
            flash(f'{event_type.capitalize()} "{name}" created successfully', 'success')
            return redirect(url_for('events.list_events'))
        except Exception as e:
            flash(f'Error creating event: {str(e)}', 'danger')
            db.session.rollback()
    
    # GET method or form submission failed
    scenarios = Scenario.query.all()
    return render_template('events/create.html', scenarios=scenarios)

@events_bp.route('/<int:event_id>', methods=['GET'])
def view_event(event_id):
    """
    View a specific event.
    
    Args:
        event_id: ID of the event
        
    Returns:
        Rendered event template or redirect
    """
    try:
        event = Event.query.get_or_404(event_id)
        return render_template('events/view.html', event=event)
    except Exception as e:
        flash(f'Error viewing event: {str(e)}', 'danger')
        return redirect(url_for('events.list_events'))

@events_bp.route('/actions')
def list_actions():
    """
    List all actions.
    
    Returns:
        Rendered template with actions
    """
    try:
        actions = Action.query.all()
        return render_template('events/actions.html', actions=actions)
    except Exception:
        flash('Actions functionality is not fully implemented yet', 'warning')
        return redirect(url_for('events.list_events'))

@events_bp.route('/api/events')
def api_list_events():
    """
    API endpoint to list all events.
    
    Returns:
        JSON response with events
    """
    try:
        events = Event.query.all()
        events_data = [
            {
                "id": e.id, 
                "name": e.name, 
                "description": e.description,
                "scenario_id": e.scenario_id,
                "scenario_name": e.scenario.name if e.scenario else None,
                "type": "action" if isinstance(e, Action) else "event",
                "created_at": e.created_at.isoformat() if hasattr(e, 'created_at') and e.created_at else None
            } for e in events
        ]
        return jsonify({"status": "success", "events": events_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@events_bp.route('/api/actions')
def api_list_actions():
    """
    API endpoint to list all actions.
    
    Returns:
        JSON response with actions
    """
    try:
        actions = Action.query.all()
        actions_data = [
            {
                "id": a.id, 
                "name": a.name, 
                "description": a.description,
                "scenario_id": a.scenario_id,
                "scenario_name": a.scenario.name if a.scenario else None,
                "created_at": a.created_at.isoformat() if hasattr(a, 'created_at') and a.created_at else None
            } for a in actions
        ]
        return jsonify({"status": "success", "actions": actions_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
