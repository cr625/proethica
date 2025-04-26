#!/usr/bin/env python3
"""
Script to verify the diff function works correctly when accessing the endpoint directly.
"""
import requests
import sys
import json

def verify_diff():
    """
    Test the diff endpoint directly by making HTTP requests.
    """
    base_url = "http://localhost:3333"
    api_url = f"{base_url}/ontology-editor/api/versions/1/diff"
    
    print("Verifying diff endpoint...")
    print(f"URL: {api_url}")
    
    # Test cases to run
    test_cases = [
        # Same version test
        {"from": "1", "to": "1", "format": "unified", "name": "Same Version Test"},
        # Unified format test
        {"from": "1", "to": "2", "format": "unified", "name": "Unified Format (1→2)"},
        # Split format test
        {"from": "1", "to": "2", "format": "split", "name": "Split Format (1→2)"},
        # Latest versions test
        {"from": "1", "format": "unified", "name": "Latest Version Test"}
    ]
    
    # Try to connect to the server
    try:
        response = requests.get(f"{base_url}/ontology-editor/api", timeout=2)
        if response.status_code != 200:
            print(f"Warning: Server returned status code {response.status_code}")
            print("The server may not be running.")
            return False
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Is it running?")
        print(f"Please start the server with './start_proethica.sh' and then try again.")
        return False
    except requests.exceptions.Timeout:
        print("Error: Connection to server timed out.")
        return False
    
    # Run all test cases
    success = True
    for test in test_cases:
        print(f"\n--- Running Test: {test['name']} ---")
        test_params = {k: v for k, v in test.items() if k != 'name'}
        print(f"Parameters: {test_params}")
        
        try:
            response = requests.get(api_url, params=test_params, timeout=5)
            print(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check response structure
                required_keys = ['diff', 'format', 'from_version', 'to_version']
                missing_keys = [key for key in required_keys if key not in data]
                
                if missing_keys:
                    print(f"Error: Missing required keys in response: {missing_keys}")
                    print("Response structure:", json.dumps({k: "..." for k in data.keys()}, indent=2))
                    success = False
                else:
                    # Print basic info
                    print("Success!")
                    print(f"From version: {data['from_version']['number']}")
                    if 'to_version' in data and data['to_version']:
                        print(f"To version: {data['to_version']['number']}")
                    print(f"Format: {data['format']}")
                    print(f"Diff size: {len(data['diff'])} chars")
                    
                    # For unified format, print the first few lines
                    if data['format'] == 'unified' and isinstance(data['diff'], str) and len(data['diff']) > 0:
                        lines = data['diff'].split('\n')[:5]  # First 5 lines
                        if len(lines) > 0:
                            print("\nDiff sample:")
                            for line in lines:
                                print(f"  {line}")
            else:
                print("Error response:", response.text)
                success = False
        except Exception as e:
            print(f"Exception during test: {str(e)}")
            success = False
    
    print("\n--- Summary ---")
    if success:
        print("✅ All tests passed! The diff endpoint is working correctly.")
        return True
    else:
        print("❌ Some tests failed. Check the error messages above.")
        return False

if __name__ == "__main__":
    if verify_diff():
        sys.exit(0)
    else:
        sys.exit(1)
