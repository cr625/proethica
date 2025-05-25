#!/usr/bin/env python3
"""
Debug script for the MCP Guideline Analysis Server

This script manually starts the MCP server with detailed error reporting
and then tests the guideline analysis functionality.
"""

import os
import sys
import json
import time
import asyncio
import requests
import logging
from pathlib import Path

# Set up logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

MCP_URL = "http://localhost:5001"
SERVER_PROCESS = None

async def start_server():
    """Start the MCP server in a separate task."""
    try:
        logger.info("Starting Enhanced Ontology MCP Server with Guidelines Support...")
        
        # Import and run the server
        from mcp.enhanced_ontology_server_with_guidelines import run_server
        
        # Print current environment variables that might be relevant
        logger.info(f"ANTHROPIC_API_KEY present: {bool(os.environ.get('ANTHROPIC_API_KEY'))}")
        logger.info(f"OPENAI_API_KEY present: {bool(os.environ.get('OPENAI_API_KEY'))}")
        
        # Create and return the server task
        return asyncio.create_task(run_server())
        
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        import traceback
        traceback.print_exc()
        return None

def wait_for_server(timeout=30):
    """Wait for the server to start, with timeout."""
    logger.info(f"Waiting up to {timeout} seconds for server to start...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Check the health endpoint instead of the root URL
            response = requests.get(f"{MCP_URL}/health", timeout=2)
            if response.status_code == 200:
                logger.info("MCP server is running!")
                return True
        except requests.exceptions.RequestException:
            # Keep waiting
            pass
        
        time.sleep(1)
    
    logger.error(f"Timed out after {timeout} seconds waiting for server to start")
    return False

def read_test_guideline():
    """Read the test guideline content."""
    try:
        guideline_path = Path("test_guideline.txt")
        if not guideline_path.exists():
            logger.error(f"Test guideline file not found at {guideline_path}")
            return None
        
        with open(guideline_path, "r") as f:
            content = f.read()
            logger.info(f"Read {len(content)} characters from test guideline")
            return content
    except Exception as e:
        logger.error(f"Error reading test guideline: {str(e)}")
        return None

def test_extract_concepts(content):
    """Test the extract_guideline_concepts tool."""
    logger.info("Testing extract_guideline_concepts tool...")
    
    try:
        response = requests.post(
            f"{MCP_URL}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "extract_guideline_concepts",
                    "arguments": {
                        "content": content[:10000],  # Limit to first 10k chars
                        "ontology_source": "engineering-ethics"
                    }
                },
                "id": 1
            },
            timeout=60
        )
        
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Response JSON: {json.dumps(result, indent=2)[:500]}...")
            
            if "result" in result:
                concepts = result["result"].get("concepts", [])
                logger.info(f"Successfully extracted {len(concepts)} concepts")
                return concepts
            else:
                logger.error(f"Error in response: {result.get('error', 'Unknown error')}")
                return None
        else:
            logger.error(f"HTTP error: {response.status_code}")
            logger.error(f"Response content: {response.text[:1000]}...")
            return None
    except Exception as e:
        logger.error(f"Error calling extract_guideline_concepts: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """Main function to run the test."""
    global SERVER_PROCESS
    
    logger.info("Starting MCP guideline analysis debug test")
    
    # Start the server
    SERVER_PROCESS = await start_server()
    if not SERVER_PROCESS:
        logger.error("Failed to start server process")
        return
    
    # Wait for server to become available
    if not wait_for_server():
        logger.error("Server did not start within the timeout period")
        if SERVER_PROCESS:
            SERVER_PROCESS.cancel()
        return
    
    # Read the test guideline
    content = read_test_guideline()
    if not content:
        if SERVER_PROCESS:
            SERVER_PROCESS.cancel()
        return
    
    # Test extract concepts
    concepts = test_extract_concepts(content)
    
    # Clean up
    if SERVER_PROCESS:
        logger.info("Stopping server...")
        SERVER_PROCESS.cancel()
        try:
            await SERVER_PROCESS
        except asyncio.CancelledError:
            logger.info("Server stopped")
    
    if concepts:
        logger.info("Test completed successfully")
    else:
        logger.error("Test failed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        import traceback
        traceback.print_exc()
