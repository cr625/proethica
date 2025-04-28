#!/usr/bin/env python3

"""
Enhanced Ontology MCP Server startup script.
This script starts the enhanced MCP server with support for advanced ontology interactions.
"""

import os
import sys
import asyncio
import aiohttp
from aiohttp import web
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import the enhanced server
from mcp.enhanced_ontology_mcp_server import EnhancedOntologyMCPServer

if __name__ == "__main__":
    print("Starting Enhanced Ontology MCP Server...")
    port = int(os.environ.get("MCP_SERVER_PORT", 5001))
    print(f"Server will listen on port {port}")
    
    # Create the server
    server = EnhancedOntologyMCPServer()
    
    # Create web application
    app = web.Application()
    
    # JSON-RPC endpoint
    app.router.add_post('/jsonrpc', server.handle_jsonrpc)
    
    # Direct API endpoints
    app.router.add_get('/api/ontology/{ontology_source}/entities', server.handle_get_entities)
    app.router.add_get('/api/guidelines/{world_name}', server.handle_get_guidelines)
    
    # CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    app.middlewares.append(cors_middleware)

    # Run the server using asyncio
    async def start():
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', port)
        await site.start()
        print(f"Server started on http://localhost:{port}")
        
        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
            
    # Start the server
    asyncio.run(start())
