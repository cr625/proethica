#!/usr/bin/env python
"""
Simplified verification script for temporal enhancement functionality.

This script tests the basic model structure without requiring
database connections.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def verify_entity_triple_model():
    """Verify that the EntityTriple model has the new fields."""
    print("Verifying EntityTriple model fields...")
    
    try:
        from app.models.entity_triple import EntityTriple
        
        # Verify model fields by checking field names
        model_fields = dir(EntityTriple)
        
        # Check for the standard fields
        assert 'id' in model_fields
        assert 'subject' in model_fields
        assert 'predicate' in model_fields
        assert 'object_literal' in model_fields
        assert 'is_literal' in model_fields
        
        # Check for existing temporal fields
        assert 'temporal_region_type' in model_fields
        assert 'temporal_start' in model_fields
        assert 'temporal_end' in model_fields
        assert 'temporal_relation_type' in model_fields
        assert 'temporal_relation_to' in model_fields
        assert 'temporal_granularity' in model_fields
        
        # Check for new temporal fields
        assert 'temporal_confidence' in model_fields
        assert 'temporal_context' in model_fields
        assert 'timeline_order' in model_fields
        assert 'timeline_group' in model_fields
        
        print("✓ EntityTriple model fields verified")
        return True
    except AssertionError as e:
        print(f"❌ EntityTriple model verification failed: Missing field")
        return False
    except Exception as e:
        print(f"❌ Error verifying EntityTriple model: {str(e)}")
        return False

def verify_temporal_service():
    """Verify that the TemporalContextService has been enhanced."""
    print("Verifying TemporalContextService enhancements...")
    
    try:
        # First import the enhancement module to ensure it's applied
        try:
            import app.services.temporal_context_service_enhancements
        except:
            pass
            
        # Now check the service
        from app.services.temporal_context_service import TemporalContextService
        
        # Check for the enhanced methods
        service_methods = dir(TemporalContextService)
        
        # Standard methods
        assert 'build_timeline' in service_methods
        assert 'find_triples_in_timeframe' in service_methods
        
        # Enhanced methods
        assert 'group_timeline_items' in service_methods
        assert 'infer_temporal_relationships' in service_methods
        assert 'recalculate_timeline_order' in service_methods
        assert 'get_enhanced_temporal_context_for_claude' in service_methods
        
        print("✓ TemporalContextService enhancements verified")
        return True
    except AssertionError:
        print("❌ TemporalContextService enhancement verification failed: Missing method")
        return False
    except Exception as e:
        print(f"❌ Error verifying TemporalContextService: {str(e)}")
        return False

def verify_sql_files():
    """Verify that the SQL files have been created."""
    print("Verifying SQL files...")
    
    files_to_check = [
        "scripts/enhance_entity_triples_temporal.sql"
    ]
    
    missing_files = []
    for file_path in files_to_check:
        if not os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), file_path)):
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing SQL files: {', '.join(missing_files)}")
        return False
    else:
        print("✓ SQL files verified")
        return True

def verify_ontology_files():
    """Verify that the ontology has been updated."""
    print("Verifying ontology files...")
    
    try:
        # Load the ontology file
        ontology_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                    "mcp/ontology/proethica-intermediate.ttl")
        
        if not os.path.exists(ontology_path):
            print(f"❌ Ontology file not found: {ontology_path}")
            return False
            
        # Check file size to ensure it's substantial
        file_size = os.path.getsize(ontology_path)
        if file_size < 10000:  # At least 10KB
            print(f"❌ Ontology file seems too small: {file_size} bytes")
            return False
            
        # Check for specific temporal concepts
        with open(ontology_path, 'r') as f:
            content = f.read()
            
        # Look for new concepts
        concepts_to_check = [
            "DecisionSequence",
            "DecisionOption", 
            "TimelinePhase",
            "TemporalPattern",
            "causedBy",
            "enabledBy",
            "hasTemporalConfidence"
        ]
        
        missing_concepts = []
        for concept in concepts_to_check:
            if concept not in content:
                missing_concepts.append(concept)
        
        if missing_concepts:
            print(f"❌ Missing ontology concepts: {', '.join(missing_concepts)}")
            return False
        else:
            print("✓ Ontology concepts verified")
            return True
    except Exception as e:
        print(f"❌ Error verifying ontology files: {str(e)}")
        return False

def run_all_verifications():
    """Run all verification functions."""
    print("\n===== Verifying Temporal Enhancements =====\n")
    
    verification_results = [
        verify_entity_triple_model(),
        verify_temporal_service(),
        verify_sql_files(),
        verify_ontology_files()
    ]
    
    print("\n===== Verification Summary =====")
    success_count = sum(1 for result in verification_results if result)
    print(f"Passed: {success_count}/{len(verification_results)} verifications")
    
    if all(verification_results):
        print("\n✅ All verifications passed! Temporal enhancements are installed.")
        return 0
    else:
        print("\n⚠️ Some verifications failed. Please check the issues.")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_verifications())
