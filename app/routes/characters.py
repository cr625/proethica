"""
Routes for managing characters.

This module provides routes for managing characters in the application.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.character import Character
from app.models.role import Role
from app.models.world import World
from app.models.scenario import Scenario
from app.models import db

# Create a blueprint for the characters routes
characters_bp = Blueprint('characters', __name__)

@characters_bp.route('/')
def list_characters():
    """
    List all characters.
    
    Returns:
        Rendered template with characters
    """
    try:
        characters = Character.query.all()
        return render_template('characters/list.html', characters=characters)
    except Exception:
        # Fallback if characters functionality is not fully implemented
        flash('Characters functionality is not fully implemented yet', 'warning')
        return redirect(url_for('index.index'))

@characters_bp.route('/create', methods=['GET', 'POST'])
def create_character():
    """
    Create a new character.
    
    Returns:
        Rendered template or redirect
    """
    if request.method == 'POST':
        try:
            # Extract data from form
            name = request.form.get('name')
            description = request.form.get('description', '')
            world_id = request.form.get('world_id')
            scenario_id = request.form.get('scenario_id')
            role_id = request.form.get('role_id')
            
            # Create new character
            character = Character(
                name=name, 
                description=description,
                world_id=world_id,
                scenario_id=scenario_id,
                role_id=role_id
            )
            db.session.add(character)
            db.session.commit()
            
            flash(f'Character "{name}" created successfully', 'success')
            return redirect(url_for('characters.list_characters'))
        except Exception as e:
            flash(f'Error creating character: {str(e)}', 'danger')
            db.session.rollback()
    
    # GET method or form submission failed
    worlds = World.query.all()
    roles = Role.query.all()
    scenarios = Scenario.query.all()
    return render_template('characters/create.html', 
                           worlds=worlds, 
                           roles=roles,
                           scenarios=scenarios)

@characters_bp.route('/<int:character_id>', methods=['GET'])
def view_character(character_id):
    """
    View a specific character.
    
    Args:
        character_id: ID of the character
        
    Returns:
        Rendered character template or redirect
    """
    try:
        character = Character.query.get_or_404(character_id)
        return render_template('characters/view.html', character=character)
    except Exception as e:
        flash(f'Error viewing character: {str(e)}', 'danger')
        return redirect(url_for('characters.list_characters'))

@characters_bp.route('/<int:character_id>/edit', methods=['GET', 'POST'])
def edit_character(character_id):
    """
    Edit a specific character.
    
    Args:
        character_id: ID of the character
        
    Returns:
        Rendered character edit template or redirect
    """
    try:
        character = Character.query.get_or_404(character_id)
        
        if request.method == 'POST':
            # Extract data from form
            character.name = request.form.get('name')
            character.description = request.form.get('description', '')
            character.world_id = request.form.get('world_id')
            character.scenario_id = request.form.get('scenario_id')
            character.role_id = request.form.get('role_id')
            
            db.session.commit()
            flash(f'Character "{character.name}" updated successfully', 'success')
            return redirect(url_for('characters.view_character', character_id=character.id))
        
        # GET method
        worlds = World.query.all()
        roles = Role.query.all()
        scenarios = Scenario.query.all()
        return render_template('characters/edit.html', 
                               character=character,
                               worlds=worlds, 
                               roles=roles,
                               scenarios=scenarios)
    except Exception as e:
        flash(f'Error editing character: {str(e)}', 'danger')
        return redirect(url_for('characters.list_characters'))

@characters_bp.route('/api/characters')
def api_list_characters():
    """
    API endpoint to list all characters.
    
    Returns:
        JSON response with characters
    """
    try:
        characters = Character.query.all()
        characters_data = [
            {
                "id": c.id, 
                "name": c.name, 
                "description": c.description,
                "world_id": c.world_id,
                "world_name": c.world.name if c.world else None,
                "scenario_id": c.scenario_id,
                "scenario_name": c.scenario.name if c.scenario else None,
                "role_id": c.role_id,
                "role_name": c.role.name if c.role else None
            } for c in characters
        ]
        return jsonify({"status": "success", "characters": characters_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
