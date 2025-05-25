"""
Local development configuration for MCP server to match production setup
"""

import os

# Update MCP server configuration to match production
def update_local_config():
    """Update local environment to match production settings"""
    
    # Set environment variables to match production
    os.environ.setdefault("MCP_SERVER_PORT", "5002")
    os.environ.setdefault("MCP_SERVER_URL", "http://localhost:5002")
    
    print("🔧 Local development config updated:")
    print(f"   MCP_SERVER_PORT: {os.environ.get('MCP_SERVER_PORT')}")
    print(f"   MCP_SERVER_URL: {os.environ.get('MCP_SERVER_URL')}")

if __name__ == "__main__":
    update_local_config()