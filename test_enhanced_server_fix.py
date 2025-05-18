#!/usr/bin/env python3
"""
Test script to verify the fix for the enhanced ontology server with guidelines.

This script tests both the ontology client wrapper and the file path fix.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import the fixed server implementation
from mcp.enhanced_ontology_server_with_guidelines import EnhancedOntologyServerWithGuidelines

async def test_server_fixes():
    """Test the fixed server implementation."""
    logger.info("Creating server instance...")
    server = EnhancedOntologyServerWithGuidelines()
    
    # Test ontology sources with correct filename
    logger.info("Testing ontology sources method...")
    sources = await server.get_ontology_sources()
    logger.info(f"Ontology sources: {sources}")
    
    # Verify the ontology source ID is now using underscore
    if sources and sources.get("sources") and len(sources["sources"]) > 0:
        source_id = sources["sources"][0]["id"]
        if source_id == "engineering_ethics":
            logger.info(f"✅ Source ID is correct: {source_id}")
        else:
            logger.error(f"❌ Source ID is incorrect: {source_id}, expected 'engineering_ethics'")
    
    # Test wrapper functionality
    logger.info("Testing wrapper functionality...")
    wrapper = server.ontology_client_wrapper
    wrapper_sources = await wrapper.get_ontology_sources()
    
    if wrapper_sources == sources:
        logger.info("✅ Wrapper correctly forwards ontology_sources method")
    else:
        logger.error(f"❌ Wrapper sources don't match server sources: {wrapper_sources} vs {sources}")
    
    # Check that the file can be loaded
    logger.info("Testing file loading with correct path...")
    try:
        # Use a direct file with extension for testing
        g = server._load_graph_from_file("engineering_ethics.ttl")
        logger.info(f"✅ Graph loaded successfully with {len(g)} triples")
    except Exception as e:
        logger.error(f"❌ Error loading graph: {str(e)}")
    
    logger.info("Tests completed")

def main():
    """Run the tests."""
    asyncio.run(test_server_fixes())

if __name__ == "__main__":
    main()
