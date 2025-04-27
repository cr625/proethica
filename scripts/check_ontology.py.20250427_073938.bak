#!/usr/bin/env python3
"""
Script to check if an ontology exists in the database.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology

def check_ontology(ontology_id):
    """Check if an ontology with the given ID exists in the database."""
    app = create_app()
    
    with app.app_context():
        ontology = Ontology.query.get(ontology_id)
        
        if ontology:
            print(f"Ontology found: ID={ontology.id}, Name={ontology.name}, Domain={ontology.domain_id}")
            print(f"Content length: {len(ontology.content) if ontology.content else 0} characters")
        else:
            print(f"No ontology found with ID {ontology_id}")
        
        # List all ontologies
        all_ontologies = Ontology.query.all()
        print(f"\nAll ontologies in database ({len(all_ontologies)}):")
        for ont in all_ontologies:
            print(f"  ID={ont.id}, Name={ont.name}, Domain={ont.domain_id}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ontology_id = int(sys.argv[1])
    else:
        ontology_id = 1  # Default to ID 1
    
    check_ontology(ontology_id)
