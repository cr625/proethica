#!/usr/bin/env python3
"""
Simplified MCP server to test database connection fix.
This script focuses only on testing the ontology database loading.
"""

import os
import sys
import json
import asyncio
from aiohttp import web

# Add the parent directory to the path so we can import mcp as a package
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from mcp.http_ontology_mcp_server import OntologyMCPServer

async def run_test_server():
    server = OntologyMCPServer()
    app = web.Application()
    
    # Only register the jsonrpc endpoint for testing
    app.router.add_post('/jsonrpc', server.handle_jsonrpc)
    app.router.add_get('/health', server.handle_health)
    
    # Add CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    app.middlewares.append(cors_middleware)
    
    # Start the server
    PORT = 5001
    print(f"Starting simplified MCP test server on port {PORT}", file=sys.stderr)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', PORT)
    await site.start()
    
    print("Server started. Press Ctrl+C to stop.", file=sys.stderr)
    
    # Test the _load_graph_from_file method directly with database loading
    print("\nTesting database loading directly...", file=sys.stderr)
    try:
        # Try loading engineering_ethics from the database
        g = server._load_graph_from_file("engineering_ethics")
        print(f"Graph loaded with {len(g)} triples", file=sys.stderr)
    except Exception as e:
        print(f"Error loading graph: {str(e)}", file=sys.stderr)
    
    # Keep the server running
    try:
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    except asyncio.CancelledError:
        print("Server shutting down...", file=sys.stderr)
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(run_test_server())
    except KeyboardInterrupt:
        print("Server stopped by user", file=sys.stderr)
