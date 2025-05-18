#!/usr/bin/env python3
"""
Test script to verify that the guideline concept extraction works through the MCP server API.
"""

import os
import sys
import json
import asyncio
import logging
import aiohttp
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Content from NSPE Code of Ethics
GUIDELINE_TEXT = """
NSPE Code of Ethics for Engineers

Engineers shall hold paramount the safety, health, and welfare of the public in the performance of their professional duties.

Engineers shall perform services only in areas of their competence.

Engineers shall issue public statements only in an objective and truthful manner.

Engineers shall act in professional matters for each employer or client as faithful agents or trustees, and shall avoid conflicts of interest.

Engineers shall build their professional reputation on the merit of their services and shall not compete unfairly with others.

Engineers shall act in such a manner as to uphold and enhance the honor, integrity, and dignity of the profession.

Engineers shall continue their professional development throughout their careers and shall provide opportunities for the professional development of those engineers under their supervision.
"""

async def test_guideline_extraction():
    """Test the guideline concept extraction API."""
    logger.info("Testing guideline concept extraction via MCP server API...")
    
    # Prepare the JSON-RPC request
    jsonrpc_request = {
        "jsonrpc": "2.0",
        "method": "call_tool",
        "params": {
            "name": "extract_guideline_concepts",
            "arguments": {
                "content": GUIDELINE_TEXT,
                "ontology_source": "engineering_ethics",
                "ontology_uri": "http://proethica.org/ontology/engineering-ethics#"
            }
        },
        "id": 1
    }
    
    # Make the API request to the running MCP server
    async with aiohttp.ClientSession() as session:
        logger.info("Sending request to MCP server...")
        async with session.post('http://localhost:5001/jsonrpc', json=jsonrpc_request) as response:
            if response.status == 200:
                result = await response.json()
                logger.info(f"Response status: {response.status}")
                
                # Check if the response contains extracted concepts
                if "result" in result and "concepts" in result["result"]:
                    # The concepts are directly in the result
                    concepts = result["result"]["concepts"]
                    logger.info(f"Successfully extracted {len(concepts)} concepts")
                    
                    # Print some sample concepts
                    if concepts:
                        logger.info("Sample concepts:")
                        for i, concept in enumerate(concepts[:5]):  # Show up to 5 sample concepts
                            logger.info(f"  {i+1}. {concept.get('label')} ({concept.get('category')})")
                        
                        logger.info("✅ Guideline concept extraction test PASSED")
                        return True
                    else:
                        logger.error("❌ No concepts found in response")
                else:
                    logger.error(f"❌ Unexpected response format: {result}")
            else:
                logger.error(f"❌ Request failed with status {response.status}")
                error_text = await response.text()
                logger.error(f"Error response: {error_text[:300]}...")
    
    logger.error("❌ Guideline concept extraction test FAILED")
    return False

def main():
    """Run the tests."""
    asyncio.run(test_guideline_extraction())

if __name__ == "__main__":
    main()
