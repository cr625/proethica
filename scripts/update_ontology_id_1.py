#!/usr/bin/env python3
"""
Script to update the name and domain_id of ontology with ID 1 in the database.
"""
import os
import sys
from datetime import datetime

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.ontology import Ontology

def update_ontology():
    """
    Update the name and domain_id of ontology with ID 1.
    """
    print("Updating ontology with ID 1...")
    
    # Create backup values for rollback if needed
    old_name = None
    old_domain_id = None
    
    app = create_app()
    with app.app_context():
        # Get the ontology
        ontology = Ontology.query.get(1)
        
        if not ontology:
            print("Error: Ontology with ID 1 not found.")
            return False
        
        # Store original values for reporting
        old_name = ontology.name
        old_domain_id = ontology.domain_id
        
        print(f"Current values:")
        print(f"  - Name: {old_name}")
        print(f"  - Domain ID: {old_domain_id}")
        
        # Update the values
        ontology.name = "Engineering Ethics"
        ontology.domain_id = "engineering-ethics"
        ontology.updated_at = datetime.utcnow()
        
        try:
            # Commit the changes
            db.session.commit()
            print("\nUpdate successful!")
            print(f"New values:")
            print(f"  - Name: {ontology.name}")
            print(f"  - Domain ID: {ontology.domain_id}")
            
            # Check if any worlds use this ontology
            worlds = ontology.worlds
            if worlds:
                print(f"\nNote: This ontology is used by {len(worlds)} world(s):")
                for world in worlds:
                    print(f"  - World ID: {world.id}, Name: {world.name}")
                print("\nMake sure these worlds can still access the ontology after the update.")
            
            return True
        except Exception as e:
            # Roll back in case of error
            db.session.rollback()
            print(f"\nError updating ontology: {str(e)}")
            return False

if __name__ == "__main__":
    update_ontology()
