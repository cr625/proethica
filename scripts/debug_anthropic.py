#!/usr/bin/env python3
"""
Debug script for Anthropic API authentication issues
"""
import os
import sys
import traceback
from dotenv import load_dotenv
from anthropic import Anthropic

def test_anthropic_client():
    """Test the Anthropic client with the current API key"""
    # Load environment variables from .env file
    load_dotenv()
    
    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: No ANTHROPIC_API_KEY found in environment variables")
        return False
        
    print(f"Found API key: {api_key[:7]}...{api_key[-5:]}")
    print(f"API key length: {len(api_key)} characters")
    
    # Check API key format
    if not api_key.startswith("sk-ant-"):
        print("WARNING: API key doesn't follow the expected format (should start with 'sk-ant-')")
    
    # Try to initialize the Anthropic client
    try:
        print("\nInitializing Anthropic client...")
        client = Anthropic(api_key=api_key)
        print("Client initialization successful")
        
        # Try to list models (simple API call)
        print("\nListing available models...")
        models = client.models.list()
        print(f"Success! Available models: {[model.id for model in models.data]}")
        return True
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        print("\nDetailed error information:")
        traceback.print_exc()
        
        print("\nPossible solutions:")
        print("1. Verify that your API key is valid and has not expired")
        print("2. Check if you have the correct permissions for your API key")
        print("3. Ensure you can connect to Anthropic's API servers")
        print("4. Try regenerating your API key in the Anthropic console")
        print("5. Check if your account has an active subscription")
        return False

def test_with_fallback():
    """Test with fallback modes enabled"""
    # Check USE_MOCK_FALLBACK setting
    use_mock = os.environ.get("USE_MOCK_FALLBACK", "").lower() == "true"
    print(f"\nUSE_MOCK_FALLBACK is set to: {use_mock}")
    
    if use_mock:
        print("The system should fall back to mock responses when API calls fail.")
        print("You can still use the system even with an invalid API key.")
    else:
        print("Consider setting USE_MOCK_FALLBACK=true in your .env file")
        print("This will allow the system to function with mock responses when API calls fail.")

if __name__ == "__main__":
    print("===== Anthropic API Debug Tool =====")
    success = test_anthropic_client()
    
    if not success:
        test_with_fallback()
        print("\nYou can also try:")
        print("1. Using a different API key")
        print("2. Making sure the application exports environment variables properly")
        print("3. Running the application with the auto_run.sh script, which ensures environment variables are loaded")
