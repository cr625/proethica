#!/usr/bin/env python
"""
Script to diagnose Claude API access and check if embeddings are available.
This will help determine if the embedding endpoint is available for your account
and what the correct endpoint URL should be.
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv

# Add the parent directory to the path so we can import the app if needed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def load_api_key():
    """Load API key from .env file or environment variables."""
    # Try loading from .env file first
    load_dotenv()
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ No ANTHROPIC_API_KEY found in environment variables or .env file")
        return None
        
    print(f"✅ Found ANTHROPIC_API_KEY: {api_key[:5]}...{api_key[-4:]}")
    return api_key

def check_basic_api_access(api_key):
    """Check if we can access the Claude API with the provided key."""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }
    
    base_url = "https://api.anthropic.com/v1"
    
    # Try to access the models endpoint which should be available
    try:
        response = requests.get(
            f"{base_url}/models",
            headers=headers
        )
        
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"✅ Successfully accessed Claude API")
            print(f"Available models: {', '.join(model.get('name', 'Unknown') for model in models)}")
            return True
        else:
            print(f"❌ Failed to access Claude API: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error accessing Claude API: {str(e)}")
        return False

def test_embedding_endpoints(api_key):
    """Test various possible embedding endpoints to find the correct one."""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
    }
    
    # Test text to embed
    data = {
        "model": "claude-3-embedding-3-0",  # The embedding model
        "input": "This is a test of the Claude embedding API"
    }
    
    # Possible endpoints to try
    endpoints = [
        {"url": "https://api.anthropic.com/v1/embeddings", "version": "2023-06-01"},
        {"url": "https://api.anthropic.com/v1/embeddings", "version": "2023-01-01"}, 
        {"url": "https://api.anthropic.com/v1/embeddings", "version": None},
        {"url": "https://api.anthropic.com/v1/embed", "version": "2023-06-01"},
        {"url": "https://api.anthropic.com/v1/vectors", "version": "2023-06-01"},
        {"url": "https://api.anthropic.com/v1/messages", "version": "2023-06-01", "embed": True}
    ]
    
    success = False
    
    for endpoint in endpoints:
        url = endpoint["url"]
        version = endpoint["version"]
        
        # Set the version header if provided
        current_headers = headers.copy()
        if version:
            current_headers["anthropic-version"] = version
        
        # Special case for messages endpoint which uses a different format
        current_data = data.copy()
        if endpoint.get("embed", False):
            current_data = {
                "model": "claude-3-sonnet-20240229",
                "messages": [{"role": "user", "content": data["input"]}],
                "max_tokens": 0,  # We only want the embedding, not a response
            }
        
        print(f"\nTrying endpoint: {url} (version: {version or 'None'})")
        
        try:
            response = requests.post(
                url,
                headers=current_headers,
                json=current_data
            )
            
            print(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Successful API call!")
                print(f"Response type: {type(response.json())}")
                
                # Check if we got what looks like an embedding
                if "embedding" in response.json():
                    embedding = response.json()["embedding"]
                    print(f"✅ Found embedding with {len(embedding)} dimensions")
                    print(f"Sample values: {embedding[:3]}...")
                    success = True
                elif "embeddings" in response.json():
                    embeddings = response.json()["embeddings"]
                    if embeddings and len(embeddings) > 0:
                        print(f"✅ Found embeddings with {len(embeddings[0])} dimensions")
                        print(f"Sample values: {embeddings[0][:3]}...")
                        success = True
                else:
                    print("❌ Response doesn't contain embedding data")
                    print(f"Keys in response: {list(response.json().keys())}")
            else:
                print(f"❌ API call failed: {response.text}")
                
                # Check for error message
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        print(f"Error type: {error_data['error'].get('type')}")
                        print(f"Error message: {error_data['error'].get('message')}")
                except:
                    pass
        except Exception as e:
            print(f"❌ Exception occurred: {str(e)}")
    
    return success

def check_account_features(api_key):
    """
    Check if embeddings are a feature enabled for the account.
    This is a guess since the API doesn't directly expose this information.
    """
    print("\nChecking account features...")
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }
    
    # Try to get account info (this may not be directly available)
    try:
        # Try a simple completion to check key validity and possibly get rate limit headers
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 10,
                "messages": [
                    {"role": "user", "content": "Hello, can you check if my API key has embeddings access?"}
                ]
            }
        )
        
        if response.status_code == 200:
            # Check response headers for any rate limit or usage info
            for header, value in response.headers.items():
                if "rate" in header.lower() or "limit" in header.lower() or "usage" in header.lower():
                    print(f"Header: {header}: {value}")
            
            # Check if there's any messaging about API access in the response
            response_data = response.json()
            if "content" in response_data and len(response_data["content"]) > 0:
                message = response_data["content"][0].get("text", "")
                if "embed" in message.lower() or "vector" in message.lower():
                    print(f"Response message contains embedding info: {message}")
        else:
            print(f"❌ Could not check account features: {response.status_code} {response.text}")
    except Exception as e:
        print(f"❌ Error checking account features: {str(e)}")

def main():
    """Main function to check Claude API access and embedding availability."""
    print("=== Claude API Diagnostic Tool ===\n")
    
    # Load API key
    api_key = load_api_key()
    if not api_key:
        print("\nPlease add your ANTHROPIC_API_KEY to the .env file or environment variables.")
        return 1
    
    # Check basic API access
    print("\nChecking basic API access...")
    if not check_basic_api_access(api_key):
        print("\nCannot proceed without basic API access. Please check your API key.")
        return 1
    
    # Test embedding endpoints
    print("\nTesting possible embedding endpoints...")
    embedding_available = test_embedding_endpoints(api_key)
    
    if not embedding_available:
        print("\nNo embedding endpoints were found to be working.")
        check_account_features(api_key)
        
        print("\nSuggestions:")
        print("1. Check if embeddings are enabled for your Claude API account/subscription")
        print("2. Check the Claude documentation for the latest embedding endpoint information")
        print("3. Contact Claude support to confirm if embeddings are available for your account")
        print("4. Consider using the local embedding model which is working correctly")
    else:
        print("\nEmbedding endpoints are working! Update your code to use the successful endpoint.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
