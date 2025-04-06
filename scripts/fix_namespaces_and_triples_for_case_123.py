#!/usr/bin/env python3
"""
Script to fix namespaces and triples for case 123, adding missing namespaces
and synchronizing entity_triples with doc_metadata.rdf_triples
"""

import sys
import os
import json

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.document import Document
from app.models.entity_triple import EntityTriple

# Define required namespaces for proper triple functionality
REQUIRED_NAMESPACES = {
    "Case": "http://proethica.org/case/",
    "ENG_ETHICS": "http://proethica.org/eng_ethics/",
    "involves": "http://proethica.org/relation/",
    "NSPE": "http://proethica.org/code/nspe/",
    "Decision": "http://proethica.org/decision/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "bfo": "http://purl.obolibrary.org/obo/",
    "time": "http://www.w3.org/2006/time#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "eth": "http://proethica.org/ethics/",
    "World": "http://proethica.org/world/",
    "references": "http://proethica.org/relation/",
    "belongsTo": "http://proethica.org/relation/"
}

app = create_app()
with app.app_context():
    print("Getting case 123...")
    # Get case 123
    case = Document.query.filter_by(id=123, document_type='case_study').first()
    
    if not case:
        print("Case 123 not found")
        sys.exit(1)
    
    print(f"Fixing case: {case.title} (ID: {case.id})")
    
    # Initialize doc_metadata if it doesn't exist
    if not case.doc_metadata:
        print("Doc metadata is None, initializing empty dictionary")
        case.doc_metadata = {}
    
    print(f"Current doc_metadata: {json.dumps(case.doc_metadata, indent=2)}")
    
    # Get entity triples from database
    entity_triples = EntityTriple.query.filter_by(
        entity_id=case.id
    ).all()
    
    if entity_triples:
        print(f"Found {len(entity_triples)} triples for this case")
        
        # Make a copy of the existing doc_metadata
        metadata = dict(case.doc_metadata) if case.doc_metadata else {}
        
        # Add namespaces to doc_metadata
        metadata['rdf_namespaces'] = REQUIRED_NAMESPACES
        print("Added namespaces to metadata")
        
        # Convert entity triples to doc_metadata format
        converted_triples = []
        for triple in entity_triples:
            # Convert entity triple to rdf_triple format
            converted_triples.append({
                "subject": triple.subject,
                "predicate": triple.predicate,
                "object": triple.object_literal if triple.is_literal else triple.object_uri,
                "is_literal": triple.is_literal
            })
        
        # Add triples to doc_metadata
        metadata['rdf_triples'] = converted_triples
        print(f"Added {len(converted_triples)} triples to metadata")
        
        # Update the case object with the new metadata
        print("Setting doc_metadata to updated metadata dictionary")
        case.doc_metadata = metadata
        
        # Save changes
        print("About to save changes")
        db.session.add(case)
        print("Case added to session")
        db.session.commit()
        print("Saved changes to database")
        
        # Force a reload of the case to verify changes were saved
        db.session.expire(case)
        case = Document.query.filter_by(id=123).first()
        print(f"Reloaded case from database. Has doc_metadata: {case.doc_metadata is not None}")
    else:
        print("No triples found for this case")
    
    # Verify the changes
    print("\nVerifying changes:")
    
    print(f"doc_metadata type: {type(case.doc_metadata)}")
    print(f"doc_metadata content: {json.dumps(case.doc_metadata, indent=2) if case.doc_metadata else None}")
    
    # Check namespaces in doc_metadata
    if case.doc_metadata and 'rdf_namespaces' in case.doc_metadata:
        print(f"✓ Found {len(case.doc_metadata['rdf_namespaces'])} namespaces in doc_metadata")
        for prefix, uri in case.doc_metadata['rdf_namespaces'].items():
            print(f"  {prefix}: {uri}")
    else:
        print("✗ No namespaces found in doc_metadata")
    
    # Check triples in doc_metadata
    if case.doc_metadata and 'rdf_triples' in case.doc_metadata:
        print(f"✓ Found {len(case.doc_metadata['rdf_triples'])} triples in doc_metadata")
        # Print a few sample triples
        for i, triple in enumerate(case.doc_metadata['rdf_triples'][:3]):
            print(f"  {i+1}. {triple['subject']} -- {triple['predicate']} --> {triple['object']}")
    else:
        print("✗ No triples found in doc_metadata")
