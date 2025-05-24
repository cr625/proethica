"""
Authentication additions for MCP server
Add this to enhanced_ontology_server_with_guidelines.py
"""

import os
import hashlib
import hmac
from aiohttp import web

class AuthenticationMiddleware:
    """Simple Bearer token authentication for MCP server."""
    
    def __init__(self):
        self.auth_token = os.environ.get('MCP_AUTH_TOKEN')
        if not self.auth_token:
            print("WARNING: No MCP_AUTH_TOKEN set - authentication disabled")
    
    async def __call__(self, app, handler):
        async def middleware_handler(request):
            # Skip auth for health check
            if request.path == '/health':
                return await handler(request)
            
            # Check authentication
            if self.auth_token:
                auth_header = request.headers.get('Authorization', '')
                if not auth_header.startswith('Bearer '):
                    return web.json_response(
                        {"error": "Missing or invalid Authorization header"},
                        status=401
                    )
                
                provided_token = auth_header[7:]  # Remove 'Bearer ' prefix
                if not hmac.compare_digest(provided_token, self.auth_token):
                    return web.json_response(
                        {"error": "Invalid authentication token"},
                        status=401
                    )
            
            return await handler(request)
        
        return middleware_handler

# Add to your server initialization:
"""
# In enhanced_ontology_server_with_guidelines.py, add:

async def run_server():
    # ... existing code ...
    
    # Add authentication middleware
    auth_middleware = AuthenticationMiddleware()
    app.middlewares.append(auth_middleware)
    
    # Add health check endpoint
    async def health_check(request):
        return web.json_response({"status": "healthy", "service": "ProEthica MCP Server"})
    
    app.router.add_get('/health', health_check)
    
    # ... rest of server setup ...
"""