#!/usr/bin/env python3
"""
Verify that the Anthropic API authentication has been fixed
This script uses run_with_env.sh to ensure proper environment variable handling
"""

import os
import sys
import time
from dotenv import load_dotenv
from anthropic import Anthropic

def print_header(title):
    """Print a section header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def main():
    # First, try loading from .env file
    load_dotenv()
    
    # Get API key from environment
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY is not set in the environment")
        return False
        
    # Mask API key for security
    masked_key = api_key[:8] + "*" * (len(api_key) - 13) + api_key[-5:]
    print(f"Using API key: {masked_key}")
    
    # Check API key format
    if not api_key.startswith("sk-ant-"):
        print("⚠️ WARNING: API key doesn't follow the expected format (should start with 'sk-ant-')")
    
    try:
        # Initialize the Anthropic client
        print("Initializing Anthropic client...")
        client = Anthropic(api_key=api_key)
        
        # Try to send a simple message
        print("Sending a test message to Claude...")
        
        start_time = time.time()
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=100,
            messages=[
                {"role": "user", "content": "If you can read this message, it means the API authentication is working. Please respond with just 'Authentication successful'."}
            ],
            system="Respond with only 'Authentication successful' if you can read this message."
        )
        end_time = time.time()
        
        # Check the response
        content = response.content[0].text.strip()
        print(f"Response received in {end_time - start_time:.2f} seconds")
        print(f"Response: {content}")
        
        if "authentication successful" in content.lower():
            print_header("✅ API Authentication is Working!")
            print("The fix has been successfully applied.")
            return True
        else:
            print("⚠️ Warning: Received response but not the expected 'Authentication successful' message.")
            print(f"Actual response: {content}")
            print("This might indicate Claude received the message but didn't follow instructions,")
            print("but the API itself seems to be working.")
            return True
    
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        print_header("The API authentication fix is NOT working")
        print("""
Recommendations:
1. Check that USE_MOCK_FALLBACK=false in .env file
2. Check that the ANTHROPIC_API_KEY in the .env file is valid
3. Make sure you're running this script with run_with_env.sh
4. Try regenerating your API key at console.anthropic.com
        """)
        return False

if __name__ == "__main__":
    print_header("Anthropic API Authentication Verification")
    main()
