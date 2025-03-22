import os
import sys
import json
from app.services.mcp_client import MCPClient

def test_get_world_entities():
    """Test the get_world_entities method of MCPClient."""
    try:
        # Initialize the MCP client
        mcp_client = MCPClient()
        
        # Test with the tccc.ttl ontology file
        ontology_source = "tccc.ttl"
        print(f"Testing get_world_entities with ontology_source={ontology_source}")
        
        # Get world entities
        entities = mcp_client.get_world_entities(ontology_source)
        
        # Print the result
        print("Success! Entities retrieved:")
        print(json.dumps(entities, indent=2))
        
        # Check if entities were retrieved
        if "entities" in entities and entities["entities"]:
            print(f"Found {len(entities['entities'])} entity types")
            for entity_type, entity_list in entities["entities"].items():
                print(f"- {entity_type}: {len(entity_list)} entities")
        else:
            print("No entities found or invalid response format")
        
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    test_get_world_entities()
