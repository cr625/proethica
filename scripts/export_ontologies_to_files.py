#!/usr/bin/env python3
"""
Script to export ontologies from the database to TTL files for better stability
"""

import os
import sys

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set the database URL directly to avoid parsing issues
os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'

# Import Flask app and models
from app import create_app
from app.models.ontology import Ontology

def export_ontologies():
    """Export all ontologies from the database to TTL files."""
    app = create_app()
    
    # Create directory for ontologies if it doesn't exist
    ontologies_dir = os.path.join(os.path.dirname(__file__), '..', 'ontologies')
    if not os.path.exists(ontologies_dir):
        os.makedirs(ontologies_dir)
        print(f"Created directory: {ontologies_dir}")
    
    with app.app_context():
        ontologies = Ontology.query.all()
        
        if not ontologies:
            print("No ontologies found in the database.")
            return
        
        print(f"Found {len(ontologies)} ontologies to export:")
        for ont in ontologies:
            # Create a filename from the domain_id
            filename = f"{ont.domain_id}.ttl"
            file_path = os.path.join(ontologies_dir, filename)
            
            # Write the ontology content to the file
            if ont.content:
                with open(file_path, 'w') as f:
                    f.write(ont.content)
                print(f"- Exported: {ont.name} to {file_path}")
                print(f"  Content length: {len(ont.content)} characters")
            else:
                print(f"- Skipped: {ont.name} (No content)")
            
        print("\nExport completed successfully.")

if __name__ == "__main__":
    export_ontologies()
