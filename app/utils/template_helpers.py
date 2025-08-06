"""
Template Helper Utilities

This module provides helper functions for rendering templates with specialized formatting.
"""

import uuid
import json
import re
from flask import render_template
from flask_login import current_user
from app.models.character import Character
from sqlalchemy.orm.exc import NoResultFound

def parse_llm_analysis(analysis_text):
    """
    Parse LLM analysis text into structured sections.
    
    Args:
        analysis_text (str): The raw text from the LLM
        
    Returns:
        list: A list of section dictionaries with type and content
    """
    sections = []
    
    # Parse options sections
    option_pattern = re.compile(r'Option (\d+)(?::|\.)(.*?)(?=Option \d+|$)', re.DOTALL)
    general_text = analysis_text
    
    for match in option_pattern.finditer(analysis_text):
        option_num = match.group(1)
        option_content = match.group(2).strip()
        
        # Extract option text and content
        lines = option_content.split('\n', 1)
        option_text = lines[0].strip()
        content = lines[1].strip() if len(lines) > 1 else ""
        
        sections.append({
            'type': 'option',
            'option_number': option_num,
            'option_text': option_text,
            'content': content,
            'formatted_label': f'<strong>Option {option_num}</strong>'
        })
        
        # Remove this option from general text
        general_text = general_text.replace(match.group(0), "")
    
    # Process remaining general text
    general_paras = re.split(r'\n\n+', general_text.strip())
    for para in general_paras:
        if para.strip():
            sections.append({
                'type': 'paragraph',
                'content': para.strip()
            })
    
    return sections

def get_scenario_entities(scenario_id):
    """
    Get all entities for a scenario.
    
    Args:
        scenario_id (int): The ID of the scenario
        
    Returns:
        list: A list of entity dictionaries
    """
    entities = []
    
    try:
        # Add characters
        characters = Character.query.filter_by(scenario_id=scenario_id).all()
        for character in characters:
            entities.append({
                'id': character.id,
                'name': character.name,
                'type': 'character'
            })
        
        # Add other entity types as needed
        # ...
    except NoResultFound:
        pass
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error fetching entities: {str(e)}")
    
    return entities

def render_llm_analysis(analysis_text, scenario_id=None, title=None):
    """
    Render LLM analysis through the template.
    
    Args:
        analysis_text (str): The raw text from the LLM
        scenario_id (int, optional): The scenario ID for fetching entities
        title (str, optional): Title for the analysis
        
    Returns:
        str: The rendered HTML
    """
    # Generate a unique ID for this analysis
    analysis_id = f"analysis-{uuid.uuid4().hex[:8]}"
    
    # Parse the LLM output into structured sections
    sections = parse_llm_analysis(analysis_text)
    
    # Get entities for this scenario
    entities = get_scenario_entities(scenario_id) if scenario_id else []
    
    # Render the template
    rendered_html = render_template(
        'components/llm_analysis.html',
        analysis_id=analysis_id,
        title=title,
        sections=sections,
        entities=entities
    )
    
    return rendered_html


# =============================================================================
# Permission & Ownership Template Helpers (Phase 3 Authentication)
# =============================================================================

def can_edit_item(item):
    """Check if current user can edit the given item."""
    if not hasattr(item, 'can_edit'):
        return False
    return item.can_edit(current_user)


def can_delete_item(item):
    """Check if current user can delete the given item.""" 
    if not hasattr(item, 'can_delete'):
        return False
    return item.can_delete(current_user)


def can_view_item(item):
    """Check if current user can view the given item."""
    if not hasattr(item, 'can_view'):
        return True  # Default to viewable
    return item.can_view(current_user)


def is_system_data(item):
    """Check if the item is system data (read-only for non-admins)."""
    if hasattr(item, 'is_system_data'):
        return item.is_system_data()
    elif hasattr(item, 'data_type'):
        return item.data_type == 'system'
    return False


def is_user_data(item):
    """Check if the item is user-created data."""
    if hasattr(item, 'is_user_data'):
        return item.is_user_data()
    elif hasattr(item, 'data_type'):
        return item.data_type == 'user'
    return True  # Default to user data


def get_creator_name(item):
    """Get the creator's name for the given item."""
    if hasattr(item, 'creator') and item.creator:
        return item.creator.username
    elif hasattr(item, 'created_by'):
        # If creator relationship is not loaded, try to get user by ID
        from app.models.user import User
        user = User.query.get(item.created_by)
        return user.username if user else 'Unknown User'
    return 'System'


def get_data_type_badge(item):
    """Get HTML badge showing who created the content."""
    if is_system_data(item):
        return '<span class="badge bg-info text-dark">System</span>'
    elif is_user_data(item):
        creator_name = get_creator_name(item)
        return f'<span class="badge bg-success">{creator_name}</span>'
    else:
        return '<span class="badge bg-secondary">Unknown</span>'


def get_permission_class(item, action='edit'):
    """Get CSS class based on permission for styling."""
    if action == 'edit' and can_edit_item(item):
        return 'can-edit'
    elif action == 'delete' and can_delete_item(item):
        return 'can-delete'
    elif action == 'view' and can_view_item(item):
        return 'can-view'
    return 'no-permission'


def register_template_helpers(app):
    """Register all template helpers with the Flask app."""
    app.jinja_env.globals.update(
        can_edit_item=can_edit_item,
        can_delete_item=can_delete_item,
        can_view_item=can_view_item,
        is_system_data=is_system_data,
        is_user_data=is_user_data,
        get_creator_name=get_creator_name,
        get_data_type_badge=get_data_type_badge,
        get_permission_class=get_permission_class
    )
