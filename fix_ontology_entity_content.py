#!/usr/bin/env python3
"""
Fix for ontology entity content issue.

The problem: Storage layer returns {concept_uri, concept_label, match_score}
but PredictionService expects {subject, predicate, object, score, source}.

This script tests the fixed field mapping logic.
"""

# Test this fix
def test_fix():
    """Test the fix with sample data that matches what storage returns."""
    
    # Simulate what storage layer returns
    sample_associations = [
        {
            'concept_uri': 'http://example.org/ethics#professional_responsibility',
            'concept_label': 'Professional Responsibility',
            'match_score': 0.85,
            'created_at': '2025-05-23T16:00:00'
        },
        {
            'concept_uri': 'http://example.org/ethics#conflict_of_interest',
            'concept_label': 'Conflict of Interest',
            'match_score': 0.72,
            'created_at': '2025-05-23T16:00:00'
        }
    ]
    
    # Process using the fixed logic
    ontology_entities = {'facts': []}
    
    for triple in sample_associations:
        concept_uri = triple.get('concept_uri', '')
        concept_label = triple.get('concept_label', '')
        match_score = triple.get('match_score', 0.0)
        
        # FIXED: Map storage field names to RDF-style format
        entity = {
            'subject': concept_label or concept_uri,  # Use label as subject
            'predicate': 'relates_to',  # Generic predicate
            'object': concept_uri,  # URI as object
            'score': float(match_score) if match_score else 0.0,
            'source': 'ontology_association'
        }
        
        ontology_entities['facts'].append(entity)
    
    print("FIXED ENTITY PROCESSING:")
    for section_type, entities in ontology_entities.items():
        print(f"\n📋 Section '{section_type}': {len(entities)} entities")
        for i, entity in enumerate(entities):
            print(f"  Entity {i+1}:")
            print(f"    subject: '{entity['subject']}'")
            print(f"    predicate: '{entity['predicate']}'")
            print(f"    object: '{entity['object']}'")
            print(f"    score: {entity['score']}")
            print(f"    source: '{entity['source']}'")
    
    # Check if the fix works
    has_content = any(
        entity['subject'] and entity['object'] 
        for entities in ontology_entities.values() 
        for entity in entities
    )
    
    print(f"\n✅ FIX VALIDATION: Entities have content: {has_content}")
    
    # Compare with the broken approach
    print("\n❌ BROKEN APPROACH (current PredictionService):")
    broken_entities = {'facts': []}
    
    for triple in sample_associations:
        # This is what PredictionService currently does (which fails)
        entity = {
            'subject': triple.get('subject', ''),  # Empty because no 'subject' key
            'predicate': triple.get('predicate', ''),  # Empty
            'object': triple.get('object', ''),  # Empty 
            'score': triple.get('score', 0.0),  # Empty
            'source': triple.get('source', '')  # Empty
        }
        broken_entities['facts'].append(entity)
    
    for i, entity in enumerate(broken_entities['facts']):
        print(f"  Broken Entity {i+1}:")
        print(f"    subject: '{entity['subject']}'")
        print(f"    predicate: '{entity['predicate']}'")
        print(f"    object: '{entity['object']}'")
        print(f"    score: {entity['score']}")
        print(f"    source: '{entity['source']}'")
    
    broken_has_content = any(
        entity['subject'] and entity['object'] 
        for entities in broken_entities.values() 
        for entity in entities
    )
    
    print(f"\n❌ BROKEN VALIDATION: Entities have content: {broken_has_content}")
    
    return has_content

if __name__ == "__main__":
    test_fix()
