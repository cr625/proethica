#!/usr/bin/env python
"""
Add temporal functionality to the HTTP ontology MCP server.

This script enhances the MCP server with additional endpoints
to support temporal queries and timeline generation for Claude.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, jsonify, request
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Function to add temporal endpoints to the HTTP MCP server
def add_temporal_endpoints(app):
    """
    Add temporal endpoints to the Flask application for the MCP server.
    
    Args:
        app: Flask application instance
    """
    logger.info("Adding temporal endpoints to MCP server...")
    
    @app.route('/api/timeline/<int:scenario_id>', methods=['GET'])
    def get_timeline(scenario_id):
        """Get the complete timeline for a scenario."""
        from app.services.temporal_context_service import TemporalContextService
        temporal_service = TemporalContextService()
        
        try:
            timeline = temporal_service.build_timeline(scenario_id)
            return jsonify(timeline)
        except Exception as e:
            logger.error(f"Error building timeline: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/temporal_context/<int:scenario_id>', methods=['GET'])
    def get_temporal_context(scenario_id):
        """Get formatted temporal context for Claude."""
        from app.services.temporal_context_service import TemporalContextService
        temporal_service = TemporalContextService()
        
        try:
            context = temporal_service.get_temporal_context_for_claude(scenario_id)
            return jsonify({"context": context})
        except Exception as e:
            logger.error(f"Error getting temporal context: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/events_in_timeframe', methods=['POST'])
    def get_events_in_timeframe():
        """Get events within a specific timeframe."""
        from app.services.temporal_context_service import TemporalContextService
        temporal_service = TemporalContextService()
        
        try:
            data = request.json
            if not data:
                return jsonify({"error": "Missing request data"}), 400
                
            start_time = data.get('start_time')
            end_time = data.get('end_time')
            scenario_id = data.get('scenario_id')
            entity_type = data.get('entity_type')
            
            if not all([start_time, end_time, scenario_id]):
                return jsonify({"error": "Missing required parameters: start_time, end_time, scenario_id"}), 400
            
            try:
                start_dt = datetime.fromisoformat(start_time)
                end_dt = datetime.fromisoformat(end_time)
            except ValueError:
                return jsonify({"error": "Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"}), 400
            
            triples = temporal_service.find_triples_in_timeframe(
                start_dt, end_dt, entity_type=entity_type, scenario_id=scenario_id
            )
            
            results = [triple.to_dict() for triple in triples]
            return jsonify({"events": results})
            
        except Exception as e:
            logger.error(f"Error finding events in timeframe: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/temporal_sequence/<int:scenario_id>', methods=['GET'])
    def get_temporal_sequence(scenario_id):
        """Get a sequence of events in temporal order."""
        from app.services.temporal_context_service import TemporalContextService
        temporal_service = TemporalContextService()
        
        try:
            entity_type = request.args.get('entity_type')
            limit = request.args.get('limit')
            if limit:
                try:
                    limit = int(limit)
                except ValueError:
                    return jsonify({"error": "Invalid limit parameter"}), 400
            
            sequence = temporal_service.find_temporal_sequence(
                scenario_id, entity_type=entity_type, limit=limit
            )
            
            results = [triple.to_dict() for triple in sequence]
            return jsonify({"sequence": results})
            
        except Exception as e:
            logger.error(f"Error getting temporal sequence: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/temporal_relation/<int:triple_id>', methods=['GET'])
    def get_temporal_relation(triple_id):
        """Get triples with a specific temporal relation to a given triple."""
        from app.services.temporal_context_service import TemporalContextService
        temporal_service = TemporalContextService()
        
        try:
            relation_type = request.args.get('relation_type')
            if not relation_type:
                return jsonify({"error": "Missing relation_type parameter"}), 400
            
            relations = temporal_service.find_temporal_relations(triple_id, relation_type)
            
            results = [triple.to_dict() for triple in relations]
            return jsonify({"relations": results})
            
        except Exception as e:
            logger.error(f"Error getting temporal relations: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    # Endpoint for creating temporal links between events
    @app.route('/api/create_temporal_relation', methods=['POST'])
    def create_temporal_relation():
        """Create a temporal relation between two triples."""
        from app.services.temporal_context_service import TemporalContextService
        temporal_service = TemporalContextService()
        
        try:
            data = request.json
            if not data:
                return jsonify({"error": "Missing request data"}), 400
                
            from_triple_id = data.get('from_triple_id')
            to_triple_id = data.get('to_triple_id')
            relation_type = data.get('relation_type')
            
            if not all([from_triple_id, to_triple_id, relation_type]):
                return jsonify({
                    "error": "Missing required parameters: from_triple_id, to_triple_id, relation_type"
                }), 400
            
            success = temporal_service.create_temporal_relation(
                from_triple_id, to_triple_id, relation_type
            )
            
            if success:
                return jsonify({"success": True})
            else:
                return jsonify({"error": "Failed to create temporal relation"}), 400
                
        except Exception as e:
            logger.error(f"Error creating temporal relation: {str(e)}")
            return jsonify({"error": str(e)}), 500

    logger.info("Temporal endpoints added successfully.")

def modify_mcp_server_file():
    """
    Modify the HTTP ontology MCP server file to include the temporal endpoints.
    """
    mcp_server_path = os.path.join(os.path.dirname(__file__), 'http_ontology_mcp_server.py')
    
    # Check if the file exists
    if not os.path.exists(mcp_server_path):
        logger.error(f"MCP server file not found at {mcp_server_path}")
        return False
    
    # Read the MCP server file
    with open(mcp_server_path, 'r') as f:
        content = f.read()
    
    # Check if temporal endpoints are already added
    if 'add_temporal_endpoints' in content:
        logger.info("Temporal endpoints already added to MCP server.")
        return True
    
    # Find the app creation part
    app_creation_index = content.find('app = Flask(__name__)')
    if app_creation_index == -1:
        logger.error("Could not find Flask app creation in MCP server file.")
        return False
    
    # Find a good position to add the import
    import_section_end = content.find('import')
    import_section_end = content.find('\n\n', import_section_end)
    if import_section_end == -1:
        import_section_end = content.find('\n', import_section_end)
    
    # Add import for temporal endpoints
    new_import = '\nfrom mcp.add_temporal_functionality import add_temporal_endpoints'
    content = content[:import_section_end] + new_import + content[import_section_end:]
    
    # Find a good position to add the function call
    # Look for the line before the app.run() call
    run_index = content.find('if __name__ == "__main__"')
    if run_index == -1:
        # Alternative: find before the route definitions
        run_index = content.find('@app.route')
        if run_index == -1:
            logger.error("Could not find appropriate position to add temporal endpoints.")
            return False
        
        # Find the line before @app.route
        run_index = content.rfind('\n', 0, run_index)
    
    # Add function call to add temporal endpoints
    new_call = '\n# Add temporal endpoints\nadd_temporal_endpoints(app)\n'
    content = content[:run_index] + new_call + content[run_index:]
    
    # Write the modified content back
    with open(mcp_server_path, 'w') as f:
        f.write(content)
    
    logger.info(f"MCP server file {mcp_server_path} updated successfully.")
    return True

def main():
    """Main function."""
    logger.info("Adding temporal functionality to MCP server...")
    
    # Modify the MCP server file
    if modify_mcp_server_file():
        logger.info("MCP server enhanced with temporal functionality.")
    else:
        logger.error("Failed to enhance MCP server.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
