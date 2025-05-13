"""
Routes for roles handling.

This module provides routes for managing roles in the application.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.world import World
from app.models.role import Role
from app.models import db

# Create a blueprint for the roles routes
roles_bp = Blueprint('roles', __name__)

@roles_bp.route('/')
def list_roles():
    """
    List all roles.
    
    Returns:
        Rendered template with roles
    """
    try:
        roles = Role.query.all()
        return render_template('roles/list.html', roles=roles)
    except Exception:
        # Fallback if roles functionality is not fully implemented
        flash('Roles functionality is not fully implemented yet', 'warning')
        return redirect(url_for('index.index'))

@roles_bp.route('/create', methods=['GET', 'POST'])
def create_role():
    """
    Create a new role.
    
    Returns:
        Rendered template or redirect
    """
    if request.method == 'POST':
        try:
            # Extract data from form
            name = request.form.get('name')
            description = request.form.get('description', '')
            
            # Create new role
            role = Role(name=name, description=description)
            db.session.add(role)
            db.session.commit()
            
            flash(f'Role "{name}" created successfully', 'success')
            return redirect(url_for('roles.list_roles'))
        except Exception as e:
            flash(f'Error creating role: {str(e)}', 'danger')
            db.session.rollback()
    
    # GET method or form submission failed
    return render_template('roles/create.html')

@roles_bp.route('/<int:role_id>', methods=['GET'])
def view_role(role_id):
    """
    View a specific role.
    
    Args:
        role_id: ID of the role
        
    Returns:
        Rendered role template or redirect
    """
    try:
        role = Role.query.get_or_404(role_id)
        return render_template('roles/view.html', role=role)
    except Exception as e:
        flash(f'Error viewing role: {str(e)}', 'danger')
        return redirect(url_for('roles.list_roles'))

@roles_bp.route('/api/roles')
def api_list_roles():
    """
    API endpoint to list all roles.
    
    Returns:
        JSON response with roles
    """
    try:
        roles = Role.query.all()
        roles_data = [{"id": r.id, "name": r.name, "description": r.description} for r in roles]
        return jsonify({"status": "success", "roles": roles_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@roles_bp.route('/api/roles/<int:role_id>')
def api_get_role(role_id):
    """
    API endpoint to get a specific role.
    
    Args:
        role_id: ID of the role
        
    Returns:
        JSON response with role data
    """
    try:
        role = Role.query.get_or_404(role_id)
        role_data = {
            "id": role.id, 
            "name": role.name, 
            "description": role.description
        }
        return jsonify({"status": "success", "role": role_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
