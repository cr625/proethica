#!/usr/bin/env python3
"""
Test Live Guideline Extraction

This script tests the guideline concept extraction through the MCP server API
with live LLM calls (no mock mode).
"""

import sys
import os
import json
import logging
import requests
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MCP_SERVER_URL = "http://localhost:5001/jsonrpc"
REQUEST_ID = 1

def send_jsonrpc_request(method, params):
    """Send a JSON-RPC request to the MCP server."""
    payload = {
        "jsonrpc": "2.0",
        "id": REQUEST_ID,
        "method": method,
        "params": params
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        MCP_SERVER_URL,
        headers=headers,
        data=json.dumps(payload)
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Request failed with status code {response.status_code}")

def test_extract_concepts():
    """Test extracting concepts from a guideline document."""
    # Sample guideline content
    guideline_content = """
    Engineers shall hold paramount the safety, health, and welfare of the public.
    
    Engineers shall perform services only in areas of their competence.
    
    Engineers shall issue public statements only in an objective and truthful manner.
    
    Engineers shall act for each employer or client as faithful agents or trustees.
    
    Engineers shall avoid deceptive acts.
    
    Engineers shall conduct themselves honorably, responsibly, ethically, and
    lawfully so as to enhance the honor, reputation, and usefulness of the profession.
    """
    
    # Call the extract_guideline_concepts tool
    logger.info("Testing extract_guideline_concepts")
    start_time = time.time()
    
    try:
        response = send_jsonrpc_request(
            "call_tool",
            {
                "name": "extract_guideline_concepts",
                "arguments": {
                    "content": guideline_content,
                    "ontology_source": "engineering_ethics"
                }
            }
        )
        
        # Check for error response
        if "error" in response:
            logger.error(f"Error response: {response['error']}")
            return False
        
        # Check the result
        if "result" in response:
            result = response["result"]
            
            # Save the result to a file for inspection
            with open("guideline_extraction_result.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            
            # Save the raw response for debugging
            with open("guideline_extraction_raw.json", "w", encoding="utf-8") as f:
                json.dump(response, f, indent=2)
            
            # Check if concepts were extracted
            if "concepts" in result:
                concepts = result["concepts"]
                num_concepts = len(concepts)
                logger.info(f"Successfully extracted {num_concepts} concepts")
                
                # Log the first few concepts
                for i, concept in enumerate(concepts[:5]):
                    logger.info(f"Concept {i+1}: {concept.get('label', 'Unknown')} - {concept.get('category', 'Unknown')}")
                
                logger.info(f"Extraction completed in {time.time() - start_time:.2f} seconds")
                return True
            else:
                logger.error("No concepts found in result")
                return False
        else:
            logger.error("No result in response")
            return False
    except Exception as e:
        logger.error(f"Error in test_extract_concepts: {str(e)}")
        return False

def main():
    """Run the tests."""
    logger.info("Testing live guideline concept extraction")
    
    # Run the extract concepts test
    success = test_extract_concepts()
    
    if success:
        logger.info("All tests passed")
        return 0
    else:
        logger.error("Tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
