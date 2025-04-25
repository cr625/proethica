#!/usr/bin/env python3
"""
Script to update the MCP ontology server to load from database instead of files.
This allows the system to function properly after removing ontology .ttl files.
"""

import os
import sys
import argparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import models
from app import db
from app.models.ontology import Ontology

def create_patch_file():
    """Create a patch file for the MCP server."""
    
    patch_content = """
import os
import sys
from app import db
from app.models.ontology import Ontology

# Patch for OntologyMCPServer class
def _load_ontology_from_db(self, ontology_source):
    \"\"\"
    Load ontology content from database.
    Replaces _load_graph_from_file to enable database-sourced ontologies.
    
    Args:
        ontology_source: Source identifier for ontology (filename)
        
    Returns:
        RDFLib Graph object with loaded ontology
    \"\"\"
    from rdflib import Graph
    
    g = Graph()
    if not ontology_source:
        print(f"Error: No ontology source specified", file=sys.stderr)
        return g

    # Handle cleanup of file extension if present
    if ontology_source.endswith('.ttl'):
        domain_id = ontology_source[:-4]  # Remove .ttl extension
    else:
        domain_id = ontology_source
        
    try:
        # Try to fetch from database
        from flask import current_app
        with current_app.app_context():
            ontology = Ontology.query.filter_by(domain_id=domain_id).first()
            if ontology:
                print(f"Loading ontology '{domain_id}' from database", file=sys.stderr)
                g.parse(data=ontology.content, format="turtle")
                print(f"Successfully loaded ontology '{domain_id}' from database", file=sys.stderr)
                return g
                
        # If not found in database, fall back to file (for backward compatibility)
        print(f"Ontology '{domain_id}' not found in database, checking filesystem", file=sys.stderr)
        ontology_path = os.path.join(ONTOLOGY_DIR, ontology_source)
        if not os.path.exists(ontology_path):
            print(f"Error: Ontology file not found: {ontology_path}", file=sys.stderr)
            return g

        g.parse(ontology_path, format="turtle")
        print(f"Successfully loaded ontology from {ontology_path}", file=sys.stderr)
    except Exception as e:
        print(f"Failed to load ontology: {str(e)}", file=sys.stderr)
    return g

# Replace the original method with our DB-aware version
OntologyMCPServer._load_graph_from_file = _load_ontology_from_db
"""

    patch_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mcp', 'load_from_db.py')
    with open(patch_path, 'w') as f:
        f.write(patch_content)
    
    print(f"Created patch file at {patch_path}")
    return patch_path

def update_init_file(patch_path):
    """Update the __init__.py file to import the patch."""
    
    init_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mcp', '__init__.py')
    
    # Read current content
    if os.path.exists(init_path):
        with open(init_path, 'r') as f:
            content = f.read()
    else:
        content = ""
    
    # Add import if not already present
    patch_import = f"from mcp.load_from_db import *  # Patch to load ontologies from database"
    if patch_import not in content:
        if content and not content.endswith('\n'):
            content += '\n'
        content += f"\n{patch_import}\n"
        
        with open(init_path, 'w') as f:
            f.write(content)
        print(f"Updated {init_path} to import patch")
    else:
        print(f"Patch already imported in {init_path}")

def main():
    """Main function to update the MCP server."""
    
    # Check if ontologies exist in database
    try:
        from app import create_app
        app = create_app("development")
        with app.app_context():
            ontology_count = Ontology.query.count()
            
        if ontology_count == 0:
            print("ERROR: No ontologies found in the database.")
            print("Please run scripts/migrate_ontologies_to_db.py first.")
            return 1
            
        print(f"Found {ontology_count} ontologies in the database.")
    except Exception as e:
        print(f"ERROR: Failed to check ontologies in database: {str(e)}")
        return 1
    
    # Create patch file
    patch_path = create_patch_file()
    
    # Update __init__.py
    update_init_file(patch_path)
    
    print("\nMCP server successfully updated to load ontologies from database.")
    print("You can now safely archive or remove the .ttl files using:")
    print("    python scripts/remove_ontology_files.py")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
