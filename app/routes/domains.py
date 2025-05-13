"""
Routes for domain handling.

This module provides routes for managing domains in the application.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.world import World

# Create a blueprint for the domains routes
domains_bp = Blueprint('domains', __name__)

@domains_bp.route('/')
def list_domains():
    """
    List all domains.
    
    Returns:
        Rendered template with domains
    """
    # In this application, domains are typically represented as worlds
    # So we'll redirect to the worlds listing
    return redirect(url_for('worlds.list_worlds'))

@domains_bp.route('/<int:domain_id>')
def view_domain(domain_id):
    """
    View a specific domain.
    
    Args:
        domain_id: ID of the domain
        
    Returns:
        Rendered domain template or redirect
    """
    # In this application, domains are typically represented as worlds
    # So we'll redirect to the world view
    return redirect(url_for('worlds.view_world', world_id=domain_id))

@domains_bp.route('/api/domains')
def api_list_domains():
    """
    API endpoint to list all domains.
    
    Returns:
        JSON response with domains
    """
    try:
        # Get worlds as domains
        worlds = World.query.all()
        domains = [{"id": w.id, "name": w.name, "description": w.description} for w in worlds]
        return jsonify({"status": "success", "domains": domains})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
