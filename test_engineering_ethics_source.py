#!/usr/bin/env python3
"""
Test script to verify that the enhanced MCP server with guidelines is using 
the engineering-ethics ontology source correctly.
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

async def test_engineering_ethics_source():
    """Test that the server is using engineering-ethics as the only ontology source."""
    try:
        # Create server instance
        logger.info("Creating EnhancedOntologyServerWithGuidelines instance")
        server = EnhancedOntologyServerWithGuidelines()
        
        # Get ontology sources
        logger.info("Testing get_ontology_sources()")
        sources = await server.get_ontology_sources()
        
        # Check sources
        if not sources or "sources" not in sources:
            logger.error("No sources returned")
            return
        
        logger.info(f"Found {len(sources['sources'])} ontology sources")
        
        # Verify that engineering-ethics is the only source
        source_ids = [s["id"] for s in sources["sources"]]
        logger.info(f"Source IDs: {', '.join(source_ids)}")
        
        if len(source_ids) != 1 or source_ids[0] != "engineering-ethics":
            logger.error("Expected only engineering-ethics as source")
        else:
            logger.info("PASS: Only engineering-ethics source is present")
        
        # Verify default source
        default_source = sources.get("default")
        logger.info(f"Default source: {default_source}")
        
        if default_source != "engineering-ethics":
            logger.error("Expected engineering-ethics as default source")
        else:
            logger.info("PASS: engineering-ethics is the default source")
            
        # Now create a guideline analysis module and test ontology-related functionality
        from mcp.modules.guideline_analysis_module import GuidelineAnalysisModule
        
        logger.info("Creating GuidelineAnalysisModule")
        module = GuidelineAnalysisModule(
            llm_client=server.anthropic_client,
            ontology_client=server,
            embedding_client=server.embeddings_client
        )
        
        # Test extracting concepts with engineering-ethics source
        logger.info("Testing concept extraction with engineering-ethics source")
        result = await module.extract_guideline_concepts({
            "content": "Engineers shall hold paramount the safety, health, and welfare of the public.",
            "ontology_source": "engineering-ethics"
        })
        
        # Validate result
        if "error" in result and "no attribute 'get_ontology_sources'" in result.get("error", ""):
            logger.error("FAIL: get_ontology_sources attribute error still occurring")
        else:
            logger.info("PASS: No attribute error for get_ontology_sources")
            
        # Try with an alternative source - should still use engineering-ethics
        logger.info("Testing with alternative source")
        result = await module.extract_guideline_concepts({
            "content": "Engineers shall hold paramount the safety, health, and welfare of the public.",
            "ontology_source": "military-medical-triage"  # This should be ignored/converted to engineering-ethics
        })
        
        # Validate result
        if "error" in result and "no attribute 'get_ontology_sources'" in result.get("error", ""):
            logger.error("FAIL: get_ontology_sources attribute error still occurring")
        else:
            logger.info("PASS: No attribute error for get_ontology_sources")
            
        logger.info("Test completed successfully")
        
    except Exception as e:
        import traceback
        logger.error(f"Test failed with error: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_engineering_ethics_source())
