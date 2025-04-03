#!/usr/bin/env python3
"""
Simplified script to test the ontology extraction functionality.
This script doesn't require the app module and can be run independently.
"""

import os
import sys
import json
import requests

def test_ontology_extraction(ontology_source):
    """
    Test entity extraction from the given ontology source using direct HTTP requests.
    
    Args:
        ontology_source (str): The ontology source identifier
        
    Returns:
        dict: The extracted entities
    """
    print(f"\nTesting entity extraction from: {ontology_source}")
    
    # MCP server URL - adjust if your server is running on a different port
    mcp_url = "http://localhost:5001"
    
    try:
        # Make a direct request to the MCP server ontology endpoint
        url = f"{mcp_url}/api/ontology/{ontology_source}/entities"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            
            # Extract entities from the response
            entities = result.get("entities", {})
            
            # Count the number of entities in each category
            categories = ["roles", "conditions", "resources", "events", "actions"]
            
            for cat in categories:
                if cat in entities:
                    entity_list = entities[cat]
                    print(f"  {cat.capitalize()}: {len(entity_list)} entities")
                    
                    # Print up to 3 example entities
                    if entity_list:
                        print(f"\n{cat.capitalize()} examples:")
                        for item in entity_list[:3]:  # Print at most 3 examples
                            if isinstance(item, dict) and "label" in item:
                                print(f"  - {item['label']}: {item.get('description', 'No description')}")
                            else:
                                print(f"  - {item}")
                else:
                    print(f"  {cat.capitalize()}: 0 entities (category not found)")
            
            return entities
        else:
            print(f"Error: HTTP status {response.status_code}")
            print(f"Response: {response.text}")
            return {}
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to MCP server at {mcp_url}")
        print("Make sure the MCP server is running.")
        return {}
    except Exception as e:
        print(f"Error: {str(e)}")
        return {}

def main():
    """Main function for testing ontologies."""
    # Process command line arguments
    if len(sys.argv) > 1:
        ontology_sources = sys.argv[1:]
    else:
        # Default ontologies to test
        ontology_sources = ["proethica-intermediate.ttl", "engineering-ethics.ttl"]
    
    # Test each ontology
    for ontology_source in ontology_sources:
        test_ontology_extraction(ontology_source)
    
    print("\nTest completed.")
    print("If you're still not seeing entities in the UI, try the following:")
    print("1. Restart the MCP server")
    print("2. Refresh the world details page in the browser")
    print("3. Edit the world and re-save it to trigger entity extraction")

if __name__ == "__main__":
    main()
