#!/usr/bin/env python3
"""
MSEO MCP Server Runner.

This script starts the MSEO MCP server, which provides access to the
Materials Science Engineering Ontology via the Model Context Protocol.
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the MSEO MCP server
from mcp.mseo.mseo_mcp_server import MSEOMCPServer

def parse_args():
    """Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Run the MSEO MCP server")
    
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind the server to (default: localhost)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8078,
        help="Port to run the server on (default: 8078)"
    )
    
    parser.add_argument(
        "--data-dir",
        type=str,
        help="Directory for ontology data"
    )
    
    parser.add_argument(
        "--ontology-file",
        type=str,
        help="Path to a specific ontology file"
    )
    
    parser.add_argument(
        "--name",
        type=str,
        default="mseo-mcp-server",
        help="Name for the MCP server"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    
    # Set log level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create data directory
    data_dir = args.data_dir
    if not data_dir:
        # Default to a data directory in the current module
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    
    os.makedirs(data_dir, exist_ok=True)
    
    try:
        # Create MSEO MCP server
        server = MSEOMCPServer(
            name=args.name,
            ontology_file=args.ontology_file,
            data_dir=data_dir
        )
        
        # Load ontology
        if not server.load_ontology():
            logger.error("Failed to load ontology")
            return 1
        
        # Start server
        server.serve(host=args.host, port=args.port)
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Error running server: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
