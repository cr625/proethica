#!/usr/bin/env python3
"""
Test script for guideline triple deduplication functionality.

This script tests the duplicate detection system with sample data.
"""

import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.triple_duplicate_detection_service import get_duplicate_detection_service
from app.models import db
from app.models.entity_triple import EntityTriple
from app.models.ontology import Ontology
from app import create_app

def test_duplicate_detection():
    """Test the duplicate detection functionality."""
    
    app = create_app()
    
    with app.app_context():
        print("Testing Guideline Triple Deduplication")
        print("=" * 50)
        
        # Initialize the duplicate detection service
        duplicate_service = get_duplicate_detection_service()
        
        print(f"Loaded ontologies: {duplicate_service.loaded_ontologies}")
        print(f"Total triples in memory: {len(duplicate_service.ontology_graph)}")
        print()
        
        # Test case 1: Exact duplicate detection
        print("Test 1: Exact Duplicate Detection")
        print("-" * 30)
        
        triple1 = {
            'subject': 'http://proethica.org/guidelines/engineer',
            'predicate': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
            'object': 'http://proethica.org/ontology/Role',
            'is_literal': False
        }
        
        # Simulate existing triple in database
        existing_triple = EntityTriple(
            subject=triple1['subject'],
            predicate=triple1['predicate'],
            object_uri=triple1['object'],
            is_literal=False,
            entity_type='test',
            guideline_id=999  # Different guideline
        )
        
        try:
            db.session.add(existing_triple)
            db.session.commit()
            
            # Test duplicate detection
            result = duplicate_service.check_duplicate_with_details(
                triple1['subject'],
                triple1['predicate'],
                triple1['object'],
                triple1['is_literal']
            )
            
            print(f"Duplicate detected: {result['is_duplicate']}")
            print(f"Details: {result['details']}")
            print(f"In database: {result['in_database']}")
            print()
            
        finally:
            # Clean up
            db.session.delete(existing_triple)
            db.session.commit()
        
        # Test case 2: Namespace variation detection
        print("Test 2: Namespace Variation Detection")
        print("-" * 30)
        
        # Test equivalent URIs with different namespaces
        original_uri = 'http://proethica.org/ontology/Engineer'
        variant_uri = 'http://proethica.org/ontology/engineering-ethics#Engineer'
        
        equivalents = duplicate_service.find_equivalent_concepts(original_uri)
        print(f"Original URI: {original_uri}")
        print(f"Equivalent URIs found: {equivalents}")
        print()
        
        # Test case 3: Value classification
        print("Test 3: Value Classification")
        print("-" * 30)
        
        predicates = [
            ('http://proethica.org/ontology/alignsWith', 'aligns with'),
            ('http://proethica.org/ontology/mentionsTerm', 'mentions term'),
            ('http://proethica.org/ontology/definesRole', 'defines role'),
            ('http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'is a type'),
            ('http://www.w3.org/2000/01/rdf-schema#label', 'has label')
        ]
        
        for predicate_uri, predicate_label in predicates:
            value_class = duplicate_service.classify_triple_value(predicate_uri, predicate_label)
            print(f"{predicate_label}: {value_class} value")
        
        print()
        
        # Test case 4: Batch duplicate filtering
        print("Test 4: Batch Duplicate Filtering")
        print("-" * 30)
        
        sample_triples = [
            {
                'subject': 'http://proethica.org/guidelines/integrity',
                'predicate': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
                'object': 'http://proethica.org/ontology/Principle',
                'is_literal': False
            },
            {
                'subject': 'http://proethica.org/guidelines/honesty',
                'predicate': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
                'object': 'http://proethica.org/ontology/Principle',
                'is_literal': False
            },
            {
                'subject': 'http://proethica.org/guidelines/guideline_190',
                'predicate': 'http://proethica.org/ontology/mentionsTerm',
                'object': 'http://proethica.org/ontology/safety',
                'is_literal': False
            }
        ]
        
        unique_triples, duplicate_triples = duplicate_service.filter_duplicate_triples(sample_triples)
        
        print(f"Total triples: {len(sample_triples)}")
        print(f"Unique triples: {len(unique_triples)}")
        print(f"Duplicate triples: {len(duplicate_triples)}")
        
        for i, dup in enumerate(duplicate_triples):
            print(f"  Duplicate {i+1}: {dup['duplicate_info']['details']}")
        
        print()
        print("Deduplication test completed successfully!")

if __name__ == '__main__':
    test_duplicate_detection()