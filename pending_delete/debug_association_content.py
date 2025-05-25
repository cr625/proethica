#!/usr/bin/env python3
"""
Debug script to investigate why ontology entities have empty content.

This script traces the data flow from section_triple_association_service
to understand why subject/object/predicate fields are empty.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.experiment.prediction_service import PredictionService
from ttl_triple_association.section_triple_association_service import SectionTripleAssociationService
from app.models.document_section import DocumentSection
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Debug association content extraction."""
    
    print("🔍 DEBUGGING ASSOCIATION CONTENT EXTRACTION")
    print("=" * 60)
    
    try:
        # Test a single section first
        case_id = 252
        
        # Get a section to test with
        print(f"1. Getting DocumentSection records for Case {case_id}...")
        doc_sections = DocumentSection.query.filter_by(document_id=case_id).all()
        
        if not doc_sections:
            print("   ❌ No DocumentSection records found")
            return
            
        print(f"   ✅ Found {len(doc_sections)} sections")
        
        # Test the first few sections
        for i, section in enumerate(doc_sections[:3]):
            print(f"\n2.{i+1} Testing Section ID {section.id} (type: {section.section_type}):")
            
            # Create association service
            association_service = SectionTripleAssociationService()
            
            # Get raw associations result
            print(f"   Getting associations for section {section.id}...")
            associations_result = association_service.get_section_associations(section.id)
            
            print(f"   Raw result type: {type(associations_result)}")
            print(f"   Raw result keys: {associations_result.keys() if isinstance(associations_result, dict) else 'Not a dict'}")
            
            if associations_result and 'associations' in associations_result:
                associations = associations_result['associations']
                print(f"   Found {len(associations)} associations")
                
                if associations:
                    # Examine first association
                    first_assoc = associations[0]
                    print(f"   First association type: {type(first_assoc)}")
                    print(f"   First association content:")
                    
                    if isinstance(first_assoc, dict):
                        for key, value in first_assoc.items():
                            print(f"     {key}: '{value}' (type: {type(value)})")
                    else:
                        print(f"     Raw content: {first_assoc}")
                        print(f"     Dir: {dir(first_assoc)}")
                        
                        # Try to access attributes if it's an object
                        if hasattr(first_assoc, 'subject'):
                            print(f"     subject attr: '{first_assoc.subject}'")
                        if hasattr(first_assoc, 'predicate'):
                            print(f"     predicate attr: '{first_assoc.predicate}'")
                        if hasattr(first_assoc, 'object'):
                            print(f"     object attr: '{first_assoc.object}'")
                        if hasattr(first_assoc, 'score'):
                            print(f"     score attr: '{first_assoc.score}'")
                        
                        # Check if it has __dict__
                        if hasattr(first_assoc, '__dict__'):
                            print(f"     __dict__: {first_assoc.__dict__}")
                
            else:
                print(f"   ❌ No associations found or invalid result format")
        
        print(f"\n3. Testing PredictionService processing:")
        service = PredictionService()
        
        # Get a sample section to test
        test_section = doc_sections[1] if len(doc_sections) > 1 else doc_sections[0]
        print(f"   Testing with section {test_section.id} (type: {test_section.section_type})")
        
        # Test how PredictionService processes the associations
        section_type = test_section.section_type.lower() if test_section.section_type else ''
        
        # Call the association service directly like PredictionService does
        associations_result = service.triple_association_service.get_section_associations(test_section.id)
        
        print(f"   Associations result: {associations_result}")
        
        if associations_result and 'associations' in associations_result:
            triples = associations_result['associations']
            print(f"   Processing {len(triples)} triples...")
            
            for i, triple in enumerate(triples[:2]):  # Test first 2
                print(f"   Triple {i+1}:")
                print(f"     Raw triple: {triple}")
                print(f"     Type: {type(triple)}")
                
                # This is how PredictionService processes each triple
                entity = {
                    'subject': triple.get('subject', '') if isinstance(triple, dict) else '',
                    'predicate': triple.get('predicate', '') if isinstance(triple, dict) else '',
                    'object': triple.get('object', '') if isinstance(triple, dict) else '',
                    'score': triple.get('score', 0.0) if isinstance(triple, dict) else 0.0,
                    'source': triple.get('source', '') if isinstance(triple, dict) else ''
                }
                
                print(f"     Processed entity: {entity}")
                
        print(f"\n🎯 DEBUGGING COMPLETE")
        
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
