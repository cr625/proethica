"""
REALM Main Routes.

This module defines the main web routes for the REALM application.
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, jsonify

# Import services
from realm.services import material_service

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Render the index page."""
    return render_template('realm/index.html')

@main_bp.route('/search')
def search():
    """Render the material search page."""
    query = request.args.get('q', '')
    
    # Get materials if query provided
    materials = []
    if query:
        materials = material_service.search_materials(query)
    
    # Get categories for filtering
    categories = material_service.get_categories()
    
    return render_template('realm/search.html', 
                           query=query, 
                           materials=materials,
                           categories=categories)

@main_bp.route('/material/<path:uri>')
def material_details(uri):
    """Render the material details page.
    
    Args:
        uri: URI of the material
    """
    material = material_service.get_material(uri)
    
    if not material:
        return render_template('realm/error.html', 
                              message=f"Material not found: {uri}"), 404
    
    return render_template('realm/material.html', material=material)

@main_bp.route('/compare')
def compare_materials():
    """Render the material comparison page."""
    uri1 = request.args.get('uri1', '')
    uri2 = request.args.get('uri2', '')
    
    material1 = None
    material2 = None
    comparison = None
    
    if uri1 and uri2:
        material1 = material_service.get_material(uri1)
        material2 = material_service.get_material(uri2)
        
        if material1 and material2:
            comparison = material_service.compare_materials(uri1, uri2)
    
    return render_template('realm/compare.html',
                           uri1=uri1,
                           uri2=uri2,
                           material1=material1,
                           material2=material2,
                           comparison=comparison)

@main_bp.route('/chat')
def chat():
    """Render the materials chat page."""
    # Initialize or get conversation history
    history = session.get('chat_history', [])
    
    return render_template('realm/chat.html', history=history)

@main_bp.route('/clear_chat', methods=['POST'])
def clear_chat():
    """Clear the chat history."""
    session['chat_history'] = []
    return redirect(url_for('main.chat'))

@main_bp.route('/categories')
def categories():
    """Render the categories page."""
    categories = material_service.get_categories()
    return render_template('realm/categories.html', categories=categories)

@main_bp.route('/about')
def about():
    """Render the about page."""
    return render_template('realm/about.html')
