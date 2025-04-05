#!/usr/bin/env python
"""
Add temporal functionality to the HTTP ontology MCP server.

This script enhances the MCP server with additional endpoints
to support temporal queries and timeline generation for Claude.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
import logging
import json
from aiohttp import web

# Setup logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Function to add temporal endpoints to the HTTP MCP server
def add_temporal_endpoints(app):
    """
    Add temporal endpoints to the aiohttp application for the MCP server.
    
    Args:
        app: aiohttp application instance
    """
    logger.info("Adding temporal endpoints to MCP server...")
    
    # Create a Flask app context helper to interact with the ORM
    async def get_flask_context():
        from app import create_app
        app = create_app()
        return app
    
    # Timeline endpoint
    async def get_timeline(request):
        """Get the complete timeline for a scenario."""
        try:
            scenario_id = int(request.match_info['scenario_id'])
            
            # Use Flask app context
            flask_app = await get_flask_context()
            with flask_app.app_context():
                from app.services.temporal_context_service import TemporalContextService
                temporal_service = TemporalContextService()
                timeline = temporal_service.build_timeline(scenario_id)
            
            return web.json_response(timeline)
        except Exception as e:
            logger.error(f"Error building timeline: {str(e)}")
            return web.json_response({"error": str(e)}, status=500)
    
    # Temporal context endpoint
    async def get_temporal_context(request):
        """Get formatted temporal context for Claude."""
        try:
            scenario_id = int(request.match_info['scenario_id'])
            
            # Use Flask app context
            flask_app = await get_flask_context()
            with flask_app.app_context():
                from app.services.temporal_context_service import TemporalContextService
                temporal_service = TemporalContextService()
                context = temporal_service.get_temporal_context_for_claude(scenario_id)
            
            return web.json_response({"context": context})
        except Exception as e:
            logger.error(f"Error getting temporal context: {str(e)}")
            return web.json_response({"error": str(e)}, status=500)
    
    # Events in timeframe endpoint
    async def get_events_in_timeframe(request):
        """Get events within a specific timeframe."""
        try:
            data = await request.json()
            if not data:
                return web.json_response({"error": "Missing request data"}, status=400)
            
            start_time = data.get('start_time')
            end_time = data.get('end_time')
            scenario_id = data.get('scenario_id')
            entity_type = data.get('entity_type')
            
            if not all([start_time, end_time, scenario_id]):
                return web.json_response({
                    "error": "Missing required parameters: start_time, end_time, scenario_id"
                }, status=400)
            
            try:
                start_dt = datetime.fromisoformat(start_time)
                end_dt = datetime.fromisoformat(end_time)
            except ValueError:
                return web.json_response({
                    "error": "Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
                }, status=400)
            
            # Use Flask app context
            flask_app = await get_flask_context()
            with flask_app.app_context():
                from app.services.temporal_context_service import TemporalContextService
                temporal_service = TemporalContextService()
                triples = temporal_service.find_triples_in_timeframe(
                    start_dt, end_dt, entity_type=entity_type, scenario_id=scenario_id
                )
                results = [triple.to_dict() for triple in triples]
            
            return web.json_response({"events": results})
        except Exception as e:
            logger.error(f"Error finding events in timeframe: {str(e)}")
            return web.json_response({"error": str(e)}, status=500)
    
    # Temporal sequence endpoint
    async def get_temporal_sequence(request):
        """Get a sequence of events in temporal order."""
        try:
            scenario_id = int(request.match_info['scenario_id'])
            
            # Get query parameters
            entity_type = request.query.get('entity_type')
            limit = request.query.get('limit')
            if limit:
                try:
                    limit = int(limit)
                except ValueError:
                    return web.json_response({"error": "Invalid limit parameter"}, status=400)
            
            # Use Flask app context
            flask_app = await get_flask_context()
            with flask_app.app_context():
                from app.services.temporal_context_service import TemporalContextService
                temporal_service = TemporalContextService()
                sequence = temporal_service.find_temporal_sequence(
                    scenario_id, entity_type=entity_type, limit=limit
                )
                results = [triple.to_dict() for triple in sequence]
            
            return web.json_response({"sequence": results})
        except Exception as e:
            logger.error(f"Error getting temporal sequence: {str(e)}")
            return web.json_response({"error": str(e)}, status=500)
    
    # Temporal relation endpoint
    async def get_temporal_relation(request):
        """Get triples with a specific temporal relation to a given triple."""
        try:
            triple_id = int(request.match_info['triple_id'])
            
            # Get query parameters
            relation_type = request.query.get('relation_type')
            if not relation_type:
                return web.json_response({"error": "Missing relation_type parameter"}, status=400)
            
            # Use Flask app context
            flask_app = await get_flask_context()
            with flask_app.app_context():
                from app.services.temporal_context_service import TemporalContextService
                temporal_service = TemporalContextService()
                relations = temporal_service.find_temporal_relations(triple_id, relation_type)
                results = [triple.to_dict() for triple in relations]
            
            return web.json_response({"relations": results})
        except Exception as e:
            logger.error(f"Error getting temporal relations: {str(e)}")
            return web.json_response({"error": str(e)}, status=500)
    
    # Create temporal relation endpoint
    async def create_temporal_relation(request):
        """Create a temporal relation between two triples."""
        try:
            data = await request.json()
            if not data:
                return web.json_response({"error": "Missing request data"}, status=400)
            
            from_triple_id = data.get('from_triple_id')
            to_triple_id = data.get('to_triple_id')
            relation_type = data.get('relation_type')
            
            if not all([from_triple_id, to_triple_id, relation_type]):
                return web.json_response({
                    "error": "Missing required parameters: from_triple_id, to_triple_id, relation_type"
                }, status=400)
            
            # Use Flask app context
            flask_app = await get_flask_context()
            with flask_app.app_context():
                from app.services.temporal_context_service import TemporalContextService
                temporal_service = TemporalContextService()
                success = temporal_service.create_temporal_relation(
                    from_triple_id, to_triple_id, relation_type
                )
            
            if success:
                return web.json_response({"success": True})
            else:
                return web.json_response({"error": "Failed to create temporal relation"}, status=400)
        except Exception as e:
            logger.error(f"Error creating temporal relation: {str(e)}")
            return web.json_response({"error": str(e)}, status=500)
    
    # Add routes to the application
    app.router.add_get('/api/timeline/{scenario_id}', get_timeline)
    app.router.add_get('/api/temporal_context/{scenario_id}', get_temporal_context)
    app.router.add_post('/api/events_in_timeframe', get_events_in_timeframe)
    app.router.add_get('/api/temporal_sequence/{scenario_id}', get_temporal_sequence)
    app.router.add_get('/api/temporal_relation/{triple_id}', get_temporal_relation)
    app.router.add_post('/api/create_temporal_relation', create_temporal_relation)
    
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
    app_creation_index = content.find('app = web.Application()')
    if app_creation_index == -1:
        logger.error("Could not find aiohttp app creation in MCP server file.")
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
    # Look for the line after app creation
    app_line_end = content.find('\n', app_creation_index)
    if app_line_end == -1:
        logger.error("Could not find appropriate position to add temporal endpoints.")
        return False
    
    # Add function call to add temporal endpoints
    new_call = '\n    # Add temporal endpoints\n    add_temporal_endpoints(app)\n'
    content = content[:app_line_end] + content[app_line_end:app_line_end+1] + new_call + content[app_line_end+1:]
    
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
