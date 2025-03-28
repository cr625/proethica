"""
Routes for the simulation feature.

This module provides functionality for simulating scenarios.
"""

import logging
import json
import re
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session, current_app
from app.models.scenario import Scenario
from app.services.simulation_controller import SimulationController
from app.services.embedding_service import EmbeddingService
from app.services.langchain_claude import LangChainClaudeService
from app.services.agent_orchestrator import AgentOrchestrator
from app.utils.template_helpers import render_llm_analysis

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
        # Include all messages in startup, including initialization
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

@simulation_bp.route('/api/analyze', methods=['POST'])
def analyze_decision():
    """Analyze a decision in a simulation using the LLM."""
    data = request.json
    scenario_id = data.get('scenario_id')
    session_id = data.get('session_id') or session.get('simulation_session_id')
    timeline_index = data.get('timeline_index')
    
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
    
    if timeline_index is None:
        return jsonify({
            'status': 'error',
            'message': 'Missing timeline_index parameter'
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
    
    try:
        # Get the timeline item directly from the simulation state
        # This ensures we're using the same state that the frontend is displaying
        timeline_items = state.get('timeline_items', [])
        
        # Find the decision at the specified timeline index
        if timeline_index < 0 or timeline_index >= len(timeline_items):
            return jsonify({
                'status': 'error',
                'message': f'Timeline index out of range: {timeline_index}'
            }), 400
        
        current_item = timeline_items[timeline_index]
        
        # Verify this is a decision
        if not current_item.get('is_decision', False):
            return jsonify({
                'status': 'error',
                'message': f'Item at timeline index {timeline_index} is not a decision'
            }), 400
        
        # Get the decision item data
        decision_data = current_item.get('data', {})
        decision_text = decision_data.get('description', 'Decision point')
        
        # Get the options
        options = []
        if 'options' in decision_data and decision_data['options']:
            # Format options from the decision data
            for i, option in enumerate(decision_data['options']):
                option_text = option
                if isinstance(option, dict) and 'description' in option:
                    option_text = option['description']
                
                options.append({
                    'id': i + 1,
                    'text': option_text
                })
        else:
            # Generate options using the controller
            options = controller._generate_decision_options(current_item, controller.claude_service.create_conversation(), "")
        
        # Process the decision with the LLM to get analysis
        from app.services.llm_service import Conversation
        conversation = Conversation()
        
        # Get the scenario
        scenario = Scenario.query.get(scenario_id)
        
        # Craft a detailed prompt for analysis
        status_callback("Analyzing decision with LLM...")
        message = f"""
        Please analyze the following decision point in the context of ethical decision-making:
        
        DECISION: {decision_text}
        
        OPTIONS:
        {", ".join(opt["text"] for opt in options)}
        
        For each option, provide:
        1. The key ethical considerations
        2. Potential consequences (both positive and negative)
        3. A balanced recommendation
        
        Keep your analysis practical, thorough, and accessible.
        """
        
        try:
            # Use the appropriate service for processing
            if controller.use_claude:
                response = controller.claude_service.send_message(
                    message=message,
                    conversation=conversation,
                    world_id=scenario.world_id
                )
                analysis_text = response.content
            else:
                response = controller.llm_service.send_message(
                    message=message,
                    conversation=conversation,
                    world_id=scenario.world_id
                )
                analysis_text = response.content
            
            # Render the analysis through our template for better formatting
            analysis_html = render_llm_analysis(
                analysis_text,
                scenario_id=scenario_id,
                title=f"Analysis of Decision: {decision_text}"
            )
            
            status_callback("LLM analysis complete")
        except Exception as e:
            logger.error(f"Error processing with LLM: {str(e)}")
            status_callback("Error in LLM processing, using fallback analysis")
            # Fallback analysis if LLM processing fails
            analysis_text = (
                f"Analysis of decision '{decision_text}':\n\n"
                f"This is an important ethical decision. Consider the implications of each option carefully before making your choice."
            )
            
            # Use our template rendering for the fallback text as well
            analysis_html = render_llm_analysis(
                analysis_text,
                scenario_id=scenario_id,
                title=f"Analysis of Decision: {decision_text}"
            )
        
        return jsonify({
            'status': 'success',
            'analysis': analysis_html,
            'options': options,
            'status_messages': status_messages
        })
            
    except Exception as e:
        logger.error(f"Error analyzing decision: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error analyzing decision: {str(e)}"
        }), 500

# Text formatting utility function
def format_llm_text(text, formatting_options=None):
    """
    Apply consistent formatting to LLM output text.
    
    Args:
        text (str): The text to format
        formatting_options (dict, optional): Dictionary of formatting options
            - bold_options (bool): Whether to make "Option X" labels bold (default: True)
            - option_paragraphs (bool): Whether to ensure options are in separate paragraphs (default: False)
            - add_html_paragraphs (bool): Whether to wrap paragraphs in <p> tags (default: False)
            
    Returns:
        str: The formatted text
    """
    if formatting_options is None:
        formatting_options = {}
    
    # Set default formatting options
    bold_options = formatting_options.get('bold_options', True)
    option_paragraphs = formatting_options.get('option_paragraphs', False)
    add_html_paragraphs = formatting_options.get('add_html_paragraphs', False)
    
    # Step 1: Make option labels bold if requested
    if bold_options:
        text = re.sub(r'(Option \d+)', r'<strong>\1</strong>', text)
    
    # Step 2: Ensure options are in separate paragraphs if requested
    if option_paragraphs:
        # Split the text into lines
        lines = text.split('\n')
        result_lines = []
        
        for i, line in enumerate(lines):
            # Check if line starts with "Option X" or "<strong>Option X</strong>"
            if (re.match(r'^\s*Option \d+', line) or 
                re.match(r'^\s*<strong>Option \d+</strong>', line)):
                # Add a blank line before if it's not the first line and the previous line isn't already blank
                if i > 0 and lines[i-1].strip():
                    result_lines.append('')
                
                # Add the current line
                result_lines.append(line)
            else:
                # Just add the line as is
                result_lines.append(line)
        
        # Join the lines back together
        text = '\n'.join(result_lines)
    
    # Step 3: Add HTML paragraph tags if requested
    if add_html_paragraphs:
        # Split text into paragraphs
        paragraphs = re.split(r'\n\n+', text)
        # Wrap each paragraph in <p> tags
        paragraphs = [f'<p>{p}</p>' for p in paragraphs]
        # Join back together
        text = ''.join(paragraphs)
    
    return text

@simulation_bp.route('/api/format_text', methods=['POST'])
def format_text():
    """Format text from LLM or other sources with consistent styling."""
    data = request.json
    
    if not data or 'text' not in data:
        return jsonify({
            'status': 'error',
            'message': 'Missing text parameter'
        }), 400
    
    text = data.get('text', '')
    formatting_options = data.get('formatting_options', {})
    
    # Apply formatting to the text
    formatted_text = format_llm_text(text, formatting_options)
    
    return jsonify({
        'status': 'success',
        'formatted_text': formatted_text
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
