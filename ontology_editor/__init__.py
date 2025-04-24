"""
Ontology Editor Module for ProEthica

A modular and flexible implementation for editing BFO-based ontologies,
designed to be integrated with the ProEthica application.
"""

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash

def create_ontology_editor_blueprint(config=None, url_prefix='/ontology-editor'):
    """
    Create a Flask blueprint for the ontology editor.
    
    Args:
        config (dict): Configuration dictionary for the ontology editor
        url_prefix (str): URL prefix for the blueprint routes
        
    Returns:
        Blueprint: Flask blueprint for the ontology editor
    """
    from ontology_editor.api.routes import create_api_routes
    
    # Create blueprint
    blueprint = Blueprint(
        'ontology_editor',
        __name__,
        template_folder='templates',
        static_folder='static',
        url_prefix=url_prefix
    )
    
    # Register routes
    api_routes = create_api_routes(config or {})
    blueprint.register_blueprint(api_routes)
    
    # Add main routes
    @blueprint.route('/')
    def index():
        """Main ontology editor landing page"""
        source = request.args.get('source')
        ontology_id = request.args.get('ontology_id')
        view = request.args.get('view', 'full')
        highlight_entity = request.args.get('highlight_entity')
        entity_type = request.args.get('entity_type')
        
        # Use ontology_id if provided, otherwise use source
        # This ensures backward compatibility
        source_param = None
        if ontology_id:
            from app.models.ontology import Ontology
            ontology = Ontology.query.get(ontology_id)
            if ontology:
                source_param = str(ontology_id)
        else:
            source_param = source
            
        # If no source parameter is available, show message
        if not source_param:
            flash('No ontology ID provided. Please select an ontology from the editor.', 'warning')

        # If view is 'entities', this is a specialized entity view
        if view == 'entities':
            return render_template('hierarchy.html',
                                 source=source_param,
                                 ontology_id=ontology_id,
                                 highlight_entity=highlight_entity,
                                 entity_type=entity_type)

        # Default full editor view
        return render_template('editor.html',
                             source=source_param,
                             ontology_id=ontology_id,
                             highlight_entity=highlight_entity,
                             entity_type=entity_type)
    
    @blueprint.route('/entity')
    def edit_entity():
        """Entity-specific editor view"""
        source = request.args.get('source')
        entity_id = request.args.get('highlight_entity')
        entity_type = request.args.get('entity_type')
        
        return render_template('hierarchy.html', 
                             source=source,
                             highlight_entity=entity_id,
                             entity_type=entity_type)
    
    return blueprint
