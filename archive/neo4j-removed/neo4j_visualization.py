"""
Neo4j Graph Visualization Routes
Provides web-based graph visualization of ontologies stored in Neo4j.
"""

from flask import Blueprint, render_template, jsonify, request, current_app
from app.services.neo4j_graph_service import get_neo4j_service
import logging

logger = logging.getLogger(__name__)

# Create blueprint
neo4j_bp = Blueprint('neo4j', __name__, url_prefix='/neo4j')

@neo4j_bp.route('/graph')
def graph_visualization():
    """
    Main graph visualization page.
    Supports query parameters:
    - ontology: 'engineering-ethics', 'proethica-intermediate', 'bfo', 'relationships', or 'all'
    - load: 'true' to auto-load data
    - limit: max number of nodes (default 100)
    """
    ontology = request.args.get('ontology', 'all')
    auto_load = request.args.get('load', 'false').lower() == 'true'
    limit = int(request.args.get('limit', 100))
    
    # Validate ontology parameter
    valid_ontologies = ['engineering-ethics', 'proethica-intermediate', 'bfo', 'relationships', 'all']
    if ontology not in valid_ontologies:
        ontology = 'all'
    
    return render_template(
        'neo4j/graph_visualization.html',
        ontology=ontology,
        auto_load=auto_load,
        limit=limit,
        valid_ontologies=valid_ontologies
    )

@neo4j_bp.route('/api/graph-data')
def get_graph_data():
    """
    API endpoint to get graph data from Neo4j.
    Returns JSON with nodes and edges for visualization.
    """
    ontology = request.args.get('ontology', 'all')
    limit = int(request.args.get('limit', 100))
    
    try:
        service = get_neo4j_service()
        data = service.get_ontology_graph(ontology=ontology, limit=limit)
        
        if 'error' in data:
            return jsonify({
                'success': False,
                'error': data['error'],
                'nodes': [],
                'edges': []
            }), 500
        
        return jsonify({
            'success': True,
            'data': data,
            'nodes': data['nodes'],
            'edges': data['edges'],
            'stats': data.get('stats', {})
        })
        
    except Exception as e:
        logger.error(f"Error getting graph data: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'nodes': [],
            'edges': []
        }), 500

@neo4j_bp.route('/api/stats')
def get_ontology_stats():
    """Get statistics about loaded ontologies."""
    try:
        service = get_neo4j_service()
        stats = service.get_ontology_stats()
        
        if 'error' in stats:
            return jsonify({
                'success': False,
                'error': stats['error']
            }), 500
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@neo4j_bp.route('/reload')
def reload_ontologies():
    """
    Endpoint to reload ontologies into Neo4j.
    This runs the loading script to refresh the data.
    """
    try:
        import subprocess
        import os
        
        # Run the ontology loading script
        script_path = os.path.join(current_app.root_path, '..', 'scripts', 'load_ontologies_to_neo4j.py')
        
        if os.path.exists(script_path):
            result = subprocess.run(
                ['python', script_path],
                capture_output=True,
                text=True,
                cwd=os.path.join(current_app.root_path, '..')
            )
            
            if result.returncode == 0:
                return jsonify({
                    'success': True,
                    'message': 'Ontologies reloaded successfully',
                    'output': result.stdout
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f"Script failed: {result.stderr}",
                    'output': result.stdout
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'Loading script not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error reloading ontologies: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500