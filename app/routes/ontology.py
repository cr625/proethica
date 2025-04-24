from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from app.services.mcp_client import MCPClient
from app.models.world import World
from app import db

ontology_bp = Blueprint('ontology', __name__, url_prefix='/ontology')

# Get singleton instances
mcp_client = MCPClient.get_instance()

@ontology_bp.route('/', methods=['GET'])
def list_ontologies():
    """List all ontologies."""
    # Redirect to the ontology editor with no source parameter
    return redirect('/ontology-editor')

@ontology_bp.route('/<path:source>', methods=['GET'])
def view_ontology(source):
    """View an ontology by source."""
    # Redirect to the ontology editor with source parameter
    return redirect(f'/ontology-editor?source={source}')

@ontology_bp.route('/<path:source>/content', methods=['GET'])
def get_ontology_content(source):
    """Get the content of an ontology file."""
    content = mcp_client.get_ontology_content(source)
    if content:
        return content, 200, {'Content-Type': 'text/turtle'}
    else:
        return jsonify({'error': 'Ontology not found'}), 404

@ontology_bp.route('/<path:source>/content', methods=['PUT'])
def update_ontology_content(source):
    """Update the content of an ontology file."""
    # Check if the user is authenticated
    try:
        from flask_login import current_user
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
    except ImportError:
        pass  # If Flask-Login is not installed, continue without authentication
    
    # Get the content from the request
    content = request.data.decode('utf-8')
    if not content:
        return jsonify({'error': 'No content provided'}), 400
    
    # Update the ontology content
    success = mcp_client.update_ontology_content(source, content)
    if success:
        # Find worlds that use this ontology source
        worlds = World.query.filter_by(ontology_source=source).all()
        
        # Refresh entities for each world
        for world in worlds:
            try:
                success = mcp_client.refresh_world_entities(world.id)
                if success:
                    print(f"Successfully refreshed entities for world {world.id}")
                else:
                    print(f"Failed to refresh entities for world {world.id}")
            except Exception as e:
                print(f"Error refreshing entities for world {world.id}: {str(e)}")
        
        return jsonify({'success': True, 'message': 'Ontology updated successfully'}), 200
    else:
        return jsonify({'error': 'Failed to update ontology'}), 500

@ontology_bp.route('/<path:source>/status', methods=['GET'])
def get_ontology_status(source):
    """Get the status of an ontology (current or deprecated)."""
    status = mcp_client.get_ontology_status(source)
    return jsonify({'status': status})

@ontology_bp.route('/<path:source>/refresh', methods=['POST'])
def refresh_ontology(source):
    """Refresh entities derived from an ontology."""
    # Check if the user is authenticated
    try:
        from flask_login import current_user
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
    except ImportError:
        pass  # If Flask-Login is not installed, continue without authentication
    
    # Get world_id from the request
    data = request.json
    if not data or 'world_id' not in data:
        # If no world_id is provided, find all worlds that use this ontology source
        worlds = World.query.filter_by(ontology_source=source).all()
        
        # Refresh entities for each world
        results = []
        for world in worlds:
            try:
                success = mcp_client.refresh_world_entities(world.id)
                results.append({
                    'world_id': world.id,
                    'success': success
                })
            except Exception as e:
                results.append({
                    'world_id': world.id,
                    'success': False,
                    'error': str(e)
                })
        
        return jsonify({'results': results})
    
    # Refresh entities for the specified world
    world_id = data['world_id']
    try:
        success = mcp_client.refresh_world_entities(world_id)
        if success:
            return jsonify({'success': True, 'message': f'Successfully refreshed entities for world {world_id}'}), 200
        else:
            return jsonify({'error': f'Failed to refresh entities for world {world_id}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ontology_bp.route('/create', methods=['GET'])
def create_form():
    """Display form to create a new ontology."""
    # Redirect to the ontology editor with create parameter
    return redirect('/ontology-editor?create=true')

@ontology_bp.route('/create', methods=['POST'])
def create_ontology():
    """Create a new ontology."""
    # Check if the user is authenticated
    try:
        from flask_login import current_user
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
    except ImportError:
        pass  # If Flask-Login is not installed, continue without authentication
    
    # This endpoint is just a proxy to the ontology editor API
    return jsonify({'error': 'Not implemented yet. Use the ontology editor to create new ontologies.'}), 501
