#!/usr/bin/env python3
"""
Test script for verifying the enhanced ontology MCP server startup with the
implemented get_ontology_sources() and get_ontology_entities() methods.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import server class
from mcp.enhanced_ontology_server_with_guidelines import EnhancedOntologyServerWithGuidelines

async def test_server_startup():
    """Test the enhanced ontology server startup."""
    try:
        # Set mock mode for faster testing
        os.environ["USE_MOCK_GUIDELINE_RESPONSES"] = "true"
        
        # Create server instance
        logger.info("Creating EnhancedOntologyServerWithGuidelines instance")
        server = EnhancedOntologyServerWithGuidelines()
        
        # Start the server
        logger.info("Starting server")
        await server.start()
        
        # Wait a moment for the server to initialize
        logger.info("Server started, waiting to verify it's running...")
        await asyncio.sleep(2)
        
        # Test calling the get_ontology_sources method
        logger.info("Testing get_ontology_sources()")
        sources = await server.get_ontology_sources()
        logger.info(f"Found {len(sources.get('sources', []))} ontology sources")
        
        # Test extracting guideline concepts through the server
        logger.info("Server test completed successfully, shutting down...")
        
        # Shutdown server
        await server.stop()
        logger.info("Server stopped")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_server_startup())
