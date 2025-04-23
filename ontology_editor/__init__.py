"""
Ontology Editor Module for ProEthica

A modular and flexible implementation for editing BFO-based ontologies,
designed to be integrated with the ProEthica application.
"""

import os
from flask import Blueprint

def create_ontology_editor_blueprint(config=None, url_prefix='/ontology-editor'):
    """
    Create a Flask blueprint for the ontology editor.
    
    Args:
        config (dict): Configuration dictionary for the ontology editor
        url_prefix (str): URL prefix for the blueprint routes
        
    Returns:
        Blueprint: Flask blueprint for the ontology editor
    """
    from ontology_editor.api.routes import register_routes
    
    # Create blueprint
    blueprint = Blueprint(
        'ontology_editor',
        __name__,
        template_folder='templates',
        static_folder='static',
        url_prefix=url_prefix
    )
    
    # Register routes
    register_routes(blueprint, config)
    
    return blueprint
