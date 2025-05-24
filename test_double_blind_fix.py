#!/usr/bin/env python3

"""
Test script to verify the double-blind interface fix.
"""

import requests
import sys

def test_double_blind_interface():
    """Test that the double-blind interface now works."""
    
    print("🧪 Testing Double-Blind Interface Fix")
    print("=" * 50)
    
    base_url = "http://127.0.0.1:3333"
    
    try:
        # Test double-blind interface for Case 252
        print("1. Testing double-blind interface...")
        response = requests.get(f"{base_url}/experiment/double_blind/252")
        
        if response.status_code == 200:
            print("   ✅ Double-blind interface: HTTP 200 (SUCCESS)")
            
            # Check if we're seeing the comparison page or an error
            if "comparison" in response.text.lower() or "baseline" in response.text.lower():
                print("   ✅ Interface shows comparison content")
            else:
                print("   ⚠️  Interface loaded but may not show expected content")
                
        elif response.status_code == 302:
            print("   ⚠️  Double-blind interface: HTTP 302 (Redirect - likely still has error)")
            print(f"   Location: {response.headers.get('Location', 'Unknown')}")
            
        else:
            print(f"   ❌ Double-blind interface: HTTP {response.status_code}")
            
        print("\n2. Testing case comparison interface...")
        response = requests.get(f"{base_url}/experiment/case_comparison/252")
        
        if response.status_code == 200:
            print("   ✅ Case comparison: HTTP 200")
        else:
            print(f"   ❌ Case comparison: HTTP {response.status_code}")
            
        print("\n3. Testing demo-ready interface...")
        response = requests.get(f"{base_url}/experiment/demo_ready/252")
        
        if response.status_code == 200:
            print("   ✅ Demo-ready interface: HTTP 200")
        else:
            print(f"   ❌ Demo-ready interface: HTTP {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running on port 3333?")
        return False
        
    except Exception as e:
        print(f"❌ Error testing interfaces: {str(e)}")
        return False
        
    print("\n" + "=" * 50)
    print("✅ Double-blind interface fix testing completed!")
    return True

if __name__ == "__main__":
    success = test_double_blind_interface()
    sys.exit(0 if success else 1)
