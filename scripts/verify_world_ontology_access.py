#!/usr/bin/env python3
"""
Script to verify that a world can still access its assigned ontology after renaming.
"""
import os
import sys
import requests
import json

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.world import World
from app.models.ontology import Ontology

def verify_world_ontology_access():
    """
    Verify that a world can access its assigned ontology after the ontology has been renamed.
    """
    print("Verifying world can access its ontology...")
    
    app = create_app()
    with app.app_context():
        # Get the world that uses ontology ID 1
        world = World.query.filter_by(ontology_id=1).first()
        
        if not world:
            print("Error: No world found with ontology_id=1.")
            return False
            
        # Get the associated ontology
        ontology = Ontology.query.get(1)
        
        if not ontology:
            print("Error: Ontology with ID 1 not found.")
            return False
            
        print(f"World: {world.name} (ID: {world.id})")
        print(f"Ontology source: {world.ontology_source}")
        print(f"Ontology: {ontology.name} (ID: {ontology.id})")
        print(f"Ontology domain_id: {ontology.domain_id}")
        
        # Check if world.ontology_source matches ontology.domain_id
        if world.ontology_source != ontology.domain_id:
            print("\nWarning: World's ontology_source does not match the ontology domain_id.")
            print("This may cause issues with entity retrieval.")
            
            # Update the world's ontology_source to match the new domain_id
            print(f"\nUpdating world's ontology_source from '{world.ontology_source}' to '{ontology.domain_id}'...")
            world.ontology_source = ontology.domain_id
            db.session.commit()
            print("Update successful!")
        else:
            print("\nWorld's ontology_source matches ontology domain_id. No update needed.")
        
        # Verify MCP server can retrieve entities for this ontology
        print("\nVerifying MCP server can retrieve entities...")
        try:
            # Try to get MCP server URL from environment
            mcp_server_url = os.environ.get('MCP_SERVER_URL', 'http://localhost:5001')
            
            # Make a request to the MCP server to get roles from this ontology
            url = f"{mcp_server_url}/api/ontology/{ontology.domain_id}/entities"
            payload = {
                "arguments": {
                    "ontology_source": ontology.domain_id,
                    "entity_type": "roles"
                }
            }
            
            print(f"Making request to: {url}")
            response = requests.post(url, json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if 'entities' in data and 'roles' in data['entities']:
                    roles = data['entities']['roles']
                    print(f"Successfully retrieved {len(roles)} roles from the ontology:")
                    for role in roles[:3]:  # Show first 3 roles
                        print(f"  - {role.get('label', 'Unknown')} ({role.get('id', 'No ID')})")
                    if len(roles) > 3:
                        print(f"  ... and {len(roles) - 3} more")
                else:
                    print("No roles found in the response.")
            else:
                print(f"Failed to retrieve roles. Status code: {response.status_code}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error accessing MCP server: {str(e)}")
            
        return True

if __name__ == "__main__":
    verify_world_ontology_access()
