#!/usr/bin/env python3
"""
This script verifies that the MCP server can correctly access and read from ontology files.
It tests the MCP server's ability to retrieve entity data from each ontology.
"""

import os
import sys
import requests
import json
from time import sleep

# Configuration
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:5001")
ONTOLOGY_FILES = [
    "engineering_ethics.ttl",
    "nj_legal_ethics.ttl",
    "tccc.ttl"
]

def check_mcp_server():
    """Check if the MCP server is running"""
    try:
        response = requests.get(f"{MCP_SERVER_URL}/api/guidelines/engineering-ethics", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

def test_ontology_access(ontology_file):
    """Test if we can access entities from a specific ontology file"""
    url = f"{MCP_SERVER_URL}/api/ontology/{ontology_file}/entities"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"❌ Failed to access {ontology_file}: HTTP {response.status_code}")
            return False
        
        data = response.json()
        if "entities" not in data:
            print(f"❌ Invalid response format for {ontology_file}")
            return False
        
        entities = data["entities"]
        entity_types = list(entities.keys())
        entity_counts = {etype: len(entities[etype]) for etype in entity_types if entities[etype]}
        
        if not any(entity_counts.values()):
            print(f"⚠️ No entities found in {ontology_file}")
            return False
        
        print(f"✅ Successfully accessed {ontology_file}")
        print(f"   Entity types: {', '.join(entity_types)}")
        for etype, count in entity_counts.items():
            if count > 0:
                print(f"   - {etype}: {count} entities")
        return True
    except requests.RequestException as e:
        print(f"❌ Error accessing {ontology_file}: {str(e)}")
        return False
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON response from {ontology_file}")
        return False

def restart_mcp_server():
    """Attempt to restart the MCP server using the script"""
    print("🔄 Attempting to restart the MCP server...")
    restart_script = "./scripts/restart_mcp_server_gunicorn.sh"
    
    if not os.path.exists(restart_script):
        print("❌ Restart script not found!")
        return False
    
    try:
        os.system(f"chmod +x {restart_script}")
        os.system(restart_script)
        print("⏳ Waiting for MCP server to start...")
        sleep(5)  # Wait for server to start
        return check_mcp_server()
    except Exception as e:
        print(f"❌ Failed to restart MCP server: {str(e)}")
        return False

def main():
    """Main function to verify MCP server and ontology access"""
    print("=== MCP Ontology Verification ===")
    
    # Check if MCP server is running
    print("\n🔍 Checking if MCP server is running...")
    if not check_mcp_server():
        print("❌ MCP server is not running or not responding")
        
        # Ask if user wants to try restarting
        restart = input("Do you want to try restarting the MCP server? (y/n): ")
        if restart.lower() == 'y':
            if restart_mcp_server():
                print("✅ MCP server restarted successfully")
            else:
                print("❌ Failed to restart MCP server")
                print("   Please check logs in mcp/server_gunicorn.log")
                sys.exit(1)
        else:
            print("Please start the MCP server manually and try again")
            sys.exit(1)
    else:
        print("✅ MCP server is running")
    
    # Test each ontology file
    print("\n🔍 Testing ontology files access...")
    success_count = 0
    
    for ontology_file in ONTOLOGY_FILES:
        print(f"\n📁 Testing {ontology_file}...")
        if test_ontology_access(ontology_file):
            success_count += 1
    
    # Summary
    print("\n=== Summary ===")
    print(f"✅ Successfully accessed {success_count}/{len(ONTOLOGY_FILES)} ontology files")
    
    if success_count == len(ONTOLOGY_FILES):
        print("\n🎉 All ontology files are accessible through the MCP server!")
        print("   The system is properly configured for agent-based simulation.")
        return 0
    else:
        print("\n⚠️ Some ontology files couldn't be accessed.")
        print("   Please check the MCP server configuration and try again.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
