#!/usr/bin/env python3
"""
Test script to verify the MCP server can extract entity types 
from the ProEthica intermediate and engineering ethics ontologies.
"""

import os
import sys
import json
from app import create_app
from app.models.world import World
from app.services.mcp_client import MCPClient

def test_ontology_entity_extraction(ontology_source):
    """
    Test entity extraction from the given ontology source.
    
    Args:
        ontology_source (str): The ontology source identifier
        
    Returns:
        dict: The extracted entities
    """
    print(f"\nTesting entity extraction from: {ontology_source}")
    
    # Create an instance of the MCP client
    mcp_client = MCPClient.get_instance()
    
    # Check if MCP server is connected
    if not mcp_client.is_connected:
        print("WARNING: MCP server is not connected. Using mock data fallback if enabled.")
    
    # Get entities from the ontology
    try:
        result = mcp_client.get_world_entities(ontology_source)
        print(f"Request successful: {'is_mock' in result and result['is_mock'] and 'Using mock data' or 'Using real data'}")
        
        # Check if result contains the 'entities' key
        if 'entities' in result:
            entities = result['entities']
            
            # Count the number of entities in each category
            categories = {
                'roles': [],
                'conditions': [],
                'resources': [],
                'events': [],
                'actions': []
            }
            
            for cat in categories.keys():
                if cat in entities:
                    categories[cat] = entities[cat]
                    print(f"  {cat.capitalize()}: {len(categories[cat])} entities")
                else:
                    print(f"  {cat.capitalize()}: 0 entities (category not found)")
            
            # Print a few example entities from each non-empty category
            print("\nExample entities from each category:")
            for cat, items in categories.items():
                if items:
                    print(f"\n{cat.capitalize()}:")
                    for item in items[:3]:  # Print at most 3 examples
                        if isinstance(item, dict) and 'label' in item:
                            print(f"  - {item['label']}: {item.get('description', 'No description')}")
                        else:
                            print(f"  - {item}")
            
            return result
        else:
            print("Error: 'entities' key not found in response")
            print(f"Response keys: {result.keys()}")
            return result
    except Exception as e:
        print(f"Error testing ontology: {str(e)}")
        return {"error": str(e)}

def create_test_world(name, description, ontology_source):
    """
    Create a test world with the given ontology source.
    
    Args:
        name (str): World name
        description (str): World description
        ontology_source (str): Ontology source
        
    Returns:
        World: The created world
    """
    print(f"\nCreating test world: {name}")
    
    # Create app and push application context
    app = create_app()
    with app.app_context():
        # Check if world with this name already exists
        existing_world = World.query.filter_by(name=name).first()
        if existing_world:
            print(f"World '{name}' already exists with ID {existing_world.id}")
            existing_world.ontology_source = ontology_source
            print(f"Updated ontology source to: {ontology_source}")
            from app import db
            db.session.commit()
            return existing_world
        
        # Create new world
        from app import db
        world = World(
            name=name,
            description=description,
            ontology_source=ontology_source,
            world_metadata={}
        )
        db.session.add(world)
        db.session.commit()
        print(f"Created world with ID {world.id}")
        return world

def main():
    """Main function for testing ontologies."""
    # Test intermediate ontology
    intermediate_result = test_ontology_entity_extraction('proethica-intermediate.ttl')
    
    # Test engineering ethics ontology
    engineering_result = test_ontology_entity_extraction('engineering-ethics.ttl')
    
    # Create test worlds if requested
    if '--create-worlds' in sys.argv:
        # Create app and push application context
        app = create_app()
        with app.app_context():
            create_test_world(
                "Intermediate Ethics World",
                "A base world using the ProEthica intermediate ontology",
                "proethica-intermediate.ttl"
            )
            
            create_test_world(
                "Engineering Ethics World",
                "A world for engineering ethics scenarios based on the engineering ethics ontology",
                "engineering-ethics.ttl"
            )
    
    print("\nTest completed.")

if __name__ == "__main__":
    main()
