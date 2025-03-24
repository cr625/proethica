from flask import Blueprint, request, jsonify
import os
import json
import subprocess
import tempfile

mcp_api_bp = Blueprint('mcp_api', __name__, url_prefix='/api')

@mcp_api_bp.route('/ontology/<path:ontology_source>/entities', methods=['GET'])
def get_ontology_entities(ontology_source):
    """
    Get entities from an ontology source.
    
    Args:
        ontology_source: Path to the ontology source file
        
    Returns:
        JSON response with entities
    """
    # Return the mock data directly
    from app.services.mcp_client import MCPClient
    client = MCPClient.get_instance()
    mock_entities = client.get_mock_entities(ontology_source)
    return jsonify(mock_entities)

@mcp_api_bp.route('/guidelines/<path:world_name>', methods=['GET'])
def get_guidelines(world_name):
    """
    Get guidelines for a specific world.
    
    Args:
        world_name: Name of the world
        
    Returns:
        JSON response with guidelines
    """
    try:
        # Return the mock guidelines
        from app.services.mcp_client import MCPClient
        client = MCPClient.get_instance()
        mock_guidelines = client.get_mock_guidelines(world_name)
        return jsonify(mock_guidelines)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
