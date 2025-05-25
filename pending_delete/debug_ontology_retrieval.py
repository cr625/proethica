#!/usr/bin/env python3
"""
Debug the ontology retrieval - why are entities empty?
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up environment  
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', 'false')
os.environ.setdefault('ENVIRONMENT', 'development')

from app import create_app
from optimize_ontology_prediction_service_final import OptimizedPredictionService

def debug_ontology_retrieval():
    """Debug ontology entity retrieval step by step."""
    app = create_app('config')
    
    with app.app_context():
        print("🔍 DEBUGGING ONTOLOGY ENTITY RETRIEVAL")
        print("="*60)
        
        # Create service and get basic data
        service = OptimizedPredictionService()
        sections = service.get_document_sections(252, leave_out_conclusion=True)
        
        print(f"✅ Document sections: {list(sections.keys())}")
        
        # Test the get_section_ontology_entities method directly
        print(f"\n🔍 TESTING get_section_ontology_entities method:")
        
        try:
            # Call the method and see what it returns
            ontology_entities = service.get_section_ontology_entities(252, sections)
            
            print(f"✅ Method completed successfully")
            print(f"✅ Returned {sum(len(entities) for entities in ontology_entities.values())} total entities")
            
            # Check the detailed structure
            for section_name, entities in ontology_entities.items():
                print(f"\n📋 Section '{section_name}': {len(entities)} entities")
                
                if entities:
                    # Show first entity in detail
                    first_entity = entities[0]
                    print(f"  First entity structure:")
                    for key, value in first_entity.items():
                        print(f"    {key}: '{value}' (type: {type(value).__name__})")
                    
                    # Check if all entities are identical/empty
                    all_same = all(entity == first_entity for entity in entities)
                    print(f"  All entities identical: {all_same}")
                    
                    if first_entity.get('subject') == '' and first_entity.get('object') == '':
                        print(f"  ❌ PROBLEM: Entities have empty subject/object fields!")
                    else:
                        print(f"  ✅ Entities have content")
                        
        except Exception as e:
            print(f"❌ Error calling get_section_ontology_entities: {e}")
            import traceback
            traceback.print_exc()
            
        # Let's also check if the parent class method works differently
        print(f"\n🔍 CHECKING PARENT CLASS METHOD:")
        try:
            from app.services.experiment.prediction_service import PredictionService
            base_service = PredictionService()
            base_entities = base_service.get_section_ontology_entities(252, sections)
            
            print(f"✅ Base service returned {sum(len(entities) for entities in base_entities.values())} entities")
            
            # Compare with optimized service
            if base_entities != ontology_entities:
                print(f"⚠️  WARNING: Base and optimized services return different results!")
            else:
                print(f"✅ Base and optimized services return identical results")
                
        except Exception as e:
            print(f"❌ Error with base service: {e}")

if __name__ == "__main__":
    debug_ontology_retrieval()
