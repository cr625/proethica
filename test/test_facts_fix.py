#!/usr/bin/env python3
"""
Test the FIXED PredictionService to verify Facts section is now included.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_facts_fix():
    """Test that the fixed PredictionService includes Facts section."""
    
    from app import create_app
    
    # Create app context
    app = create_app('config')
    
    with app.app_context():
        try:
            # Import the FIXED prediction service
            from app.services.experiment.prediction_service_fixed import PredictionService
            
            print("=== Testing FIXED PredictionService ===")
            
            # Initialize the fixed prediction service
            fixed_service = PredictionService()
            
            # Test get_document_sections with Case 252
            print("\n1. Testing get_document_sections with Case 252...")
            sections = fixed_service.get_document_sections(252, leave_out_conclusion=True)
            
            print(f"   Retrieved sections: {list(sections.keys())}")
            
            # Check for Facts section
            if 'facts' in sections:
                facts_content = sections['facts']
                print(f"   ✅ SUCCESS: Facts section found!")
                print(f"   Facts content length: {len(facts_content)} characters")
                print(f"   Facts preview: {facts_content[:200]}...")
            else:
                print("   ❌ FAILED: Facts section still missing")
                return False
            
            # Test conclusion prediction to verify Facts are included in prompt
            print("\n2. Testing generate_conclusion_prediction...")
            result = fixed_service.generate_conclusion_prediction(252)
            
            if result['success']:
                prompt = result['prompt']
                print(f"   ✅ Conclusion prediction generated successfully")
                print(f"   Prompt length: {len(prompt)} characters")
                
                # Check if Facts are in the prompt
                if 'FACTS:' in prompt and len(sections['facts']) > 100:
                    facts_in_prompt = prompt[prompt.find('FACTS:'):prompt.find('FACTS:')+500]
                    print(f"   ✅ Facts section found in prompt:")
                    print(f"   {facts_in_prompt}...")
                    
                    # Check for Engineer T mention
                    if 'Engineer T' in facts_in_prompt:
                        print("   ✅ Engineer T mentioned in Facts - content is correct!")
                        return True
                    else:
                        print("   ⚠️  Engineer T not found in Facts section")
                        return False
                else:
                    print("   ❌ Facts section not properly included in prompt")
                    return False
            else:
                print(f"   ❌ Conclusion prediction failed: {result.get('error')}")
                return False
                
        except Exception as e:
            print(f"Error in test: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_facts_fix()
    if success:
        print("\n🎉 FACTS SECTION FIX VERIFIED SUCCESSFUL! 🎉")
        print("The fixed PredictionService now properly includes Facts in prompts.")
    else:
        print("\n❌ Fix verification failed - Facts section still missing")
