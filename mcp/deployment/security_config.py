"""
Security configuration and token management for MCP server
"""

import os
import secrets
import json
from pathlib import Path

def generate_secure_tokens():
    """Generate secure tokens for production use."""
    
    tokens = {
        'mcp_auth_token': secrets.token_urlsafe(32),
        'jwt_secret': secrets.token_urlsafe(64),
        'api_key': secrets.token_urlsafe(32)
    }
    
    print("🔐 Generated secure tokens:")
    print("=" * 50)
    for name, token in tokens.items():
        print(f"{name.upper()}: {token}")
    
    return tokens

def update_env_file(env_path: str, tokens: dict):
    """Update environment file with new tokens."""
    
    env_lines = []
    
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_lines = f.readlines()
    
    # Update or add token lines
    token_lines = {
        'MCP_AUTH_TOKEN': tokens['mcp_auth_token'],
        'JWT_SECRET': tokens['jwt_secret'], 
        'MCP_API_KEY': tokens['api_key']
    }
    
    updated_lines = []
    found_tokens = set()
    
    for line in env_lines:
        updated = False
        for token_name, token_value in token_lines.items():
            if line.startswith(f"{token_name}="):
                updated_lines.append(f"{token_name}={token_value}\n")
                found_tokens.add(token_name)
                updated = True
                break
        
        if not updated:
            updated_lines.append(line)
    
    # Add missing tokens
    for token_name, token_value in token_lines.items():
        if token_name not in found_tokens:
            updated_lines.append(f"{token_name}={token_value}\n")
    
    # Write updated file
    with open(env_path, 'w') as f:
        f.writelines(updated_lines)
    
    print(f"✅ Updated {env_path} with new tokens")

def create_client_config(tokens: dict, mcp_url: str = "https://mcp.proethica.org"):
    """Create client configuration for using the MCP server."""
    
    config = {
        "mcp_servers": [{
            "url": mcp_url,
            "authorization_token": tokens['mcp_auth_token']
        }],
        "anthropic_headers": {
            "anthropic-beta": "mcp-client-2025-04-04"
        },
        "rate_limits": {
            "requests_per_minute": 100,
            "burst_requests": 20
        }
    }
    
    config_path = Path(__file__).parent / "client_config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Created client config at {config_path}")
    return config

def setup_production_security():
    """Complete security setup for production."""
    
    print("🚀 Setting up production security for MCP server")
    print("=" * 50)
    
    # Generate tokens
    tokens = generate_secure_tokens()
    
    # Update environment files
    env_files = [
        "/home/chris/proethica-mcp/mcp.env",  # Production
        "/home/chris/ai-ethical-dm/.env",     # Local development
    ]
    
    for env_file in env_files:
        if os.path.exists(env_file):
            update_env_file(env_file, tokens)
        else:
            print(f"⚠️  Environment file not found: {env_file}")
    
    # Create client config
    client_config = create_client_config(tokens)
    
    print("\n🔧 Next steps:")
    print("1. Restart the MCP server: sudo systemctl restart proethica-mcp-home")
    print("2. Test the new authentication")
    print("3. Update any existing API clients with new tokens")
    
    return tokens, client_config

if __name__ == "__main__":
    setup_production_security()