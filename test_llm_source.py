#!/usr/bin/env python3
"""
Test script to identify the source of military medical triage content in predictions.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.experiment.prediction_service import PredictionService
from app.services.llm_service import LLMService
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_llm_sources():
    """Test what type of LLM is being used by different services."""
    
    print("=== Testing LLM Sources ===")
    
    # Test 1: Direct LLMService
    print("\n1. Testing direct LLMService:")
    llm_service = LLMService()
    print(f"   LLM type: {type(llm_service.llm)}")
    print(f"   Model name: {llm_service.model_name}")
    
    # Test 2: PredictionService LLM
    print("\n2. Testing PredictionService LLM:")
    prediction_service = PredictionService()
    print(f"   LLM type: {type(prediction_service.llm_service.llm)}")
    print(f"   Model name: {prediction_service.llm_service.model_name}")
    
    # Test 3: Check environment variables
    print("\n3. Environment variables:")
    print(f"   USE_MOCK_GUIDELINE_RESPONSES: {os.environ.get('USE_MOCK_GUIDELINE_RESPONSES')}")
    print(f"   ANTHROPIC_API_KEY exists: {'ANTHROPIC_API_KEY' in os.environ}")
    print(f"   OPENAI_API_KEY exists: {'OPENAI_API_KEY' in os.environ}")
    print(f"   ANTHROPIC_MODEL: {os.environ.get('ANTHROPIC_MODEL')}")
    
    # Test 4: Simple LLM call
    print("\n4. Testing simple LLM call:")
    try:
        response = prediction_service.llm_service.llm.invoke("Tell me about engineering ethics")
        print(f"   Response: {response[:200]}...")
        
        # Check if response contains military content
        military_keywords = ['military', 'medical', 'triage', 'patient', 'allocating', 'limited resources']
        found_keywords = [kw for kw in military_keywords if kw.lower() in str(response).lower()]
        if found_keywords:
            print(f"   ⚠️  FOUND MILITARY KEYWORDS: {found_keywords}")
        else:
            print(f"   ✓ No military keywords found")
            
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    test_llm_sources()
