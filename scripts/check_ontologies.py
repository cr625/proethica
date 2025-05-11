#!/usr/bin/env python3
"""
Script to check ontologies in the database
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

def check_ontologies():
    """List all ontologies in the database."""
    app = create_app()
    
    with app.app_context():
        ontologies = Ontology.query.all()
        
        if not ontologies:
            print("No ontologies found in the database.")
            return
        
        print(f"Found {len(ontologies)} ontologies:")
        for ont in ontologies:
            print(f"- ID: {ont.id}, Name: {ont.name}, Domain ID: {ont.domain_id}")
            print(f"  Base: {ont.is_base}, Editable: {ont.is_editable}")
            print(f"  Content length: {len(ont.content) if ont.content else 0} characters")
            print()

if __name__ == "__main__":
    check_ontologies()
