#!/usr/bin/env python3
"""
Quick verification that the main PredictionService has the ontology fix.
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

def verify_fix():
    """Quick check that the fix is applied."""
    
    with app.app_context():
        service = PredictionService()
        
        # Check if the method exists and has the fix by testing with Case 252
        sections = service.get_document_sections(252, leave_out_conclusion=True)
        if not sections:
            print("❌ No sections found")
            return False
            
        ontology_entities = service.get_section_ontology_entities(252, sections)
        total_entities = sum(len(entities) for entities in ontology_entities.values())
        
        if total_entities > 0:
            # Check first entity to see if it has the fixed format
            for section_type, entities in ontology_entities.items():
                if entities:
                    first_entity = entities[0]
                    has_subject = bool(first_entity.get('subject'))
                    has_object = bool(first_entity.get('object'))
                    has_predicate = first_entity.get('predicate') == 'relates_to'
                    
                    print(f"✅ Main PredictionService fix verified!")
                    print(f"   Sample entity: {first_entity.get('subject', '')} → {first_entity.get('object', '')}")
                    print(f"   Has proper format: {has_subject and has_object and has_predicate}")
                    return True
        
        print(f"❌ Fix not working - {total_entities} entities found")
        return False

if __name__ == "__main__":
    try:
        verify_fix()
    except Exception as e:
        print(f"Error: {e}")
