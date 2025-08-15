"""
Routes for the ontology editor integration with the main application.
Includes secure endpoints to edit, fetch, refresh, and delete ontologies.
"""

from flask import Blueprint, redirect, request, jsonify, current_app, url_for, flash, render_template
from flask_login import login_required, current_user 
from app.models import db
from app.models.ontology import Ontology
from app.models.ontology_import import OntologyImport
from app.models.ontology_version import OntologyVersion
from app.models.world import World
from app.services import MCPClient

ontology_bp = Blueprint('ontology', __name__, url_prefix='/ontology')

@ontology_bp.route('/<source>')
def edit_ontology(source):
    """
    Redirect to the ontology editor for the specified ontology source.
    
    Args:
        source (str): Source identifier for the ontology
        
    Returns:
        Redirect to the ontology editor
    """
    # Check if user has admin permission
    if not getattr(current_user, 'is_admin', False):
        flash('You must be an admin to edit ontologies', 'error')
        return redirect(url_for('worlds.list_worlds'))
        
    # Redirect to the ontology editor
    return redirect(f'/ontology-editor?source={source}')

@ontology_bp.route('/<source>/content')
def get_ontology_content(source):
    """
    Get the content of the specified ontology.
    
    Args:
        source (str): Source identifier for the ontology
        
    Returns:
        JSON response with the ontology content
    """
    # Check if user has admin permission
    if not getattr(current_user, 'is_admin', False):
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        # Get MCP client instance
        client = MCPClient.get_instance()
        
        # Get the content of the ontology
        result = client.get_ontology_content(source)
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Failed to get ontology content for {source}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@ontology_bp.route('/<source>/content', methods=['PUT'])
def update_ontology_content(source):
    """
    Update the content of the specified ontology.
    
    Args:
        source (str): Source identifier for the ontology
        
    Returns:
        JSON response with the update status
    """
    # Check if user has admin permission
    if not getattr(current_user, 'is_admin', False):
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        # Get the request data
        data = request.get_json()
        
        if not data or 'content' not in data:
            return jsonify({'error': 'Missing content parameter'}), 400
            
        # Get MCP client instance
        client = MCPClient.get_instance()
        
        # Update the content of the ontology
        result = client.update_ontology_content(source, data['content'])
        
        # Refresh entities for worlds using this ontology
        client.refresh_world_entities_by_ontology(source)
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Failed to update ontology content for {source}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@ontology_bp.route('/<source>/status')
def get_ontology_status(source):
    """
    Get the status of the specified ontology.
    
    Args:
        source (str): Source identifier for the ontology
        
    Returns:
        JSON response with the ontology status
    """
    try:
        # Get MCP client instance
        client = MCPClient.get_instance()
        
        # Get the status of the ontology
        result = client.get_ontology_status(source)
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Failed to get ontology status for {source}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@ontology_bp.route('/<source>/refresh', methods=['POST'])
def refresh_ontology(source):
    """
    Refresh entities derived from the specified ontology.
    
    Args:
        source (str): Source identifier for the ontology
        
    Returns:
        JSON response with the refresh status
    """
    # Check if user has admin permission
    if not getattr(current_user, 'is_admin', False):
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        # Get MCP client instance
        client = MCPClient.get_instance()
        
        # Refresh entities for worlds using this ontology
        result = client.refresh_world_entities_by_ontology(source)
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Failed to refresh entities for ontology {source}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@ontology_bp.route('/entity')
def edit_entity():
    """
    Redirect to the ontology editor for editing a specific entity.
    
    Query parameters:
        entity_id (str): ID of the entity to edit
        type (str): Type of the entity (role, condition, resource, etc.)
        source (str): Source identifier for the ontology
        
    Returns:
        Redirect to the ontology editor with the entity highlighted
    """
    # Check if user has admin permission
    if not getattr(current_user, 'is_admin', False):
        flash('You must be an admin to edit ontologies', 'error')
        return redirect(url_for('worlds.list_worlds'))
        
    # Get the query parameters
    entity_id = request.args.get('entity_id')
    entity_type = request.args.get('type')
    ontology_source = request.args.get('source')
    
    if not entity_id or not entity_type or not ontology_source:
        flash('Missing required parameters', 'error')
        return redirect(url_for('worlds.list_worlds'))
        
    # Redirect to the ontology editor with the entity highlighted
    return redirect(f'/ontology-editor?source={ontology_source}&highlight_entity={entity_id}&entity_type={entity_type}')


@ontology_bp.route('/<int:ontology_id>/delete', methods=['POST'])
@login_required
def delete_ontology(ontology_id):
    """Delete an ontology by ID with safety checks.

    Only admins may delete ontologies. Base ontologies and non-editable ontologies
    cannot be deleted. If any World references the ontology as its base ontology,
    deletion is blocked.
    """
    # Admin check
    if not getattr(current_user, 'is_admin', False):
        flash('You must be an admin to delete ontologies', 'danger')
        return redirect(url_for('dashboard.index'))

    ontology = Ontology.query.get_or_404(ontology_id)

    # Safety checks
    if ontology.is_base or not ontology.is_editable:
        flash('This ontology is protected and cannot be deleted.', 'warning')
        return redirect(url_for('dashboard.index'))

    # Check for worlds referencing this ontology
    referencing_worlds = World.query.filter_by(ontology_id=ontology_id).count()
    if referencing_worlds > 0:
        flash('Ontology is in use by one or more Worlds and cannot be deleted.', 'warning')
        return redirect(url_for('dashboard.index'))

    try:
        # Manually remove import relationships (both directions) for safety
        OntologyImport.query.filter(
            (OntologyImport.importing_ontology_id == ontology_id) |
            (OntologyImport.imported_ontology_id == ontology_id)
        ).delete(synchronize_session=False)

        # Remove version history
        OntologyVersion.query.filter_by(ontology_id=ontology_id).delete(synchronize_session=False)

        # Finally delete the ontology
        db.session.delete(ontology)
        db.session.commit()
        flash('Ontology deleted successfully.', 'success')
    except Exception as e:
        current_app.logger.error(f"Failed to delete ontology {ontology_id}: {e}")
        db.session.rollback()
        flash(f'Failed to delete ontology: {e}', 'danger')

    # Return to dashboard
    return redirect(url_for('dashboard.index'))
