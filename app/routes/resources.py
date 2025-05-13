"""
Routes for managing resources.

This module provides routes for managing resources in the application.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.resource import Resource
from app.models import db

# Create a blueprint for the resources routes
resources_bp = Blueprint('resources', __name__)

@resources_bp.route('/')
def list_resources():
    """
    List all resources.
    
    Returns:
        Rendered template with resources
    """
    try:
        resources = Resource.query.all()
        return render_template('resources/list.html', resources=resources)
    except Exception:
        # Fallback if resources functionality is not fully implemented
        flash('Resources functionality is not fully implemented yet', 'warning')
        return redirect(url_for('index.index'))

@resources_bp.route('/create', methods=['GET', 'POST'])
def create_resource():
    """
    Create a new resource.
    
    Returns:
        Rendered template or redirect
    """
    if request.method == 'POST':
        try:
            # Extract data from form
            name = request.form.get('name')
            description = request.form.get('description', '')
            
            # Create new resource
            resource = Resource(name=name, description=description)
            db.session.add(resource)
            db.session.commit()
            
            flash(f'Resource "{name}" created successfully', 'success')
            return redirect(url_for('resources.list_resources'))
        except Exception as e:
            flash(f'Error creating resource: {str(e)}', 'danger')
            db.session.rollback()
    
    # GET method or form submission failed
    return render_template('resources/create.html')

@resources_bp.route('/<int:resource_id>', methods=['GET'])
def view_resource(resource_id):
    """
    View a specific resource.
    
    Args:
        resource_id: ID of the resource
        
    Returns:
        Rendered resource template or redirect
    """
    try:
        resource = Resource.query.get_or_404(resource_id)
        return render_template('resources/view.html', resource=resource)
    except Exception as e:
        flash(f'Error viewing resource: {str(e)}', 'danger')
        return redirect(url_for('resources.list_resources'))

@resources_bp.route('/api/resources')
def api_list_resources():
    """
    API endpoint to list all resources.
    
    Returns:
        JSON response with resources
    """
    try:
        resources = Resource.query.all()
        resources_data = [{"id": r.id, "name": r.name, "description": r.description} for r in resources]
        return jsonify({"status": "success", "resources": resources_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@resources_bp.route('/api/resources/<int:resource_id>')
def api_get_resource(resource_id):
    """
    API endpoint to get a specific resource.
    
    Args:
        resource_id: ID of the resource
        
    Returns:
        JSON response with resource data
    """
    try:
        resource = Resource.query.get_or_404(resource_id)
        resource_data = {
            "id": resource.id, 
            "name": resource.name, 
            "description": resource.description
        }
        return jsonify({"status": "success", "resource": resource_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
