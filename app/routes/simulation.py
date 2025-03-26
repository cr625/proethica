"""
Routes for the simulation feature.

This module provides functionality for simulating scenarios.
"""

import logging
import json
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session
from app.models.scenario import Scenario
from app.services.simulation_controller import SimulationController

# Set up logging
logger = logging.getLogger(__name__)

# Create blueprint
simulation_bp = Blueprint('simulation', __name__, url_prefix='/simulation')

@simulation_bp.route('/scenario/<int:id>', methods=['GET'])
def simulate_scenario(id):
    """Display simulation interface for a scenario."""
    # Get the scenario
    scenario = Scenario.query.get_or_404(id)
    
    # Render the simulation template with the scenario data
    return render_template('simulate_scenario.html', scenario=scenario)

@simulation_bp.route('/api/start', methods=['POST'])
def start_simulation():
    """Start a simulation."""
    data = request.json
    scenario_id = data.get('scenario_id')
    
    if not scenario_id:
        return jsonify({
            'status': 'error',
            'message': 'Missing scenario_id parameter'
        }), 400
    
    # Create a simulation controller
    controller = SimulationController(scenario_id)
    
    # Start the simulation
    result = controller.start_simulation()
    
    # Store session ID in Flask session
    session['simulation_session_id'] = result['state']['session_id']
    
    return jsonify({
        'status': 'success',
        'message': result['message'],
        'session_id': result['state']['session_id'],
        'is_decision': result.get('is_decision', False),
        'options': result.get('options', [])
    })

@simulation_bp.route('/api/advance', methods=['POST'])
def advance_simulation():
    """Advance a simulation."""
    data = request.json
    scenario_id = data.get('scenario_id')
    session_id = data.get('session_id') or session.get('simulation_session_id')
    
    if not scenario_id:
        return jsonify({
            'status': 'error',
            'message': 'Missing scenario_id parameter'
        }), 400
    
    if not session_id:
        return jsonify({
            'status': 'error',
            'message': 'Missing session_id parameter'
        }), 400
    
    # Create a simulation controller
    controller = SimulationController(scenario_id)
    
    # Load state from storage
    state = controller.get_state(session_id)
    if not state:
        return jsonify({
            'status': 'error',
            'message': f'No simulation state found for session ID: {session_id}'
        }), 404
    
    # Advance the simulation
    result = controller.advance_simulation()
    
    return jsonify({
        'status': 'success',
        'message': result['message'],
        'is_decision': result.get('is_decision', False),
        'options': result.get('options', [])
    })

@simulation_bp.route('/api/decide', methods=['POST'])
def make_decision():
    """Make a decision in a simulation."""
    data = request.json
    scenario_id = data.get('scenario_id')
    session_id = data.get('session_id') or session.get('simulation_session_id')
    decision_index = data.get('decision_index')
    
    if not scenario_id:
        return jsonify({
            'status': 'error',
            'message': 'Missing scenario_id parameter'
        }), 400
    
    if not session_id:
        return jsonify({
            'status': 'error',
            'message': 'Missing session_id parameter'
        }), 400
    
    if decision_index is None:
        return jsonify({
            'status': 'error',
            'message': 'Missing decision_index parameter'
        }), 400
    
    # Create a simulation controller
    controller = SimulationController(scenario_id)
    
    # Load state from storage
    state = controller.get_state(session_id)
    if not state:
        return jsonify({
            'status': 'error',
            'message': f'No simulation state found for session ID: {session_id}'
        }), 404
    
    # Make the decision
    result = controller.make_decision(decision_index)
    
    return jsonify({
        'status': 'success',
        'message': result['message'],
        'is_decision': result.get('is_decision', False),
        'options': result.get('options', [])
    })

@simulation_bp.route('/api/reset', methods=['POST'])
def reset_simulation():
    """Reset a simulation."""
    data = request.json
    scenario_id = data.get('scenario_id')
    
    if not scenario_id:
        return jsonify({
            'status': 'error',
            'message': 'Missing scenario_id parameter'
        }), 400
    
    # Create a simulation controller
    controller = SimulationController(scenario_id)
    
    # Reset the simulation
    result = controller.reset_simulation()
    
    # Store new session ID in Flask session
    session['simulation_session_id'] = result['state']['session_id']
    
    return jsonify({
        'status': 'success',
        'message': result['message'],
        'session_id': result['state']['session_id'],
        'is_decision': result.get('is_decision', False),
        'options': result.get('options', [])
    })
