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
        
        # Store controller in session
        # Note: We can't store the controller object directly in the session
        # Instead, we'll store the scenario_id and other parameters, and recreate the controller as needed
        session['simulation'] = {
            'scenario_id': id,
            'selected_character_id': data.get('character_id'),
            'perspective': data.get('perspective', 'specific'),
            'initialized': True
        }
        
        # Store the current state in the session
        session['simulation_state'] = initial_state
        
        return jsonify({
            'success': True,
            'initial_state': initial_state
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
        # Recreate the controller
        controller = SimulationController(
            scenario_id=session['simulation']['scenario_id'],
            selected_character_id=session['simulation']['selected_character_id'],
            perspective=session['simulation']['perspective']
        )
        
        # Restore the current state
        controller.current_state = session.get('simulation_state', {})
        
        # Process decision
        next_state, evaluation = controller.process_decision(data)
        
        # Update the state in the session
        session['simulation_state'] = next_state
        
        # Store the session data for later saving
        if 'simulation_data' not in session:
            session['simulation_data'] = {
                'states': [controller.current_state],
                'decisions': [],
                'evaluations': [],
                'timestamps': [controller.session_data['timestamps'][0]]
            }
        
        # Add the decision and evaluation to the session data
        session['simulation_data']['states'].append(next_state)
        session['simulation_data']['decisions'].append(data)
        session['simulation_data']['evaluations'].append(evaluation)
        session['simulation_data']['timestamps'].append(controller.session_data['timestamps'][-1])
        
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
        # Create a new session record
        simulation_session = SimulationSession(
            scenario_id=id,
            user_id=current_user.id,
            session_data=session.get('simulation_data', {}),
            created_at=datetime.now()
        )
        
        # Save to database
        db.session.add(simulation_session)
        db.session.commit()
        
        # Clear simulation data from session
        session.pop('simulation_data', None)
        
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
