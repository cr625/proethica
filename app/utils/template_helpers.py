"""
Template Helper Utilities

This module provides helper functions for rendering templates with specialized formatting.
"""

import uuid
import json
import re
from flask import render_template
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
            'content': content
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
