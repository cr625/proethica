from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required
from app.services.llm_service import LLMService, Conversation, Message
from app.services.claude_service import ClaudeService
from app.services.application_context_service import ApplicationContextService
from app.models.world import World
import json
import os

# Create blueprint
agent_bp = Blueprint('agent', __name__, url_prefix='/agent')

# Initialize services
llm_service = LLMService()

# Initialize Claude service with API key
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set. Please set it to use ClaudeService.")
claude_service = ClaudeService(api_key=api_key)

# Service selection flag - set to 'claude' to use Claude, 'langchain' to use LangChain
active_service = 'claude'  # Default to Claude

@agent_bp.route('/', methods=['GET'])
@login_required
def agent_window():
    """Display the agent window prototype."""
    # Get world_id from query parameters if provided
    world_id = request.args.get('world_id', type=int)
    
    # Get list of worlds for the dropdown
    worlds = World.query.all()
    
    # Get the selected world if world_id is provided
    selected_world = None
    if world_id:
        selected_world = World.query.get(world_id)
    
    # Initialize conversation in session if not already present
    if 'conversation' not in session:
        session['conversation'] = json.dumps({
            'messages': [
                {
                    'content': 'Hello! I am your assistant for ethical decision analysis. Choose a world to generate suggestions or type your message below.',
                    'role': 'assistant',
                    'timestamp': None
                }
            ],
            'metadata': {'world_id': world_id}
        })
    
    # This will be our hidden route that requires the URL to access
    return render_template('agent_window.html', worlds=worlds, selected_world=selected_world)

@agent_bp.route('/api/message', methods=['POST'])
@login_required
def send_message():
    """Send a message to the agent."""
    data = request.json
    
    # Get message and world_id from request
    message = data.get('message', '')
    world_id = data.get('world_id')
    scenario_id = data.get('scenario_id')
    
    # Get conversation from session
    conversation_data = json.loads(session.get('conversation', '{}'))
    conversation = Conversation.from_dict(conversation_data)
    
    # Update metadata if provided
    if world_id is not None:
        conversation.metadata['world_id'] = world_id
    if scenario_id is not None:
        conversation.metadata['scenario_id'] = scenario_id
    
    # Get application context
    app_context_service = ApplicationContextService.get_instance()
    context = app_context_service.get_full_context(
        world_id=conversation.metadata.get('world_id'),
        scenario_id=conversation.metadata.get('scenario_id'),
        query=message
    )
    
    # Format context for LLM
    formatted_context = app_context_service.format_context_for_llm(context)
    
    # Send message to the appropriate service with enhanced context
    if active_service == 'claude':
        response = claude_service.send_message_with_context(
            message=message,
            conversation=conversation,
            application_context=formatted_context,
            world_id=conversation.metadata.get('world_id')
        )
    else:
        response = llm_service.send_message_with_context(
            message=message,
            conversation=conversation,
            application_context=formatted_context,
            world_id=conversation.metadata.get('world_id')
        )
    
    # Update conversation in session
    session['conversation'] = json.dumps(conversation.to_dict())
    
    # Return response
    return jsonify({
        'status': 'success',
        'message': response.to_dict()
    })

@agent_bp.route('/api/options', methods=['GET'])
@login_required
def get_options():
    """Get available prompt options."""
    # Get world_id from query parameters
    world_id = request.args.get('world_id', type=int)
    
    # Get conversation from session
    conversation_data = json.loads(session.get('conversation', '{}'))
    conversation = Conversation.from_dict(conversation_data)
    
    # Update world_id in metadata if provided
    if world_id is not None:
        conversation.metadata['world_id'] = world_id
        # Update conversation in session
        session['conversation'] = json.dumps(conversation.to_dict())
    
    # Get prompt options from the appropriate service based on active_service flag
    if active_service == 'claude':
        options = claude_service.get_prompt_options(
            conversation=conversation,
            world_id=conversation.metadata.get('world_id')
        )
    else:
        options = llm_service.get_prompt_options(
            conversation=conversation,
            world_id=conversation.metadata.get('world_id')
        )
    
    # Return options
    return jsonify({
        'status': 'success',
        'options': options
    })

@agent_bp.route('/api/reset', methods=['POST'])
@login_required
def reset_conversation():
    """Reset the conversation."""
    # Get world_id from request
    data = request.json
    world_id = data.get('world_id')
    
    # Initialize new conversation
    session['conversation'] = json.dumps({
        'messages': [
            {
                'content': 'Hello! I am your assistant for ethical decision analysis. Choose a world to generate suggestions or type your message below.',
                'role': 'assistant',
                'timestamp': None
            }
        ],
        'metadata': {'world_id': world_id}
    })
    
    # Return success
    return jsonify({
        'status': 'success',
        'message': 'Conversation reset successfully'
    })

@agent_bp.route('/api/guidelines', methods=['GET'])
@login_required
def get_guidelines():
    """Get guidelines for a specific world."""
    # Get world_id from query parameters
    world_id = request.args.get('world_id', type=int)
    
    if not world_id:
        return jsonify({
            'status': 'error',
            'message': 'World ID is required'
        }), 400
    
    # Get guidelines from the appropriate service based on active_service flag
    if active_service == 'claude':
        guidelines = claude_service.get_guidelines_for_world(world_id=world_id)
    else:
        guidelines = llm_service.get_guidelines_for_world(world_id=world_id)
    
    # Return guidelines
    return jsonify({
        'status': 'success',
        'guidelines': guidelines
    })

@agent_bp.route('/api/switch_service', methods=['POST'])
@login_required
def switch_service():
    """Switch between Claude and LangChain services."""
    global active_service
    
    data = request.json
    service = data.get('service')
    
    if service not in ['claude', 'langchain']:
        return jsonify({
            'status': 'error',
            'message': 'Invalid service. Must be "claude" or "langchain".'
        }), 400
    
    # Switch the active service
    active_service = service
    
    # Reset the conversation to start fresh with the new service
    world_id = data.get('world_id')
    session['conversation'] = json.dumps({
        'messages': [
            {
                'content': f'Hello! I am your AI assistant for ethical decision-making using the {service} service. How can I help you today?',
                'role': 'assistant',
                'timestamp': None
            }
        ],
        'metadata': {'world_id': world_id}
    })
    
    return jsonify({
        'status': 'success',
        'message': f'Switched to {service} service',
        'active_service': active_service
    })
