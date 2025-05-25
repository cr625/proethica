#!/usr/bin/env python3
"""
Investigate the missing Facts section issue in Case 252.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def investigate_facts_section():
    """Investigate what Facts data exists for Case 252 and how it's used."""
    
    print("=== Investigating Facts Section for Case 252 ===")
    
    # Create app context
    app = create_app('config')
    
    with app.app_context():
        try:
            # 1. Check Case 252 in database
            print("1. Checking Case 252 in database...")
            from app.models.document import Document
            from app.models.document_section import DocumentSection
            
            case_252 = Document.query.get(252)
            if not case_252:
                print("   ❌ Case 252 not found in database")
                return
            
            print(f"   ✓ Case 252 found: {case_252.title}")
            print(f"   Document ID: {case_252.id}")
            print(f"   Document type: {case_252.document_type}")
            
            # 2. Check document sections
            print("\n2. Checking document sections...")
            sections = DocumentSection.query.filter_by(document_id=252).all()
            
            print(f"   Found {len(sections)} sections:")
            for section in sections:
                print(f"   - Section {section.id}: {section.section_type} ({len(section.content) if section.content else 0} chars)")
                if section.section_type and 'fact' in section.section_type.lower():
                    print(f"     FACTS SECTION FOUND: {section.content[:200]}...")
            
            # 3. Look for Facts section specifically
            facts_sections = [s for s in sections if s.section_type and 'fact' in s.section_type.lower()]
            if facts_sections:
                print(f"\n   ✓ Found {len(facts_sections)} Facts sections:")
                for section in facts_sections:
                    print(f"     Section {section.id}: {section.section_type}")
                    print(f"     Content preview: {section.content[:300] if section.content else 'No content'}...")
            else:
                print("   ❌ No Facts sections found")
            
            # 4. Check how PredictionService builds prompts
            print("\n3. Checking how PredictionService builds prompts...")
            from app.services.experiment.prediction_service import PredictionService
            
            prediction_service = PredictionService()
            
            # Get the document sections using the correct method
            sections = prediction_service.get_document_sections(252, leave_out_conclusion=True)
            
            print(f"   Retrieved sections: {list(sections.keys())}")
            
            # Check if Facts are included
            if 'facts' in sections:
                print("   ✓ Facts section found in get_document_sections")
                print(f"   Facts content length: {len(sections['facts'])}")
                print(f"   Facts preview: {sections['facts'][:200]}...")
            else:
                print("   ❌ Facts section NOT found in get_document_sections")
            
            # 5. Check specific prompt generation
            print("\n4. Checking specific prompt generation...")
            
            # Use the same method as prediction service to build prompt
            try:
                # Get ontology entities
                ontology_entities = prediction_service.get_section_ontology_entities(252, sections)
                
                # Find similar cases
                similar_cases = prediction_service._find_similar_cases(252, limit=3)
                
                print(f"   Found {len(similar_cases)} similar cases")
                
                # Build the full prompt using the actual method
                full_prompt = prediction_service._construct_conclusion_prediction_prompt(
                    document=case_252,
                    sections=sections,
                    ontology_entities=ontology_entities,
                    similar_cases=similar_cases
                )
                
                print(f"   Full prompt length: {len(full_prompt) if full_prompt else 0} chars")
                
                # Check if Facts are in the full prompt
                if full_prompt:
                    facts_keywords = ['FACTS:', 'Facts:', 'FACT:', 'Fact:']
                    facts_found = any(keyword in full_prompt for keyword in facts_keywords)
                    
                    if facts_found:
                        print("   ✓ Facts section found in full prompt")
                        # Find the Facts section
                        for keyword in facts_keywords:
                            if keyword in full_prompt:
                                facts_start = full_prompt.find(keyword)
                                facts_section = full_prompt[facts_start:facts_start+500]
                                print(f"   Facts section preview: {facts_section}...")
                                break
                    else:
                        print("   ❌ Facts section NOT found in full prompt")
                        
                        # Show what sections ARE included
                        print("   Sections that ARE included:")
                        section_keywords = ['TITLE:', 'QUESTION:', 'BACKGROUND:', 'CONCLUSION:', 'DISCUSSION:']
                        for keyword in section_keywords:
                            if keyword in full_prompt:
                                print(f"     - {keyword}")
                        
                        # Show a sample of the prompt
                        print(f"   Prompt preview: {full_prompt[:800]}...")
                
            except Exception as e:
                print(f"   ❌ Error building prompt: {e}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            print(f"Error in investigation: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    investigate_facts_section()
