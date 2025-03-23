#!/usr/bin/env python3
"""
Test script to verify the MCPClient singleton pattern.
This script creates multiple instances of MCPClient and verifies that they are all the same instance.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.mcp_client import MCPClient

def test_singleton():
    """Test that MCPClient is a singleton."""
    print("Testing MCPClient singleton pattern...")
    
    # Create multiple instances
    client1 = MCPClient.get_instance()
    client2 = MCPClient.get_instance()
    client3 = MCPClient.get_instance()
    
    # Verify they are the same instance
    print(f"Client 1 ID: {id(client1)}")
    print(f"Client 2 ID: {id(client2)}")
    print(f"Client 3 ID: {id(client3)}")
    
    if id(client1) == id(client2) == id(client3):
        print("SUCCESS: All clients are the same instance!")
    else:
        print("FAILURE: Clients are different instances!")
    
    # Test that direct instantiation doesn't create a new instance
    direct_client = MCPClient()
    print(f"Direct client ID: {id(direct_client)}")
    
    if id(direct_client) != id(client1):
        print("WARNING: Direct instantiation creates a different instance!")
        print("Make sure to always use MCPClient.get_instance() instead of MCPClient()")
    else:
        print("Direct instantiation also returns the singleton instance.")

if __name__ == "__main__":
    test_singleton()
