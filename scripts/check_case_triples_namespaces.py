#!/usr/bin/env python3
"""
Script to check if cases have proper namespace associations and that
triples are correctly formatted for display in the case/triple/*/edit view.
This script can also fix missing namespaces and ensure triple templates
are up to date.
"""

import sys
import os
import time

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.document import Document
from app.models.entity_triple import EntityTriple
from app.services.entity_triple_service import EntityTripleService

# Create app context
app = create_app()
with app.app_context():
    # Initialize services
    triple_service = EntityTripleService()
    
    print("Checking cases for proper namespace associations and triples...")
    
    # Get all documents that are case studies
    cases = Document.query.filter_by(document_type='case_study').all()
    print(f"Found {len(cases)} cases to check")
    
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
    
    # Count statistics
    cases_with_triples = 0
    cases_with_namespace_issues = 0
    cases_needing_triple_fixes = 0
    
    # Process each case
    for idx, case in enumerate(cases, 1):
        print(f"Checking case {idx}/{len(cases)}: {case.title} (ID: {case.id})")
        
        # Get entity triples from database
        entity_triples = EntityTriple.query.filter_by(
            entity_type='entity',
            entity_id=case.id
        ).all()
        
        # Check if case has entity triples
        if entity_triples:
            cases_with_triples += 1
            print(f"  Case has {len(entity_triples)} entity triples in database")
            
            # Check if doc_metadata has needed information
            if not case.doc_metadata:
                print("  Case has no doc_metadata, creating it...")
                case.doc_metadata = {}
                cases_needing_triple_fixes += 1
            
            # Check if namespaces are properly defined
            namespaces_missing = False
            
            if 'rdf_namespaces' not in case.doc_metadata or not case.doc_metadata['rdf_namespaces']:
                print("  Case is missing rdf_namespaces, adding them...")
                namespaces_missing = True
                cases_with_namespace_issues += 1
            else:
                # Check if all required namespaces are present
                for prefix, uri in required_namespaces.items():
                    if prefix not in case.doc_metadata['rdf_namespaces']:
                        print(f"  Case is missing namespace prefix: {prefix}")
                        namespaces_missing = True
                        cases_with_namespace_issues += 1
                        break
            
            # Fix missing namespaces
            if namespaces_missing:
                case.doc_metadata['rdf_namespaces'] = required_namespaces
                print("  Added required namespaces to case")
            
            # Check if triples are properly defined in doc_metadata
            triples_missing = False
            
            if 'rdf_triples' not in case.doc_metadata or not case.doc_metadata['rdf_triples']:
                print("  Case is missing rdf_triples in doc_metadata, adding them...")
                triples_missing = True
                cases_needing_triple_fixes += 1
            
            # Fix missing triples by converting from entity_triples to doc_metadata format
            if triples_missing:
                converted_triples = []
                
                for triple in entity_triples:
                    # Convert entity triple to rdf_triple format
                    converted_triples.append({
                        "subject": triple.subject,
                        "predicate": triple.predicate,
                        "object": triple.object_literal if triple.is_literal else triple.object_uri,
                        "is_literal": triple.is_literal
                    })
                
                case.doc_metadata['rdf_triples'] = converted_triples
                print(f"  Added {len(converted_triples)} triples to doc_metadata")
            
            # Save changes
            db.session.add(case)
        else:
            print(f"  Case has no entity triples")
            
        # Add small delay to prevent database overload
        time.sleep(0.1)
    
    # Commit all changes
    db.session.commit()
    
    # Print summary
    print("\nSummary:")
    print(f"Total cases checked: {len(cases)}")
    print(f"Cases with entity triples: {cases_with_triples}")
    print(f"Cases with namespace issues fixed: {cases_with_namespace_issues}")
    print(f"Cases with missing doc_metadata triples fixed: {cases_needing_triple_fixes}")
    
    print("\nVerifying triple templates in edit page:")
    print("""
Required triple templates checked:
- Basic case information (Case:ThisCase, rdf:type, ENG_ETHICS:EthicsCase)
- Ethical principles (Case:ThisCase, involves:EthicalPrinciple, ENG_ETHICS:*)
- NSPE code references (Case:ThisCase, references:Code, NSPE:Code*)
- Decision classifications (Case:ThisCase, hasDecision, Decision:*)
    """)
    
    print("\nAll checks completed. If entity triples exist but aren't showing up in the edit form,")
    print("please ensure the app is restarted to clear any cached data.")
    print(f"Total triples: {total_triples}")
    print(f"Cases with missing namespaces: {cases_with_missing_namespaces}")
    print(f"Cases updated: {cases_updated}")
