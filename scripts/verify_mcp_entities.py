#!/usr/bin/env python3
"""
Script to verify MCP server can access entities for the updated ontology
using the application's MCP client.
"""
import os
import sys
import json

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.services.mcp_client import MCPClient

def verify_mcp_entities():
    """
    Verify that the MCP client can access entities for the updated ontology.
    """
    print("Verifying MCP client can access entities for the updated ontology...")
    
    app = create_app()
    with app.app_context():
        # Create an MCP client
        mcp_client = MCPClient()
        
        # Try accessing entities for the ontology
        ontology_source = "engineering-ethics"
        print(f"Trying to access entities for ontology source: {ontology_source}")
        
        try:
            # Get roles
            print("Getting roles...")
            roles_result = mcp_client.get_world_entities(ontology_source, entity_type="roles")
            
            if roles_result and 'entities' in roles_result and 'roles' in roles_result['entities']:
                roles = roles_result['entities']['roles']
                print(f"Successfully retrieved {len(roles)} roles:")
                for role in roles[:3]:  # Show first 3 roles
                    print(f"  - {role.get('label', 'Unknown')} ({role.get('id', 'No ID')})")
                if len(roles) > 3:
                    print(f"  ... and {len(roles) - 3} more")
            else:
                print("No roles found in the response.")
                print(f"Response: {json.dumps(roles_result, indent=2)}")
                
            # Get conditions
            print("\nGetting conditions...")
            conditions_result = mcp_client.get_world_entities(ontology_source, entity_type="conditions")
            
            if conditions_result and 'entities' in conditions_result and 'conditions' in conditions_result['entities']:
                conditions = conditions_result['entities']['conditions']
                print(f"Successfully retrieved {len(conditions)} conditions:")
                for condition in conditions[:3]:  # Show first 3 conditions
                    print(f"  - {condition.get('label', 'Unknown')} ({condition.get('id', 'No ID')})")
                if len(conditions) > 3:
                    print(f"  ... and {len(conditions) - 3} more")
            else:
                print("No conditions found in the response.")
                print(f"Response: {json.dumps(conditions_result, indent=2)}")
                
            # Try getting all entity types at once
            print("\nTrying to get all entity types at once...")
            all_entities = mcp_client.get_world_entities(ontology_source)
            
            if all_entities and 'entities' in all_entities:
                print("Successfully retrieved entities:")
                for entity_type, entities in all_entities['entities'].items():
                    print(f"  - {entity_type}: {len(entities)} entities")
            else:
                print("Failed to get all entities.")
                print(f"Response: {json.dumps(all_entities, indent=2)}")
                
            return True
        except Exception as e:
            print(f"Error accessing MCP entities: {str(e)}")
            return False

if __name__ == "__main__":
    verify_mcp_entities()
