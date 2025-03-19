from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.world import World
from app.services.mcp_client import MCPClient
from datetime import datetime
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
        guidelines_url=data.get('guidelines_url', ''),
        guidelines_text=data.get('guidelines_text', ''),
        cases=[],
        rulesets=[],
        world_metadata={}
    )
    
    # Handle guidelines file upload
    if not request.is_json and 'guidelines_file' in request.files:
        guidelines_file = request.files['guidelines_file']
        if guidelines_file and guidelines_file.filename:
            try:
                # Read the file content
                guidelines_content = guidelines_file.read().decode('utf-8')
                # Update the guidelines text
                world.guidelines_text = guidelines_content
            except Exception as e:
                flash(f'Error reading guidelines file: {str(e)}', 'danger')
    
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

@worlds_bp.route('/<int:id>/edit', methods=['GET'])
def edit_world(id):
    """Display form to edit an existing world."""
    world = World.query.get_or_404(id)
    return render_template('edit_world.html', world=world)

@worlds_bp.route('/<int:id>/edit', methods=['POST'])
def update_world_form(id):
    """Update an existing world from form data."""
    world = World.query.get_or_404(id)
    
    # Update world fields from form data
    world.name = request.form.get('name', '')
    world.description = request.form.get('description', '')
    world.ontology_source = request.form.get('ontology_source', '')
    world.guidelines_url = request.form.get('guidelines_url', '')
    world.guidelines_text = request.form.get('guidelines_text', '')
    
    # Handle guidelines file upload
    if 'guidelines_file' in request.files:
        guidelines_file = request.files['guidelines_file']
        if guidelines_file and guidelines_file.filename:
            try:
                # Read the file content
                guidelines_content = guidelines_file.read().decode('utf-8')
                # Update the guidelines text
                world.guidelines_text = guidelines_content
            except Exception as e:
                flash(f'Error reading guidelines file: {str(e)}', 'danger')
    
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
    if 'cases' in data:
        world.cases = data['cases']
    if 'rulesets' in data:
        world.rulesets = data['rulesets']
    if 'metadata' in data:
        world.world_metadata = data['metadata']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'World updated successfully',
        'data': world.to_dict()
    })

@worlds_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_world_confirm(id):
    """Delete a world after confirmation."""
    world = World.query.get_or_404(id)
    
    # Store the name for the flash message
    world_name = world.name
    
    try:
        # Delete related records first
        # 1. Delete scenarios associated with this world
        from app.models.scenario import Scenario
        scenarios = Scenario.query.filter_by(world_id=id).all()
        for scenario in scenarios:
            db.session.delete(scenario)
        
        # 2. Delete roles associated with this world
        from app.models.role import Role
        roles = Role.query.filter_by(world_id=id).all()
        for role in roles:
            db.session.delete(role)
        
        # 3. Delete resource types associated with this world
        from app.models.resource_type import ResourceType
        resource_types = ResourceType.query.filter_by(world_id=id).all()
        for resource_type in resource_types:
            db.session.delete(resource_type)
        
        # 4. Delete condition types associated with this world
        from app.models.condition_type import ConditionType
        condition_types = ConditionType.query.filter_by(world_id=id).all()
        for condition_type in condition_types:
            db.session.delete(condition_type)
        
        # Now delete the world itself
        db.session.delete(world)
        db.session.commit()
        
        flash(f'World "{world_name}" has been deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting world: {str(e)}', 'danger')
    
    return redirect(url_for('worlds.list_worlds'))

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

@worlds_bp.route('/<int:id>/references/<item_key>/citation', methods=['GET'])
def get_reference_citation(id, item_key):
    """Get citation for a reference."""
    world = World.query.get_or_404(id)
    style = request.args.get('style', 'apa')
    
    # Initialize MCP client
    mcp_client = MCPClient()
    
    # Get citation
    try:
        citation = mcp_client.get_zotero_citation(item_key, style)
        return jsonify({
            'success': True,
            'citation': citation
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@worlds_bp.route('/<int:id>/references/add', methods=['POST'])
def add_reference(id):
    """Add a reference to the Zotero library."""
    world = World.query.get_or_404(id)
    data = request.json
    
    # Initialize MCP client
    mcp_client = MCPClient()
    
    # Add reference
    try:
        result = mcp_client.add_zotero_item(
            item_type=data.get('item_type', 'journalArticle'),
            title=data.get('title', ''),
            creators=data.get('creators', []),
            additional_fields=data.get('additional_fields', {})
        )
        
        return jsonify({
            'success': True,
            'message': 'Reference added successfully',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Case management routes
@worlds_bp.route('/<int:id>/cases', methods=['GET'])
def list_cases(id):
    """Get all cases for a world."""
    world = World.query.get_or_404(id)
    
    return jsonify({
        'success': True,
        'data': world.cases or []
    })

@worlds_bp.route('/<int:id>/cases', methods=['POST'])
def add_case(id):
    """Add a case to a world."""
    world = World.query.get_or_404(id)
    data = request.json
    
    # Initialize cases list if it doesn't exist
    if world.cases is None:
        world.cases = []
    
    # Add the new case
    case = {
        'title': data.get('title', ''),
        'description': data.get('description', ''),
        'decision': data.get('decision', ''),
        'outcome': data.get('outcome', ''),
        'ethical_analysis': data.get('ethical_analysis', ''),
        'date': data.get('date', datetime.now().strftime('%Y-%m-%d'))
    }
    
    world.cases.append(case)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Case added successfully',
        'data': case
    })

@worlds_bp.route('/<int:id>/cases/<int:case_index>', methods=['PUT'])
def update_case(id, case_index):
    """Update a case in a world."""
    world = World.query.get_or_404(id)
    data = request.json
    
    # Check if the case exists
    if not world.cases or len(world.cases) <= case_index:
        return jsonify({
            'success': False,
            'message': 'Case not found'
        }), 404
    
    # Update the case
    case = world.cases[case_index]
    case['title'] = data.get('title', case.get('title', ''))
    case['description'] = data.get('description', case.get('description', ''))
    case['decision'] = data.get('decision', case.get('decision', ''))
    case['outcome'] = data.get('outcome', case.get('outcome', ''))
    case['ethical_analysis'] = data.get('ethical_analysis', case.get('ethical_analysis', ''))
    case['date'] = data.get('date', case.get('date', ''))
    
    world.cases[case_index] = case
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Case updated successfully',
        'data': case
    })

@worlds_bp.route('/<int:id>/cases/<int:case_index>', methods=['DELETE'])
def delete_case(id, case_index):
    """Delete a case from a world."""
    world = World.query.get_or_404(id)
    
    # Check if the case exists
    if not world.cases or len(world.cases) <= case_index:
        return jsonify({
            'success': False,
            'message': 'Case not found'
        }), 404
    
    # Remove the case
    world.cases.pop(case_index)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Case deleted successfully'
    })

# Ruleset management routes
@worlds_bp.route('/<int:id>/rulesets', methods=['GET'])
def list_rulesets(id):
    """Get all rulesets for a world."""
    world = World.query.get_or_404(id)
    
    return jsonify({
        'success': True,
        'data': world.rulesets or []
    })

@worlds_bp.route('/<int:id>/rulesets', methods=['POST'])
def add_ruleset(id):
    """Add a ruleset to a world."""
    world = World.query.get_or_404(id)
    data = request.json
    
    # Initialize rulesets list if it doesn't exist
    if world.rulesets is None:
        world.rulesets = []
    
    # Add the new ruleset
    ruleset = {
        'name': data.get('name', ''),
        'description': data.get('description', ''),
        'rules': data.get('rules', []),
        'date_created': datetime.now().strftime('%Y-%m-%d')
    }
    
    world.rulesets.append(ruleset)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Ruleset added successfully',
        'data': ruleset
    })

@worlds_bp.route('/<int:id>/rulesets/<int:ruleset_index>', methods=['PUT'])
def update_ruleset(id, ruleset_index):
    """Update a ruleset in a world."""
    world = World.query.get_or_404(id)
    data = request.json
    
    # Check if the ruleset exists
    if not world.rulesets or len(world.rulesets) <= ruleset_index:
        return jsonify({
            'success': False,
            'message': 'Ruleset not found'
        }), 404
    
    # Update the ruleset
    ruleset = world.rulesets[ruleset_index]
    ruleset['name'] = data.get('name', ruleset.get('name', ''))
    ruleset['description'] = data.get('description', ruleset.get('description', ''))
    ruleset['rules'] = data.get('rules', ruleset.get('rules', []))
    
    world.rulesets[ruleset_index] = ruleset
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Ruleset updated successfully',
        'data': ruleset
    })

@worlds_bp.route('/<int:id>/rulesets/<int:ruleset_index>', methods=['DELETE'])
def delete_ruleset(id, ruleset_index):
    """Delete a ruleset from a world."""
    world = World.query.get_or_404(id)
    
    # Check if the ruleset exists
    if not world.rulesets or len(world.rulesets) <= ruleset_index:
        return jsonify({
            'success': False,
            'message': 'Ruleset not found'
        }), 404
    
    # Remove the ruleset
    world.rulesets.pop(ruleset_index)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Ruleset deleted successfully'
    })

@worlds_bp.route('/<int:id>', methods=['DELETE'])
@login_required
def delete_world(id):
    """Delete a world via API."""
    world = World.query.get_or_404(id)
    world_name = world.name
    
    try:
        # Delete related records first
        # 1. Delete scenarios associated with this world
        from app.models.scenario import Scenario
        scenarios = Scenario.query.filter_by(world_id=id).all()
        for scenario in scenarios:
            db.session.delete(scenario)
        
        # 2. Delete roles associated with this world
        from app.models.role import Role
        roles = Role.query.filter_by(world_id=id).all()
        for role in roles:
            db.session.delete(role)
        
        # 3. Delete resource types associated with this world
        from app.models.resource_type import ResourceType
        resource_types = ResourceType.query.filter_by(world_id=id).all()
        for resource_type in resource_types:
            db.session.delete(resource_type)
        
        # 4. Delete condition types associated with this world
        from app.models.condition_type import ConditionType
        condition_types = ConditionType.query.filter_by(world_id=id).all()
        for condition_type in condition_types:
            db.session.delete(condition_type)
        
        # Now delete the world itself
        db.session.delete(world)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'World "{world_name}" deleted successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error deleting world: {str(e)}'
        }), 500
