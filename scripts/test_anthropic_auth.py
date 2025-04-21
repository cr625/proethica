#!/usr/bin/env python3
"""
A simplified script to test Anthropic API authentication using current best practices.
"""

import os
import requests
import json
from dotenv import load_dotenv

def main():
    # Load environment variables
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("Error: No API key found. Please set ANTHROPIC_API_KEY in your .env file.")
        return
    
    print(f"Using API key: {api_key[:5]}...{api_key[-5:]}")
    
    # Test with x-api-key header (older method)
    headers_old = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }
    
    # Test with Authorization header (newer method)
    headers_new = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "anthropic-version": "2023-06-01"
    }
    
    # Test with both newer Anthropic API versions
    versions = ["2023-06-01", "2023-01-01"]
    headers_combinations = []
    
    for version in versions:
        headers_combinations.append({
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": version
        })
        
        headers_combinations.append({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "anthropic-version": version
        })
    
    # Test all combinations
    for i, headers in enumerate(headers_combinations):
        version = headers.get("anthropic-version")
        auth_type = "Authorization: Bearer" if "Authorization" in headers else "x-api-key"
        print(f"\nTrying combination {i+1}: {auth_type} with API version {version}")
        
        try:
            response = requests.get(
                "https://api.anthropic.com/v1/models",
                headers=headers,
                timeout=10
            )
            
            print(f"Status code: {response.status_code}")
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model.get("name", "Unknown") for model in models]
                print(f"Success! Available models: {', '.join(model_names)}")
                print(f"Working header configuration: {headers}")
                return
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Request failed: {str(e)}")
    
    print("\nAll authentication methods failed. Suggestions:")
    print("1. Verify that your API key is valid and hasn't expired")
    print("2. Check if you have proper network connectivity to api.anthropic.com")
    print("3. Ensure you have a proper Anthropic subscription with API access")
    print("4. If you're on a corporate network, check if there are any firewall restrictions")

if __name__ == "__main__":
    main()
