#!/usr/bin/env python3
"""
Script to debug ontology routes in the API.
"""

import sys
import os
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.ontology import Ontology
from flask import Flask, jsonify, request, current_app
from ontology_editor.models.metadata import MetadataStorage
from ontology_editor.services.file_storage_utils import read_ontology_file

def debug_get_ontology(ontology_id):
    """Debug the get_ontology route logic."""
    app = create_app()
    
    with app.app_context():
        print(f"Debugging get_ontology route for ID: {ontology_id}")
        
        # Step 1: Try to get from database
        print("\n1. Querying database...")
        ontology = Ontology.query.get(ontology_id)
        
        if ontology:
            print(f"  Found ontology in DB: ID={ontology.id}, Name={ontology.name}")
            print(f"  Content length: {len(ontology.content) if ontology.content else 0} characters")
            print(f"  to_dict() result: {json.dumps(ontology.to_dict(), indent=2)}")
            return
        else:
            print(f"  No ontology found in DB with ID {ontology_id}")
        
        # Step 2: Try legacy metadata storage
        print("\n2. Checking legacy metadata storage...")
        try:
            metadata_storage = MetadataStorage()
            ontology_meta = metadata_storage.get_ontology(ontology_id)
            
            if ontology_meta:
                print(f"  Found ontology in metadata: {json.dumps(ontology_meta, indent=2)}")
                
                # Step 3: Try to read ontology file
                domain = ontology_meta['domain']
                print(f"\n3. Attempting to read ontology file for domain: {domain}")
                content = read_ontology_file(domain, 'main/current.ttl')
                
                if content:
                    print(f"  Successfully read file, content length: {len(content)} characters")
                else:
                    print("  Failed to read ontology file")
            else:
                print(f"  No ontology found in metadata with ID {ontology_id}")
        except Exception as e:
            print(f"  Error accessing metadata storage: {str(e)}")
        
        print("\nConclusion: Ontology not found in either database or metadata storage")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ontology_id = sys.argv[1]
    else:
        ontology_id = "1"  # Default to ID 1
    
    debug_get_ontology(ontology_id)
