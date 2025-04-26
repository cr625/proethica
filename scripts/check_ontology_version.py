#!/usr/bin/env python
"""
Script to check if an ontology version exists in the database
and print details about it.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology_version import OntologyVersion

def check_version(ontology_id, version_number):
    """
    Check if a specific version of an ontology exists in the database.
    
    Args:
        ontology_id (int): The ID of the ontology to check.
        version_number (int): The version number to check.
    """
    print(f"Checking version {version_number} of ontology {ontology_id}...")
    
    app = create_app()
    with app.app_context():
        # Query the database for the version
        version = OntologyVersion.query.filter_by(
            ontology_id=ontology_id,
            version_number=version_number
        ).first()
        
        if version:
            print(f"Version {version_number} found!")
            print(f"  ID: {version.id}")
            print(f"  Created at: {version.created_at}")
            print(f"  Commit message: {version.commit_message}")
            print(f"  Content summary: {len(version.content)} characters")
            print(f"  First few characters: {version.content[:100]}...")
        else:
            print(f"Version {version_number} of ontology {ontology_id} not found in the database!")
            
            # Check what versions do exist
            versions = OntologyVersion.query.filter_by(ontology_id=ontology_id).all()
            if versions:
                print(f"Found {len(versions)} versions for ontology {ontology_id}:")
                for v in versions:
                    print(f"  - Version {v.version_number} (ID: {v.id}, Created: {v.created_at})")
            else:
                print(f"No versions found for ontology {ontology_id}!")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python check_ontology_version.py <ontology_id> <version_number>")
        sys.exit(1)
    
    ontology_id = int(sys.argv[1])
    version_number = int(sys.argv[2])
    
    check_version(ontology_id, version_number)
