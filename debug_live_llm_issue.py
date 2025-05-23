#!/usr/bin/env python3
"""
Debug script to investigate the live LLM military medical triage issue.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_live_llm():
    """Debug the live LLM configuration and responses."""
    
    print("=== Debugging Live LLM Issue ===")
    
    # Create app context for database access
    app = create_app('config')
    
    with app.app_context():
        try:
            from app.services.experiment.prediction_service import PredictionService
            
            print("1. Creating PredictionService...")
            prediction_service = PredictionService()
            
            print(f"   LLM Type: {type(prediction_service.llm_service.llm)}")
            print(f"   Model Name: {prediction_service.llm_service.model_name}")
            
            # Check environment variables
            print(f"\n2. Environment Variables:")
            print(f"   USE_MOCK_GUIDELINE_RESPONSES: {os.environ.get('USE_MOCK_GUIDELINE_RESPONSES')}")
            print(f"   FORCE_MOCK_LLM: {os.environ.get('FORCE_MOCK_LLM')}")
            print(f"   ANTHROPIC_API_KEY exists: {'ANTHROPIC_API_KEY' in os.environ}")
            print(f"   ANTHROPIC_MODEL: {os.environ.get('ANTHROPIC_MODEL')}")
            
            # Test the specific Case 252 prediction flow
            print(f"\n3. Testing Case 252 conclusion prediction...")
            try:
                result = prediction_service.generate_conclusion_prediction(document_id=252)
                
                if result.get('success'):
                    print("   ✓ Prediction generated successfully")
                    
                    # Examine the full result
                    prediction = result.get('prediction', '')
                    full_response = result.get('full_response', '')
                    prompt = result.get('prompt', '')
                    
                    print(f"   Prompt length: {len(str(prompt))}")
                    print(f"   Prediction length: {len(str(prediction))}")
                    print(f"   Full response length: {len(str(full_response))}")
                    
                    # Show first 300 chars of each
                    print(f"\n   Prompt preview:")
                    print(f"   {str(prompt)[:300]}...")
                    
                    print(f"\n   Prediction preview:")
                    print(f"   {str(prediction)[:300]}...")
                    
                    print(f"\n   Full response preview:")
                    print(f"   {str(full_response)[:300]}...")
                    
                    # Check for military keywords
                    military_keywords = ['military', 'medical', 'triage', 'patient', 'allocating', 'limited resources']
                    
                    prompt_military = [kw for kw in military_keywords if kw.lower() in str(prompt).lower()]
                    prediction_military = [kw for kw in military_keywords if kw.lower() in str(prediction).lower()]
                    response_military = [kw for kw in military_keywords if kw.lower() in str(full_response).lower()]
                    
                    print(f"\n   Military keywords in prompt: {prompt_military}")
                    print(f"   Military keywords in prediction: {prediction_military}")
                    print(f"   Military keywords in full response: {response_military}")
                    
                    # Check for engineering keywords
                    engineering_keywords = ['engineer', 'nspe', 'ethics', 'professional', 'public safety', 'design']
                    
                    prompt_engineering = [kw for kw in engineering_keywords if kw.lower() in str(prompt).lower()]
                    prediction_engineering = [kw for kw in engineering_keywords if kw.lower() in str(prediction).lower()]
                    response_engineering = [kw for kw in engineering_keywords if kw.lower() in str(full_response).lower()]
                    
                    print(f"   Engineering keywords in prompt: {prompt_engineering}")
                    print(f"   Engineering keywords in prediction: {prediction_engineering}")
                    print(f"   Engineering keywords in full response: {response_engineering}")
                    
                else:
                    print(f"   ❌ Prediction failed: {result.get('error')}")
                    
            except Exception as e:
                print(f"   ❌ Error generating prediction: {e}")
                import traceback
                traceback.print_exc()
            
            # Test direct LLM call
            print(f"\n4. Testing direct LLM call...")
            try:
                direct_prompt = "You are analyzing an engineering ethics case from the NSPE Board of Ethical Review. Please explain the key ethical principles involved."
                direct_response = prediction_service.llm_service.llm.invoke(direct_prompt)
                
                print(f"   Direct prompt: {direct_prompt}")
                print(f"   Direct response: {str(direct_response)[:300]}...")
                
                # Check for military content in direct response
                direct_military = [kw for kw in military_keywords if kw.lower() in str(direct_response).lower()]
                if direct_military:
                    print(f"   ⚠️  Direct response has military keywords: {direct_military}")
                else:
                    print(f"   ✓ Direct response is clean")
                    
            except Exception as e:
                print(f"   ❌ Error in direct LLM call: {e}")
                
        except Exception as e:
            print(f"Error in debug: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_live_llm()
