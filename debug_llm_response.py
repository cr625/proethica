#!/usr/bin/env python3
"""
Debug the LLM response format to fix JSON parsing.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.llm_service import LLMService
import json
import re

def test_llm_response():
    """Test what Claude actually returns for annotation prompts."""
    print("🔬 Testing Claude LLM response format...")
    
    llm_service = LLMService()
    
    # Simple test prompt
    test_prompt = """You are an expert in professional ethics. Identify text segments that match ethical concepts.

DOCUMENT CONTENT:
Engineers must hold paramount the safety, health, and welfare of the public.

AVAILABLE CONCEPTS:
[
  {
    "uri": "http://proethica.org/ontology/core#Obligation",
    "label": "Obligation", 
    "definition": "Required actions or behaviors in professional contexts",
    "type": "class"
  }
]

Return your response as a JSON array:

[
    {
        "text_segment": "exact text from document",
        "concept_uri": "http://...",
        "concept_label": "concept name",
        "confidence": 0.85,
        "reasoning": "brief explanation"
    }
]"""

    print("📤 Sending test prompt to Claude...")
    result = llm_service.generate_response(test_prompt)
    
    print("📥 Claude response received:")
    print("Type:", type(result))
    print("Keys:", list(result.keys()) if isinstance(result, dict) else "Not a dict")
    
    if isinstance(result, dict) and 'analysis' in result:
        analysis = result['analysis']
        print("\n📄 Analysis content:")
        print("Length:", len(analysis))
        print("First 200 chars:", repr(analysis[:200]))
        print("Last 200 chars:", repr(analysis[-200:]))
        
        # Test JSON extraction
        print("\n🔍 Testing JSON extraction...")
        json_match = re.search(r'\[.*\]', analysis, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            print("✅ Found JSON array")
            print("JSON length:", len(json_str))
            print("JSON preview:", json_str[:200] + "..." if len(json_str) > 200 else json_str)
            
            try:
                parsed = json.loads(json_str)
                print("✅ JSON parsed successfully")
                print("Number of items:", len(parsed))
                if parsed:
                    print("First item:", parsed[0])
            except json.JSONDecodeError as e:
                print("❌ JSON parsing failed:", e)
                print("Problematic JSON:", repr(json_str[:100]))
        else:
            print("❌ No JSON array found")
            print("Looking for other patterns...")
            
            # Try different patterns
            patterns = [
                r'\[\s*{.*?}\s*\]',
                r'```json\s*(\[.*?\])\s*```',
                r'```\s*(\[.*?\])\s*```'
            ]
            
            for i, pattern in enumerate(patterns):
                match = re.search(pattern, analysis, re.DOTALL)
                if match:
                    print(f"✅ Found match with pattern {i+1}")
                    json_str = match.group(1) if match.groups() else match.group(0)
                    print("Content:", repr(json_str[:100]))
                    break
            else:
                print("❌ No JSON patterns found")

if __name__ == "__main__":
    test_llm_response()
