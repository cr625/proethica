#!/usr/bin/env python3
"""
Enhanced script to:
1. Copy triples from entity_triples table to document metadata
2. Fix entity_type to be 'document' instead of 'entity' for case triples
3. Add required namespaces

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
        "references": "http://proethica.org/reference/",
        "hasConflict": "http://proethica.org/conflict/",
        "hasDecision": "http://proethica.org/decision/",
        "belongsTo": "http://proethica.org/belongs/",
        "NSPE": "http://proethica.org/code/nspe/",
        "Decision": "http://proethica.org/decision/",
        "World": "http://proethica.org/world/",
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
    fixed_entity_types = 0
    total_triples = 0
    cases_with_triples = 0
    
    # Process each case
    for idx, case in enumerate(cases, 1):
        print(f"Processing case {idx}/{len(cases)}: {case.title} (ID: {case.id})")
        
        # Step 1: Look for entity triples with entity_type='entity'
        entity_triples = EntityTriple.query.filter_by(
            entity_type='entity',
            entity_id=case.id
        ).all()
        
        # Step 2: Also look for entity triples with entity_type='document' 
        document_triples = EntityTriple.query.filter_by(
            entity_type='document',
            entity_id=case.id
        ).all()
        
        # Combine both types
        all_triples = entity_triples + document_triples
        
        if all_triples:
            cases_with_triples += 1
            print(f"  Found {len(all_triples)} entity triples in database ({len(entity_triples)} entity type, {len(document_triples)} document type)")
            total_triples += len(all_triples)
            
            # Fix entity_type for triples that use 'entity' instead of 'document'
            if entity_triples:
                print(f"  Fixing entity_type for {len(entity_triples)} triples")
                for triple in entity_triples:
                    triple.entity_type = 'document'
                    db.session.add(triple)
                fixed_entity_types += len(entity_triples)
            
            # Create document metadata if it doesn't exist
            if not case.doc_metadata:
                print("  Creating document metadata")
                case.doc_metadata = {}
            
            # Ensure namespaces are defined
            if 'rdf_namespaces' not in case.doc_metadata or not case.doc_metadata['rdf_namespaces']:
                print("  Adding required namespaces")
                case.doc_metadata['rdf_namespaces'] = required_namespaces
            
            # Convert all triples to doc_metadata format (after fixing entity_type)
            rdf_triples = []
            for triple in all_triples:
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
    print(f"Entity types fixed: {fixed_entity_types}")
    print(f"Total triples: {total_triples}")
    print("\nNow the triples should appear in the cases/triple/*/edit view")
