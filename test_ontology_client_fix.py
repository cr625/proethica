#!/usr/bin/env python3
"""
Test script to fix the ontology client issue in the Enhanced Ontology Server with Guidelines.
This confirms the presence of the get_ontology_sources method and proposes a fix.
"""

import sys
import asyncio
import logging
from pathlib import Path
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp.enhanced_ontology_server_with_guidelines import EnhancedOntologyServerWithGuidelines
from mcp.modules.guideline_analysis_module import GuidelineAnalysisModule

class OntologyClientWrapper:
    """
    Wrapper class for the ontology client to ensure method availability.
    This provides a guaranteed interface to the ontology client methods.
    """
    
    def __init__(self, server):
        self.server = server
    
    async def get_ontology_sources(self):
        """Forward to the server's get_ontology_sources method."""
        try:
            if hasattr(self.server, 'get_ontology_sources'):
                return await self.server.get_ontology_sources()
            else:
                logger.error("Server does not have get_ontology_sources method")
                return {"sources": [], "default": None}
        except Exception as e:
            logger.error(f"Error in get_ontology_sources wrapper: {str(e)}")
            return {"sources": [], "default": None}
    
    async def get_ontology_entities(self, ontology_source):
        """Forward to the server's get_ontology_entities method."""
        try:
            if hasattr(self.server, 'get_ontology_entities'):
                return await self.server.get_ontology_entities(ontology_source)
            else:
                logger.error("Server does not have get_ontology_entities method")
                return {"entities": {}}
        except Exception as e:
            logger.error(f"Error in get_ontology_entities wrapper: {str(e)}")
            return {"entities": {}}

async def test_ontology_client():
    """Test the ontology client wrapper to fix the issue."""
    # Create the server instance
    server = EnhancedOntologyServerWithGuidelines()
    
    # Test direct access to server method
    logger.info("Testing direct access to server method...")
    try:
        sources = await server.get_ontology_sources()
        logger.info(f"Direct access successful: {sources}")
    except Exception as e:
        logger.error(f"Direct access failed: {str(e)}")
    
    # Test with wrapper
    logger.info("Testing wrapper access...")
    wrapper = OntologyClientWrapper(server)
    try:
        sources = await wrapper.get_ontology_sources()
        logger.info(f"Wrapper access successful: {sources}")
    except Exception as e:
        logger.error(f"Wrapper access failed: {str(e)}")
    
    # Test with module using wrapper
    logger.info("Testing module with wrapper...")
    module = GuidelineAnalysisModule(
        llm_client=None,
        ontology_client=wrapper,
        embedding_client=None
    )
    
    try:
        entities = await module._get_default_entities()
        logger.info(f"Module access successful: {len(entities)} entities found")
    except Exception as e:
        logger.error(f"Module access failed: {str(e)}")
    
    logger.info("Tests completed")

def main():
    """Run the test."""
    asyncio.run(test_ontology_client())

if __name__ == "__main__":
    main()
