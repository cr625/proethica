"""
Routes for the simulation feature.

This module provides functionality for simulating scenarios.
"""

import logging
import json
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session, current_app
from app.models.scenario import Scenario
from app.services.simulation_controller import SimulationController
from app.services.embedding_service import EmbeddingService
from app.services.langchain_claude import LangChainClaudeService
from app.services.agent_orchestrator import AgentOrchestrator

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
    
    # Get agent orchestrator config
    use_agent_orchestrator = current_app.config.get('USE_AGENT_ORCHESTRATOR', False)
    
    # Status messages list to capture status updates
    status_messages = []
    
    # Status callback function
    def status_callback(message):
        status_messages.append(message)
    
    # Create a simulation controller with status callback
    controller = SimulationController(
        scenario_id=scenario_id,
        use_agent_orchestrator=use_agent_orchestrator,
        status_callback=status_callback
    )
    
    # Start the simulation
    result = controller.start_simulation()
    
    # Store session ID in Flask session
    session['simulation_session_id'] = result['state']['session_id']
    
    return jsonify({
        'status': 'success',
        'message': result['message'],
        'session_id': result['state']['session_id'],
        'is_decision': result.get('is_decision', False),
        'options': result.get('options', []),
        'status_messages': status_messages
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
    
    # Get agent orchestrator config
    use_agent_orchestrator = current_app.config.get('USE_AGENT_ORCHESTRATOR', False)
    
    # Status messages list to capture status updates
    status_messages = []
    
    # Status callback function
    def status_callback(message):
        status_messages.append(message)
    
    # Create a simulation controller with status callback
    controller = SimulationController(
        scenario_id=scenario_id,
        use_agent_orchestrator=use_agent_orchestrator,
        status_callback=status_callback
    )
    
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
        'options': result.get('options', []),
        'status_messages': status_messages
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
    
    # Get agent orchestrator config
    use_agent_orchestrator = current_app.config.get('USE_AGENT_ORCHESTRATOR', False)
    
    # Status messages list to capture status updates
    status_messages = []
    
    # Status callback function
    def status_callback(message):
        status_messages.append(message)
    
    # Create a simulation controller with status callback
    controller = SimulationController(
        scenario_id=scenario_id,
        use_agent_orchestrator=use_agent_orchestrator,
        status_callback=status_callback
    )
    
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
        'options': result.get('options', []),
        'status_messages': status_messages
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
    
    # Get agent orchestrator config
    use_agent_orchestrator = current_app.config.get('USE_AGENT_ORCHESTRATOR', False)
    
    # Create a simulation controller
    controller = SimulationController(
        scenario_id=scenario_id,
        use_agent_orchestrator=use_agent_orchestrator
    )
    
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

@simulation_bp.route('/api/test_agents/<int:scenario_id>', methods=['GET'])
def test_agents(scenario_id):
    """Test the agent-based decision processing."""
    # Get the scenario
    scenario = Scenario.query.get_or_404(scenario_id)
    
    # Create a test decision
    decision_text = "How should the ethical dilemma in this scenario be resolved?"
    
    # Create test options
    options = [
        "Option 1: Prioritize safety and transparency",
        "Option 2: Balance competing interests",
        "Option 3: Follow established protocols",
        "Option 4: Seek additional guidance"
    ]
    
    # Extract scenario data
    scenario_data = {
        'id': scenario.id,
        'name': scenario.name,
        'description': scenario.description,
        'world_id': scenario.world_id
    }
    
    # Initialize services
    embedding_service = EmbeddingService()
    langchain_claude = LangChainClaudeService.get_instance()
    
    # Initialize agent orchestrator
    agent_orchestrator = AgentOrchestrator(
        embedding_service=embedding_service,
        langchain_claude=langchain_claude,
        world_id=scenario.world_id
    )
    
    # Process with agent orchestrator
    try:
        result = agent_orchestrator.process_decision(
            scenario_data=scenario_data,
            decision_text=decision_text,
            options=options
        )
        
        # Create a simulation controller with agent orchestrator
        controller_with_agents = SimulationController(
            scenario_id=scenario_id,
            use_agent_orchestrator=True
        )
        
        # Create a simulation controller without agent orchestrator
        controller_without_agents = SimulationController(
            scenario_id=scenario_id,
            use_agent_orchestrator=False
        )
        
        return render_template(
            'agent_test_results.html',
            scenario=scenario,
            decision_text=decision_text,
            options=options,
            agent_results=result,
            controller_with_agents=controller_with_agents is not None,
            controller_without_agents=controller_without_agents is not None
        )
    except Exception as e:
        logger.error(f"Error testing agents: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error testing agents: {str(e)}"
        }), 500
