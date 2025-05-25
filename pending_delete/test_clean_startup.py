#!/usr/bin/env python3
"""
Test script to see clean startup output
"""

import os
from app import create_app

# Set environment (without DEBUG to show clean output)
os.environ['ENVIRONMENT'] = 'development'
os.environ['MCP_SERVER_URL'] = 'https://mcp.proethica.org'
os.environ['MCP_AUTH_TOKEN'] = 'test-token'

print("🧪 Testing clean startup (normal mode)...")
print("=" * 50)

# Create app (should be quiet)
app = create_app('config')

print("✅ App created successfully with minimal output!")
print()
print("🔍 Testing with DEBUG=true...")
print("=" * 50)

# Now test with debug mode
os.environ['DEBUG'] = 'true'
app_debug = create_app('config')

print("✅ Debug mode shows detailed information!")