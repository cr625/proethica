#!/usr/bin/env python3
"""
Quick focused test to understand Claude model version responses.
"""

import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def quick_model_test():
    try:
        import anthropic
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        client = anthropic.Anthropic(api_key=api_key)
        
        # Test just our current models with a very specific prompt
        models = {
            "Sonnet 4": "claude-sonnet-4-20250514",
            "Opus 4.1": "claude-opus-4-1-20250805", 
            "Haiku 3.5": "claude-3-5-haiku-20241022"
        }
        
        prompt = "I am calling you via API with model ID '{}'. Please confirm: Are you actually {}, or are you a different Claude model? Be precise about your actual model version."
        
        print("🔍 QUICK MODEL VERIFICATION")
        print("=" * 50)
        
        for name, model_id in models.items():
            print(f"\n📋 Testing {name} ({model_id})")
            
            try:
                response = client.messages.create(
                    model=model_id,
                    max_tokens=100,
                    temperature=0,
                    messages=[{
                        "role": "user", 
                        "content": prompt.format(model_id, name)
                    }]
                )
                
                print(f"✅ Response: {response.content[0].text}")
                print(f"   Model in API call: {model_id}")
                
            except Exception as e:
                print(f"❌ Failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    quick_model_test()