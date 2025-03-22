from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from datetime import datetime
from app import db
from app.models.world import World
from app.models.scenario import Scenario
from app.models.role import Role
from app.models.condition_type import ConditionType
from app.models.resource_type import ResourceType
from app.services.mcp_client import MCPClient

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
        metadata={}
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

@worlds_bp.route('/<int:id>', methods=['GET'])
def view_world(id):
    """Display a specific world."""
    world = World.query.get_or_404(id)
    
    # Get world entities from MCP client if ontology source is specified
    entities = {}
    if world.ontology_source:
        try:
            mcp_client = MCPClient()
            entities = mcp_client.get_world_entities(world.ontology_source)
        except Exception as e:
            entities = {"error": str(e)}
    
    return render_template('world_detail.html', world=world, entities=entities)

@worlds_bp.route('/<int:id>/edit', methods=['GET'])
def edit_world(id):
    """Display form to edit an existing world."""
    world = World.query.get_or_404(id)
    return render_template('edit_world.html', world=world)

@worlds_bp.route('/<int:id>/edit', methods=['POST'])
def update_world_form(id):
    """Update an existing world from form data."""
    world = World.query.get_or_404(id)
    
    # Update world fields
    world.name = request.form.get('name', '')
    world.description = request.form.get('description', '')
    world.ontology_source = request.form.get('ontology_source', '')
    world.guidelines_url = request.form.get('guidelines_url', '')
    world.guidelines_text = request.form.get('guidelines_text', '')
    
    db.session.commit()
    
    flash('World updated successfully', 'success')
    return redirect(url_for('worlds.view_world', id=world.id))

@worlds_bp.route('/<int:id>', methods=['PUT'])
def update_world(id):
    """Update an existing world via API."""
    world = World.query.get_or_404(id)
    data = request.json
    
    # Update world fields
    if 'name' in data:
        world.name = data['name']
    if 'description' in data:
        world.description = data['description']
    if 'ontology_source' in data:
        world.ontology_source = data['ontology_source']
    if 'guidelines_url' in data:
        world.guidelines_url = data['guidelines_url']
    if 'guidelines_text' in data:
        world.guidelines_text = data['guidelines_text']
    if 'metadata' in data:
        world.metadata = data['metadata']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'World updated successfully',
        'data': world.to_dict()
    })

@worlds_bp.route('/<int:id>', methods=['DELETE'])
def delete_world(id):
    """Delete a world via API."""
    world = World.query.get_or_404(id)
    db.session.delete(world)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'World deleted successfully'
    })

@worlds_bp.route('/<int:id>/delete', methods=['POST'])
def delete_world_confirm(id):
    """Delete a world from web form."""
    world = World.query.get_or_404(id)
    db.session.delete(world)
    db.session.commit()
    
    flash('World deleted successfully', 'success')
    return redirect(url_for('worlds.list_worlds'))

# Case management routes
@worlds_bp.route('/<int:id>/cases', methods=['POST'])
def add_case(id):
    """Add a case to a world."""
    world = World.query.get_or_404(id)
    data = request.json
    
    # If no cases field exists in metadata, create it
    if not world.metadata:
        world.metadata = {}
    if 'cases' not in world.metadata:
        world.metadata['cases'] = []
    
    # Create case object
    case = {
        'title': data.get('title', ''),
        'description': data.get('description', ''),
        'decision': data.get('decision', ''),
        'outcome': data.get('outcome', ''),
        'ethical_analysis': data.get('ethical_analysis', ''),
        'date': data.get('date') or datetime.now().strftime('%Y-%m-%d')
    }
    
    # Add to metadata
    world.metadata['cases'].append(case)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Case added successfully',
        'data': case
    })

@worlds_bp.route('/<int:id>/cases/<int:case_id>', methods=['DELETE'])
def delete_case(id, case_id):
    """Delete a case from a world."""
    world = World.query.get_or_404(id)
    
    # Check if cases exist in metadata
    if not world.metadata or 'cases' not in world.metadata:
        return jsonify({
            'success': False,
            'message': 'No cases found for this world'
        }), 404
    
    # Check if case_id is valid
    if case_id < 0 or case_id >= len(world.metadata['cases']):
        return jsonify({
            'success': False,
            'message': f'Case with ID {case_id} not found'
        }), 404
    
    # Remove case
    world.metadata['cases'].pop(case_id)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Case deleted successfully'
    })

# Ruleset management routes
@worlds_bp.route('/<int:id>/rulesets', methods=['POST'])
def add_ruleset(id):
    """Add a ruleset to a world."""
    world = World.query.get_or_404(id)
    data = request.json
    
    # If no rulesets field exists in metadata, create it
    if not world.metadata:
        world.metadata = {}
    if 'rulesets' not in world.metadata:
        world.metadata['rulesets'] = []
    
    # Create ruleset object
    ruleset = {
        'name': data.get('name', ''),
        'description': data.get('description', ''),
        'rules': data.get('rules', [])
    }
    
    # Add to metadata
    world.metadata['rulesets'].append(ruleset)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Ruleset added successfully',
        'data': ruleset
    })

@worlds_bp.route('/<int:id>/rulesets/<int:ruleset_id>', methods=['DELETE'])
def delete_ruleset(id, ruleset_id):
    """Delete a ruleset from a world."""
    world = World.query.get_or_404(id)
    
    # Check if rulesets exist in metadata
    if not world.metadata or 'rulesets' not in world.metadata:
        return jsonify({
            'success': False,
            'message': 'No rulesets found for this world'
        }), 404
    
    # Check if ruleset_id is valid
    if ruleset_id < 0 or ruleset_id >= len(world.metadata['rulesets']):
        return jsonify({
            'success': False,
            'message': f'Ruleset with ID {ruleset_id} not found'
        }), 404
    
    # Remove ruleset
    world.metadata['rulesets'].pop(ruleset_id)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Ruleset deleted successfully'
    })

# References routes
@worlds_bp.route('/<int:id>/references', methods=['GET'])
def world_references(id):
    """Display references for a world."""
    world = World.query.get_or_404(id)
    
    # Get search query from request parameters
    query = request.args.get('query', '')
    
    # Initialize MCP client
    mcp_client = MCPClient()
    
    # Get references
    if query:
        # Search with the provided query
        references = mcp_client.search_zotero_items(query, limit=10)
    else:
        # Get references based on world content
        references = mcp_client.get_references_for_world(world)
    
    return render_template('world_references.html', world=world, references=references, query=query)
