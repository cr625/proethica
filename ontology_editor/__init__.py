"""
Stub Ontology Editor - ARCHIVED functionality moved to OntServe.

This stub exists to prevent import errors during the transition period.
Real ontology editing now happens in OntServe.
"""

from flask import Blueprint, render_template, redirect, flash
from flask_login import login_required

def create_ontology_editor_blueprint(config=None):
    """
    Create a stub ontology editor blueprint that redirects to OntServe.
    
    Args:
        config (dict): Configuration (ignored in stub)
        
    Returns:
        Blueprint: Stub blueprint that redirects to OntServe
    """
    ontology_editor_bp = Blueprint('ontology_editor', __name__, url_prefix='/ontology-editor')
    
    @ontology_editor_bp.route('/')
    @ontology_editor_bp.route('/<path:subpath>')
    @login_required
    def editor_redirect(subpath=''):
        """Redirect all ontology editor requests to OntServe."""
        flash('The Ontology Editor has moved to OntServe for better integration and performance.', 'info')
        if subpath:
            return redirect(f'http://localhost:5003/editor/{subpath}')
        else:
            return redirect('http://localhost:5003/editor')
    
    return ontology_editor_bp