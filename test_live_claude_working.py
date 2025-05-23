#!/usr/bin/env python3
"""
Test script to verify live Claude is now working.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set environment variables for live Claude
os.environ['USE_MOCK_GUIDELINE_RESPONSES'] = 'false'
os.environ['FORCE_MOCK_LLM'] = 'false'
os.environ['ANTHROPIC_MODEL'] = 'claude-3-7-sonnet-20250219'

from app import create_app
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_live_claude():
    """Test that live Claude is working."""
    
    print("=== Testing Live Claude ===")
    
    # Create app context
    app = create_app('config')
    
    with app.app_context():
        try:
            # Test LLM Service directly
            print("1. Testing LLMService directly...")
            from app.services.llm_service import LLMService
            
            llm_service = LLMService()
            print(f"   LLM Type: {type(llm_service.llm)}")
            print(f"   Model Name: {llm_service.model_name}")
            
            # Test simple prompt
            test_prompt = "Explain the key principles of engineering ethics in exactly one sentence."
            response = llm_service.llm.invoke(test_prompt)
            
            print(f"   Test prompt: {test_prompt}")
            print(f"   Response: {str(response)[:200]}...")
            
            # Check if it's using live Claude
            is_live_claude = (
                "ChatAnthropic" in str(type(llm_service.llm)) or
                (len(str(response)) > 100 and "I understand you're looking at an engineering ethics scenario" not in str(response))
            )
            
            if is_live_claude:
                print("   ✅ Using live Claude!")
            else:
                print("   ❌ Still using mock LLM")
            
            # Test PredictionService
            print("\n2. Testing PredictionService with live Claude...")
            from app.services.experiment.prediction_service import PredictionService
            
            prediction_service = PredictionService()
            print(f"   PredictionService LLM Type: {type(prediction_service.llm_service.llm)}")
            
            # Generate a prediction for Case 252
            result = prediction_service.generate_conclusion_prediction(document_id=252)
            
            if result.get('success'):
                prediction = result.get('prediction', '')
                print(f"   ✅ Prediction generated successfully")
                print(f"   Length: {len(str(prediction))}")
                print(f"   Preview: {str(prediction)[:200]}...")
                
                # Check for mock response patterns
                is_mock_response = any(phrase in str(prediction) for phrase in [
                    "I understand you're looking at an engineering ethics scenario",
                    "This appears to be related to a military medical triage situation"
                ])
                
                if is_mock_response:
                    print("   ❌ Prediction shows mock response patterns")
                else:
                    print("   ✅ Prediction appears to be from live Claude")
                    
            else:
                print(f"   ❌ Prediction failed: {result.get('error')}")
                
        except Exception as e:
            print(f"Error in test: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_live_claude()
