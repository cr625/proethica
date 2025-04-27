#!/usr/bin/env python3
"""
Script to debug the MCP client's ability to retrieve world entities.
"""
import sys
import os
import requests

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.mcp_client import MCPClient
from app.models.world import World

def test_mcp_client():
    print("Initializing MCP Client...")
    mcp_client = MCPClient()
    
    print("\nTesting direct API endpoint access...")
    # Test direct endpoint with ontology_source (the basename)
    ontology_source = "engineering-ethics-nspe-extended"
    url = f"{mcp_client.mcp_url}/api/ontology/{ontology_source}/entities"
    print(f"Testing URL: {url}")
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Success! API endpoint accessible.")
            result = response.json()
            entity_types = list(result.get('entities', {}).keys())
            print(f"Entity types found: {entity_types}")
            
            # Print count of each entity type
            for entity_type in entity_types:
                count = len(result['entities'][entity_type])
                print(f"  {entity_type}: {count} entities")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Request failed: {str(e)}")
    
    # Try with .ttl extension
    print("\nTesting with .ttl extension...")
    ontology_source_ttl = f"{ontology_source}.ttl"
    url = f"{mcp_client.mcp_url}/api/ontology/{ontology_source_ttl}/entities"
    print(f"Testing URL: {url}")
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Success! API endpoint accessible with .ttl extension.")
            result = response.json()
            entity_types = list(result.get('entities', {}).keys())
            print(f"Entity types found: {entity_types}")
            
            # Print count of each entity type
            for entity_type in entity_types:
                count = len(result['entities'][entity_type])
                print(f"  {entity_type}: {count} entities")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Request failed: {str(e)}")
    
    print("\nTesting MCP client get_world_entities...")
    try:
        # First with regular domain_id
        print(f"Using domain_id: {ontology_source}")
        result = mcp_client.get_world_entities(ontology_source)
        is_mock = result.get('is_mock', False)
        print(f"Result is mock data: {is_mock}")
        entity_types = list(result.get('entities', {}).keys())
        print(f"Entity types found: {entity_types}")
        
        # Print count of each entity type
        for entity_type in entity_types:
            count = len(result['entities'][entity_type])
            print(f"  {entity_type}: {count} entities")
        
        # Now with .ttl extension
        print(f"\nUsing domain_id with .ttl: {ontology_source_ttl}")
        result = mcp_client.get_world_entities(ontology_source_ttl)
        is_mock = result.get('is_mock', False)
        print(f"Result is mock data: {is_mock}")
        entity_types = list(result.get('entities', {}).keys())
        print(f"Entity types found: {entity_types}")
        
        # Print count of each entity type
        for entity_type in entity_types:
            count = len(result['entities'][entity_type])
            print(f"  {entity_type}: {count} entities")
    except Exception as e:
        print(f"MCP client error: {str(e)}")
    
    print("\nDone testing MCP client")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        test_mcp_client()
