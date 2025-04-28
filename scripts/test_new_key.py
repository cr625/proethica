#!/usr/bin/env python3
"""
Temporary script to test the new Anthropic API key.
"""
import sys
import time
from anthropic import Anthropic

def test_key(api_key):
    """Test the provided API key with Anthropic API"""
    print(f"Testing new API key: {api_key[:8]}...{api_key[-5:]}")
    
    try:
        # Create Anthropic client with the key
        client = Anthropic(api_key=api_key)
        print("✅ Client initialized successfully")
        
        # Test listing models
        print("\nListing available models...")
        models = client.models.list()
        print(f"✅ Available models: {[model.id for model in models.data]}")
        
        # Test messaging API
        print("\nSending a test message...")
        start_time = time.time()
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Reply with exactly 7 words to confirm you're working."}
            ],
            system="Be extremely brief."
        )
        end_time = time.time()
        
        print(f"✅ Response received in {end_time - start_time:.2f} seconds")
        print(f"Response: {response.content[0].text}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please provide an API key as the first argument")
        sys.exit(1)
        
    api_key = sys.argv[1]
    success = test_key(api_key)
    
    if success:
        print("\n🎉 API key works correctly!")
        print("You can now update your .env file with this key")
    else:
        print("\n❌ API key test failed")
