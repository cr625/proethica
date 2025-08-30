"""
Stub Ontology routes - ARCHIVED functionality moved to OntServe.

This stub exists to prevent import errors and provide redirect messages.
Real ontology management now happens in OntServe.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, flash
from flask_login import login_required

# Create blueprint
ontology_bp = Blueprint('ontology', __name__)

@ontology_bp.route('/')
@login_required
def ontology_index():
    """Redirect to OntServe with helpful message."""
    flash('Ontology management has moved to OntServe. Redirecting you there.', 'info')
    return redirect('http://localhost:5003')

@ontology_bp.route('/<path:subpath>')
@login_required  
def ontology_redirect(subpath):
    """Redirect ontology subpages to OntServe."""
    return jsonify({
        'message': 'Ontology functionality has been moved to OntServe',
        'redirect_url': f'http://localhost:5003/ontology/{subpath}',
        'note': 'Please visit OntServe for ontology management'
    }), 302

@ontology_bp.route('/api/<path:api_path>')
@login_required
def ontology_api_redirect(api_path):
    """Redirect ontology API calls to OntServe.""" 
    return jsonify({
        'success': False,
        'error': 'Ontology API has been moved to OntServe',
        'redirect_url': f'http://localhost:5003/api/{api_path}',
        'message': 'Please update your API calls to use OntServe at localhost:5003'
    }), 301