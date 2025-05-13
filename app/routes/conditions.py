"""
Routes for managing conditions.

This module provides routes for managing conditions in the application.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.condition import Condition
from app.models.condition_type import ConditionType
from app.models import db

# Create a blueprint for the conditions routes
conditions_bp = Blueprint('conditions', __name__)

@conditions_bp.route('/')
def list_conditions():
    """
    List all conditions.
    
    Returns:
        Rendered template with conditions
    """
    try:
        conditions = Condition.query.all()
        return render_template('conditions/list.html', conditions=conditions)
    except Exception:
        # Fallback if conditions functionality is not fully implemented
        flash('Conditions functionality is not fully implemented yet', 'warning')
        return redirect(url_for('index.index'))

@conditions_bp.route('/types')
def list_condition_types():
    """
    List all condition types.
    
    Returns:
        Rendered template with condition types
    """
    try:
        condition_types = ConditionType.query.all()
        return render_template('conditions/types.html', condition_types=condition_types)
    except Exception:
        flash('Condition types functionality is not fully implemented yet', 'warning')
        return redirect(url_for('index.index'))

@conditions_bp.route('/create', methods=['GET', 'POST'])
def create_condition():
    """
    Create a new condition.
    
    Returns:
        Rendered template or redirect
    """
    if request.method == 'POST':
        try:
            # Extract data from form
            name = request.form.get('name')
            description = request.form.get('description', '')
            condition_type_id = request.form.get('condition_type_id')
            
            # Create new condition
            condition = Condition(
                name=name, 
                description=description,
                condition_type_id=condition_type_id
            )
            db.session.add(condition)
            db.session.commit()
            
            flash(f'Condition "{name}" created successfully', 'success')
            return redirect(url_for('conditions.list_conditions'))
        except Exception as e:
            flash(f'Error creating condition: {str(e)}', 'danger')
            db.session.rollback()
    
    # GET method or form submission failed
    condition_types = ConditionType.query.all()
    return render_template('conditions/create.html', condition_types=condition_types)

@conditions_bp.route('/<int:condition_id>', methods=['GET'])
def view_condition(condition_id):
    """
    View a specific condition.
    
    Args:
        condition_id: ID of the condition
        
    Returns:
        Rendered condition template or redirect
    """
    try:
        condition = Condition.query.get_or_404(condition_id)
        return render_template('conditions/view.html', condition=condition)
    except Exception as e:
        flash(f'Error viewing condition: {str(e)}', 'danger')
        return redirect(url_for('conditions.list_conditions'))

@conditions_bp.route('/api/conditions')
def api_list_conditions():
    """
    API endpoint to list all conditions.
    
    Returns:
        JSON response with conditions
    """
    try:
        conditions = Condition.query.all()
        conditions_data = [
            {
                "id": c.id, 
                "name": c.name, 
                "description": c.description,
                "condition_type_id": c.condition_type_id,
                "condition_type_name": c.condition_type.name if c.condition_type else None
            } for c in conditions
        ]
        return jsonify({"status": "success", "conditions": conditions_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@conditions_bp.route('/api/condition-types')
def api_list_condition_types():
    """
    API endpoint to list all condition types.
    
    Returns:
        JSON response with condition types
    """
    try:
        condition_types = ConditionType.query.all()
        types_data = [
            {
                "id": ct.id, 
                "name": ct.name, 
                "description": ct.description
            } for ct in condition_types
        ]
        return jsonify({"status": "success", "condition_types": types_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
