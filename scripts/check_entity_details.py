#!/usr/bin/env python3
"""
Script to check entity details from the MCP server API.
This helps verify what information is available to the UI for display.
"""

import os
import sys
import json
import argparse
import requests

def get_entity_details(ontology_source, entity_id, mcp_url="http://localhost:5001"):
    """
    Get detailed information about a specific entity from the MCP server.
    
    Args:
        ontology_source (str): The ontology source identifier (e.g., 'engineering-ethics.ttl')
        entity_id (str): The full URI of the entity to check
        mcp_url (str): The URL of the MCP server
    
    Returns:
        dict: The entity details
    """
    print(f"\nChecking entity details for: {entity_id}")
    print(f"From ontology: {ontology_source}")
    
    # First, get all entities to verify the entity is there
    try:
        # Make request to the entities endpoint
        entities_url = f"{mcp_url}/api/ontology/{ontology_source}/entities"
        response = requests.get(entities_url, timeout=10)
        
        if response.status_code != 200:
            print(f"Error: Failed to get entities. HTTP status {response.status_code}")
            print(f"Response: {response.text}")
            return None
        
        # Parse the response
        entities_data = response.json()
        all_entities = {}
        
        # Collect all entities from all categories
        for category in ["roles", "conditions", "resources", "events", "actions"]:
            if category in entities_data.get("entities", {}):
                for entity in entities_data["entities"][category]:
                    if isinstance(entity, dict):
                        all_entities[entity.get("id")] = entity
        
        # Check if the requested entity exists
        if entity_id not in all_entities:
            # Try with different variations of the URI
            if not entity_id.startswith("http://"):
                alt_id = f"http://proethica.org/ontology/engineering-ethics#{entity_id}"
                if alt_id in all_entities:
                    entity_id = alt_id
                else:
                    print(f"Entity not found in any category: {entity_id}")
                    print(f"Available entities: {list(all_entities.keys())[:5]} (and more)")
                    return None
        
        # Get the entity details
        entity_details = all_entities.get(entity_id)
        
        if not entity_details:
            print(f"Entity found but details missing: {entity_id}")
            return None
        
        print("\nEntity Details:")
        print(json.dumps(entity_details, indent=2))
        
        # Check for specific attributes the UI might display
        print("\nKey Attributes for UI Display:")
        for attr in ["label", "description", "tier", "capabilities", "type", "severity", "location"]:
            if attr in entity_details:
                if isinstance(entity_details[attr], list):
                    print(f"  {attr}: {len(entity_details[attr])} items")
                    for item in entity_details[attr][:5]:  # Show up to 5 items
                        print(f"    - {item}")
                    if len(entity_details[attr]) > 5:
                        print(f"    - ... ({len(entity_details[attr]) - 5} more)")
                else:
                    print(f"  {attr}: {entity_details[attr]}")
            else:
                print(f"  {attr}: Not present")
        
        return entity_details
    
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to MCP server at {mcp_url}")
        print("Make sure the MCP server is running.")
        return None
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def find_entity_by_name(ontology_source, entity_name, mcp_url="http://localhost:5001"):
    """
    Find an entity by its name (label) in the ontology.
    
    Args:
        ontology_source (str): The ontology source identifier
        entity_name (str): The name (label) to search for
        mcp_url (str): The URL of the MCP server
    
    Returns:
        str: The entity ID if found, None otherwise
    """
    print(f"\nSearching for entity with name: {entity_name}")
    
    try:
        # Get all entities
        entities_url = f"{mcp_url}/api/ontology/{ontology_source}/entities"
        response = requests.get(entities_url, timeout=10)
        
        if response.status_code != 200:
            print(f"Error: Failed to get entities. HTTP status {response.status_code}")
            return None
        
        # Parse the response
        entities_data = response.json()
        
        # Search through all categories
        for category in ["roles", "conditions", "resources", "events", "actions"]:
            if category in entities_data.get("entities", {}):
                for entity in entities_data["entities"][category]:
                    if isinstance(entity, dict) and entity.get("label") == entity_name:
                        print(f"Found entity in category '{category}': {entity.get('id')}")
                        return entity.get("id")
        
        print(f"No entity found with name: {entity_name}")
        return None
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def main():
    """Main function to check entity details."""
    parser = argparse.ArgumentParser(description="Check entity details from the MCP server")
    parser.add_argument("--ontology", default="engineering-ethics.ttl", help="The ontology source to use")
    parser.add_argument("--entity-id", help="The entity ID (URI) to check")
    parser.add_argument("--entity-name", help="The entity name (label) to search for")
    parser.add_argument("--mcp-url", default="http://localhost:5001", help="The MCP server URL")
    
    args = parser.parse_args()
    
    # First, try to find the entity by name if provided
    if args.entity_name and not args.entity_id:
        entity_id = find_entity_by_name(args.ontology, args.entity_name, args.mcp_url)
        if entity_id:
            args.entity_id = entity_id
    
    # If we have an entity ID, get its details
    if args.entity_id:
        get_entity_details(args.ontology, args.entity_id, args.mcp_url)
    else:
        print("Please provide either --entity-id or --entity-name")
        
        # List a few example entities to help the user
        try:
            entities_url = f"{args.mcp_url}/api/ontology/{args.ontology}/entities"
            response = requests.get(entities_url, timeout=10)
            
            if response.status_code == 200:
                entities_data = response.json()
                
                print("\nAvailable entities by category:")
                for category in ["roles", "conditions", "resources", "events", "actions"]:
                    if category in entities_data.get("entities", {}):
                        entities = entities_data["entities"][category]
                        print(f"\n{category.capitalize()} ({len(entities)} items):")
                        for entity in entities[:3]:  # Show up to 3 entities per category
                            if isinstance(entity, dict):
                                print(f"  - {entity.get('label')}")
        except:
            pass

if __name__ == "__main__":
    main()
