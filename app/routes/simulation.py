"""
Routes for the simulation feature.

This module provides routes for initializing, running, and saving simulation sessions.
"""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import current_user, login_required
from app import db
from app.models import Scenario, Character, SimulationSession
from app.services.simulation_controller import SimulationController
from app.services.simulation_storage import SimulationStorage

# Set up logging
logger = logging.getLogger(__name__)

# Create blueprint
simulation_bp = Blueprint('simulation', __name__, url_prefix='/simulation')

@simulation_bp.route('/scenario/<int:id>', methods=['GET'])
def simulate_scenario(id):
    """Display simulation interface for a scenario."""
    scenario = Scenario.query.get_or_404(id)
    
    # Get characters for the scenario
    characters = Character.query.filter_by(scenario_id=id).all()
    
    return render_template(
        'simulate_scenario.html', 
        scenario=scenario,
        characters=characters
    )

@simulation_bp.route('/scenario/<int:id>/initialize', methods=['POST'])
def initialize_simulation(id):
    """Initialize a simulation session."""
    scenario = Scenario.query.get_or_404(id)
    data = request.json or {}
    
    try:
        # Create simulation controller
        controller = SimulationController(
            scenario_id=id,
            selected_character_id=data.get('character_id'),
            perspective=data.get('perspective', 'specific')
        )
        
        # Initialize simulation
        initial_state = controller.initialize_simulation()
        
        # Store the state in the simulation storage
        sim_session_id = SimulationStorage.store_state(initial_state)
        
        # Store minimal information in the session
        session['simulation'] = {
            'scenario_id': id,
            'selected_character_id': data.get('character_id'),
            'perspective': data.get('perspective', 'specific'),
            'initialized': True,
            'session_id': sim_session_id
        }
        
        # Initialize session data for later saving
        session['simulation_data'] = {
            'scenario_id': id,
            'timestamps': [datetime.now().isoformat()]
        }
        
        return jsonify({
            'success': True,
            'initial_state': initial_state,
            'session_id': sim_session_id
        })
    except Exception as e:
        logger.error(f"Error initializing simulation: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error initializing simulation: {str(e)}"
        }), 500

@simulation_bp.route('/scenario/<int:id>/decision', methods=['POST'])
def process_decision(id):
    """Process a decision in the simulation."""
    scenario = Scenario.query.get_or_404(id)
    data = request.json or {}
    
    # Check if simulation is initialized
    if 'simulation' not in session or not session['simulation'].get('initialized'):
        return jsonify({
            'success': False,
            'message': 'Simulation not initialized'
        }), 400
    
    try:
        # Get the simulation session ID
        sim_session_id = session['simulation'].get('session_id')
        if not sim_session_id:
            return jsonify({
                'success': False,
                'message': 'Simulation session ID not found'
            }), 400
        
        # Get the current state from storage
        current_state = SimulationStorage.get_state(sim_session_id)
        if not current_state:
            return jsonify({
                'success': False,
                'message': 'Simulation state not found or expired'
            }), 400
        
        # Recreate the controller
        controller = SimulationController(
            scenario_id=session['simulation']['scenario_id'],
            selected_character_id=session['simulation']['selected_character_id'],
            perspective=session['simulation']['perspective']
        )
        
        # Set the current state
        controller.current_state = current_state
        
        # Process decision
        next_state, evaluation = controller.process_decision(data)
        
        # Store the updated state
        SimulationStorage.store_state(next_state, sim_session_id)
        
        # Update minimal data for later saving
        if 'simulation_data' not in session:
            session['simulation_data'] = {
                'scenario_id': id,
                'decision_count': 0,
                'timestamps': [datetime.now().isoformat()]
            }
        
        # Increment decision count
        session['simulation_data']['decision_count'] = session['simulation_data'].get('decision_count', 0) + 1
        session['simulation_data']['timestamps'].append(datetime.now().isoformat())
        
        return jsonify({
            'success': True,
            'next_state': next_state,
            'evaluation': evaluation
        })
    except Exception as e:
        logger.error(f"Error processing decision: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error processing decision: {str(e)}"
        }), 500

@simulation_bp.route('/scenario/<int:id>/advance', methods=['POST'])
def advance_simulation(id):
    """Advance to the next event in the simulation."""
    scenario = Scenario.query.get_or_404(id)
    
    # Check if simulation is initialized
    if 'simulation' not in session or not session['simulation'].get('initialized'):
        return jsonify({
            'success': False,
            'message': 'Simulation not initialized'
        }), 400
    
    try:
        # Get the simulation session ID
        sim_session_id = session['simulation'].get('session_id')
        if not sim_session_id:
            return jsonify({
                'success': False,
                'message': 'Simulation session ID not found'
            }), 400
        
        # Get the current state from storage
        current_state = SimulationStorage.get_state(sim_session_id)
        if not current_state:
            return jsonify({
                'success': False,
                'message': 'Simulation state not found or expired'
            }), 400
        
        # Recreate the controller
        controller = SimulationController(
            scenario_id=session['simulation']['scenario_id'],
            selected_character_id=session['simulation']['selected_character_id'],
            perspective=session['simulation']['perspective']
        )
        
        # Set the current state
        controller.current_state = current_state
        
        # Advance to the next event
        next_state = controller._advance_timeline(controller.current_state)
        
        # Ensure decisions are attached to events
        if 'decision_history' in next_state:
            for history_item in next_state['decision_history']:
                event_index = history_item['event_index']
                if event_index < len(next_state['events']):
                    # Attach decision and evaluation to the event
                    next_state['events'][event_index]['decision'] = history_item['decision']
                    next_state['events'][event_index]['evaluation'] = history_item['evaluation']
        
        # Store the updated state
        SimulationStorage.store_state(next_state, sim_session_id)
        
        # Update minimal data for later saving
        if 'simulation_data' not in session:
            session['simulation_data'] = {
                'scenario_id': id,
                'event_count': 0,
                'timestamps': [datetime.now().isoformat()]
            }
        
        # Increment event count
        session['simulation_data']['event_count'] = session['simulation_data'].get('event_count', 0) + 1
        session['simulation_data']['timestamps'].append(datetime.now().isoformat())
        
        return jsonify({
            'success': True,
            'next_state': next_state
        })
    except Exception as e:
        logger.error(f"Error advancing simulation: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error advancing simulation: {str(e)}"
        }), 500

@simulation_bp.route('/scenario/<int:id>/save', methods=['POST'])
@login_required
def save_simulation(id):
    """Save a simulation session."""
    scenario = Scenario.query.get_or_404(id)
    
    # Check if simulation is initialized
    if 'simulation' not in session or not session['simulation'].get('initialized'):
        return jsonify({
            'success': False,
            'message': 'Simulation not initialized'
        }), 400
    
    try:
        # Get the simulation session ID
        sim_session_id = session['simulation'].get('session_id')
        if not sim_session_id:
            return jsonify({
                'success': False,
                'message': 'Simulation session ID not found'
            }), 400
        
        # Get the current state from storage
        current_state = SimulationStorage.get_state(sim_session_id)
        if not current_state:
            return jsonify({
                'success': False,
                'message': 'Simulation state not found or expired'
            }), 400
        
        # Prepare session data for saving
        session_data = {
            'scenario_id': id,
            'selected_character_id': session['simulation'].get('selected_character_id'),
            'perspective': session['simulation'].get('perspective'),
            'final_state': current_state,
            'event_count': session['simulation_data'].get('event_count', 0),
            'decision_count': session['simulation_data'].get('decision_count', 0),
            'timestamps': session['simulation_data'].get('timestamps', [datetime.now().isoformat()])
        }
        
        # Create a new session record
        simulation_session = SimulationSession(
            scenario_id=id,
            user_id=current_user.id,
            session_data=session_data,
            created_at=datetime.now()
        )
        
        # Save to database
        db.session.add(simulation_session)
        db.session.commit()
        
        # Clear simulation data from session
        session.pop('simulation_data', None)
        
        # Remove the state from storage
        SimulationStorage.remove_state(sim_session_id)
        
        return jsonify({
            'success': True,
            'session_id': simulation_session.id
        })
    except Exception as e:
        logger.error(f"Error saving simulation: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error saving simulation: {str(e)}"
        }), 500

@simulation_bp.route('/sessions', methods=['GET'])
@login_required
def list_sessions():
    """List simulation sessions for the current user."""
    # Get sessions for the current user
    sessions = SimulationSession.query.filter_by(user_id=current_user.id).order_by(SimulationSession.created_at.desc()).all()
    
    return render_template(
        'simulation_sessions.html',
        sessions=sessions
    )

@simulation_bp.route('/sessions/<int:id>', methods=['GET'])
@login_required
def view_session(id):
    """View a simulation session."""
    # Get the session
    session_record = SimulationSession.query.get_or_404(id)
    
    # Check if the session belongs to the current user
    if session_record.user_id != current_user.id:
        flash('You do not have permission to view this session', 'danger')
        return redirect(url_for('simulation.list_sessions'))
    
    return render_template(
        'simulation_session_detail.html',
        session=session_record
    )
