#!/usr/bin/env python3
"""
Test script to check MCP server responses for military medical content.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.mcp_client import MCPClient
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_mcp_responses():
    """Test MCP server responses for military medical content."""
    
    print("=== Testing MCP Server Responses ===")
    
    # Test MCP client
    try:
        mcp_client = MCPClient.get_instance()
        print(f"MCP Server URL: {mcp_client.mcp_server_url}")
        
        # Test 1: Get guidelines for engineering ethics
        print("\n1. Testing engineering ethics guidelines:")
        guidelines = mcp_client.get_guidelines("engineering-ethics")
        print(f"   Guidelines response: {str(guidelines)[:300]}...")
        
        # Check for military content
        military_keywords = ['military', 'medical', 'triage', 'patient', 'allocating', 'limited resources']
        found_keywords = [kw for kw in military_keywords if kw.lower() in str(guidelines).lower()]
        if found_keywords:
            print(f"   ⚠️  FOUND MILITARY KEYWORDS: {found_keywords}")
        else:
            print(f"   ✓ No military keywords found")
        
        # Test 2: Get mock guidelines
        print("\n2. Testing mock guidelines:")
        mock_guidelines = mcp_client.get_mock_guidelines("engineering-ethics")
        print(f"   Mock guidelines response: {str(mock_guidelines)[:300]}...")
        
        found_keywords_mock = [kw for kw in military_keywords if kw.lower() in str(mock_guidelines).lower()]
        if found_keywords_mock:
            print(f"   ⚠️  FOUND MILITARY KEYWORDS IN MOCK: {found_keywords_mock}")
        else:
            print(f"   ✓ No military keywords found in mock")
            
        # Test 3: Get entities
        print("\n3. Testing entities:")
        entities = mcp_client.get_world_entities("nspe")
        print(f"   Entities response: {str(entities)[:300]}...")
        
        found_keywords_entities = [kw for kw in military_keywords if kw.lower() in str(entities).lower()]
        if found_keywords_entities:
            print(f"   ⚠️  FOUND MILITARY KEYWORDS IN ENTITIES: {found_keywords_entities}")
        else:
            print(f"   ✓ No military keywords found in entities")
            
    except Exception as e:
        print(f"Error testing MCP responses: {e}")

if __name__ == "__main__":
    test_mcp_responses()
