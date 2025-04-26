#!/usr/bin/env python3
"""
Script to check details of ontology with ID 1 in the database.
"""
import os
import sys

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.ontology import Ontology

def check_ontology():
    """
    Check details of the ontology with ID 1 in the database.
    """
    print("Checking ontology with ID 1...")
    
    app = create_app()
    with app.app_context():
        ontology = Ontology.query.get(1)
        
        if not ontology:
            print("Error: Ontology with ID 1 not found.")
            return False
            
        print(f"Ontology ID: {ontology.id}")
        print(f"Name: {ontology.name}")
        print(f"Description: {ontology.description}")
        print(f"Domain ID: {ontology.domain_id}")
        print(f"Base URI: {ontology.base_uri}")
        print(f"Is base: {ontology.is_base}")
        print(f"Is editable: {ontology.is_editable}")
        print(f"Created at: {ontology.created_at}")
        print(f"Updated at: {ontology.updated_at}")
        
        # Check if any worlds use this ontology
        worlds = ontology.worlds
        if worlds:
            print(f"\nThis ontology is used by {len(worlds)} world(s):")
            for world in worlds:
                print(f"  - World ID: {world.id}, Name: {world.name}")
        else:
            print("\nThis ontology is not used by any worlds.")
            
        return True

if __name__ == "__main__":
    check_ontology()
