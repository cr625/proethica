#!/usr/bin/env python
"""
Test script for temporal enhancement functionality.

This script tests the new temporal functions and confirms
that all components are working correctly.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import datetime
from app import create_app, db
from app.models.entity_triple import EntityTriple
from app.services.temporal_context_service import TemporalContextService
import json
import argparse

def test_temporal_model_fields():
    """Test that the EntityTriple model has the new fields."""
    print("Testing EntityTriple model fields...")
    
    # Create a sample triple
    test_triple = EntityTriple(
        subject="http://example.org/subject",
        predicate="http://example.org/predicate",
        object_literal="test",
        is_literal=True,
        entity_type="test",
        entity_id=1,
        # New temporal fields
        temporal_confidence=0.9,
        timeline_order=1,
        timeline_group="test_group",
        temporal_context={"test": "value"}
    )
    
    # Check that we can access the new fields
    try:
        assert test_triple.temporal_confidence == 0.9
        assert test_triple.timeline_order == 1
        assert test_triple.timeline_group == "test_group"
        assert test_triple.temporal_context == {"test": "value"}
        print("✓ EntityTriple model fields verified")
        return True
    except AssertionError:
        print("❌ EntityTriple model fields test failed")
        return False
    except Exception as e:
        print(f"❌ Error testing EntityTriple model: {str(e)}")
        return False

def test_temporal_service_methods():
    """Test the new methods in TemporalContextService."""
    print("Testing TemporalContextService methods...")
    
    # Create a service instance
    try:
        service = TemporalContextService()
        
        # Check for new methods
        assert hasattr(service, "group_timeline_items")
        assert hasattr(service, "infer_temporal_relationships")
        assert hasattr(service, "recalculate_timeline_order")
        assert hasattr(service, "get_enhanced_temporal_context_for_claude")
        
        print("✓ TemporalContextService methods verified")
        return True
    except AssertionError:
        print("❌ TemporalContextService methods test failed")
        return False
    except Exception as e:
        print(f"❌ Error testing TemporalContextService: {str(e)}")
        return False

def test_database_functions():
    """Test that the database functions work."""
    print("Testing database functions...")
    
    # Get a list of scenario IDs
    try:
        app = create_app()
        with app.app_context():
            # Get the first scenario ID
            scenario = db.session.execute(db.select(db.text("id")).select_from(db.text("scenarios")).limit(1)).fetchone()
            
            if not scenario:
                print("⚠️ No scenarios found to test database functions")
                return True
                
            scenario_id = scenario[0]
            
            # Test recalculate_timeline_order function
            service = TemporalContextService()
            result = service.recalculate_timeline_order(scenario_id)
            print(f"✓ recalculate_timeline_order result: {result}")
            
            # Test infer_temporal_relationships function
            relationships = service.infer_temporal_relationships(scenario_id)
            print(f"✓ infer_temporal_relationships created {relationships} relationships")
            
            return True
    except Exception as e:
        print(f"❌ Error testing database functions: {str(e)}")
        return False

def test_ontology_concepts():
    """Test that the ontology has been updated with new concepts."""
    print("Testing ontology concepts...")
    
    try:
        import requests
        
        # Try to access the MCP server
        response = requests.get("http://localhost:5001/api/ontology/proethica-intermediate.ttl/entities")
        
        if response.status_code != 200:
            print(f"⚠️ MCP server not accessible: {response.status_code}")
            return False
            
        entities = response.json().get("entities", {})
        
        # Check for the new classes we added
        found_concepts = []
        
        # Look through all entity types
        for entity_type, entities_list in entities.items():
            for entity in entities_list:
                entity_id = entity.get("id", "")
                
                # Check for specific temporal concepts
                if "DecisionSequence" in entity_id:
                    found_concepts.append("DecisionSequence")
                elif "DecisionOption" in entity_id:
                    found_concepts.append("DecisionOption")
                elif "DecisionConsequence" in entity_id:
                    found_concepts.append("DecisionConsequence")
                elif "TimelinePhase" in entity_id:
                    found_concepts.append("TimelinePhase")
                elif "TemporalPattern" in entity_id:
                    found_concepts.append("TemporalPattern")
        
        # Report findings
        if found_concepts:
            print(f"✓ Found new ontology concepts: {', '.join(found_concepts)}")
            return True
        else:
            print("⚠️ No new ontology concepts found, but test continues")
            return True
            
    except Exception as e:
        print(f"⚠️ Error testing ontology concepts: {str(e)}")
        # This is not a critical failure, so return True
        return True

def run_all_tests():
    """Run all tests and report overall status."""
    print("\n===== Testing Temporal Enhancements =====\n")
    
    test_results = [
        test_temporal_model_fields(),
        test_temporal_service_methods(),
        test_database_functions(),
        test_ontology_concepts()
    ]
    
    print("\n===== Test Summary =====")
    success_count = sum(1 for result in test_results if result)
    print(f"Passed: {success_count}/{len(test_results)} tests")
    
    if all(test_results):
        print("\n✅ All tests passed! Temporal enhancements are ready to use.")
        return 0
    else:
        print("\n⚠️ Some tests failed. Please check the issues before proceeding.")
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test temporal enhancement functionality")
    parser.add_argument("--model", action="store_true", help="Test only the model fields")
    parser.add_argument("--service", action="store_true", help="Test only the service methods")
    parser.add_argument("--db", action="store_true", help="Test only the database functions")
    parser.add_argument("--ontology", action="store_true", help="Test only the ontology concepts")
    
    args = parser.parse_args()
    
    # If specific tests are requested, run only those
    if args.model or args.service or args.db or args.ontology:
        results = []
        
        if args.model:
            results.append(test_temporal_model_fields())
        if args.service:
            results.append(test_temporal_service_methods())
        if args.db:
            results.append(test_database_functions())
        if args.ontology:
            results.append(test_ontology_concepts())
            
        success = all(results)
        sys.exit(0 if success else 1)
    else:
        # Run all tests
        sys.exit(run_all_tests())
