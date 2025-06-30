"""
Routes for domain handling.

This module provides routes for managing domains in the application.
Now enhanced to support the new domain registry system.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.models.world import World
from app.services.domain_registry import domain_registry

# Create a blueprint for the domains routes
domains_bp = Blueprint('domains', __name__)

@domains_bp.route('/')
@login_required
def list_domains():
    """
    List all available domain types from the domain registry.
    
    Returns:
        Rendered template with domain configurations
    """
    domains = domain_registry.get_all_domains()
    return render_template('domains/list.html', domains=domains)

@domains_bp.route('/registry')
@login_required 
def view_registry():
    """
    View the domain registry details including all configurations.
    
    Returns:
        Rendered template with registry information
    """
    domains = domain_registry.get_all_domains()
    return render_template('domains/registry.html', domains=domains)

@domains_bp.route('/api/domains')
def api_list_domains():
    """
    API endpoint to list all available domain types.
    
    Returns:
        JSON response with domain configurations
    """
    try:
        domains = domain_registry.get_all_domains()
        domain_list = []
        
        for name, config in domains.items():
            domain_list.append({
                "name": config.name,
                "display_name": config.display_name,
                "description": config.description,
                "adapter_class": config.adapter_class_name,
                "sections": {
                    "guidelines": config.guideline_sections,
                    "cases": config.case_sections
                },
                "ontology_namespace": config.ontology_namespace
            })
        
        return jsonify({
            "status": "success", 
            "domains": domain_list,
            "count": len(domain_list)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@domains_bp.route('/api/domains/<domain_name>')
def api_get_domain(domain_name):
    """
    API endpoint to get a specific domain configuration.
    
    Args:
        domain_name: Name of the domain
        
    Returns:
        JSON response with domain configuration
    """
    try:
        domain_config = domain_registry.get_domain(domain_name)
        
        if not domain_config:
            return jsonify({
                "status": "error", 
                "message": f"Domain '{domain_name}' not found"
            }), 404
        
        return jsonify({
            "status": "success",
            "domain": domain_config.to_dict()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@domains_bp.route('/api/domains/reload', methods=['POST'])
@login_required
def api_reload_domains():
    """
    API endpoint to reload domain configurations from disk.
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        domain_registry.reload_configs()
        domains = domain_registry.list_domains()
        
        return jsonify({
            "status": "success",
            "message": "Domain configurations reloaded",
            "domains": domains
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@domains_bp.route('/test')
@login_required
def test_domain_registry():
    """
    Test page to validate domain registry functionality.
    
    Returns:
        Rendered test page with domain registry information
    """
    domains = domain_registry.get_all_domains()
    
    # Test creating an adapter for engineering domain
    adapter_test = None
    try:
        if 'engineering' in domains:
            adapter = domain_registry.create_adapter('engineering')
            adapter_test = {
                "success": True,
                "adapter_class": adapter.__class__.__name__,
                "message": "Successfully created engineering adapter"
            }
    except Exception as e:
        adapter_test = {
            "success": False,
            "message": str(e)
        }
    
    return render_template(
        'domains/test.html', 
        domains=domains,
        adapter_test=adapter_test
    )
