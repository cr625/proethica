#!/usr/bin/env python3
"""
Test script for Anthropic API authentication using Bearer token method
"""

import os
import sys
import time
import json
import requests
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

def print_header(title):
    """Print a section header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def test_with_bearer_token():
    """Test API directly using Authorization Bearer token"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY environment variable is not set")
        return False
        
    # Mask most of the API key for security
    masked_key = api_key[:8] + "*" * (len(api_key) - 13) + api_key[-5:]
    print(f"Using API key: {masked_key}")
    print(f"API key length: {len(api_key)} characters")
    
    # Check API key format
    if not api_key.startswith("sk-ant-"):
        print("⚠️ WARNING: API key doesn't follow the expected format (should start with 'sk-ant-')")
    
    print_header("Testing Anthropic API with Bearer Token")
    
    # Try both new and old authentication methods
    auth_methods = [
        {"name": "Bearer token", "header": {"Authorization": f"Bearer {api_key}"}},
        {"name": "x-api-key", "header": {"x-api-key": api_key}}
    ]
    
    # Try both API versions
    api_versions = ["2023-06-01", "2023-01-01"]
    
    # Try with different models endpoint
    for auth in auth_methods:
        for version in api_versions:
            print(f"\nTrying with {auth['name']} and API version {version}")
            
            headers = {
                "Content-Type": "application/json",
                "anthropic-version": version,
                **auth["header"]
            }
            
            try:
                # First, check models endpoint
                print("Testing models endpoint...")
                response = requests.get(
                    "https://api.anthropic.com/v1/models",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    print(f"✅ Models API success! Status code: {response.status_code}")
                    models = response.json().get("models", [])
                    model_names = [model.get("name", "Unknown") for model in models]
                    print(f"Available models: {', '.join(model_names)}")
                    
                    # Now test messages API
                    print("\nTesting messages endpoint...")
                    
                    payload = {
                        "model": "claude-3-opus-20240229",
                        "max_tokens": 50,
                        "messages": [
                            {"role": "user", "content": "Say hello in exactly 5 words."}
                        ],
                        "system": "Be extremely brief."
                    }
                    
                    msg_response = requests.post(
                        "https://api.anthropic.com/v1/messages",
                        headers=headers,
                        json=payload,
                        timeout=15
                    )
                    
                    if msg_response.status_code == 200:
                        msg_data = msg_response.json()
                        print(f"✅ Messages API success! Status code: {msg_response.status_code}")
                        print(f"Response: {msg_data.get('content', [{'text': 'No content'}])[0]['text']}")
                        
                        print("\n🎉 WORKING CONFIGURATION FOUND:")
                        print(f"Authentication method: {auth['name']}")
                        print(f"API version: {version}")
                        print(f"Headers: {json.dumps(headers)}")
                        
                        # Save the working configuration
                        with open("scripts/working_anthropic_config.json", "w") as f:
                            config = {
                                "auth_method": auth["name"],
                                "api_version": version,
                                "headers": headers
                            }
                            # Remove actual API key before saving
                            if "Authorization" in config["headers"]:
                                config["headers"]["Authorization"] = "Bearer YOUR_API_KEY"
                            if "x-api-key" in config["headers"]:
                                config["headers"]["x-api-key"] = "YOUR_API_KEY"
                            
                            json.dump(config, f, indent=2)
                            print("Configuration saved to scripts/working_anthropic_config.json")
                        
                        return True
                    else:
                        print(f"❌ Messages API failed with status code: {msg_response.status_code}")
                        print(f"Error: {msg_response.text}")
                else:
                    print(f"❌ Models API failed with status code: {response.status_code}")
                    print(f"Error: {response.text}")
                    
            except Exception as e:
                print(f"❌ Request failed: {str(e)}")
    
    return False

def main():
    """Main function"""
    print_header("Anthropic API Direct Authentication Test")
    
    # Get the API key from command line if provided
    if len(sys.argv) > 1:
        os.environ["ANTHROPIC_API_KEY"] = sys.argv[1]
        print("Using API key from command line argument")
    
    # Test with bearer token
    if test_with_bearer_token():
        print_header("🎉 Authentication test successful!")
    else:
        print_header("❌ Authentication test failed!")
        print("""
Recommendations:
1. The API key may be invalid or expired
2. Try generating a new API key from the Anthropic console
3. Check if you have API access with your current subscription
4. Run this script with your API key as an argument: 
   python scripts/try_anthropic_bearer.py sk-ant-your-key-here
5. If issues persist, set USE_MOCK_FALLBACK=true in your .env file
6. Contact Anthropic support if you believe your account should have API access
        """)

if __name__ == "__main__":
    main()
