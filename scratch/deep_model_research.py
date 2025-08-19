#!/usr/bin/env python3
"""
Deep research into Claude model responses to understand version mapping.
This will help us verify we're actually getting the correct models.
"""

import os
import sys
import json
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.models import ModelConfig

def deep_model_test():
    """Comprehensive test of Claude models with detailed analysis."""
    try:
        import anthropic
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("❌ ANTHROPIC_API_KEY not found")
            return
            
        client = anthropic.Anthropic(api_key=api_key)
        
        # Test all model configurations we have
        models_to_test = {
            # Our current configuration
            "Sonnet 4 (current default)": "claude-sonnet-4-20250514",
            "Opus 4.1 (current powerful)": "claude-opus-4-1-20250805",
            "Haiku 3.5 (current fast option)": "claude-3-5-haiku-20241022",
            
            # Test some older models for comparison
            "Sonnet 3.5 (older)": "claude-3-5-sonnet-20241022",
            "Opus 3 (older)": "claude-3-opus-20240229",
            
            # Test aliases if they work
            "Sonnet 4 alias": "claude-sonnet-4",
            "Opus 4.1 alias": "claude-opus-4-1",
        }
        
        # More detailed prompts to test capabilities
        test_prompts = [
            {
                "name": "Version Identity",
                "prompt": "Please tell me exactly what model you are, including your full version identifier. Be as specific as possible about your model name and version."
            },
            {
                "name": "Model Capabilities", 
                "prompt": "What are your key capabilities and when were you released? Please be specific about your model version."
            },
            {
                "name": "Knowledge Cutoff",
                "prompt": "What is your knowledge cutoff date and what Claude model version are you specifically?"
            }
        ]
        
        print("🔍 DEEP CLAUDE MODEL RESEARCH")
        print("=" * 80)
        
        results = {}
        
        for model_name, model_id in models_to_test.items():
            print(f"\n📋 Testing: {model_name} ({model_id})")
            print("-" * 60)
            
            model_results = {"model_id": model_id, "tests": {}}
            
            for test in test_prompts:
                print(f"\n🧪 {test['name']}:")
                try:
                    response = client.messages.create(
                        model=model_id,
                        max_tokens=200,
                        temperature=0.0,  # Use 0 temperature for consistent responses
                        messages=[{
                            "role": "user",
                            "content": test["prompt"]
                        }]
                    )
                    
                    response_text = response.content[0].text
                    print(f"✅ Response: {response_text}")
                    print(f"   Tokens: {response.usage.input_tokens} → {response.usage.output_tokens}")
                    
                    model_results["tests"][test["name"]] = {
                        "success": True,
                        "response": response_text,
                        "tokens": {
                            "input": response.usage.input_tokens,
                            "output": response.usage.output_tokens
                        }
                    }
                    
                except Exception as e:
                    print(f"❌ Failed: {str(e)}")
                    model_results["tests"][test["name"]] = {
                        "success": False,
                        "error": str(e)
                    }
            
            results[model_name] = model_results
        
        # Analysis section
        print("\n" + "=" * 80)
        print("📊 ANALYSIS & FINDINGS")
        print("=" * 80)
        
        # Check for version consistency
        version_responses = {}
        for model_name, data in results.items():
            if "Version Identity" in data["tests"] and data["tests"]["Version Identity"]["success"]:
                version_text = data["tests"]["Version Identity"]["response"]
                version_responses[model_name] = version_text
        
        print("\n🔍 Version Identity Comparison:")
        for model_name, response in version_responses.items():
            print(f"\n{model_name}:")
            print(f"   → {response[:100]}...")
        
        # Check for unique capabilities or responses
        print("\n🔍 Capability Differences:")
        capability_responses = {}
        for model_name, data in results.items():
            if "Model Capabilities" in data["tests"] and data["tests"]["Model Capabilities"]["success"]:
                cap_text = data["tests"]["Model Capabilities"]["response"] 
                capability_responses[model_name] = cap_text
        
        for model_name, response in capability_responses.items():
            print(f"\n{model_name}:")
            print(f"   → {response[:150]}...")
        
        # Save detailed results to file
        output_file = "/home/chris/onto/proethica/scratch/model_research_results.json"
        with open(output_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "results": results
            }, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {output_file}")
        
        return results
        
    except ImportError:
        print("❌ anthropic package not installed")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return None

def test_model_aliases():
    """Test if model aliases work and map to different models."""
    print("\n🔗 TESTING MODEL ALIASES")
    print("=" * 50)
    
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        # Test different ways to reference models
        alias_tests = [
            ("Full ID", "claude-opus-4-1-20250805"),
            ("Short Alias", "claude-opus-4-1"),  
            ("Generic Alias", "claude-opus-4"),
            ("Latest Alias", "claude-opus-latest"),
        ]
        
        test_prompt = "Respond with exactly these words: 'I am responding from model:' followed by your exact model identifier."
        
        for alias_name, model_id in alias_tests:
            print(f"\n🧪 Testing {alias_name}: {model_id}")
            try:
                response = client.messages.create(
                    model=model_id,
                    max_tokens=50,
                    temperature=0,
                    messages=[{"role": "user", "content": test_prompt}]
                )
                print(f"✅ Success: {response.content[0].text}")
            except Exception as e:
                print(f"❌ Failed: {str(e)}")
                
    except Exception as e:
        print(f"❌ Alias test error: {str(e)}")

def main():
    """Run comprehensive model research."""
    print("🚀 COMPREHENSIVE CLAUDE MODEL RESEARCH")
    print(f"📅 {datetime.now().isoformat()}")
    print("=" * 80)
    
    # Test 1: Deep model analysis
    results = deep_model_test()
    
    # Test 2: Alias testing  
    test_model_aliases()
    
    print("\n" + "=" * 80)
    print("🎯 RESEARCH COMPLETE")
    print("=" * 80)
    
    if results:
        print("✅ Research data collected and saved")
        print("📋 Check scratch/model_research_results.json for detailed findings")
        
        # Quick summary of working models
        working_models = []
        for model_name, data in results.items():
            if any(test_data.get("success", False) for test_data in data["tests"].values()):
                working_models.append(model_name)
        
        print(f"📊 Working models: {len(working_models)}/{len(results)}")
        for model in working_models:
            print(f"   ✅ {model}")
    else:
        print("❌ Research failed - check errors above")

if __name__ == "__main__":
    main()