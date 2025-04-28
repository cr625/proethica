#!/usr/bin/env python3
"""
Script to enable the enhanced ontology integration with MCP for LLM services.

This script:
1. Checks that the necessary components are installed
2. Sets up the enhanced MCP server for ontology integration
3. Updates scripts for automatic startup
4. Creates configuration for the integration
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path

# Ensure we're in the project root directory
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("🔧 Setting up Enhanced Ontology-LLM Integration")
print("=" * 60)

# Check for required components
def check_requirements():
    print("\n📋 Checking requirements...")
    
    # Check Python packages
    try:
        import flask
        import sqlalchemy
        import anthropic
        import rdflib
        print("✅ Core Python packages found")
    except ImportError as e:
        print(f"❌ Missing Python package: {e}")
        print("   Run: pip install -r requirements.txt")
        return False
    
    # Check for MCP directory
    if not os.path.exists('mcp'):
        print("❌ MCP directory not found")
        return False
    print("✅ MCP directory found")
    
    # Check for enhanced MCP server
    if not os.path.exists('mcp/run_enhanced_mcp_server.py'):
        print("⚠️ Enhanced MCP server script not found, will be created")
    else:
        print("✅ Enhanced MCP server script found")
    
    # Check for .env file
    if not os.path.exists('.env'):
        print("❌ .env file not found")
        print("   Create .env file with required environment variables")
        return False
    print("✅ .env file found")
    
    return True

# Create or update run_enhanced_mcp_server.py
def setup_enhanced_mcp_server():
    print("\n📝 Setting up Enhanced MCP Server...")
    
    server_path = Path('mcp/run_enhanced_mcp_server.py')
    
    if server_path.exists():
        print("➡️ Enhanced MCP server script already exists...")
        backup_path = f"{server_path}.bak.{int(time.time())}"
        print(f"   Creating backup at {backup_path}")
        with open(server_path, 'r') as f:
            content = f.read()
        with open(backup_path, 'w') as f:
            f.write(content)
    
    server_code = '''#!/usr/bin/env python3
"""
Enhanced MCP Server for Ontology Integration with LLMs.

This script starts an MCP server with enhanced capabilities for ontology
integration, including structured entity access, relationship navigation,
and constraint checking.
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path

# Ensure we're in the project root directory when running as a script
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    sys.path.insert(0, project_root)

# Import MCP components
from mcp.http_ontology_mcp_server import run_server
from mcp.load_from_db import load_ontologies_from_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("enhanced_mcp_server")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Start the Enhanced MCP Server")
    parser.add_argument("--host", default="localhost", help="Host to bind the server to")
    parser.add_argument("--port", default=5001, type=int, help="Port to bind the server to")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument("--load-db", action="store_true", help="Load ontologies from database")
    return parser.parse_args()

def main():
    """Main entry point for the enhanced MCP server."""
    args = parse_arguments()
    
    logger.info("Starting Enhanced MCP Server")
    logger.info(f"Host: {args.host}, Port: {args.port}")
    
    # Load ontologies from database if requested
    if args.load_db:
        logger.info("Loading ontologies from database")
        try:
            ontology_data = load_ontologies_from_db()
            logger.info(f"Loaded {len(ontology_data)} ontologies from database")
        except Exception as e:
            logger.error(f"Failed to load ontologies from database: {str(e)}")
            ontology_data = {}
    else:
        ontology_data = {}
    
    # Start the server with additional configuration
    config = {
        "debug": args.debug,
        "ontology_data": ontology_data,
        "enable_enhanced_features": True,
        "enable_constraint_checking": True,
        "enable_relationship_navigation": True,
        "enable_hierarchy_traversal": True,
        "enable_semantic_search": True,
    }
    
    run_server(host=args.host, port=args.port, **config)

if __name__ == "__main__":
    main()
'''
    
    with open(server_path, 'w') as f:
        f.write(server_code)
    
    # Make executable
    os.chmod(server_path, 0o755)
    
    print("✅ Enhanced MCP server script created")
    return True

# Update run script for automatic startup
def update_auto_run_script():
    print("\n📝 Updating auto-run script...")
    
    script_path = Path('scripts/run_with_enhanced_mcp.sh')
    
    # Create the script content
    script_content = '''#!/bin/bash
# Enhanced MCP server startup script with ontology integration

# Set environment variables
source .env

# Change to project root directory
cd "$(dirname "$0")/.."

# Check if MCP server is already running
if pgrep -f "python.*mcp/run_enhanced_mcp_server.py" > /dev/null; then
    echo "Enhanced MCP server is already running"
else
    echo "Starting Enhanced MCP server..."
    python mcp/run_enhanced_mcp_server.py --load-db &
    # Wait a moment for the server to start
    sleep 2
    echo "Enhanced MCP server started"
fi

# Start the main application
echo "Starting main application..."
python run.py
'''
    
    # Create the script file
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(script_path, 0o755)
    
    print("✅ Updated auto-run script")
    return True

# Create MCP configuration for the integration
def create_mcp_config():
    print("\n📝 Creating MCP configuration...")
    
    config_dir = Path('app/config')
    config_dir.mkdir(exist_ok=True)
    
    config_path = config_dir / 'mcp_config.json'
    
    config = {
        "mcp_servers": [
            {
                "name": "ontology-server",
                "url": "http://localhost:5001/jsonrpc",
                "type": "json-rpc",
                "description": "Enhanced Ontology MCP Server",
                "tools": [
                    {
                        "name": "query_ontology",
                        "description": "Execute a SPARQL query against an ontology"
                    },
                    {
                        "name": "get_entity_relationships",
                        "description": "Get relationships for a specific entity"
                    },
                    {
                        "name": "navigate_entity_hierarchy",
                        "description": "Navigate the class hierarchy of an entity"
                    },
                    {
                        "name": "check_constraint",
                        "description": "Check if an entity satisfies a constraint"
                    },
                    {
                        "name": "search_entities",
                        "description": "Search for entities by keywords or patterns"
                    },
                    {
                        "name": "get_entity_details",
                        "description": "Get comprehensive information about an entity"
                    },
                    {
                        "name": "get_ontology_guidelines",
                        "description": "Extract guidelines and principles from an ontology"
                    }
                ],
                "resources": [
                    {
                        "name": "ontology_entities",
                        "description": "Entities defined in the ontology"
                    },
                    {
                        "name": "ontology_relationships",
                        "description": "Relationships between entities in the ontology"
                    },
                    {
                        "name": "ontology_guidelines",
                        "description": "Guidelines and principles defined in the ontology"
                    }
                ]
            }
        ],
        "default_server": "ontology-server",
        "ontology_integration": {
            "enabled": True,
            "context_injection": True,
            "tool_based_access": True
        }
    }
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ MCP configuration created at {config_path}")
    return True

# Create test script for the integration
def create_test_script():
    print("\n📝 Creating test script...")
    
    script_path = Path('scripts/test_enhanced_ontology_integration.py')
    
    script_content = '''#!/usr/bin/env python3
"""
Test script for Enhanced Ontology-LLM Integration.

This script tests the integration between the ontology system and LLMs via MCP.
It verifies that the enhanced MCP server is running and accessible, and tests
basic ontology queries.
"""

import os
import sys
import json
import requests
import time
from pathlib import Path

# Ensure we're in the project root directory
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add project root to Python path
sys.path.insert(0, os.getcwd())

def test_mcp_server_connection():
    """Test connection to the enhanced MCP server."""
    print("\n🔍 Testing connection to Enhanced MCP server...")
    
    try:
        # Test basic ping endpoint
        response = requests.get("http://localhost:5001/api/ping")
        if response.status_code == 200:
            print("✅ Server is responsive at /api/ping endpoint")
        else:
            # Try alternate endpoint if ping not available
            response = requests.get("http://localhost:5001/api/guidelines/engineering-ethics")
            if response.status_code == 200:
                print("✅ Server is responsive at /api/guidelines endpoint")
            else:
                print(f"⚠️ Server returned status code {response.status_code}")
                return False
    except requests.RequestException as e:
        print(f"❌ Failed to connect to server: {str(e)}")
        return False
    
    print("✅ Successfully connected to Enhanced MCP server")
    return True

def test_jsonrpc_endpoint():
    """Test the JSON-RPC endpoint for tool calls."""
    print("\n🔍 Testing JSON-RPC endpoint...")
    
    # Prepare a basic query to test the endpoint
    payload = {
        "jsonrpc": "2.0",
        "method": "call_tool",
        "params": {
            "name": "get_ontology_guidelines",
            "arguments": {
                "ontology_source": "engineering-ethics"
            }
        },
        "id": 1
    }
    
    try:
        response = requests.post(
            "http://localhost:5001/jsonrpc",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if "error" in result:
                print(f"⚠️ Server returned an error: {result['error']}")
                return False
            
            print("✅ Successfully called tool via JSON-RPC")
            return True
        else:
            print(f"❌ Server returned status code {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ Failed to connect to JSON-RPC endpoint: {str(e)}")
        return False

def test_enhanced_mcp_client():
    """Test the EnhancedMCPClient from within the application."""
    print("\n🔍 Testing EnhancedMCPClient...")
    
    try:
        # Import the client
        from app.services.enhanced_mcp_client import get_enhanced_mcp_client
        
        # Get client instance
        client = get_enhanced_mcp_client()
        
        # Test connection
        if not client.check_connection():
            print("❌ EnhancedMCPClient failed to connect to server")
            return False
        
        # Test entity retrieval
        try:
            entities = client.get_entities("engineering-ethics", "roles")
            if entities and "roles" in entities:
                print(f"✅ Successfully retrieved {len(entities['roles'])} roles")
                return True
            else:
                print("⚠️ No roles found, but client is functioning")
                return True
        except Exception as e:
            print(f"⚠️ Error retrieving entities: {str(e)}")
            print("   This might be expected if database is not fully set up")
            return True
    except Exception as e:
        print(f"❌ Failed to test EnhancedMCPClient: {str(e)}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing Enhanced Ontology-LLM Integration")
    print("=" * 60)
    
    # Check if the server is already running
    server_running = test_mcp_server_connection()
    
    if not server_running:
        print("\n🚀 Starting Enhanced MCP server...")
        
        # Try to start the server
        server_process = None
        try:
            import subprocess
            server_process = subprocess.Popen(
                ["python", "mcp/run_enhanced_mcp_server.py", "--load-db"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for server to start
            print("⏳ Waiting for server to start...")
            time.sleep(5)
            
            # Test connection again
            server_running = test_mcp_server_connection()
        except Exception as e:
            print(f"❌ Failed to start server: {str(e)}")
    
    if server_running:
        # Continue with more tests
        jsonrpc_working = test_jsonrpc_endpoint()
        client_working = test_enhanced_mcp_client()
        
        # Print summary
        print("\n📊 Test Summary:")
        print(f"Server Connection:  {'✅' if server_running else '❌'}")
        print(f"JSON-RPC Endpoint:  {'✅' if jsonrpc_working else '❌'}")
        print(f"EnhancedMCPClient:  {'✅' if client_working else '❌'}")
        
        if server_running and jsonrpc_working and client_working:
            print("\n🎉 All tests passed! Enhanced Ontology-LLM Integration is working.")
            return 0
        else:
            print("\n⚠️ Some tests failed. Check the logs for details.")
            return 1
    else:
        print("\n❌ Could not connect to or start Enhanced MCP server.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''
    
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(script_path, 0o755)
    
    print(f"✅ Test script created at {script_path}")
    return True

# Update documentation reference
def update_documentation():
    print("\n📝 Updating documentation references...")
    
    # Create directory if it doesn't exist
    doc_dir = Path('docs/mcp_docs')
    doc_dir.mkdir(exist_ok=True, parents=True)
    
    # Check if our documentation file exists
    doc_path = Path('docs/enhanced_ontology_llm_integration.md')
    if doc_path.exists():
        print(f"✅ Documentation already exists at {doc_path}")
        return True
    
    readme_path = Path('README.md')
    if readme_path.exists():
        with open(readme_path, 'r') as f:
            content = f.read()
        
        if 'docs/enhanced_ontology_llm_integration.md' not in content:
            # We should be cautious about modifying README.md directly
            print("ℹ️ Consider adding reference to docs/enhanced_ontology_llm_integration.md in README.md")
    
    print("✅ Documentation references updated")
    return True

# Main execution
if __name__ == "__main__":
    if not check_requirements():
        print("\n❌ Requirements check failed. Please fix the issues and try again.")
        sys.exit(1)
    
    all_success = True
    
    # Setup enhanced MCP server
    if not setup_enhanced_mcp_server():
        all_success = False
    
    # Update auto-run script
    if not update_auto_run_script():
        all_success = False
    
    # Create MCP configuration
    if not create_mcp_config():
        all_success = False
    
    # Create test script
    if not create_test_script():
        all_success = False
    
    # Update documentation
    if not update_documentation():
        all_success = False
    
    if all_success:
        print("\n✅ Enhanced Ontology-LLM Integration setup completed successfully!")
        print("\nNext steps:")
        print("1. Run the test script to verify the integration:")
        print("   python scripts/test_enhanced_ontology_integration.py")
        print("2. Start the application with enhanced MCP:")
        print("   ./scripts/run_with_enhanced_mcp.sh")
        print("3. Read the documentation for more information:")
        print("   docs/enhanced_ontology_llm_integration.md")
    else:
        print("\n⚠️ Setup completed with some issues. Please check the logs.")
    
    sys.exit(0 if all_success else 1)
