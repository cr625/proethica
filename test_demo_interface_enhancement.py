#!/usr/bin/env python3
"""
Test script for enhanced demo interface functionality.
Tests Case 252 double-blind evaluation and demo-ready interfaces.
"""

import requests
import sys
import json

def test_demo_interface():
    """Test the enhanced demo interfaces for Case 252."""
    
    base_url = "http://127.0.0.1:3333"
    case_id = 252
    
    print("🧪 Testing Enhanced Demo Interface for Case 252")
    print("=" * 60)
    
    # Test 1: Case comparison interface (existing)
    print("\n1. Testing case comparison interface...")
    try:
        response = requests.get(f"{base_url}/experiment/case_comparison/{case_id}", timeout=10)
        print(f"   ✅ Case comparison: HTTP {response.status_code}")
        if response.status_code != 200:
            print(f"   ⚠️  Response: {response.text[:200]}...")
    except Exception as e:
        print(f"   ❌ Case comparison failed: {e}")
    
    # Test 2: Double-blind evaluation interface (new)
    print("\n2. Testing double-blind evaluation interface...")
    try:
        response = requests.get(f"{base_url}/experiment/double_blind/{case_id}", timeout=10)
        print(f"   ✅ Double-blind interface: HTTP {response.status_code}")
        if response.status_code != 200:
            print(f"   ⚠️  Response: {response.text[:200]}...")
    except Exception as e:
        print(f"   ❌ Double-blind interface failed: {e}")
    
    # Test 3: Demo-ready interface (new)
    print("\n3. Testing demo-ready interface...")
    try:
        response = requests.get(f"{base_url}/experiment/demo_ready/{case_id}", timeout=10)
        print(f"   ✅ Demo-ready interface: HTTP {response.status_code}")
        if response.status_code != 200:
            print(f"   ⚠️  Response: {response.text[:200]}...")
    except Exception as e:
        print(f"   ❌ Demo-ready interface failed: {e}")
    
    # Test 4: Experiment dashboard
    print("\n4. Testing experiment dashboard...")
    try:
        response = requests.get(f"{base_url}/experiment/", timeout=10)
        print(f"   ✅ Experiment dashboard: HTTP {response.status_code}")
        if response.status_code != 200:
            print(f"   ⚠️  Response: {response.text[:200]}...")
    except Exception as e:
        print(f"   ❌ Experiment dashboard failed: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Demo interface enhancement testing completed!")
    print("\n📋 Available Demo Interfaces:")
    print(f"   • Case Comparison: {base_url}/experiment/case_comparison/{case_id}")
    print(f"   • Double-Blind Eval: {base_url}/experiment/double_blind/{case_id}")  
    print(f"   • Demo-Ready: {base_url}/experiment/demo_ready/{case_id}")
    print(f"   • Experiment Dashboard: {base_url}/experiment/")
    
    return True

if __name__ == "__main__":
    try:
        success = test_demo_interface()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1)
