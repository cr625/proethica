#!/usr/bin/env python3
"""
Simple client to test guideline concept extraction with the running MCP server.
"""

import sys
import json
import asyncio
import aiohttp
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_extract_guideline_concepts():
    """Test the extract_guideline_concepts tool with the running server."""
    server_url = "http://localhost:5001/jsonrpc"
    
    # Example NSPE code of ethics content
    content = """
    NSPE Code of Ethics for Engineers
    
    I. Fundamental Canons
    Engineers, in the fulfillment of their professional duties, shall:
    1. Hold paramount the safety, health, and welfare of the public.
    2. Perform services only in areas of their competence.
    3. Issue public statements only in an objective and truthful manner.
    4. Act for each employer or client as faithful agents or trustees.
    5. Avoid deceptive acts.
    6. Conduct themselves honorably, responsibly, ethically, and lawfully so as to enhance the honor, reputation, and usefulness of the profession.
    """
    
    # Prepare the JSON-RPC request
    request_data = {
        "jsonrpc": "2.0",
        "method": "call_tool",
        "params": {
            "name": "extract_guideline_concepts",
            "arguments": {
                "content": content,
                "ontology_source": "engineering-ethics"
            }
        },
        "id": 1
    }
    
    logger.info(f"Sending request to MCP server at {server_url}")
    
    async with aiohttp.ClientSession() as session:
        start_time = datetime.now()
        async with session.post(server_url, json=request_data) as response:
            elapsed = (datetime.now() - start_time).total_seconds()
            
            if response.status != 200:
                logger.error(f"Error: HTTP {response.status}")
                return
            
            # Save the raw JSON response for inspection
            raw_result = await response.text()
            with open("guideline_extraction_raw.json", "w") as f:
                f.write(raw_result)
            logger.info("Saved raw response to guideline_extraction_raw.json")
            
            result = await response.json()
            logger.info(f"Request completed in {elapsed:.2f} seconds")
            
            if "error" in result:
                logger.error(f"Error: {result['error']}")
                return
                
            if "result" not in result:
                logger.error("No result returned")
                return
                
            # Success - check for errors in the result
            if "error" in result["result"]:
                logger.error(f"Tool error: {result['result']['error']}")
                # Continue processing to save results despite the error
                
            # Save the processed result
            with open("guideline_extraction_result.json", "w") as f:
                json.dump(result["result"], f, indent=2)
            logger.info("Saved processed results to guideline_extraction_result.json")
                
            # Check if concepts were extracted
            concepts = result["result"].get("concepts", [])
            logger.info(f"Extracted {len(concepts)} concepts from guideline content")
            
            # Print first few concepts
            if concepts:
                logger.info("Examples:")
                for i, concept in enumerate(concepts[:3]):
                    logger.info(f"  {i+1}. {concept.get('label', 'Unnamed')}: {concept.get('description', 'No description')[:100]}...")
            
            logger.info("Test completed successfully")

if __name__ == "__main__":
    asyncio.run(test_extract_guideline_concepts())
