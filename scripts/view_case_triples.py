#!/usr/bin/env python3
"""
Script to view the triples associated with a specific case ID.
This retrieves the triples directly from the database and prints them.
"""

import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.document import Document
from app.models.entity_triple import EntityTriple

# Case ID to check
CASE_ID = 134

# Create app context
app = create_app()
with app.app_context():
    # Get the case document
    case = Document.query.get(CASE_ID)
    if not case:
        print(f"Case ID {CASE_ID} not found!")
        sys.exit(1)
    
    print(f"Case: {case.title} (ID: {CASE_ID})")
    
    # Get entity triples from database - try both entity and document types
    entity_triples = EntityTriple.query.filter_by(
        entity_type='entity',
        entity_id=CASE_ID
    ).all()
    
    if not entity_triples:
        entity_triples = EntityTriple.query.filter_by(
            entity_type='document',
            entity_id=CASE_ID
        ).all()
    
    if not entity_triples:
        print("No entity triples found in database.")
    else:
        print(f"Found {len(entity_triples)} entity triples in database:")
        for i, triple in enumerate(entity_triples, 1):
            print(f"\n{i}. Triple ID: {triple.id}")
            print(f"   Subject: {triple.subject}")
            print(f"   Predicate: {triple.predicate}")
            if triple.is_literal:
                print(f"   Object: \"{triple.object_literal}\" (literal)")
            else:
                print(f"   Object: {triple.object_uri} (URI)")
            print(f"   Graph: {triple.graph}")
    
    # Check document metadata
    print("\nDocument Metadata:")
    if not case.doc_metadata:
        print("No document metadata found.")
    else:
        # Check for namespaces
        if 'rdf_namespaces' in case.doc_metadata:
            print(f"Namespaces defined: {len(case.doc_metadata['rdf_namespaces'])} namespaces")
            for prefix, uri in case.doc_metadata['rdf_namespaces'].items():
                print(f"   {prefix}: {uri}")
        else:
            print("No namespaces defined in document metadata.")
        
        # Check for triples
        if 'rdf_triples' in case.doc_metadata:
            print(f"\nTriples in document metadata: {len(case.doc_metadata['rdf_triples'])} triples")
            for i, triple in enumerate(case.doc_metadata['rdf_triples'], 1):
                print(f"\n{i}. Triple:")
                print(f"   Subject: {triple['subject']}")
                print(f"   Predicate: {triple['predicate']}")
                if triple['is_literal']:
                    print(f"   Object: \"{triple['object']}\" (literal)")
                else:
                    print(f"   Object: {triple['object']} (URI)")
        else:
            print("No triples defined in document metadata.")
