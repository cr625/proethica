from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required
from app.services.llm_service import LLMService, Conversation, Message
from app.models.world import World
import json

# Create blueprint
agent_bp = Blueprint('agent', __name__, url_prefix='/agent')

# Initialize LLM service
llm_service = LLMService()

@agent_bp.route('/', methods=['GET'])
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
                    'content': 'Hello! I am your AI assistant for ethical decision-making. How can I help you today?',
                    'role': 'assistant',
                    'timestamp': None
                }
            ],
            'metadata': {'world_id': world_id}
        })
    
    # This will be our hidden route that requires the URL to access
    return render_template('agent_window.html', worlds=worlds, selected_world=selected_world)

@agent_bp.route('/api/message', methods=['POST'])
def send_message():
    """Send a message to the agent."""
    data = request.json
    
    # Get message and world_id from request
    message = data.get('message', '')
    world_id = data.get('world_id')
    
    # Get conversation from session
    conversation_data = json.loads(session.get('conversation', '{}'))
    conversation = Conversation.from_dict(conversation_data)
    
    # Update world_id in metadata if provided
    if world_id is not None:
        conversation.metadata['world_id'] = world_id
    
    # Send message to LLM service
    response = llm_service.send_message(
        message=message,
        conversation=conversation,
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
    
    # Get prompt options from LLM service
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
def reset_conversation():
    """Reset the conversation."""
    # Get world_id from request
    data = request.json
    world_id = data.get('world_id')
    
    # Initialize new conversation
    session['conversation'] = json.dumps({
        'messages': [
            {
                'content': 'Hello! I am your AI assistant for ethical decision-making. How can I help you today?',
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
def get_guidelines():
    """Get guidelines for a specific world."""
    # Get world_id from query parameters
    world_id = request.args.get('world_id', type=int)
    
    if not world_id:
        return jsonify({
            'status': 'error',
            'message': 'World ID is required'
        }), 400
    
    # Get guidelines from LLM service
    guidelines = llm_service.get_guidelines_for_world(world_id=world_id)
    
    # Return guidelines
    return jsonify({
        'status': 'success',
        'guidelines': guidelines
    })
