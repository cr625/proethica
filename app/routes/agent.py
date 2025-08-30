from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required
from app.services.unified_agent_service import get_unified_agent_service
from app.services.llm_service import Conversation, Message  # Keep for compatibility
from app.services.application_context_service import ApplicationContextService
from app.models.world import World
import json
import os

# Create blueprint
agent_bp = Blueprint('agent', __name__, url_prefix='/agent')

# Initialize unified agent service
unified_agent_service = get_unified_agent_service()

# Service selection flag - now handled by the unified service internally
active_service = 'claude'  # Default preference (unified service handles fallback)

@agent_bp.route('/', methods=['GET'])
@login_required
def agent_window():
    """Display the agent window prototype."""
    # Get world_id from query parameters if provided
    world_id = request.args.get('world_id', type=int)
    
    # Get list of worlds for the dropdown
    worlds = World.query.all()
    
    # Default to engineering world (ID 1) if no world_id is provided and worlds exist
    selected_world = None
    if world_id:
        selected_world = World.query.get(world_id)
    elif worlds:
        # Default to first world (assumed to be engineering world)
        selected_world = worlds[0]
        world_id = selected_world.id
    
    # Initialize conversation in session if not already present
    if 'conversation' not in session:
        session['conversation'] = json.dumps({
            'messages': [
                {
                    'content': 'Hello! I am your assistant for ethical decision analysis analyzing engineering ethics scenarios.',
                    'role': 'assistant',
                    'timestamp': None
                }
            ],
            'metadata': {'world_id': world_id}
        })
    
    # Pass whether to show world selector (only if more than one world)
    show_world_selector = len(worlds) > 1
    
    # This will be our hidden route that requires the URL to access
    return render_template('agent_window.html', worlds=worlds, selected_world=selected_world, show_world_selector=show_world_selector)

@agent_bp.route('/api/message', methods=['POST'])
@login_required
def send_message():
    """Send a message to the agent."""
    data = request.json
    
    # Get message and service preference from request
    message = data.get('message', '')
    world_id = data.get('world_id')
    scenario_id = data.get('scenario_id')
    service = data.get('service', active_service)
    
    # Get conversation from session
    conversation_data = json.loads(session.get('conversation', '{}'))
    conversation = Conversation.from_dict(conversation_data)
    
    # Update metadata if provided
    if world_id is not None:
        conversation.metadata['world_id'] = world_id
    if scenario_id is not None:
        conversation.metadata['scenario_id'] = scenario_id
    
    try:
        # Send message using unified agent service
        response = unified_agent_service.send_message(
            message=message,
            conversation=conversation,
            world_id=conversation.metadata.get('world_id'),
            scenario_id=conversation.metadata.get('scenario_id'),
            service=service
        )
        
        # Update conversation in session
        session['conversation'] = json.dumps(conversation.to_dict())
        
        # Return response
        return jsonify({
            'status': 'success',
            'message': response.to_dict()
        })
        
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        
        # Log the full traceback for debugging
        logger.error(f"Agent message processing failed: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        return jsonify({
            'status': 'error',
            'message': f'Failed to process message: {str(e)}'
        }), 500

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
    
    try:
        # Get prompt options using unified agent service
        options = unified_agent_service.get_prompt_options(
            conversation=conversation,
            world_id=conversation.metadata.get('world_id'),
            service=active_service
        )
        
        # Return options
        return jsonify({
            'status': 'success',
            'options': options
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get prompt options: {str(e)}'
        }), 500

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
    
    try:
        # Get guidelines using unified agent service
        guidelines = unified_agent_service.get_guidelines_for_world(world_id=world_id)
        
        # Return guidelines
        return jsonify({
            'status': 'success',
            'guidelines': guidelines
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get guidelines: {str(e)}'
        }), 500

@agent_bp.route('/api/select-world', methods=['POST'])
@login_required
def select_world():
    """Select a world for the agent context."""
    data = request.json
    world_id = data.get('world_id')
    
    # Update session with selected world
    session['selected_world_id'] = world_id
    
    return jsonify({
        'status': 'success',
        'world_id': world_id
    })

@agent_bp.route('/api/select-service', methods=['POST'])
@login_required
def select_service():
    """Select LLM service preference."""
    global active_service
    
    data = request.json
    service = data.get('service', 'claude')
    
    # Get available providers to validate the selection
    try:
        providers_info = unified_agent_service.get_available_providers()
        available_services = [p['id'] for p in providers_info]
    except Exception:
        # Fallback to basic validation if we can't get providers
        available_services = ['claude', 'openai', 'mock', 'langchain']
    
    if service not in available_services:
        return jsonify({
            'status': 'error',
            'message': f'Invalid service. Available options: {", ".join(available_services)}'
        }), 400
    
    # Update the active service preference
    active_service = service
    
    return jsonify({
        'status': 'success',
        'service': service
    })

@agent_bp.route('/api/suggestions', methods=['POST'])
@login_required
def generate_suggestions():
    """Generate prompt suggestions based on world context."""
    data = request.json
    world_id = data.get('world_id')
    service = data.get('service', active_service)
    
    try:
        # Create empty conversation for suggestion generation
        conversation = Conversation(messages=[])
        
        # Get suggestions using unified agent service
        options = unified_agent_service.get_prompt_options(
            conversation=conversation,
            world_id=world_id,
            service=service
        )
        
        return jsonify({
            'status': 'success',
            'suggestions': options
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to generate suggestions: {str(e)}'
        }), 500

@agent_bp.route('/api/service-info', methods=['GET'])
@login_required
def get_service_info():
    """Get information about the current LLM service configuration."""
    try:
        info = unified_agent_service.get_service_info()
        return jsonify({
            'status': 'success',
            'service_info': info,
            'active_service': active_service
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get service info: {str(e)}'
        }), 500

@agent_bp.route('/api/providers', methods=['GET'])
@login_required
def get_available_providers():
    """Get available LLM providers with their status."""
    try:
        providers_info = unified_agent_service.get_available_providers()
        return jsonify({
            'status': 'success',
            'providers': providers_info,
            'active_service': active_service
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get providers: {str(e)}'
        }), 500

@agent_bp.route('/api/test-mcp-tool', methods=['POST'])
@login_required
def test_mcp_tool():
    """Test MCP tool calls to demonstrate integration."""
    import time
    
    data = request.json
    tool_type = data.get('tool_type', 'entities')
    
    start_time = time.time()
    
    try:
        # Import MCP client to make direct tool calls
        from app.services.mcp_client import MCPClient
        mcp_client = MCPClient.get_instance()
        
        if tool_type == 'entities':
            # Test get_world_entities (shows mock data fallback working)
            result = mcp_client.get_world_entities('engineering_ethics.ttl', 'all')
            # Add context about what this demonstrates
            if isinstance(result, dict):
                result['demo_note'] = 'Shows MCPClient→OntServe integration with mock fallback'
                result['integration_status'] = 'Working (fallback to mock data as designed)'
            tool_name = 'get_world_entities'
            
        elif tool_type == 'domain':
            # Test ontology status (available method)
            result = mcp_client.get_ontology_status('engineering-ethics')
            # Add context about the integration
            if isinstance(result, dict):
                result['demo_note'] = 'Shows ProEthica→MCPClient integration working'
                result['unified_llm_status'] = unified_agent_service.get_service_info()
            tool_name = 'get_ontology_status'
            
        elif tool_type == 'sparql':
            # For SPARQL, show what our unified orchestration system provides
            # Since MCPClient doesn't have SPARQL, demonstrate unified system integration
            try:
                service_info = unified_agent_service.get_service_info()
                result = {
                    "unified_orchestration_available": service_info.get('unified_available', False),
                    "service_type": service_info.get('service_type', 'unknown'),
                    "providers_available": "Mock, Claude (with API key), OpenAI (with API key)",
                    "mcp_integration": "Connected to OntServe on port 8082",
                    "note": "SPARQL queries available through OntServe MCP server tools"
                }
                tool_name = 'unified_orchestration_info'
            except Exception as e:
                result = {"error": str(e)}
                tool_name = 'unified_orchestration_info'
            
        else:
            return jsonify({
                'status': 'error',
                'message': f'Unknown tool type: {tool_type}'
            }), 400
        
        response_time = int((time.time() - start_time) * 1000)
        
        # Format the result for display
        if isinstance(result, dict):
            formatted_data = json.dumps(result, indent=2)
        else:
            formatted_data = str(result)
        
        return jsonify({
            'status': 'success',
            'tool': tool_name,
            'response_time': response_time,
            'data': formatted_data,
            'raw_result': result
        })
        
    except Exception as e:
        response_time = int((time.time() - start_time) * 1000)
        return jsonify({
            'status': 'error',
            'tool': tool_type,
            'response_time': response_time,
            'message': f'MCP tool call failed: {str(e)}',
            'data': f'Error: {str(e)}'
        })
