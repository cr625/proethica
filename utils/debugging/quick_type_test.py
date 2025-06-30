#!/usr/bin/env python3
"""
Quick test of type mapper with proper LLM types.
"""
import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.services.guideline_concept_type_mapper import GuidelineConceptTypeMapper

def test_proper_mapping():
    """Test type mapper with the actual LLM types from our test data."""
    print("🎯 TESTING TYPE MAPPER WITH PROPER LLM TYPES")
    print("=" * 50)
    
    app = create_app('config')
    with app.app_context():
        mapper = GuidelineConceptTypeMapper()
        
        # Test the proper concept types from our test data
        test_cases = [
            ('Fundamental Principle', 'Public Safety Paramount'),
            ('Professional Standard', 'Professional Competence'), 
            ('Core Value', 'Honesty and Integrity'),
            ('Environmental Responsibility', 'Sustainability'),
            ('Professional Growth', 'Professional Development')
        ]
        
        improvements = 0
        for llm_type, concept_name in test_cases:
            result = mapper.map_concept_type(
                llm_type=llm_type,
                concept_name=concept_name,
                concept_description=''
            )
            
            if result.mapped_type != 'state':
                improvements += 1
                status = '✅ IMPROVEMENT'
            else:
                status = '⚠️ NO CHANGE'
                
            print(f'{status}: {llm_type} → {result.mapped_type} (confidence: {result.confidence:.2f})')
            print(f'    Concept: {concept_name}')
            print(f'    Justification: {result.justification}')
            print()
        
        improvement_rate = improvements / len(test_cases) * 100
        print(f"📊 SUMMARY: {improvements}/{len(test_cases)} concepts improved ({improvement_rate:.1f}%)")
        
        if improvement_rate > 60:
            print("✅ Type mapper working correctly!")
        else:
            print("⚠️ Type mapper needs investigation")

if __name__ == "__main__":
    test_proper_mapping()