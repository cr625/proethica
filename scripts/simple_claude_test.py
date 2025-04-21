#!/usr/bin/env python3
"""
Minimal Claude API test using environment variables
"""
import os
import sys
from anthropic import Anthropic
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("Error: ANTHROPIC_API_KEY not found in environment")
    sys.exit(1)

print(f"Testing with API key: {api_key[:7]}...{api_key[-5:]}")

try:
    # Initialize the client
    client = Anthropic(api_key=api_key)
    print("Client initialized successfully")
    
    # Try to list models
    print("Attempting to list models...")
    models = client.models.list()
    print(f"Success! Models: {[model.id for model in models.data]}")
    sys.exit(0)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
