#!/usr/bin/env python3
"""
Script to check the triples and namespaces for case 123
"""

import sys
import os
import json
from pprint import pprint

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.document import Document
from app.models.entity_triple import EntityTriple

app = create_app()
with app.app_context():
    # Get case 123
    case = Document.query.filter_by(id=123, document_type='case_study').first()
    
    if not case:
        print("Case 123 not found")
        sys.exit(1)
    
    print(f"Case: {case.title} (ID: {case.id})")
    
    # Print namespaces from document metadata
    if case.doc_metadata and 'rdf_namespaces' in case.doc_metadata:
        print("\nNamespaces in document metadata:")
        for prefix, uri in case.doc_metadata['rdf_namespaces'].items():
            print(f"  {prefix}: {uri}")
    else:
        print("\nNo namespaces found in document metadata")
    
    # Get entity triples from database
    entity_triples = EntityTriple.query.filter_by(
        entity_id=case.id
    ).all()
    
    if entity_triples:
        print(f"\nFound {len(entity_triples)} triples for this case:")
        
        # Count entity types
        entity_type_counts = {}
        for triple in entity_triples:
            entity_type = triple.entity_type
            if entity_type not in entity_type_counts:
                entity_type_counts[entity_type] = 0
            entity_type_counts[entity_type] += 1
        
        print("\nEntity type counts:")
        for entity_type, count in entity_type_counts.items():
            print(f"  {entity_type}: {count}")
        
        # Print a sample of the triples
        print("\nSample triples (up to 10):")
        for i, triple in enumerate(entity_triples[:10]):
            obj_value = triple.object_literal if triple.is_literal else triple.object_uri
            print(f"  {i+1}. {triple.subject} -- {triple.predicate} --> {obj_value}")
            print(f"     (entity_type: {triple.entity_type})")
        
        # Check which namespaces are actually used in the triples
        used_prefixes = set()
        for triple in entity_triples:
            # Check subject
            if ':' in triple.subject:
                prefix = triple.subject.split(':', 1)[0]
                used_prefixes.add(prefix)
            
            # Check predicate
            if ':' in triple.predicate:
                prefix = triple.predicate.split(':', 1)[0]
                used_prefixes.add(prefix)
            
            # Check object if it's a URI
            if not triple.is_literal and ':' in triple.object_uri:
                prefix = triple.object_uri.split(':', 1)[0]
                used_prefixes.add(prefix)
        
        print("\nNamespace prefixes used in triples:")
        for prefix in sorted(used_prefixes):
            print(f"  {prefix}")
    else:
        print("\nNo triples found for this case")
    
    # Check if triples in doc_metadata match entity_triples
    if case.doc_metadata and 'rdf_triples' in case.doc_metadata:
        metadata_triples = case.doc_metadata['rdf_triples']
        print(f"\nFound {len(metadata_triples)} triples in doc_metadata")
        
        # Print a sample of the metadata triples
        print("\nSample doc_metadata triples (up to 10):")
        for i, triple in enumerate(metadata_triples[:10]):
            obj_value = triple['object']
            is_literal = triple.get('is_literal', False)
            print(f"  {i+1}. {triple['subject']} -- {triple['predicate']} --> {obj_value}")
            print(f"     (is_literal: {is_literal})")
    else:
        print("\nNo triples found in doc_metadata")
