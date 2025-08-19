#!/usr/bin/env python3
"""
Detailed script to check ontologies in the database and compare with files
"""

import os
import sys

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Set the database URL directly to avoid parsing issues
os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'

# Import Flask app and models
from app import create_app
from app.models.ontology import Ontology

def check_ontologies_detailed():
    """List all ontologies in the database with detailed information."""
    app = create_app('config')
    
    with app.app_context():
        ontologies = Ontology.query.all()
        
        if not ontologies:
            print("No ontologies found in the database.")
            return
        
        print("=" * 80)
        print("DATABASE ONTOLOGIES DETAILED REPORT")
        print("=" * 80)
        print(f"Found {len(ontologies)} ontologies:")
        print()
        
        for ont in ontologies:
            print(f"ONTOLOGY #{ont.id}: {ont.name}")
            print("-" * 60)
            print(f"Domain ID: {ont.domain_id}")
            print(f"Description: {ont.description or 'None'}")
            print(f"Base URI: {ont.base_uri or 'None'}")
            print(f"Is Base: {ont.is_base}")
            print(f"Is Editable: {ont.is_editable}")
            print(f"Created: {ont.created_at}")
            print(f"Updated: {ont.updated_at}")
            print(f"Content length: {len(ont.content) if ont.content else 0} characters")
            
            # Show first few lines of content
            if ont.content:
                print("\nFirst 10 lines of content:")
                lines = ont.content.split('\n')
                for i, line in enumerate(lines[:10]):
                    if line.strip():
                        print(f"  {i+1:2d}: {line}")
            
            # Show last few lines of content
            if ont.content:
                print("\nLast 5 lines of content:")
                lines = ont.content.split('\n')
                for i, line in enumerate(lines[-5:]):
                    if line.strip():
                        print(f"  {len(lines)-5+i+1:2d}: {line}")
            
            print()

def check_file_ontologies():
    """Check ontologies in the ontologies folder."""
    ontologies_dir = '/home/chris/onto/proethica/ontologies'
    
    print("=" * 80)
    print("FILE ONTOLOGIES REPORT")
    print("=" * 80)
    
    if not os.path.exists(ontologies_dir):
        print(f"Ontologies directory not found: {ontologies_dir}")
        return
    
    files = [f for f in os.listdir(ontologies_dir) if f.endswith('.ttl')]
    
    print(f"Found {len(files)} TTL files in {ontologies_dir}:")
    print()
    
    for filename in sorted(files):
        filepath = os.path.join(ontologies_dir, filename)
        
        print(f"FILE: {filename}")
        print("-" * 60)
        
        with open(filepath, 'r') as f:
            content = f.read()
            
        print(f"Size: {len(content)} characters")
        print(f"Lines: {len(content.split('\n'))}")
        
        # Show first few lines
        print("\nFirst 10 lines:")
        lines = content.split('\n')
        for i, line in enumerate(lines[:10]):
            if line.strip():
                print(f"  {i+1:2d}: {line}")
        
        print()

if __name__ == "__main__":
    check_ontologies_detailed()
    check_file_ontologies()