"""
Authentication improvements for MCP server
"""

import os
import hmac
import hashlib
import time
import jwt
import secrets
from typing import Optional, Dict, Any
from aiohttp import web
import logging

logger = logging.getLogger(__name__)

class EnhancedAuthenticationMiddleware:
    """Enhanced authentication with JWT tokens, rate limiting, and security features."""
    
    def __init__(self):
        self.auth_token = os.environ.get('MCP_AUTH_TOKEN')
        self.jwt_secret = os.environ.get('JWT_SECRET', secrets.token_urlsafe(32))
        self.rate_limit_requests = int(os.environ.get('MCP_RATE_LIMIT', '100'))  # requests per minute
        self.rate_limit_window = 60  # seconds
        
        # Rate limiting storage (in production, use Redis)
        self.rate_limit_store = {}
        
        if not self.auth_token:
            logger.warning("No MCP_AUTH_TOKEN set - authentication disabled")
        
        logger.info(f"Enhanced authentication initialized with rate limit: {self.rate_limit_requests}/min")
    
    def _check_rate_limit(self, client_ip: str) -> bool:
        """Check if client is within rate limits."""
        current_time = time.time()
        window_start = current_time - self.rate_limit_window
        
        # Clean old entries
        if client_ip in self.rate_limit_store:
            self.rate_limit_store[client_ip] = [
                req_time for req_time in self.rate_limit_store[client_ip]
                if req_time > window_start
            ]
        else:
            self.rate_limit_store[client_ip] = []
        
        # Check limit
        request_count = len(self.rate_limit_store[client_ip])
        if request_count >= self.rate_limit_requests:
            return False
        
        # Add current request
        self.rate_limit_store[client_ip].append(current_time)
        return True
    
    def _verify_bearer_token(self, token: str) -> bool:
        """Verify bearer token (constant time comparison)."""
        if not self.auth_token:
            return True  # No auth configured
        
        return hmac.compare_digest(token, self.auth_token)
    
    def _verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return payload."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            
            # Check expiration
            if payload.get('exp', 0) < time.time():
                return None
            
            return payload
        except jwt.InvalidTokenError:
            return None
    
    def _create_jwt_token(self, client_id: str, expires_in: int = 3600) -> str:
        """Create a JWT token for a client."""
        payload = {
            'client_id': client_id,
            'iat': time.time(),
            'exp': time.time() + expires_in,
            'scope': 'mcp:read mcp:write'
        }
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address (considering proxies)."""
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.remote
    
    async def __call__(self, app, handler):
        async def middleware_handler(request):
            client_ip = self._get_client_ip(request)
            
            # Skip auth for health check
            if request.path == '/health':
                return await handler(request)
            
            # Rate limiting
            if not self._check_rate_limit(client_ip):
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return web.json_response(
                    {"error": "Rate limit exceeded. Try again later."},
                    status=429,
                    headers={
                        'Retry-After': str(self.rate_limit_window),
                        'X-RateLimit-Limit': str(self.rate_limit_requests),
                        'X-RateLimit-Remaining': '0'
                    }
                )
            
            # Authentication check
            if self.auth_token:
                auth_header = request.headers.get('Authorization', '')
                
                if not auth_header:
                    return web.json_response(
                        {"error": "Missing Authorization header"},
                        status=401,
                        headers={'WWW-Authenticate': 'Bearer realm="MCP API"'}
                    )
                
                if auth_header.startswith('Bearer '):
                    token = auth_header[7:]
                    
                    # Try JWT first, then fallback to simple bearer token
                    jwt_payload = self._verify_jwt_token(token)
                    bearer_valid = self._verify_bearer_token(token)
                    
                    if not (jwt_payload or bearer_valid):
                        logger.warning(f"Invalid authentication attempt from {client_ip}")
                        return web.json_response(
                            {"error": "Invalid authentication token"},
                            status=401,
                            headers={'WWW-Authenticate': 'Bearer realm="MCP API"'}
                        )
                    
                    # Add client info to request for logging
                    if jwt_payload:
                        request['client_id'] = jwt_payload.get('client_id', 'unknown')
                        request['auth_method'] = 'jwt'
                    else:
                        request['client_id'] = 'bearer_token'
                        request['auth_method'] = 'bearer'
                else:
                    return web.json_response(
                        {"error": "Invalid Authorization header format. Use 'Bearer <token>'"},
                        status=401,
                        headers={'WWW-Authenticate': 'Bearer realm="MCP API"'}
                    )
            
            # Add security headers
            response = await handler(request)
            
            # Add security headers
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['Content-Security-Policy'] = "default-src 'self'"
            
            # Add rate limit headers
            remaining = max(0, self.rate_limit_requests - len(self.rate_limit_store.get(client_ip, [])))
            response.headers['X-RateLimit-Limit'] = str(self.rate_limit_requests)
            response.headers['X-RateLimit-Remaining'] = str(remaining)
            
            return response
        
        return middleware_handler

class TokenManager:
    """Manage JWT tokens for clients."""
    
    def __init__(self, jwt_secret: str):
        self.jwt_secret = jwt_secret
    
    def create_client_token(self, client_id: str, expires_in: int = 86400) -> str:
        """Create a new JWT token for a client (default 24 hours)."""
        payload = {
            'client_id': client_id,
            'iat': time.time(),
            'exp': time.time() + expires_in,
            'scope': 'mcp:read mcp:write'
        }
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')
    
    def revoke_token(self, token: str) -> bool:
        """Revoke a token (in production, store in blacklist)."""
        # In production, you'd store revoked tokens in Redis/database
        # For now, we'll just validate that the token is properly formatted
        try:
            jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            return True
        except jwt.InvalidTokenError:
            return False

# Usage in enhanced_ontology_server_with_guidelines.py:
"""
# Add to imports:
from mcp.deployment.auth_improvements import EnhancedAuthenticationMiddleware, TokenManager

# In run_server() function:
async def run_server():
    # ... existing code ...
    
    # Add enhanced authentication middleware
    auth_middleware = EnhancedAuthenticationMiddleware()
    app.middlewares.append(auth_middleware)
    
    # Add token management endpoint
    token_manager = TokenManager(os.environ.get('JWT_SECRET', 'default-secret'))
    
    async def create_token(request):
        # Only allow token creation with master auth token
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer ') or auth_header[7:] != os.environ.get('MCP_AUTH_TOKEN'):
            return web.json_response({"error": "Unauthorized"}, status=401)
        
        data = await request.json()
        client_id = data.get('client_id', 'unknown')
        expires_in = data.get('expires_in', 86400)
        
        token = token_manager.create_client_token(client_id, expires_in)
        
        return web.json_response({
            "token": token,
            "expires_in": expires_in,
            "token_type": "Bearer"
        })
    
    app.router.add_post('/auth/token', create_token)
    
    # ... rest of server setup ...
"""