"""
Custom template filters for the application.
"""

import os
import re
import markdown
from flask import current_app
from markupsafe import Markup
from app.services.concept_hierarchy_service import ConceptHierarchyService

def init_app(app):
    """Initialize template filters for the application."""
    
    @app.template_filter('basename')
    def basename_filter(path):
        """Return the basename of a file path."""
        return os.path.basename(path) if path else ''
    
    @app.template_filter('nl2br')
    def nl2br_filter(text):
        """Convert newlines to HTML line breaks."""
        if not text:
            return ''
        text = str(text)
        return Markup(text.replace('\n', '<br>\n'))
    
    @app.template_filter('markdown')
    def markdown_filter(text):
        """Convert markdown text to HTML."""
        if not text:
            return ''
        text = str(text)
        # Convert markdown to HTML using the Python-Markdown library
        md = markdown.Markdown(extensions=['extra', 'codehilite', 'fenced_code'])
        return Markup(md.convert(text))
    
    @app.template_filter('slice')
    def slice_filter(iterable, start, end=None):
        """Slice an iterable and return a list."""
        if not iterable:
            return []
        if end is None:
            return list(iterable)[start:]
        return list(iterable)[start:end]
    
    @app.template_filter('camel_to_readable')
    def camel_to_readable_filter(text):
        """Convert camelCase or PascalCase to readable format with spaces.

        Examples:
            hasProfessionalScope -> Professional Scope
            hasDistinguishingFeature -> Distinguishing Feature
            initiatedBy -> Initiated By
        """
        if not text:
            return ''

        # Remove 'has' prefix if present
        if text.startswith('has'):
            text = text[3:]

        # Add space before capital letters (but not at the start)
        result = ''
        for i, char in enumerate(text):
            if i > 0 and char.isupper() and text[i-1].islower():
                result += ' '
            result += char

        # Capitalize properly
        return result.title()

    @app.template_filter('hash')
    def hash_filter(value):
        """Generate a hash value for the input."""
        if not value:
            return 0
        return hash(str(value))
    
    @app.template_filter('hash_participant_id')
    def hash_participant_id_filter(value):
        """Generate a participant ID based on hash of the input."""
        if not value:
            return "P0000"
        hash_value = abs(hash(str(value))) % 10000
        return f"P{hash_value:04d}"
    
    @app.template_filter('map_to_intermediate_type')
    def map_to_intermediate_type_filter(category):
        """Map concept categories to the 8 basic intermediate ontology types."""
        if not category:
            return "Concept"
        
        category_lower = str(category).lower()
        
        # Mapping dictionary
        mappings = {
            'principle': ['principle', 'value', 'ethical principle', 'standard', 'norm'],
            'obligation': ['obligation', 'duty', 'responsibility', 'requirement', 'must'],
            'role': ['stakeholder', 'role', 'position', 'actor', 'agent', 'party'],
            'action': ['action', 'activity', 'process', 'procedure', 'operation', 'practice'],
            'state': ['state', 'condition', 'situation', 'status', 'circumstance'],
            'capability': ['capability', 'competence', 'skill', 'ability', 'capacity'],
            'event': ['event', 'occurrence', 'incident', 'happening', 'case'],
            'resource': ['resource', 'constraint', 'limitation', 'asset', 'tool']
        }
        
        # Check each mapping
        for intermediate_type, keywords in mappings.items():
            if category_lower in keywords:
                return intermediate_type.capitalize()
        
        # If no mapping found, return the original category capitalized
        return category.capitalize()
    
    @app.template_filter('concept_hierarchy')
    def concept_hierarchy_filter(concept, format_type='breadcrumb'):
        """
        Display concept hierarchy showing ontological path.
        
        Args:
            concept: Dictionary with concept information
            format_type: 'breadcrumb', 'compact', 'tree'
            
        Returns:
            HTML string showing hierarchical path
        """
        try:
            hierarchy_service = ConceptHierarchyService()
            hierarchy = hierarchy_service.get_concept_hierarchy(concept)
            return Markup(hierarchy_service.format_hierarchy_for_display(hierarchy, format_type))
        except Exception as e:
            # Fallback to simple display
            concept_label = concept.get('label', 'Unknown Concept')
            semantic_label = concept.get('semantic_label') or concept.get('category') or concept.get('type')
            if semantic_label:
                return Markup(f'<small class="text-muted">{semantic_label.capitalize()}</small> → <strong>{concept_label}</strong>')
            return Markup(f'<strong>{concept_label}</strong>')
    
    @app.template_filter('primary_type_badge')
    def primary_type_badge_filter(concept):
        """
        Display primary type as a colored badge.
        
        Returns badge with appropriate color for the 8 intermediate types.
        """
        primary_type = (concept.get('primary_type') or concept.get('type', '')).lower()
        
        # Color mapping for the 8 intermediate types
        type_colors = {
            'role': 'bg-primary',
            'principle': 'bg-success', 
            'obligation': 'bg-warning',
            'state': 'bg-info',
            'resource': 'bg-secondary',
            'action': 'bg-danger',
            'event': 'bg-dark',
            'capability': 'bg-light text-dark'
        }
        
        color_class = type_colors.get(primary_type, 'bg-secondary')
        display_type = primary_type.capitalize() if primary_type else 'Concept'
        
        return Markup(f'<span class="badge {color_class}">{display_type}</span>')
