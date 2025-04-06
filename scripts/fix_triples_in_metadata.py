#!/usr/bin/env python3
"""
Script to ensure that triples in the entity_triples table are also
present in the doc_metadata['rdf_triples'] field for each case.
This fixes cases where triples exist in the database but don't appear
in the edit form when viewing cases/triple/*/edit.
"""

import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.document import Document
from app.models.entity_triple import EntityTriple

# Create app context
app = create_app()
with app.app_context():
    # Get all documents that are case studies
    cases = Document.query.filter_by(document_type='case_study').all()
    print(f"Found {len(cases)} cases to process")
    
    # Define required namespaces for proper triple functionality
    required_namespaces = {
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
        "eth": "http://proethica.org/ethics/"
    }
    
    # Track stats for report
    fixed_cases = 0
    total_triples = 0
    cases_with_triples = 0
    
    # Process each case
    for idx, case in enumerate(cases, 1):
        print(f"Processing case {idx}/{len(cases)}: {case.title} (ID: {case.id})")
        
        # Get entity triples from database
        entity_triples = EntityTriple.query.filter_by(
            entity_type='entity',
            entity_id=case.id
        ).all()
        
        if entity_triples:
            cases_with_triples += 1
            print(f"  Found {len(entity_triples)} entity triples in database")
            total_triples += len(entity_triples)
            
            # Create document metadata if it doesn't exist
            if not case.doc_metadata:
                print("  Creating document metadata")
                case.doc_metadata = {}
            
            # Ensure namespaces are defined
            if 'rdf_namespaces' not in case.doc_metadata or not case.doc_metadata['rdf_namespaces']:
                print("  Adding required namespaces")
                case.doc_metadata['rdf_namespaces'] = required_namespaces
            
            # Convert entity triples to doc_metadata format
            rdf_triples = []
            for triple in entity_triples:
                rdf_triples.append({
                    "subject": triple.subject,
                    "predicate": triple.predicate,
                    "object": triple.object_literal if triple.is_literal else triple.object_uri,
                    "is_literal": triple.is_literal
                })
            
            # Update doc_metadata with triples
            case.doc_metadata['rdf_triples'] = rdf_triples
            print(f"  Added {len(rdf_triples)} triples to document metadata")
            fixed_cases += 1
            
            # Save changes
            db.session.add(case)
        else:
            print("  No entity triples found")
    
    # Commit all changes
    db.session.commit()
    
    # Print summary
    print("\nSummary:")
    print(f"Total cases: {len(cases)}")
    print(f"Cases with triples: {cases_with_triples}")
    print(f"Cases fixed: {fixed_cases}")
    print(f"Total triples: {total_triples}")
    print("\nNow the triples should appear in the cases/triple/*/edit view")
