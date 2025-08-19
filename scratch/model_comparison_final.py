#!/usr/bin/env python3
"""
Final comprehensive test comparing old vs new Claude models.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/home/chris/onto/proethica/.env')

def final_model_comparison():
    try:
        import anthropic
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        client = anthropic.Anthropic(api_key=api_key)
        
        # Compare old vs new models
        model_comparison = {
            # New models (what we configured)
            "🆕 Sonnet 4": "claude-sonnet-4-20250514",
            "🆕 Opus 4.1": "claude-opus-4-1-20250805",
            
            # Older models for comparison
            "🕐 Sonnet 3.5 (Oct 2024)": "claude-3-5-sonnet-20241022", 
            "🕐 Opus 3 (Feb 2024)": "claude-3-opus-20240229"
        }
        
        print("🔍 CLAUDE MODEL GENERATION COMPARISON")
        print("=" * 60)
        
        # Test each model with identity question
        identity_results = {}
        
        for name, model_id in model_comparison.items():
            print(f"\n📋 {name}")
            print(f"   Model ID: {model_id}")
            
            try:
                response = client.messages.create(
                    model=model_id,
                    max_tokens=100,
                    temperature=0,
                    messages=[{
                        "role": "user",
                        "content": "What Claude model version are you? Please be as specific as possible."
                    }]
                )
                
                answer = response.content[0].text
                identity_results[name] = answer
                
                print(f"✅ Identity: {answer[:80]}...")
                
                # Check for version indicators
                if "4.1" in answer or "opus 4" in answer.lower():
                    print("   🎯 Claims to be Opus 4.1")
                elif "sonnet 4" in answer.lower():
                    print("   🎯 Claims to be Sonnet 4") 
                elif "3.5" in answer:
                    print("   📅 Claims to be 3.5 generation")
                elif "3 " in answer or "claude 3" in answer.lower():
                    print("   📅 Claims to be Claude 3")
                    
            except Exception as e:
                print(f"❌ Failed: {e}")
        
        # Summary analysis
        print(f"\n" + "=" * 60)
        print("📊 ANALYSIS SUMMARY")
        print("=" * 60)
        
        print(f"\n🔍 Model Identity Responses:")
        for name, response in identity_results.items():
            print(f"\n{name}:")
            print(f"   → {response}")
        
        # Key findings
        print(f"\n🎯 KEY FINDINGS:")
        newer_models = [k for k in identity_results.keys() if "🆕" in k]
        older_models = [k for k in identity_results.keys() if "🕐" in k]
        
        print(f"✅ Newer models tested: {len(newer_models)}")
        print(f"📅 Older models tested: {len(older_models)}")
        
        # Check if newer models identify differently
        new_identifies_correctly = 0
        for name in newer_models:
            if name in identity_results:
                response = identity_results[name].lower()
                if "4.1" in response or "sonnet 4" in response or "opus 4" in response:
                    new_identifies_correctly += 1
        
        print(f"🎯 New models identifying as v4+: {new_identifies_correctly}/{len(newer_models)}")
        
        if new_identifies_correctly > 0:
            print(f"✅ SUCCESS: We are getting the newer Claude models!")
            print(f"🎉 Model configuration is working correctly!")
        else:
            print(f"⚠️  Models may be aliases or not identifying correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    final_model_comparison()