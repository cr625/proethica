#!/usr/bin/env python3
"""
Test script for MCP integration with Anthropic API
"""

import os
import anthropic
import requests
import json
from typing import Dict, Any

# Test configuration
MCP_URL = "https://mcp.proethica.org"
MCP_AUTH_TOKEN = "nGkmBr1jlyYLi8ZKCeXEFMMD5KddiCMzAahi7j5G43c"

def test_mcp_health():
    """Test MCP server health endpoint"""
    print("🔍 Testing MCP server health...")
    try:
        response = requests.get(f"{MCP_URL}/health", timeout=10)
        if response.status_code == 200:
            print("✅ MCP server is healthy")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_mcp_list_tools():
    """Test MCP server tool listing"""
    print("\n🔍 Testing MCP tool listing...")
    try:
        headers = {
            "Authorization": f"Bearer {MCP_AUTH_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "jsonrpc": "2.0",
            "method": "list_tools",
            "id": 1
        }
        
        response = requests.post(f"{MCP_URL}/jsonrpc", 
                               headers=headers, 
                               json=payload, 
                               timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Tool listing successful")
            if 'result' in result and 'tools' in result['result']:
                tools = result['result']['tools']
                print(f"   Found {len(tools)} tools:")
                for tool in tools[:3]:  # Show first 3 tools
                    print(f"   - {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")
                if len(tools) > 3:
                    print(f"   ... and {len(tools) - 3} more")
            return True
        else:
            print(f"❌ Tool listing failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Tool listing error: {e}")
        return False

def test_anthropic_api():
    """Test basic Anthropic API connectivity"""
    print("\n🔍 Testing Anthropic API connectivity...")
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in environment")
        return False
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        # Simple test without MCP
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": "Just say 'API test successful' and nothing else."
            }]
        )
        
        print("✅ Anthropic API is working")
        print(f"   Response: {response.content[0].text}")
        return True
        
    except Exception as e:
        print(f"❌ Anthropic API error: {e}")
        return False

def test_mcp_with_anthropic():
    """Test MCP integration with Anthropic API"""
    print("\n🔍 Testing MCP integration with Anthropic API...")
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in environment")
        return False
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        # Configure MCP server
        mcp_servers = [{
            "url": MCP_URL,
            "authorization_token": MCP_AUTH_TOKEN
        }]
        
        # Test MCP integration
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": "Can you list the available MCP tools and briefly describe what they do?"
            }],
            mcp_servers=mcp_servers,
            headers={"anthropic-beta": "mcp-client-2025-04-04"}
        )
        
        print("✅ MCP integration with Anthropic API successful!")
        print("📋 Claude's response about available tools:")
        print(f"   {response.content[0].text}")
        return True
        
    except Exception as e:
        print(f"❌ MCP integration error: {e}")
        return False

def test_ontology_query():
    """Test ontology querying through MCP"""
    print("\n🔍 Testing ontology query through MCP...")
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in environment")
        return False
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        mcp_servers = [{
            "url": MCP_URL,
            "authorization_token": MCP_AUTH_TOKEN
        }]
        
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=800,
            messages=[{
                "role": "user",
                "content": "Use the ProEthica ontology tools to find engineering ethics roles and principles. Show me what entities are available in the engineering ethics domain."
            }],
            mcp_servers=mcp_servers,
            headers={"anthropic-beta": "mcp-client-2025-04-04"}
        )
        
        print("✅ Ontology query through MCP successful!")
        print("📊 Claude's ontology analysis:")
        print(f"   {response.content[0].text}")
        return True
        
    except Exception as e:
        print(f"❌ Ontology query error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 ProEthica MCP Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("MCP Health Check", test_mcp_health),
        ("MCP Tool Listing", test_mcp_list_tools),
        ("Anthropic API", test_anthropic_api),
        ("MCP + Anthropic Integration", test_mcp_with_anthropic),
        ("Ontology Query via MCP", test_ontology_query)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'=' * 20} {test_name} {'=' * 20}")
        results[test_name] = test_func()
    
    # Summary
    print(f"\n{'=' * 50}")
    print("🎯 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! MCP integration is working perfectly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    # Check for required environment variables
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Please set ANTHROPIC_API_KEY environment variable")
        print("   export ANTHROPIC_API_KEY=your-api-key")
        exit(1)
    
    success = main()
    exit(0 if success else 1)