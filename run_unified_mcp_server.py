#!/usr/bin/env python3
"""
Run script for the Unified Ontology MCP Server.

This script initializes and runs the server with all available modules.
"""

import os
import sys
import logging
import signal
import argparse
from typing import Dict, Any
import asyncio
import json
import traceback
from aiohttp import web

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from mcp.unified_ontology_server import UnifiedOntologyServer

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("run_unified_mcp_server")


async def get_health(request):
    """Health check endpoint."""
    return web.json_response({"status": "ok", "service": "unified-ontology-mcp"})


async def get_info(request):
    """Server info endpoint."""
    server = request.app["server"]
    
    # Get available modules and tools
    modules = []
    tools = []
    
    for name, module in server.modules.items():
        module_tools = module.get_tools()
        tools.extend(module_tools)
        
        modules.append({
            "name": name,
            "description": module.description,
            "tools_count": len(module_tools)
        })
    
    result = {
        "modules": modules,
        "tools": [t["name"] for t in tools],
        "server_type": "unified-ontology-mcp",
        "version": "0.1.0"
    }
    
    return web.json_response(result)


async def on_startup(app):
    """Initialize components on startup."""
    # Create and initialize the server
    server = UnifiedOntologyServer()
    app["server"] = server
    logger.info("Server initialized")


async def on_cleanup(app):
    """Perform cleanup on shutdown."""
    logger.info("Shutting down server...")
    
    # Shutdown the server
    if "server" in app:
        app["server"].shutdown()
    
    logger.info("Server shut down successfully")


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run the Unified Ontology MCP Server")
    
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Port to bind the server to (default: 5001)"
    )
    
    return parser.parse_args()


def setup_routes(app):
    """Set up the application routes."""
    app.add_routes([
        web.get("/health", get_health),
        web.get("/info", get_info),
        web.post("/jsonrpc", lambda request: request.app["server"].handle_jsonrpc(request)),
        
        # Direct API endpoints (alternative to JSON-RPC)
        web.get("/api/entities/{ontology_source}", lambda request: request.app["server"].handle_get_entities(request)),
        web.get("/api/guidelines/{world_name}", lambda request: request.app["server"].handle_get_guidelines(request)),
        
        # Legacy paths for backward compatibility
        web.post("/api/v1/get_world_entities", lambda request: request.app["server"].handle_jsonrpc(request)),
        web.post("/api/v1/get_entity_relationships", lambda request: request.app["server"].handle_jsonrpc(request)),
        web.post("/api/v1/query_ontology", lambda request: request.app["server"].handle_jsonrpc(request))
    ])


def handle_signals():
    """Set up signal handlers for graceful shutdown."""
    # Get the event loop
    loop = asyncio.get_event_loop()
    
    # Set up signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(loop)))


async def shutdown(loop):
    """Shut down the server gracefully."""
    logger.info("Shutdown signal received")
    
    # Close all tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    for task in tasks:
        task.cancel()
    
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Stop the event loop
    loop.stop()


def main():
    """Main entry point for the server."""
    args = parse_arguments()
    
    # Create and configure the application
    app = web.Application()
    
    # Set up startup and cleanup handlers
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    # Set up routes
    setup_routes(app)
    
    # Set up signal handlers
    handle_signals()
    
    # Run the server
    logger.info(f"Starting server on {args.host}:{args.port}")
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
