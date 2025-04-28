#!/usr/bin/env python3
"""
Test script for Anthropic API authentication using run_with_env.sh

This script should be run with:
./scripts/run_with_env.sh python scripts/test_claude_with_env.py
"""

import os
import sys
import time
import json
from dotenv import load_dotenv
from anthropic import Anthropic

def print_header(title):
    """Print a section header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def print_env_vars():
    """Print relevant environment variables"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY environment variable is not set")
        return False
        
    # Mask most of the API key for security
    masked_key = api_key[:8] + "*" * (len(api_key) - 13) + api_key[-5:]
    print(f"ANTHROPIC_API_KEY: {masked_key}")
    print(f"API key length: {len(api_key)} characters")
    print(f"USE_MOCK_FALLBACK: {os.environ.get('USE_MOCK_FALLBACK', 'Not set')}")
    print(f"ENVIRONMENT: {os.environ.get('ENVIRONMENT', 'Not set')}")
    
    # Check API key format
    if not api_key.startswith("sk-ant-"):
        print("⚠️ WARNING: API key doesn't follow the expected format (should start with 'sk-ant-')")
    
    return True

def test_anthropic_client():
    """Test the Anthropic client with the current environment"""
    # First, try to load from .env file as a backup
    load_dotenv()
    
    # Check environment variables
    if not print_env_vars():
        return False
    
    print_header("Testing Anthropic SDK Initialization")
    
    try:
        # Try to create the client
        print("Initializing Anthropic client...")
        # Explicitly pass API key and also ensure it's in environment
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = api_key
        
        client = Anthropic(api_key=api_key)
        print("✅ Client initialized successfully")
        
        # Test listing models
        print_header("Testing Models API")
        print("Fetching available models...")
        models = client.models.list()
        print(f"✅ Success! Available models: {[model.id for model in models.data]}")
        
        # Test a simple message API call
        print_header("Testing Messages API")
        print("Sending a simple message to Claude...")
        
        start_time = time.time()
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Please respond with a very brief message to confirm authentication is working."}
            ],
            system="Respond in 10 words or less."
        )
        end_time = time.time()
        
        print(f"✅ Success! Response received in {end_time - start_time:.2f} seconds")
        print(f"Response: {response.content[0].text}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return False

def main():
    """Main function"""
    print_header("Anthropic API Authentication Test")
    
    # Print environment information
    print(f"Python version: {sys.version}")
    print(f"Current working directory: {os.getcwd()}")
    
    # Test the client
    if test_anthropic_client():
        print_header("🎉 All tests passed! Authentication working correctly")
        print("""
Recommendations:
1. Make sure USE_MOCK_FALLBACK=false in .env file
2. Use the run_with_env.sh script to launch the application:
   ./scripts/run_with_env.sh python run.py
3. For any scripts that use Claude API, run them with:
   ./scripts/run_with_env.sh python your_script.py
        """)
    else:
        print_header("❌ Tests failed! Authentication not working correctly")
        print("""
Recommendations:
1. Check that the ANTHROPIC_API_KEY in your .env file is valid
2. Ensure you're using the Anthropic SDK correctly
3. Try regenerating a new API key at console.anthropic.com
4. Ensure proper environment variable export using run_with_env.sh
5. If issues persist, set USE_MOCK_FALLBACK=true in your .env file
        """)

if __name__ == "__main__":
    main()
