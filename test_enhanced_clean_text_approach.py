#!/usr/bin/env python3
"""
Test the enhanced clean text approach in the main PredictionService.
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

def test_enhanced_approach():
    """Test the enhanced clean text approach."""
    
    print("🎯 TESTING ENHANCED CLEAN TEXT APPROACH")
    print("=" * 50)
    
    with app.app_context():
        
        # Initialize main prediction service
        service = PredictionService()
        
        # Test with Case 252
        case_id = 252
        print(f"1. Testing document sections retrieval for Case {case_id}...")
        
        sections = service.get_document_sections(case_id, leave_out_conclusion=True)
        
        if not sections:
            print("   ❌ No sections retrieved")
            return False
        
        print(f"   ✅ Retrieved {len(sections)} sections: {list(sections.keys())}")
        
        # Check for HTML in sections
        html_detected = False
        clean_sections = 0
        
        for section_type, content in sections.items():
            if '<' in content and '>' in content:
                html_detected = True
                print(f"   🟡 '{section_type}' contains HTML ({len(content)} chars)")
                print(f"      Sample: {content[:80]}...")
            else:
                clean_sections += 1
                print(f"   ✅ '{section_type}' is clean text ({len(content)} chars)")
                print(f"      Sample: {content[:80]}...")
        
        # Assessment
        clean_ratio = clean_sections / len(sections) if sections else 0
        
        print(f"\n2. 📊 CLEANLINESS ASSESSMENT:")
        print(f"   Total sections: {len(sections)}")
        print(f"   Clean sections: {clean_sections}")
        print(f"   Clean ratio: {clean_ratio:.1%}")
        
        if clean_ratio >= 0.6:
            print(f"   ✅ SUCCESS: Enhanced approach working!")
            print(f"   🎯 Clean metadata sections are being used effectively")
        elif clean_ratio > 0:
            print(f"   🟡 PARTIAL: Some improvements but more cleaning needed")
        else:
            print(f"   ❌ ISSUE: HTML still present in all sections")
        
        # Test quick prediction to see if prompt is cleaner
        print(f"\n3. 🧪 Testing prediction generation...")
        
        try:
            result = service.generate_conclusion_prediction(case_id)
            
            if result.get('success'):
                prompt = result.get('prompt', '')
                prompt_sample = prompt[:500] + "..." if len(prompt) > 500 else prompt
                
                print(f"   ✅ Prediction generated successfully")
                print(f"   📄 Prompt length: {len(prompt)} chars")
                print(f"   📖 Prompt sample: {prompt_sample}")
                
                # Check for HTML in prompt
                if '<' in prompt and '>' in prompt:
                    import re
                    html_tags = re.findall(r'<[^>]+>', prompt)
                    print(f"   🟡 HTML still in prompt: {len(html_tags)} tags found")
                else:
                    print(f"   ✅ Prompt is clean (no HTML detected)")
                
            else:
                print(f"   ❌ Prediction failed: {result.get('error')}")
                
        except Exception as e:
            print(f"   ❌ Error generating prediction: {e}")
        
        print(f"\n🏆 FINAL RESULT:")
        
        if clean_ratio >= 0.6 and not html_detected:
            print(f"   ✅ COMPLETE SUCCESS: Enhanced clean text approach working perfectly!")
            print(f"   🎉 Clean metadata sections being used, HTML eliminated")
            return True
        elif clean_ratio >= 0.6:
            print(f"   🟡 MOSTLY SUCCESS: Clean text approach working, some HTML cleaning still needed")
            return True
        else:
            print(f"   ❌ NEEDS WORK: Enhanced approach not fully effective")
            return False

if __name__ == "__main__":
    try:
        success = test_enhanced_approach()
        exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
