#!/usr/bin/env python3
"""
Run script for the Hosted LLM MCP Server.

This script provides a convenient way to start the server with environment variables
and configuration options.
"""

import os
import sys
import argparse
import logging
import asyncio

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the server module
from mcp.hosted_llm_mcp.server import HostedLLMMCPServer

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Start the Hosted LLM MCP Server')
    
    parser.add_argument('--anthropic-key', type=str, help='Anthropic API Key')
    parser.add_argument('--openai-key', type=str, help='OpenAI API Key')
    parser.add_argument('--mcp-url', type=str, default='http://localhost:5001', 
                        help='URL of the enhanced ontology MCP server')
    parser.add_argument('--config', type=str, default=None, 
                        help='Path to a custom config.json file')
    parser.add_argument('--log-level', type=str, default='INFO', 
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level')
    
    return parser.parse_args()

async def main():
    """Main function to run the server."""
    args = parse_args()
    
    # Set up logging
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=os.path.join(os.path.dirname(__file__), 'hosted_llm_server.log')
    )
    console = logging.StreamHandler()
    console.setLevel(log_level)
    logging.getLogger('').addHandler(console)
    
    logger = logging.getLogger(__name__)
    
    # Set environment variables from command line arguments if provided
    if args.anthropic_key:
        os.environ['ANTHROPIC_API_KEY'] = args.anthropic_key
        
    if args.openai_key:
        os.environ['OPENAI_API_KEY'] = args.openai_key
        
    if args.mcp_url:
        os.environ['MCP_SERVER_URL'] = args.mcp_url
    
    # Check for required API keys
    if not os.environ.get('ANTHROPIC_API_KEY'):
        logger.error("ANTHROPIC_API_KEY not set. Please set it in the environment or use --anthropic-key")
        return
        
    if not os.environ.get('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY not set. Please set it in the environment or use --openai-key")
        return
    
    # Start the server
    logger.info("Starting Hosted LLM MCP Server...")
    server = HostedLLMMCPServer()
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
