#!/usr/bin/env python3
"""
Validate that Case 252 prediction in database is clean (HTML-free).
"""

import os
import sys

# Set environment
os.environ['FLASK_APP'] = 'run.py'
os.environ['FLASK_ENV'] = 'development'

# Add path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from run import app
from app.models.experiment import Prediction

def main():
    """Check the stored Case 252 prediction for HTML."""
    
    print("🔍 VALIDATING CASE 252 CLEAN PREDICTION IN DATABASE")
    print("=" * 55)
    
    with app.app_context():
        # Get the latest prediction for Case 252
        prediction = Prediction.query.filter_by(
            document_id=252,
            target='conclusion'
        ).first()
        
        if not prediction:
            print("❌ No prediction found for Case 252")
            return
            
        print(f"📊 Prediction ID: {prediction.id}")
        print(f"📊 Condition: {prediction.condition}")
        print(f"📊 Created: {prediction.created_at}")
        
        # Check the prompt for HTML
        prompt = prediction.prompt or ''
        html_indicators = ['<div', '<span', '<p>', '</div>', '</span>', '</p>']
        html_found = any(indicator in prompt for indicator in html_indicators)
        
        print(f"\n🧪 PROMPT ANALYSIS:")
        print(f"   Length: {len(prompt)} characters")
        print(f"   HTML detected: {'❌ YES' if html_found else '✅ NO'}")
        
        if html_found:
            print("   ⚠️  HTML still present in stored prompt")
            for indicator in html_indicators:
                if indicator in prompt:
                    count = prompt.count(indicator)
                    print(f"     - {indicator}: {count} occurrences")
            return False
        else:
            print("   🎉 SUCCESS: Stored prompt is completely HTML-free!")
        
        # Sample the prompt to verify content quality
        print(f"\n📄 PROMPT PREVIEW:")
        lines = prompt.split('\n')[:10]  # First 10 lines
        for i, line in enumerate(lines, 1):
            preview = line[:80] + "..." if len(line) > 80 else line
            print(f"   {i:2d}: {preview}")
        
        if len(lines) > 10:
            print(f"   ... ({len(lines)-10} more lines)")
        
        # Check if Facts section is present and clean
        if '# FACTS:' in prompt:
            facts_start = prompt.find('# FACTS:')
            facts_section = prompt[facts_start:facts_start+500]  # First 500 chars of facts
            
            print(f"\n✅ FACTS SECTION VERIFICATION:")
            print(f"   Found Facts section starting at position {facts_start}")
            print(f"   Preview: {facts_section[:200]}...")
            
            # Check if facts section is clean
            facts_html = any(indicator in facts_section for indicator in html_indicators)
            print(f"   HTML in Facts: {'❌ YES' if facts_html else '✅ NO'}")
        else:
            print(f"\n❌ Facts section not found in prompt")
        
        # Check References section
        if '# REFERENCES:' in prompt:
            refs_start = prompt.find('# REFERENCES:')
            refs_section = prompt[refs_start:refs_start+500]
            
            print(f"\n✅ REFERENCES SECTION VERIFICATION:")
            print(f"   Found References section starting at position {refs_start}")
            print(f"   Preview: {refs_section[:200]}...")
            
            # Check if references section is clean
            refs_html = any(indicator in refs_section for indicator in html_indicators)
            print(f"   HTML in References: {'❌ YES' if refs_html else '✅ NO'}")
        else:
            print(f"\n❓ References section not found in prompt")
        
        print(f"\n🎯 FINAL VALIDATION RESULT:")
        if not html_found:
            print(f"   ✅ SUCCESS: Case 252 prediction is ready for clean web display")
            print(f"   🌐 Web interface will now show HTML-free prompts")
            return True
        else:
            print(f"   ❌ FAILURE: HTML still detected, additional cleaning needed")
            return False

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
