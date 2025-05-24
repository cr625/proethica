#!/usr/bin/env python3
"""
Test script to verify the Anthropic SDK integration with v0.51.0.
"""

import os
import sys
import json
from pathlib import Path

# Set up paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("===============================================")
print("Testing Anthropic API Integration")
print("===============================================")

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded environment variables from .env")
except ImportError:
    print("⚠️ python-dotenv not installed, skipping .env loading")
    
# Check for API key
api_key = os.environ.get('ANTHROPIC_API_KEY')
if not api_key:
    print("❌ ANTHROPIC_API_KEY not found in environment variables")
    print("Make sure to add your API key to the .env file")
    sys.exit(1)
else:
    print("✅ Found ANTHROPIC_API_KEY in environment variables")

# Test direct Anthropic SDK import and client creation
try:
    import anthropic
    print(f"✅ Successfully imported anthropic module v{anthropic.__version__}")
    
    # Create a client
    client = anthropic.Anthropic(api_key=api_key)
    print("✅ Successfully created Anthropic client")
    
    # Check client attributes
    if hasattr(client, 'messages') and hasattr(client.messages, 'create'):
        print("✅ Client has messages.create capability (v0.5x.x API)")
    elif hasattr(client, 'completion'):
        print("✅ Client has completion capability (old API)")
    else:
        print("❌ Client missing expected capabilities")
    
    # Test a simple API call
    print("\nTesting simple API call...")
    try:
        # Using messages API (v0.5x.x)
        if hasattr(client, 'messages') and hasattr(client.messages, 'create'):
            response = client.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=20,
                messages=[
                    {"role": "user", "content": "Say hello world very briefly"}
                ]
            )
            
            # Check response structure
            if hasattr(response, 'content'):
                if isinstance(response.content, list) and len(response.content) > 0:
                    print(f"API Response: {response.content[0].text}")
                    print("✅ Successfully received API response with content list structure")
                else:
                    print(f"API Response: {response.content}")
                    print("✅ Successfully received API response with content attribute")
            else:
                print("❓ Response has unexpected structure:", response)
        
        # Using older API (unlikely with v0.51.0)
        elif hasattr(client, 'completion'):
            response = client.completion(
                prompt="\n\nHuman: Say hello world\n\nAssistant:",
                model="claude-2.0",
                max_tokens_to_sample=20
            )
            print(f"API Response: {response.completion}")
            print("✅ Successfully received API response")
    
    except Exception as e:
        print(f"❌ API call failed: {str(e)}")

except ImportError as e:
    print(f"❌ Failed to import anthropic module: {str(e)}")
except Exception as e:
    print(f"❌ Error testing anthropic module: {str(e)}")

# Try to import application's LLM utils
print("\nTesting application's LLM utilities...")
try:
    # Set Flask environment variables
    os.environ['FLASK_APP'] = 'run.py'
    os.environ['FLASK_ENV'] = 'development'
    
    # Import the LLM utils directly (without Flask context)
    from app.utils.llm_utils import get_llm_client, LLMUtilsConfig
    
    print("✅ Successfully imported app.utils.llm_utils")
    print(f"Current LLMUtilsConfig settings: {vars(LLMUtilsConfig)}")
    
    # Try to create a test client without Flask (may fail but gives useful debug info)
    try:
        client = get_llm_client()
        print("✅ Successfully created LLM client using get_llm_client()")
        print(f"Client type: {type(client).__name__}")
    except Exception as e:
        print(f"⚠️ Could not create client with get_llm_client(): {str(e)}")
        print("   This is expected if database access is needed - full Flask context required")

except ImportError as e:
    print(f"⚠️ Could not import app.utils.llm_utils: {str(e)}")
except Exception as e:
    print(f"⚠️ Error testing LLM utils: {str(e)}")

print("\n===============================================")
print("Test complete!")
print("===============================================")
