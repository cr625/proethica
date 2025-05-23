#!/usr/bin/env python3
"""
Test script to verify that all military medical triage mock data has been replaced 
with engineering ethics content.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variables
os.environ['DATABASE_URL'] = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
os.environ['SQLALCHEMY_TRACK_MODIFICATIONS'] = "false"
os.environ['USE_MOCK_GUIDELINE_RESPONSES'] = "true"
os.environ['ENVIRONMENT'] = "development"

def test_llm_service_mock_responses():
    """Test that LLMService mock responses are engineering-focused."""
    
    print("🧪 Testing LLMService mock responses...")
    print("=" * 50)
    
    try:
        from app.services.llm_service import LLMService
        
        # Create LLM service (should use mock LLM)
        llm_service = LLMService()
        
        # Get the mock LLM responses
        mock_llm = llm_service.llm
        responses = mock_llm.responses
        
        print(f"Found {len(responses)} mock responses:")
        
        for i, response in enumerate(responses):
            print(f"\nResponse {i+1}:")
            print(f"Length: {len(response)} characters")
            print(f"Preview: {response[:100]}...")
            
            # Check for military/medical content
            military_keywords = ['military', 'medical', 'triage', 'patients', 'personnel must make']
            engineering_keywords = ['engineering', 'engineer', 'NSPE', 'design', 'professional']
            
            has_military = any(keyword.lower() in response.lower() for keyword in military_keywords)
            has_engineering = any(keyword.lower() in response.lower() for keyword in engineering_keywords)
            
            print(f"Contains military/medical terms: {'❌ YES' if has_military else '✅ NO'}")
            print(f"Contains engineering terms: {'✅ YES' if has_engineering else '❌ NO'}")
            
            if has_military:
                print(f"⚠️  ISSUE: Response {i+1} still contains military/medical content!")
                return False
            
            if not has_engineering:
                print(f"⚠️  WARNING: Response {i+1} doesn't mention engineering")
        
        print("\n✅ All LLMService mock responses are engineering-focused!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing LLMService: {e}")
        return False

def test_decision_engine_mock_responses():
    """Test that DecisionEngine mock responses are engineering-focused."""
    
    print("\n🧪 Testing DecisionEngine mock responses...")
    print("=" * 50)
    
    try:
        from app.services.decision_engine import DecisionEngine
        
        # Create decision engine (should use mock LLM)
        decision_engine = DecisionEngine()
        
        # Get the mock LLM responses
        mock_llm = decision_engine.llm
        responses = mock_llm.responses
        
        print(f"Found {len(responses)} mock responses:")
        
        for i, response in enumerate(responses):
            print(f"\nResponse {i+1}:")
            print(f"Length: {len(response)} characters")
            print(f"Preview: {response[:100]}...")
            
            # Check for military/medical content
            military_keywords = ['military', 'medical', 'triage', 'patients', 'personnel must make']
            engineering_keywords = ['engineering', 'engineer', 'NSPE', 'design', 'professional']
            
            has_military = any(keyword.lower() in response.lower() for keyword in military_keywords)
            has_engineering = any(keyword.lower() in response.lower() for keyword in engineering_keywords)
            
            print(f"Contains military/medical terms: {'❌ YES' if has_military else '✅ NO'}")
            print(f"Contains engineering terms: {'✅ YES' if has_engineering else '✅ YES' if has_engineering else '⚠️  NO'}")
            
            if has_military:
                print(f"⚠️  ISSUE: Response {i+1} still contains military/medical content!")
                return False
        
        print("\n✅ All DecisionEngine mock responses are engineering-focused!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing DecisionEngine: {e}")
        return False

def test_default_domain():
    """Test that default domain is now engineering-ethics."""
    
    print("\n🧪 Testing default domain logic...")
    print("=" * 50)
    
    try:
        from app.services.decision_engine import DecisionEngine
        
        decision_engine = DecisionEngine()
        
        # Test with empty scenario (should default to engineering-ethics)
        test_scenario = {}
        default_domain = decision_engine._get_domain_from_scenario(test_scenario)
        
        print(f"Default domain for empty scenario: {default_domain}")
        
        if default_domain == "engineering-ethics":
            print("✅ Default domain is correctly set to engineering-ethics!")
            return True
        else:
            print(f"❌ Default domain is {default_domain}, should be engineering-ethics!")
            return False
            
    except Exception as e:
        print(f"❌ Error testing default domain: {e}")
        return False

def test_case_252_simulation():
    """Simulate what Case 252 would see."""
    
    print("\n🧪 Simulating Case 252 response...")
    print("=" * 50)
    
    try:
        from app.services.llm_service import LLMService, Message, Conversation
        
        # Create LLM service
        llm_service = LLMService()
        
        # Simulate a Case 252 interaction
        conversation = Conversation()
        response = llm_service.send_message(
            "Tell me about this engineering ethics case involving design errors.",
            conversation=conversation
        )
        
        print(f"Mock response for Case 252 inquiry:")
        print(f"Content: {response.content}")
        
        # Check content
        military_keywords = ['military', 'medical', 'triage', 'patients', 'personnel must make']
        engineering_keywords = ['engineering', 'engineer', 'NSPE', 'design', 'professional']
        
        has_military = any(keyword.lower() in response.content.lower() for keyword in military_keywords)
        has_engineering = any(keyword.lower() in response.content.lower() for keyword in engineering_keywords)
        
        print(f"\nContent analysis:")
        print(f"Contains military/medical terms: {'❌ YES' if has_military else '✅ NO'}")
        print(f"Contains engineering terms: {'✅ YES' if has_engineering else '❌ NO'}")
        
        if has_military:
            print("❌ ISSUE: Case 252 would still see military content!")
            return False
        elif has_engineering:
            print("✅ Case 252 will see appropriate engineering ethics content!")
            return True
        else:
            print("⚠️  WARNING: Response doesn't mention engineering explicitly")
            return True
            
    except Exception as e:
        print(f"❌ Error simulating Case 252: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Testing comprehensive mock data fix...")
    print("=" * 60)
    
    all_tests_passed = True
    
    # Run all tests
    tests = [
        ("LLMService Mock Responses", test_llm_service_mock_responses),
        ("DecisionEngine Mock Responses", test_decision_engine_mock_responses), 
        ("Default Domain Logic", test_default_domain),
        ("Case 252 Simulation", test_case_252_simulation)
    ]
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        test_passed = test_func()
        if not test_passed:
            all_tests_passed = False
    
    print("=" * 60)
    if all_tests_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Military medical triage content has been successfully eliminated")
        print("✅ Engineering ethics content is now properly configured")
        print("✅ Case 252 should now show appropriate content")
    else:
        print("❌ SOME TESTS FAILED!")
        print("🔍 Review the output above to identify remaining issues")
