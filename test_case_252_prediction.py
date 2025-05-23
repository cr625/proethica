#!/usr/bin/env python3
"""
Test script to simulate the exact Case 252 prediction flow that's showing military content.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.experiment.prediction_service import PredictionService
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_case_252_prediction():
    """Test the exact prediction flow for Case 252."""
    
    print("=== Testing Case 252 Prediction Flow ===")
    
    try:
        # Create prediction service (this simulates what the interface does)
        prediction_service = PredictionService()
        
        print(f"LLM Service Type: {type(prediction_service.llm_service.llm)}")
        print(f"Model Name: {prediction_service.llm_service.model_name}")
        
        # Test 1: Generate conclusion prediction for Case 252 (this is what the button does)
        print("\n1. Testing generate_conclusion_prediction for Case 252:")
        try:
            result = prediction_service.generate_conclusion_prediction(document_id=252)
            
            if result.get('success'):
                prediction = result.get('prediction', '')
                full_response = result.get('full_response', '')
                prompt = result.get('prompt', '')
                
                print(f"   Prediction success: {result.get('success')}")
                print(f"   Prediction length: {len(str(prediction))}")
                print(f"   Full response length: {len(str(full_response))}")
                print(f"   Prompt length: {len(str(prompt))}")
                
                # Check prompt for military content
                military_keywords = ['military', 'medical', 'triage', 'patient', 'allocating', 'limited resources']
                
                prompt_keywords = [kw for kw in military_keywords if kw.lower() in str(prompt).lower()]
                if prompt_keywords:
                    print(f"   ⚠️  PROMPT has military keywords: {prompt_keywords}")
                else:
                    print(f"   ✓ Prompt is clean")
                
                # Check prediction for military content
                prediction_keywords = [kw for kw in military_keywords if kw.lower() in str(prediction).lower()]
                if prediction_keywords:
                    print(f"   ⚠️  PREDICTION has military keywords: {prediction_keywords}")
                    print(f"   Prediction snippet: {str(prediction)[:200]}...")
                else:
                    print(f"   ✓ Prediction is clean")
                
                # Check full response for military content
                response_keywords = [kw for kw in military_keywords if kw.lower() in str(full_response).lower()]
                if response_keywords:
                    print(f"   ⚠️  FULL RESPONSE has military keywords: {response_keywords}")
                    print(f"   Full response snippet: {str(full_response)[:200]}...")
                else:
                    print(f"   ✓ Full response is clean")
                    
            else:
                print(f"   ❌ Prediction failed: {result.get('error')}")
                
        except Exception as e:
            print(f"   ❌ Error in conclusion prediction: {e}")
        
        # Test 2: Test a direct LLM call with engineering ethics prompt
        print("\n2. Testing direct LLM call:")
        try:
            direct_response = prediction_service.llm_service.llm.invoke(
                "Analyze this engineering ethics scenario about professional responsibility and the NSPE Code of Ethics."
            )
            
            print(f"   Direct response: {str(direct_response)[:200]}...")
            
            # Check for military content in direct response
            direct_keywords = [kw for kw in military_keywords if kw.lower() in str(direct_response).lower()]
            if direct_keywords:
                print(f"   ⚠️  DIRECT RESPONSE has military keywords: {direct_keywords}")
            else:
                print(f"   ✓ Direct response is clean")
                
        except Exception as e:
            print(f"   ❌ Error in direct LLM call: {e}")
            
    except Exception as e:
        print(f"Error in prediction flow test: {e}")

if __name__ == "__main__":
    test_case_252_prediction()
