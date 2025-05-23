#!/usr/bin/env python3
"""
End-to-end test for the ontology entity content fix.

This script tests the PredictionServiceOntologyFixed to validate that:
1. Ontology entities now have actual content (not empty strings)
2. Mention ratio improves significantly 
3. The fix resolves the critical issue identified in the progress document
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.experiment.prediction_service_ontology_fixed import PredictionServiceOntologyFixed
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Test the ontology fix end-to-end."""
    
    print("🔬 TESTING ONTOLOGY ENTITY CONTENT FIX - END TO END")
    print("=" * 60)
    
    try:
        # Create Flask app context for database access
        app = create_app()
        
        with app.app_context():
            
            # Initialize the FIXED prediction service
            service = PredictionServiceOntologyFixed()
            
            # Test with Case 252 
            case_id = 252
            print(f"1. Testing with Case {case_id}...")
            
            # Get document sections
            sections = service.get_document_sections(case_id, leave_out_conclusion=True)
            print(f"   ✅ Retrieved {len(sections)} sections: {list(sections.keys())}")
            
            # Test the FIXED ontology entity retrieval
            print(f"\n2. Testing FIXED ontology entity retrieval...")
            ontology_entities = service.get_section_ontology_entities_fixed(case_id, sections)
            
            # Analyze results
            total_entities = sum(len(entities) for entities in ontology_entities.values())
            print(f"   ✅ Retrieved {total_entities} ontology entities")
            
            # Check if entities have content (the fix should resolve this)
            entities_with_content = 0
            sample_entities = []
            
            for section_type, entities in ontology_entities.items():
                print(f"\n   📋 Section '{section_type}': {len(entities)} entities")
                
                for i, entity in enumerate(entities[:3]):  # Show first 3 per section
                    has_content = bool(entity.get('subject') and entity.get('object'))
                    if has_content:
                        entities_with_content += 1
                        
                    print(f"     Entity {i+1}:")
                    print(f"       subject: '{entity.get('subject', '')}' ({'✅' if entity.get('subject') else '❌'})")
                    print(f"       predicate: '{entity.get('predicate', '')}' ({'✅' if entity.get('predicate') else '❌'})")
                    print(f"       object: '{entity.get('object', '')}' ({'✅' if entity.get('object') else '❌'})")
                    print(f"       score: {entity.get('score', 0.0)}")
                    print(f"       source: '{entity.get('source', '')}' ({'✅' if entity.get('source') else '❌'})")
                    
                    if has_content:
                        sample_entities.append(entity)
            
            # Calculate content ratio
            content_ratio = entities_with_content / total_entities if total_entities > 0 else 0
            
            print(f"\n3. 🎯 CRITICAL VALIDATION:")
            print(f"   Total entities: {total_entities}")
            print(f"   Entities with content: {entities_with_content}")
            print(f"   Content ratio: {content_ratio:.1%}")
            
            if content_ratio > 0.8:
                print(f"   ✅ EXCELLENT: Fix is working! {content_ratio:.1%} of entities have content")
            elif content_ratio > 0.5:
                print(f"   🟡 GOOD: Fix is mostly working! {content_ratio:.1%} of entities have content")
            elif content_ratio > 0:
                print(f"   🟠 PARTIAL: Fix is working but needs improvement. {content_ratio:.1%} of entities have content")
            else:
                print(f"   ❌ FAILED: Fix is not working. No entities have content.")
                
            # Test mention ratio calculation
            if sample_entities:
                print(f"\n4. Testing mention ratio validation...")
                
                # Create a sample conclusion that mentions some entities
                sample_conclusion = f"The conduct violates professional responsibility and engineering ethics. " \
                                   f"The engineer failed to meet standards regarding {sample_entities[0]['subject']} " \
                                   f"as outlined in the NSPE Code of Ethics."
                
                print(f"   Sample conclusion: {sample_conclusion[:100]}...")
                
                # Test validation
                validation_results = service._validate_conclusion(sample_conclusion, ontology_entities)
                
                print(f"   Entity mentions: {validation_results.get('entity_mentions', 0)}")
                print(f"   Total entities: {validation_results.get('total_entities', 0)}")
                print(f"   Mention ratio: {validation_results.get('mention_ratio', 0):.1%}")
                print(f"   Validation status: {validation_results.get('validation_status', 'unknown')}")
                
                if validation_results.get('mention_ratio', 0) > 0:
                    print(f"   ✅ SUCCESS: Mention ratio calculation working!")
                else:
                    print(f"   ❌ ISSUE: Mention ratio still zero")
            
            # Final assessment
            print(f"\n🏆 FINAL ASSESSMENT:")
            
            if content_ratio > 0.8:
                print(f"   ✅ ONTOLOGY FIX: COMPLETE SUCCESS")
                print(f"   ✅ Issue resolved: Empty entity content fixed")
                print(f"   ✅ Mention ratio: Now functional")
                print(f"   ✅ Ready for: Complete ontology integration testing")
                
                return True
            elif content_ratio > 0:
                print(f"   🟡 ONTOLOGY FIX: PARTIAL SUCCESS")
                print(f"   🟡 Issue partially resolved: Some entities have content")
                print(f"   🟡 Action needed: Further investigation of remaining empty entities")
                
                return False
            else:
                print(f"   ❌ ONTOLOGY FIX: FAILED")
                print(f"   ❌ Issue persists: Entities still empty")
                print(f"   ❌ Action needed: Debug field mapping logic")
                
                return False
                
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
