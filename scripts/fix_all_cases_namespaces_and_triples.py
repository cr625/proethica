#!/usr/bin/env python3
"""
Script to fix namespaces and triples for all cases, adding missing namespaces
and synchronizing entity_triples with doc_metadata.rdf_triples to ensure they
appear in the cases/triple/?/edit view.
"""

import sys
import os
import json
import time

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

def fix_case(case):
    """
    Fix namespaces and triples for a single case
    """
    # Get entity triples from database
    entity_triples = EntityTriple.query.filter_by(
        entity_id=case.id
    ).all()
    
    # Check entity types and convert if necessary
    changed_entity_types = 0
    for triple in entity_triples:
        if triple.entity_type == 'entity':
            triple.entity_type = 'document'
            db.session.add(triple)
            changed_entity_types += 1
    
    if changed_entity_types > 0:
        print(f"  Changed {changed_entity_types} triples from entity_type='entity' to entity_type='document'")

    if entity_triples:
        # Make a copy of the existing doc_metadata or initialize if it doesn't exist
        metadata = dict(case.doc_metadata) if case.doc_metadata else {}
        
        # Add namespaces to doc_metadata
        metadata['rdf_namespaces'] = REQUIRED_NAMESPACES
        
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
        
        # Update the case object with the new metadata
        case.doc_metadata = metadata
        
        # Save changes
        db.session.add(case)
        
        return True, len(entity_triples), changed_entity_types
    else:
        return False, 0, changed_entity_types

app = create_app()
with app.app_context():
    # Get all documents that are case studies
    cases = Document.query.filter_by(document_type='case_study').all()
    print(f"Found {len(cases)} cases to process")
    
    # Statistics
    cases_updated = 0
    total_triples = 0
    total_entity_types_changed = 0
    cases_with_no_triples = 0
    
    # Process each case
    for idx, case in enumerate(cases, 1):
        print(f"Processing case {idx}/{len(cases)}: {case.title} (ID: {case.id})")
        
        updated, triple_count, entity_types_changed = fix_case(case)
        
        if updated:
            cases_updated += 1
            total_triples += triple_count
            total_entity_types_changed += entity_types_changed
            print(f"  ✓ Updated with {triple_count} triples")
        else:
            cases_with_no_triples += 1
            print(f"  ✗ No triples found for this case")
        
        # Commit every 10 cases to avoid transaction timeout
        if idx % 10 == 0 or idx == len(cases):
            print(f"Committing changes (processed {idx}/{len(cases)} cases)")
            db.session.commit()
        
        # Add small delay to prevent database overload
        time.sleep(0.1)
    
    # Commit any remaining changes
    if len(cases) % 10 != 0:
        print("Committing final changes")
        db.session.commit()
    
    # Print summary
    print("\nSummary:")
    print(f"Total cases processed: {len(cases)}")
    print(f"Cases with triples updated: {cases_updated}")
    print(f"Cases with no triples: {cases_with_no_triples}")
    print(f"Total triples added to doc_metadata: {total_triples}")
    print(f"Total entity_type changes from 'entity' to 'document': {total_entity_types_changed}")
    
    print("\nAll cases processed successfully!")
    print("The triples should now appear correctly in the cases/triple/*/edit view")
