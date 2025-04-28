from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required
from app.services.llm_service import LLMService, Conversation, Message
from app.services.claude_service import ClaudeService
from app.services.application_context_service import ApplicationContextService
from app.services.enhanced_mcp_client import get_enhanced_mcp_client
from app.models.world import World
from app.models.ontology import Ontology
import json
import os

# Create blueprint
ontology_agent_bp = Blueprint('ontology_agent', __name__, url_prefix='/agent/ontology')

# Initialize services
llm_service = LLMService()

# Initialize Enhanced MCP client
mcp_client = get_enhanced_mcp_client()

# Initialize Claude service with API key
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set. Please set it to use ClaudeService.")
claude_service = ClaudeService(api_key=api_key)

# Service selection flag - set to 'claude' to use Claude, 'langchain' to use LangChain
active_service = 'claude'  # Default to Claude

@ontology_agent_bp.route('/', methods=['GET'])
def ontology_agent_window():
    """Display the ontology agent window."""
    # Get world_id from query parameters if provided
    world_id = request.args.get('world_id', type=int)
    
    # Get ontology_id from query parameters if provided
    ontology_id = request.args.get('ontology_id', type=int)

    # Get list of worlds for the dropdown
    worlds = World.query.all()
    
    # Get list of ontologies for the dropdown
    ontologies = Ontology.query.all()

    # Get the selected world if world_id is provided
    selected_world = None
    if world_id:
        selected_world = World.query.get(world_id)
        
    # Get the selected ontology if ontology_id is provided
    selected_ontology = None
    if ontology_id:
        selected_ontology = Ontology.query.get(ontology_id)

    # Initialize conversation in session if not already present
    if 'ontology_conversation' not in session:
        session['ontology_conversation'] = json.dumps({
            'messages': [
                {
                    'content': 'Hello! I am your ontology assistant. Choose a world or ontology to explore and ask questions about the ontology structure, entities, and relationships.',
                    'role': 'assistant',
                    'timestamp': None
                }
            ],
            'metadata': {'world_id': world_id, 'ontology_id': ontology_id}
        })

    return render_template('ontology_agent_window.html', 
                          worlds=worlds, 
                          ontologies=ontologies,
                          selected_world=selected_world,
                          selected_ontology=selected_ontology)

@ontology_agent_bp.route('/api/message', methods=['POST'])
def send_message():
    """Send a message to the ontology agent."""
    data = request.json

    # Get message and context parameters from request
    message = data.get('message', '')
    world_id = data.get('world_id')
    ontology_id = data.get('ontology_id')

    # Get conversation from session
    conversation_data = json.loads(session.get('ontology_conversation', '{}'))
    conversation = Conversation.from_dict(conversation_data)

    # Update metadata if provided
    if world_id is not None:
        conversation.metadata['world_id'] = world_id
    if ontology_id is not None:
        conversation.metadata['ontology_id'] = ontology_id

    # Get application context
    app_context_service = ApplicationContextService.get_instance()
    context = app_context_service.get_full_context(
        world_id=conversation.metadata.get('world_id'),
        query=message
    )

    # Add ontology-specific context
    ontology_source = None
    if ontology_id:
        # Get ontology from database
        ontology = Ontology.query.get(ontology_id)
        if ontology:
            ontology_source = ontology.domain_id
    elif world_id:
        # Get world from database to find associated ontology
        world = World.query.get(world_id)
        if world and world.ontology_source:
            ontology_source = world.ontology_source
    
    # Add ontology context if we found a source
    if ontology_source:
        # Get ontology entities and structure from the enhanced MCP client
        try:
            # Get roles
            roles_result = mcp_client.get_entities(ontology_source, 'roles')
            if roles_result and 'roles' in roles_result:
                context['ontology_roles'] = roles_result['roles']
            
            # Get capabilities
            capabilities_result = mcp_client.get_entities(ontology_source, 'capabilities')
            if capabilities_result and 'capabilities' in capabilities_result:
                context['ontology_capabilities'] = capabilities_result['capabilities']
                
            # Get other entity types
            entity_types = ['conditions', 'resources', 'events', 'actions']
            for entity_type in entity_types:
                entities_result = mcp_client.get_entities(ontology_source, entity_type)
                if entities_result and entity_type in entities_result:
                    context[f'ontology_{entity_type}'] = entities_result[entity_type]
            
            # Get guidelines
            guidelines = mcp_client.get_ontology_guidelines(ontology_source)
            if guidelines:
                context['ontology_guidelines'] = guidelines
                
            # Perform a search based on the user's message to find relevant entities
            search_results = mcp_client.search_entities(ontology_source, message)
            if search_results and 'entities' in search_results:
                context['ontology_search_results'] = search_results['entities']
                
        except Exception as e:
            print(f"Error getting ontology context: {str(e)}")
    
    # Format context for LLM
    formatted_context = app_context_service.format_context_for_llm(context)
    
    # Add specific guidance for the ontology agent
    ontology_guidelines = """
    As an ontology assistant, help the user understand the structure and relationships in the ontology. You can:
    1. Explain entity types (roles, capabilities, conditions, resources, events, actions)
    2. Describe relationships between entities
    3. Show how different ontology elements connect to each other
    4. Use the ontology to answer domain-specific questions
    5. Explain how the ontology can be used to model real-world scenarios
    
    Base your responses on the provided ontology context and entity information.
    """
    
    formatted_context += "\n\n" + ontology_guidelines

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
    session['ontology_conversation'] = json.dumps(conversation.to_dict())

    # Return response
    return jsonify({
        'status': 'success',
        'message': response.to_dict()
    })

@ontology_agent_bp.route('/api/reset', methods=['POST'])
def reset_conversation():
    """Reset the conversation."""
    # Get parameters from request
    data = request.json
    world_id = data.get('world_id')
    ontology_id = data.get('ontology_id')

    # Initialize new conversation
    session['ontology_conversation'] = json.dumps({
        'messages': [
            {
                'content': 'Hello! I am your ontology assistant. Choose a world or ontology to explore and ask questions about the ontology structure, entities, and relationships.',
                'role': 'assistant',
                'timestamp': None
            }
        ],
        'metadata': {'world_id': world_id, 'ontology_id': ontology_id}
    })

    # Return success
    return jsonify({
        'status': 'success',
        'message': 'Conversation reset successfully'
    })

@ontology_agent_bp.route('/api/suggestions', methods=['POST'])
def get_suggestions():
    """Get conversation prompt suggestions."""
    # Get parameters from request
    data = request.json
    world_id = data.get('world_id')
    ontology_id = data.get('ontology_id')
    
    # Determine ontology source
    ontology_source = None
    if ontology_id:
        ontology = Ontology.query.get(ontology_id)
        if ontology:
            ontology_source = ontology.domain_id
    elif world_id:
        world = World.query.get(world_id)
        if world:
            ontology_source = world.ontology_source
    
    # Default suggestions
    suggestions = [
        {"id": 1, "text": "What entities are defined in this ontology?"},
        {"id": 2, "text": "How are roles and capabilities related in this ontology?"},
        {"id": 3, "text": "Explain the structure of this ontology"}
    ]
    
    # Add ontology-specific suggestions if we have a source
    if ontology_source:
        try:
            # Get entity counts to inform suggestions
            entities = mcp_client.get_entities(ontology_source, 'all')
            
            # Add entity-specific suggestions based on what's available
            if entities:
                if entities.get('roles', []):
                    suggestions.append({"id": 4, "text": f"What roles are defined in this ontology?"})
                    if len(entities.get('roles', [])) > 0:
                        first_role = entities['roles'][0]['label']
                        suggestions.append({"id": 5, "text": f"Tell me about the {first_role} role"})
                        
                if entities.get('capabilities', []):
                    suggestions.append({"id": 6, "text": f"What capabilities are defined in this ontology?"})
                    
                if entities.get('events', []):
                    suggestions.append({"id": 7, "text": f"What events are represented in this ontology?"})
                    
                if entities.get('actions', []):
                    suggestions.append({"id": 8, "text": f"Explain the actions in this ontology"})
                    
            # Try to get guidelines to inform suggestions    
            guidelines = mcp_client.get_ontology_guidelines(ontology_source)
            if guidelines:
                suggestions.append({"id": 9, "text": "What guidelines are associated with this ontology?"})
        
        except Exception as e:
            print(f"Error generating ontology suggestions: {str(e)}")
    
    # Return suggestions (max 5)
    return jsonify({
        'status': 'success',
        'suggestions': suggestions[:5]
    })

@ontology_agent_bp.route('/api/entities', methods=['GET'])
def get_entities():
    """Get entities from an ontology."""
    # Get parameters from request
    world_id = request.args.get('world_id', type=int)
    ontology_id = request.args.get('ontology_id', type=int)
    entity_type = request.args.get('entity_type', 'all')
    
    # Determine ontology source
    ontology_source = None
    if ontology_id:
        ontology = Ontology.query.get(ontology_id)
        if ontology:
            ontology_source = ontology.domain_id
    elif world_id:
        world = World.query.get(world_id)
        if world:
            ontology_source = world.ontology_source
    
    if not ontology_source:
        return jsonify({
            'status': 'error',
            'message': 'No ontology source could be determined'
        }), 400
    
    try:
        # Get entities from MCP client
        entities = mcp_client.get_entities(ontology_source, entity_type)
        
        return jsonify({
            'status': 'success',
            'entities': entities
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error getting entities: {str(e)}'
        }), 500
