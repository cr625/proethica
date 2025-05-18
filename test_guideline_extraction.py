#!/usr/bin/env python3
"""
Test script for guideline concept extraction using the enhanced ontology MCP server.
This script verifies that the get_ontology_sources() and get_ontology_entities() methods
are working correctly.
"""

import os
import sys
import json
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

# Import server and module classes
from mcp.enhanced_ontology_server_with_guidelines import EnhancedOntologyServerWithGuidelines
from mcp.modules.guideline_analysis_module import GuidelineAnalysisModule

# Sample guideline text for testing
SAMPLE_GUIDELINE = """
NSPE Code of Ethics for Engineers

Preamble
Engineering is an important and learned profession. As members of this profession, engineers are expected to exhibit the highest standards of honesty and integrity. Engineering has a direct and vital impact on the quality of life for all people. Accordingly, the services provided by engineers require honesty, impartiality, fairness, and equity, and must be dedicated to the protection of the public health, safety, and welfare. Engineers must perform under a standard of professional behavior that requires adherence to the highest principles of ethical conduct.

I. Fundamental Canons
Engineers, in the fulfillment of their professional duties, shall:
1. Hold paramount the safety, health, and welfare of the public.
2. Perform services only in areas of their competence.
3. Issue public statements only in an objective and truthful manner.
4. Act for each employer or client as faithful agents or trustees.
5. Avoid deceptive acts.
6. Conduct themselves honorably, responsibly, ethically, and lawfully so as to enhance the honor, reputation, and usefulness of the profession.
"""

async def test_guideline_extraction():
    """Test guideline concept extraction with the enhanced ontology server."""
    # Create server instance
    logger.info("Creating EnhancedOntologyServerWithGuidelines instance")
    server = EnhancedOntologyServerWithGuidelines()
    
    try:
        # Configure environment for mock mode - set this BEFORE creating any modules
        os.environ["USE_MOCK_GUIDELINE_RESPONSES"] = "true"
        
        # Test get_ontology_sources method
        logger.info("Testing get_ontology_sources()")
        sources = await server.get_ontology_sources()
        logger.info(f"Found {len(sources.get('sources', []))} ontology sources")
        
        for i, source in enumerate(sources.get('sources', [])):
            logger.info(f"Source {i+1}: {source.get('id')} - {source.get('label')}")
        
        # Use the correct source ID format without .ttl extension
        default_source = "engineering-ethics"
        logger.info(f"Using source: {default_source}")
        
        if default_source:
            # Test get_ontology_entities method
            logger.info(f"Testing get_ontology_entities() with source '{default_source}'")
            entities = await server.get_ontology_entities(default_source)
            
            # Check if entities were loaded
            entity_types = entities.get('entities', {}).keys()
            logger.info(f"Loaded entity types: {', '.join(entity_types)}")
            
            total_entities = sum(len(e) for e in entities.get('entities', {}).values())
            logger.info(f"Total entities loaded: {total_entities}")
        
        # Create guideline analysis module with mock mode - no need to pass use_mock parameter
        logger.info("Creating GuidelineAnalysisModule with mock mode enabled via environment variable")
        module = GuidelineAnalysisModule(
            ontology_client=server,
            embedding_client=server.embeddings_client
        )
        
        # Test extracting concepts
        logger.info("Testing concept extraction with mock responses")
        
        result = await module.extract_guideline_concepts({
            "content": SAMPLE_GUIDELINE,
            "ontology_source": default_source
        })
        
        # Check result
        if "error" in result:
            logger.error(f"Error extracting concepts: {result['error']}")
        else:
            concepts = result.get("concepts", [])
            logger.info(f"Successfully extracted {len(concepts)} concepts")
            
            # Print some example concepts
            for i, concept in enumerate(concepts[:5]):  # Show first 5 concepts
                logger.info(f"Concept {i+1}: {concept.get('label')} - {concept.get('category')}")
                
        logger.info("Test completed successfully")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
    
if __name__ == "__main__":
    asyncio.run(test_guideline_extraction())
