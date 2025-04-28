#!/usr/bin/env python3
"""
Test script to verify the fixes for Anthropic API authentication
"""
import os
import sys
import time
from dotenv import load_dotenv

# First, load environment variables from .env file
load_dotenv()

# Second, explicitly print API key info to verify it's being loaded
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("ERROR: No ANTHROPIC_API_KEY found in environment variables")
    sys.exit(1)

print(f"Found API key: {api_key[:7]}...{api_key[-5:]}")
print(f"API key length: {len(api_key)} characters")

# Third, directly set the API key in the environment 
# (ensuring it's properly set for the Anthropic SDK)
os.environ["ANTHROPIC_API_KEY"] = api_key
print(f"Explicitly set ANTHROPIC_API_KEY in environment")

# Fourth, try to import and use the Anthropic SDK directly
try:
    print("\nImporting Anthropic SDK...")
    from anthropic import Anthropic
    print("Anthropic SDK import successful")
    
    print("\nInitializing Anthropic client...")
    # Initialize the client with the API key explicitly passed
    client = Anthropic(api_key=api_key)
    print("Anthropic client initialized successfully")
    
    print("\nTesting models listing API...")
    models = client.models.list()
    print(f"Available models: {[model.id for model in models.data]}")
    
    print("\nTesting basic conversation with Claude...")
    # Send a simple message and time the response
    start_time = time.time()
    print("Sending message to Claude...")
    message = "Hello, please respond with a very short message to test authentication."
    
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=100,
        messages=[
            {"role": "user", "content": message}
        ],
        system="You are a helpful assistant. Keep your responses very brief."
    )
    end_time = time.time()
    
    # Print the response
    print(f"\nResponse received in {end_time - start_time:.2f} seconds:")
    print(f"Message: {response.content[0].text}")
    print("\nAuthentication test PASSED! ✅")
    
except Exception as e:
    print(f"\nERROR: {str(e)}")
    print("Authentication test FAILED! ❌")
    print("\nDetailed error information:")
    import traceback
    traceback.print_exc()
    
    print("\nPossible solutions:")
    print("1. Check if your API key is valid in the .env file")
    print("2. Try running with auto_run.sh script: ./auto_run.sh python scripts/verify_anthropic_fix.py")
    print("3. Directly export the API key: export ANTHROPIC_API_KEY=your-key && python scripts/verify_anthropic_fix.py")
