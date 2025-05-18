#!/usr/bin/env python3
"""
Test script for guideline concept extraction using the live LLM (not mock responses).
This script verifies that the EnhancedOntologyServerWithGuidelines can successfully
extract concepts from guideline text using the Claude API.
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

# Sample guideline text for testing - small excerpt to minimize token usage
SAMPLE_GUIDELINE = """
NSPE Code of Ethics for Engineers - Excerpt

I. Fundamental Canons
Engineers, in the fulfillment of their professional duties, shall:
1. Hold paramount the safety, health, and welfare of the public.
2. Perform services only in areas of their competence.
3. Issue public statements only in an objective and truthful manner.
4. Act for each employer or client as faithful agents or trustees.
5. Avoid deceptive acts.
6. Conduct themselves honorably, responsibly, ethically, and lawfully so as to enhance the honor, reputation, and usefulness of the profession.
"""

async def test_live_llm_extraction():
    """Test guideline concept extraction with live LLM integration."""
    # Check if API keys are set
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    
    if not anthropic_key and not openai_key:
        logger.error("ERROR: Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY environment variables are set")
        logger.error("Please set at least one of these environment variables to test live LLM extraction")
        return
    
    # Create server instance
    logger.info("Creating EnhancedOntologyServerWithGuidelines instance")
    server = EnhancedOntologyServerWithGuidelines()
    
    try:
        # Explicitly disable mock mode
        os.environ["USE_MOCK_GUIDELINE_RESPONSES"] = "false"
        logger.info("Mock responses are DISABLED - using live LLM")
        
        # Test get_ontology_sources method
        logger.info("Testing get_ontology_sources()")
        sources = await server.get_ontology_sources()
        logger.info(f"Found {len(sources.get('sources', []))} ontology sources")
        
        # Use the default source from the sources
        default_source = sources.get('default') or "engineering-ethics"
        logger.info(f"Using source: {default_source}")
        
        # Create guideline analysis module 
        logger.info("Creating GuidelineAnalysisModule")
        module = GuidelineAnalysisModule(
            llm_client=server.anthropic_client,  # Pass the LLM client explicitly
            ontology_client=server,
            embedding_client=server.embeddings_client
        )
        
        # Verify the module settings
        logger.info(f"Module mock mode is: {module.use_mock_responses}")
        logger.info(f"Module has LLM client: {module.llm_client is not None}")
        
        # Test extracting concepts with live LLM
        logger.info("Testing concept extraction with LIVE LLM responses")
        logger.info("This may take a minute or two as it makes a real API call...")
        
        # Start timing
        import time
        start_time = time.time()
        
        # Make the API call
        result = await module.extract_guideline_concepts({
            "content": SAMPLE_GUIDELINE,
            "ontology_source": default_source
        })
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        logger.info(f"API call completed in {elapsed_time:.2f} seconds")
        
        # Check result
        if "error" in result:
            logger.error(f"Error extracting concepts: {result['error']}")
            if "LLM client not available" in result.get("error", ""):
                logger.error("LLM client initialization failed - check if your API key is valid")
        else:
            concepts = result.get("concepts", [])
            logger.info(f"Successfully extracted {len(concepts)} concepts")
            
            # Print all extracted concepts
            for i, concept in enumerate(concepts):
                logger.info(f"Concept {i+1}: {concept.get('label')} - {concept.get('category')}")
                
            # Write results to file for inspection
            output_file = "live_llm_extraction_results.json"
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2)
            logger.info(f"Saved detailed results to {output_file}")
                
        logger.info("Test completed successfully")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
    
if __name__ == "__main__":
    asyncio.run(test_live_llm_extraction())
