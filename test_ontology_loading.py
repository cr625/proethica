#!/usr/bin/env python3
"""
Test script to verify the fixed ontology loading from database in the MCP server.
Run this after starting the MCP server with `./restart_mcp_server.sh`.
"""

import os
import sys
import json
import requests

# Set up paths
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def test_get_world_entities():
    """Test the get_world_entities tool via the JSON-RPC endpoint."""
    print("Testing ontology loading from database...")
    
    url = "http://localhost:5001/jsonrpc"
    
    # Prepare JSON-RPC request
    payload = {
        "jsonrpc": "2.0",
        "method": "call_tool",
        "params": {
            "name": "get_world_entities",
            "arguments": {
                "ontology_source": "engineering_ethics",  # This should be loaded from DB or file
                "entity_type": "all"
            }
        },
        "id": 1
    }
    
    try:
        # Make the request
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Parse the response
        result = response.json()
        
        if "error" in result:
            print(f"Error: {result['error']['message']}")
            return False
        
        # Parse the entity data from the JSON string
        content_text = result["result"]["content"][0]["text"]
        entities_data = json.loads(content_text)["entities"]
        
        # Count the entities
        total_entities = sum(len(entity_list) for entity_list in entities_data.values())
        
        print(f"Successfully loaded ontology with {total_entities} total entities:")
        
        for entity_type, entities in entities_data.items():
            print(f"  - {len(entities)} {entity_type}")
            
            # Print a sample of each entity type (up to 3)
            for i, entity in enumerate(entities[:3]):
                print(f"    * {entity['label']}")
            
            if len(entities) > 3:
                print(f"    * ... and {len(entities) - 3} more")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return False
    except json.JSONDecodeError:
        print(f"Invalid JSON response: {response.text}")
        return False
    except Exception as e:
        print(f"Test failed: {e}")
        return False

def test_server_health():
    """Test the health endpoint of the MCP server."""
    print("Testing MCP server health...")
    
    try:
        response = requests.get("http://localhost:5001/health")
        response.raise_for_status()
        
        result = response.json()
        print(f"Server health: {result['status']} - {result['message']}")
        return True
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

if __name__ == "__main__":
    # First check if the server is running
    if not test_server_health():
        print("MCP server does not appear to be running. Please start it with ./restart_mcp_server.sh")
        sys.exit(1)
    
    # Test ontology loading
    if test_get_world_entities():
        print("\nSUCCESS: Ontology loading is working correctly!")
    else:
        print("\nFAILURE: Ontology loading test failed.")
        sys.exit(1)
