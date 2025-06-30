#!/usr/bin/env python3
"""
Debug the association generation error
"""

import os
import sys
import traceback

# Set up environment
os.environ['DATABASE_URL'] = 'postgresql://ai_ethical_dm_user:password@localhost:5433/ai_ethical_dm'
os.environ['FLASK_ENV'] = 'development'

# Add project to path
sys.path.insert(0, '/home/chris/proethica')

def test_simple_association():
    """Test just the association generation without Flask context"""
    
    try:
        # Import required modules
        from app.services.enhanced_guideline_association_service import EnhancedGuidelineAssociationService
        from app.models.document import Document
        from app.models.entity_triple import EntityTriple
        
        print("✅ Imports successful")
        
        # Create service
        service = EnhancedGuidelineAssociationService()
        print("✅ Service created")
        
        # Create a minimal test case
        class MockDocument:
            def __init__(self):
                self.id = 19
                self.doc_metadata = {
                    'document_structure': {
                        'sections': [
                            {
                                'type': 'facts',
                                'content': 'The engineer was asked to work on a safety-critical project requiring specialized competence in structural analysis.',
                                'content_text': 'The engineer was asked to work on a safety-critical project requiring specialized competence in structural analysis.'
                            }
                        ]
                    }
                }
        
        mock_doc = MockDocument()
        
        # Test section extraction
        sections = service._extract_case_sections(mock_doc)
        print(f"✅ Extracted {len(sections)} sections: {list(sections.keys())}")
        
        if sections:
            section_content = list(sections.values())[0]
            print(f"   Content length: {len(section_content)}")
            
            # Test pattern indicators generation
            class MockConcept:
                def __init__(self):
                    self.subject = 'http://example.org/safety'
                    self.id = 1
            
            class MockScore:
                def __init__(self):
                    self.overall_confidence = 0.75
                    self.semantic_similarity = 0.80
                    self.keyword_overlap = 0.60
                    self.contextual_relevance = 0.70
                    self.reasoning = 'Test reasoning'
            
            mock_concept = MockConcept()
            mock_score = MockScore()
            
            # Test pattern indicators
            indicators = service._generate_pattern_indicators('facts', section_content, mock_concept, mock_score)
            print(f"✅ Generated pattern indicators: {type(indicators)}")
            print(f"   Keys: {list(indicators.keys())}")
            print(f"   Sample: safety_mentioned = {indicators.get('safety_mentioned', 'Not found')}")
            
            # Test if indicators is properly a dict
            if hasattr(indicators, 'get'):
                print("✅ Pattern indicators has .get() method")
            else:
                print(f"❌ Pattern indicators type: {type(indicators)} - no .get() method")
            
        else:
            print("❌ No sections extracted")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    test_simple_association()