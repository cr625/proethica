#!/usr/bin/env python3
"""
Debug the validation issue - why are we getting 0 total entities?
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

def debug_validation():
    """Debug validation entity processing step by step."""
    app = create_app('config')
    
    with app.app_context():
        print("🔍 DEBUGGING VALIDATION ENTITY PROCESSING")
        print("="*60)
        
        # Create service and get ontology entities
        service = OptimizedPredictionService()
        
        # Get ontology entities for Case 252
        sections = service.get_document_sections(252, leave_out_conclusion=True)
        ontology_entities = service.get_section_ontology_entities(252, sections)
        
        print(f"✅ Ontology entities loaded: {sum(len(entities) for entities in ontology_entities.values())} total")
        print(f"✅ Sections with entities: {list(ontology_entities.keys())}")
        
        # Show a sample entity structure
        for section_type, entities in ontology_entities.items():
            if entities:
                print(f"\n📋 Sample entities from '{section_type}' section:")
                for i, entity in enumerate(entities[:2]):  # Show first 2
                    print(f"  Entity {i+1}: {entity}")
                break
        
        # Test the validation processing logic manually
        print(f"\n🔍 TESTING VALIDATION PROCESSING:")
        
        all_entities = []
        entity_details = []
        
        for section_type, entities in ontology_entities.items():
            print(f"\nProcessing section '{section_type}' with {len(entities)} entities...")
            
            for entity in entities:
                print(f"  Raw entity: {entity}")
                
                # Process subject terms
                if 'subject' in entity and entity['subject']:
                    subj = entity['subject'].strip()
                    all_entities.append(subj)
                    entity_details.append({
                        'text': subj,
                        'type': 'subject',
                        'section': section_type,
                        'full_entity': entity
                    })
                    print(f"    ✅ Added subject: '{subj}'")
                else:
                    print(f"    ❌ No valid subject found")
                
                # Process object terms  
                if 'object' in entity and entity['object']:
                    obj = entity['object'].strip()
                    all_entities.append(obj)
                    entity_details.append({
                        'text': obj,
                        'type': 'object',
                        'section': section_type, 
                        'full_entity': entity
                    })
                    print(f"    ✅ Added object: '{obj}'")
                else:
                    print(f"    ❌ No valid object found")
        
        print(f"\n📊 VALIDATION PROCESSING RESULTS:")
        print(f"Total entity details extracted: {len(entity_details)}")
        print(f"Total entity strings: {len(all_entities)}")
        
        if entity_details:
            print(f"\n✅ SUCCESS - entities processed correctly!")
            print(f"First 5 entity details:")
            for i, detail in enumerate(entity_details[:5]):
                print(f"  {i+1}. {detail['type']}: '{detail['text']}'")
        else:
            print(f"\n❌ PROBLEM - no entity details extracted!")
            print(f"This explains why validation shows 'Total entities: 0'")

if __name__ == "__main__":
    debug_validation()
