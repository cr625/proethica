#!/usr/bin/env python3
"""
Test the updated main PredictionService to validate the ontology fix is working.
"""

import os
import sys

# Set environment
os.environ['FLASK_APP'] = 'run.py'
os.environ['FLASK_ENV'] = 'development'

# Add path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from run import app
from app.services.experiment.prediction_service import PredictionService

def test_updated_prediction_service():
    """Test the updated main PredictionService."""
    
    print("🔬 TESTING UPDATED MAIN PREDICTION SERVICE")
    print("=" * 55)
    
    with app.app_context():
        
        # Initialize the main prediction service
        service = PredictionService()
        
        # Test with Case 252 
        case_id = 252
        print(f"1. Testing with Case {case_id}...")
        
        # Get document sections
        sections = service.get_document_sections(case_id, leave_out_conclusion=True)
        print(f"   ✅ Retrieved {len(sections)} sections: {list(sections.keys())}")
        
        if not sections:
            print("   ❌ No sections found, cannot test")
            return False
        
        # Test the FIXED ontology entity retrieval (now in main service)
        print(f"\n2. Testing ontology entity retrieval in main service...")
        ontology_entities = service.get_section_ontology_entities(case_id, sections)
        
        # Analyze results
        total_entities = sum(len(entities) for entities in ontology_entities.values())
        print(f"   ✅ Retrieved {total_entities} ontology entities")
        
        if total_entities == 0:
            print("   ❌ No ontology entities found")
            return False
        
        # Check if entities have content (the fix should be working)
        entities_with_content = 0
        sample_entities = []
        
        for section_type, entities in ontology_entities.items():
            print(f"\n   📋 Section '{section_type}': {len(entities)} entities")
            
            for i, entity in enumerate(entities[:2]):  # Show first 2 per section
                has_content = bool(entity.get('subject') and entity.get('object'))
                if has_content:
                    entities_with_content += 1
                    
                print(f"     Entity {i+1}:")
                print(f"       subject: '{entity.get('subject', '')}' ({'✅' if entity.get('subject') else '❌'})")
                print(f"       predicate: '{entity.get('predicate', '')}' ({'✅' if entity.get('predicate') else '❌'})")
                print(f"       object: '{entity.get('object', '')}' ({'✅' if entity.get('object') else '❌'})")
                print(f"       score: {entity.get('score', 0.0)}")
                
                if has_content:
                    sample_entities.append(entity)
        
        # Calculate content ratio
        content_ratio = entities_with_content / total_entities if total_entities > 0 else 0
        
        print(f"\n3. 🎯 VALIDATION RESULTS:")
        print(f"   Total entities: {total_entities}")
        print(f"   Entities with content: {entities_with_content}")
        print(f"   Content ratio: {content_ratio:.1%}")
        
        # Test mention ratio if we have sample entities
        if sample_entities:
            print(f"\n4. Testing mention ratio validation...")
            
            # Create a sample conclusion that mentions some entities
            sample_conclusion = f"The conduct violates professional responsibility and engineering ethics. " \
                               f"The engineer failed to meet standards regarding {sample_entities[0]['subject']} " \
                               f"as outlined in the NSPE Code of Ethics."
            
            print(f"   Sample conclusion: {sample_conclusion[:80]}...")
            
            # Test validation
            validation_results = service._validate_conclusion(sample_conclusion, ontology_entities)
            
            print(f"   Entity mentions: {validation_results.get('entity_mentions', 0)}")
            print(f"   Total entities: {validation_results.get('total_entities', 0)}")
            print(f"   Mention ratio: {validation_results.get('mention_ratio', 0):.1%}")
            
            if validation_results.get('mention_ratio', 0) > 0:
                print(f"   ✅ SUCCESS: Mention ratio calculation working!")
            else:
                print(f"   ❌ ISSUE: Mention ratio still zero")
        
        # Final assessment
        print(f"\n🏆 FINAL ASSESSMENT:")
        
        if content_ratio > 0.8:
            print(f"   ✅ MAIN SERVICE: COMPLETE SUCCESS")
            print(f"   ✅ Ontology fix successfully applied to main PredictionService")
            print(f"   ✅ Ready for: Production use and cleanup of temporary classes")
            return True
        elif content_ratio > 0:
            print(f"   🟡 MAIN SERVICE: PARTIAL SUCCESS")
            print(f"   🟡 Ontology fix working but could be optimized")
            return True
        else:
            print(f"   ❌ MAIN SERVICE: FAILED")
            print(f"   ❌ Fix not properly applied")
            return False

if __name__ == "__main__":
    try:
        success = test_updated_prediction_service()
        
        if success:
            print(f"\n🎉 SUCCESS: Main PredictionService now has working ontology integration!")
            print(f"🧹 NEXT: Clean up temporary PredictionServiceOntologyFixed class")
        
        exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
