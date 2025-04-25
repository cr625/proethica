#!/usr/bin/env python3

"""
Script to mark base ontologies (like BFO) as non-editable in the database.
This prevents users from modifying core ontologies while still allowing them to be viewed and imported.
"""

import sys
import os
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.ontology import Ontology

# List of BFO and core ontology domain IDs that should be protected
PROTECTED_ONTOLOGIES = [
    "bfo-core",
    "proethica-intermediate",
]

def mark_base_ontologies():
    app = create_app()
    with app.app_context():
        # Find all ontologies
        ontologies = Ontology.query.all()
        
        # Display current status
        print("Current ontology status:")
        for ont in ontologies:
            print(f"ID: {ont.id}, Name: {ont.name}, Domain: {ont.domain_id}, Base: {ont.is_base}, Editable: {ont.is_editable}")
        
        print("\nUpdating status for base ontologies:")
        
        # Update protected ontologies
        updated = 0
        for ont in ontologies:
            # Check if this is a protected ontology by its domain_id
            if ont.domain_id in PROTECTED_ONTOLOGIES:
                # Mark as base and non-editable
                ont.is_base = True
                ont.is_editable = False
                updated += 1
                print(f"Protected: {ont.name} (domain: {ont.domain_id})")
            
            # Also check by URI or name if domain_id check fails
            elif ont.base_uri and "purl.obolibrary.org/obo/BFO" in ont.base_uri:
                # This is a BFO ontology by URI
                ont.is_base = True
                ont.is_editable = False
                updated += 1
                print(f"Protected by URI: {ont.name} (URI: {ont.base_uri})")
            
            elif "BFO" in ont.name or "Basic Formal Ontology" in ont.name:
                # This is likely a BFO ontology by name
                ont.is_base = True
                ont.is_editable = False
                updated += 1
                print(f"Protected by name: {ont.name}")
        
        # Commit changes if any ontologies were updated
        if updated > 0:
            db.session.commit()
            print(f"\nSuccessfully updated {updated} ontologies")
        else:
            print("\nNo matching ontologies found to protect")
        
        # Display final status
        print("\nUpdated ontology status:")
        for ont in Ontology.query.all():
            print(f"ID: {ont.id}, Name: {ont.name}, Domain: {ont.domain_id}, Base: {ont.is_base}, Editable: {ont.is_editable}")

def allow_ontology_upload():
    """Future functionality to allow uploading new base ontologies (admin only)"""
    print("\nNote: Uploading new base ontologies will be implemented in a future update.")
    print("This will be restricted to admin users only, maintaining system integrity")
    print("while allowing flexibility for different ontology foundations.")

if __name__ == "__main__":
    print("Protecting base ontologies from editing...\n")
    mark_base_ontologies()
    allow_ontology_upload()
