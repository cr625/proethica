#!/usr/bin/env python3
"""
Test HTML cleaning integration in the main PredictionService.

This script tests that the main prediction service now cleans HTML content
from prompts before sending to the LLM.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.experiment.prediction_service import PredictionService
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Test HTML cleaning integration."""
    
    print("🧪 Testing HTML Cleaning Integration")
    print("=" * 50)
    
    try:
        # Case 252 ID
        case_id = 252
        
        # Step 1: Test the main prediction service
        print(f"\n1. Testing main PredictionService with HTML cleaning...")
        service = PredictionService()
        
        # Get sections to see if HTML is cleaned
        sections = service.get_document_sections(case_id, leave_out_conclusion=True)
        
        print(f"\n2. Section Analysis:")
        has_any_html = False
        for section_type, content in sections.items():
            has_html = '<' in content and '>' in content
            has_any_html = has_any_html or has_html
            print(f"   {section_type}: {len(content)} chars, HTML detected: {has_html}")
            
            if has_html:
                print(f"   ❌ HTML still present in {section_type}!")
                # Show first 200 chars
                print(f"   Sample: {content[:200]}...")
                
                # Show specific HTML tags found
                import re
                html_tags = re.findall(r'<[^>]+>', content[:1000])
                if html_tags:
                    print(f"   HTML tags: {html_tags[:3]}...")
            else:
                print(f"   ✅ {section_type} is clean")
        
        # Step 2: Test HTML cleaning method directly
        print(f"\n3. Testing HTML cleaning method directly...")
        test_html = '<div class="field__items"><p>This is a test paragraph.</p><h2>Header</h2></div>'
        cleaned = service.clean_html_content(test_html)
        print(f"   Original: {test_html}")
        print(f"   Cleaned:  {cleaned}")
        print(f"   HTML removed: {'<' not in cleaned}")
        
        # Step 3: Generate a test prediction
        print(f"\n4. Generating conclusion prediction...")
        result = service.generate_conclusion_prediction(case_id)
        
        if result.get('success'):
            prompt = result.get('prompt', '')
            
            # Check if prompt contains HTML
            html_patterns = ['<div', '<p>', '<h1>', '<h2>', '<span', 'class=', 'field__']
            html_found = []
            
            for pattern in html_patterns:
                if pattern in prompt:
                    html_found.append(pattern)
            
            has_html_in_prompt = len(html_found) > 0
            
            print(f"   ✓ Prediction generated successfully")
            print(f"   Prompt length: {len(prompt)} characters")
            print(f"   HTML patterns in prompt: {html_found}")
            print(f"   HTML detected: {has_html_in_prompt}")
            
            if has_html_in_prompt:
                print("   ❌ HTML still detected in prompt!")
                # Find and show HTML snippets
                import re
                html_matches = re.findall(r'<[^>]+>', prompt)
                if html_matches:
                    print(f"   HTML tags found: {html_matches[:5]}...")
            else:
                print("   ✅ Prompt is clean - no HTML detected!")
                
            # Show a sample of the facts section in the prompt
            if '# FACTS:' in prompt:
                facts_start = prompt.find('# FACTS:')
                facts_end = prompt.find('\n\n#', facts_start + 10)
                if facts_end == -1:
                    facts_end = facts_start + 500
                facts_section = prompt[facts_start:facts_end]
                print(f"\n   Facts section sample:")
                print(f"   {facts_section[:300]}...")
            
            # Show a sample of the references section in the prompt
            if '# REFERENCES:' in prompt:
                refs_start = prompt.find('# REFERENCES:')
                refs_end = prompt.find('\n\n#', refs_start + 10)
                if refs_end == -1:
                    refs_end = refs_start + 300
                refs_section = prompt[refs_start:refs_end]
                print(f"\n   References section sample:")
                print(f"   {refs_section[:200]}...")
                
        else:
            print(f"   ❌ Prediction failed: {result.get('error')}")
            has_html_in_prompt = True  # Consider as failure
        
        print(f"\n🎯 Integration Test Complete!")
        print("=" * 50)
        
        # Summary
        if result.get('success') and not has_html_in_prompt and not has_any_html:
            print("✅ SUCCESS: HTML cleaning is working perfectly in main PredictionService!")
        elif result.get('success') and not has_html_in_prompt:
            print("✅ PARTIAL SUCCESS: Prompt is clean, but sections may still have HTML")
        else:
            print("❌ ISSUE: HTML cleaning may not be working properly")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
