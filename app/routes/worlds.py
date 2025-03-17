from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from app import db
from app.models.world import World
from app.services.mcp_client import MCPClient
import json

worlds_bp = Blueprint('worlds', __name__, url_prefix='/worlds')

# API endpoints
@worlds_bp.route('/api', methods=['GET'])
def api_get_worlds():
    """API endpoint to get all worlds."""
    worlds = World.query.all()
    return jsonify({
        'success': True,
        'data': [world.to_dict() for world in worlds]
    })

@worlds_bp.route('/api/<int:id>', methods=['GET'])
def api_get_world(id):
    """API endpoint to get a specific world by ID."""
    world = World.query.get_or_404(id)
    return jsonify({
        'success': True,
        'data': world.to_dict()
    })

# Web routes
@worlds_bp.route('/', methods=['GET'])
def list_worlds():
    """Display all worlds."""
    worlds = World.query.all()
    return render_template('worlds.html', worlds=worlds)

@worlds_bp.route('/new', methods=['GET'])
def new_world():
    """Display form to create a new world."""
    return render_template('create_world.html')

@worlds_bp.route('/<int:id>', methods=['GET'])
def view_world(id):
    """Display a specific world."""
    world = World.query.get_or_404(id)
    
    # Get world entities from MCP server
    client = MCPClient()
    try:
        world_name = world.name.lower().replace(' ', '-')
        entities = client._send_request(
            "call_tool",
            {
                "name": "get_world_entities",
                "arguments": {
                    "world_name": world_name,
                    "entity_type": "all"
                }
            }
        )
        entities_data = json.loads(entities["content"][0]["text"])
    except Exception as e:
        entities_data = {"error": str(e)}
    
    return render_template('world_detail.html', world=world, entities=entities_data)

@worlds_bp.route('/', methods=['POST'])
def create_world():
    """Create a new world."""
    # Check if the request is JSON or form data
    if request.is_json:
        data = request.json
    else:
        data = request.form
    
    # Create world
    world = World(
        name=data.get('name', ''),
        description=data.get('description', ''),
        ontology_source=data.get('ontology_source', ''),
        world_metadata={}
    )
    db.session.add(world)
    db.session.commit()
    
    if request.is_json:
        return jsonify({
            'success': True,
            'message': 'World created successfully',
            'data': world.to_dict()
        }), 201
    else:
        flash('World created successfully', 'success')
        return redirect(url_for('worlds.view_world', id=world.id))

@worlds_bp.route('/<int:id>', methods=['PUT'])
def update_world(id):
    """Update an existing world."""
    world = World.query.get_or_404(id)
    data = request.json
    
    # Update world fields
    if 'name' in data:
        world.name = data['name']
    if 'description' in data:
        world.description = data['description']
    if 'ontology_source' in data:
        world.ontology_source = data['ontology_source']
    if 'metadata' in data:
        world.world_metadata = data['metadata']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'World updated successfully',
        'data': world.to_dict()
    })

@worlds_bp.route('/<int:id>', methods=['DELETE'])
def delete_world(id):
    """Delete a world."""
    world = World.query.get_or_404(id)
    db.session.delete(world)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'World deleted successfully'
    })
