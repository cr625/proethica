"""
Ontology Routes

This module provides routes for interacting with the ontology system,
including verification endpoints to check connectivity between the
Flask application and the unified ontology server.
"""

from flask import Blueprint, jsonify, request, current_app, render_template
import requests
import os
import json
from urllib.parse import urljoin
import logging

# Create a blueprint for ontology routes
bp = Blueprint('ontology', __name__, url_prefix='/api/ontology')

@bp.route('/status', methods=['GET'])
def ontology_status():
    """Test the connection to the ontology server and return its status"""
    ontology_url = os.getenv('MCP_SERVER_URL', 'http://localhost:5002')
    
    try:
        # Try to get info from the ontology server
        response = requests.get(f"{ontology_url}/info", timeout=5)
        
        if response.status_code == 200:
            # Get server info
            info = response.json()
            
            return jsonify({
                'status': 'connected',
                'ontology_server': ontology_url,
                'server_info': info,
                'message': 'Successfully connected to the ontology server'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f"Failed to connect to ontology server: HTTP {response.status_code}"
            }), 500
            
    except requests.RequestException as e:
        return jsonify({
            'status': 'error',
            'message': f"Failed to connect to ontology server: {str(e)}"
        }), 500

@bp.route('/tools', methods=['GET'])
def list_tools():
    """Get the list of available tools from the ontology server"""
    ontology_url = os.getenv('MCP_SERVER_URL', 'http://localhost:5002')
    
    try:
        # Try to get tools from the ontology server
        response = requests.get(f"{ontology_url}/info", timeout=5)
        
        if response.status_code == 200:
            info = response.json()
            tools = info.get('tools', [])
            
            return jsonify({
                'status': 'success',
                'tools': tools
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f"Failed to get tools: HTTP {response.status_code}"
            }), 500
            
    except requests.RequestException as e:
        return jsonify({
            'status': 'error',
            'message': f"Failed to connect to ontology server: {str(e)}"
        }), 500

@bp.route('/query', methods=['POST'])
def query_ontology():
    """Execute a SPARQL query against the ontology"""
    ontology_url = os.getenv('MCP_SERVER_URL', 'http://localhost:5002')
    
    # Get query from request
    data = request.json
    if not data or 'query' not in data:
        return jsonify({
            'status': 'error',
            'message': 'Missing query parameter'
        }), 400
        
    query = data['query']
    
    try:
        # Send query to ontology server
        response = requests.post(
            f"{ontology_url}/rpc",
            json={
                'jsonrpc': '2.0',
                'method': 'query_module.execute_sparql',
                'params': {
                    'query': query
                },
                'id': 1
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Check for JSON-RPC error
            if 'error' in result:
                return jsonify({
                    'status': 'error',
                    'message': result['error'].get('message', 'Unknown error'),
                    'code': result['error'].get('code', -1)
                }), 500
                
            return jsonify({
                'status': 'success',
                'results': result.get('result', {})
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f"Failed to execute query: HTTP {response.status_code}"
            }), 500
            
    except requests.RequestException as e:
        return jsonify({
            'status': 'error',
            'message': f"Failed to connect to ontology server: {str(e)}"
        }), 500

@bp.route('/entity/<entity_id>', methods=['GET'])
def get_entity(entity_id):
    """Get detailed information about an entity from the ontology"""
    ontology_url = os.getenv('MCP_SERVER_URL', 'http://localhost:5002')
    
    try:
        # Send request to ontology server
        response = requests.post(
            f"{ontology_url}/rpc",
            json={
                'jsonrpc': '2.0',
                'method': 'query_module.get_entity_details',
                'params': {
                    'entity_id': entity_id
                },
                'id': 1
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Check for JSON-RPC error
            if 'error' in result:
                return jsonify({
                    'status': 'error',
                    'message': result['error'].get('message', 'Unknown error'),
                    'code': result['error'].get('code', -1)
                }), 404 if "not found" in result['error'].get('message', '').lower() else 500
                
            return jsonify({
                'status': 'success',
                'entity': result.get('result', {})
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f"Failed to get entity details: HTTP {response.status_code}"
            }), 500
            
    except requests.RequestException as e:
        return jsonify({
            'status': 'error',
            'message': f"Failed to connect to ontology server: {str(e)}"
        }), 500

@bp.route('/analyze_case/<case_id>', methods=['GET'])
def analyze_case(case_id):
    """Analyze a case using the ontology"""
    ontology_url = os.getenv('MCP_SERVER_URL', 'http://localhost:5002')
    
    try:
        # Send request to ontology server
        response = requests.post(
            f"{ontology_url}/rpc",
            json={
                'jsonrpc': '2.0',
                'method': 'case_analysis_module.analyze_case',
                'params': {
                    'case_id': case_id
                },
                'id': 1
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Check for JSON-RPC error
            if 'error' in result:
                return jsonify({
                    'status': 'error',
                    'message': result['error'].get('message', 'Unknown error'),
                    'code': result['error'].get('code', -1)
                }), 404 if "not found" in result['error'].get('message', '').lower() else 500
                
            return jsonify({
                'status': 'success',
                'analysis': result.get('result', {})
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f"Failed to analyze case: HTTP {response.status_code}"
            }), 500
            
    except requests.RequestException as e:
        return jsonify({
            'status': 'error',
            'message': f"Failed to connect to ontology server: {str(e)}"
        }), 500
