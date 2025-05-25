# Production MCP Server Migration - May 24, 2024

## Summary
The MCP server has been migrated from `/var/www/proethica` to `/home/chris/proethica-mcp` on the production server. This change was made to allow for easier development and deployment of the MCP server independent of the main ProEthica application.

## Changes Made on Production

### 1. MCP Server Location Change
- **Old location**: `/var/www/proethica/mcp/`
- **New location**: `/home/chris/proethica-mcp/`
- **Port change**: From 5001 to 5002 (to avoid conflicts during migration)

### 2. Systemd Services Modified

#### Disabled Service
- `mcp-server.service` - The old MCP server service has been disabled and stopped

#### New Service Created
- `proethica-mcp-home.service` - New service running from home directory
- Runs as user `chris` instead of `www-data`
- Configuration file: `/home/chris/proethica-mcp/mcp.env`

#### Updated Service
- `proethica.service` - Updated to:
  - Remove dependency on old `mcp-server.service`
  - Add dependency on new `proethica-mcp-home.service`
  - Change `MCP_SERVER_URL` environment variable from `http://localhost:5001` to `http://localhost:5002`

### 3. Environment Configuration
The new MCP server uses `/home/chris/proethica-mcp/mcp.env` with:
```bash
ANTHROPIC_API_KEY=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
DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
MCP_AUTH_TOKEN=nGkmBr1jlyYLi8ZKCeXEFMMD5KddiCMzAahi7j5G43c
MCP_SERVER_PORT=5002
USE_MOCK_GUIDELINE_RESPONSES=false
PYTHONPATH=/home/chris/proethica-mcp
```

## Required Code Changes for Development

### 1. Update Application Configuration
In the main ProEthica application, update any references to the MCP server URL:

**File**: `app/config.py` or wherever MCP_SERVER_URL is configured
```python
# Change from:
MCP_SERVER_URL = os.environ.get('MCP_SERVER_URL', 'http://localhost:5001')

# To:
MCP_SERVER_URL = os.environ.get('MCP_SERVER_URL', 'http://localhost:5002')
```

### 2. Update Environment Files
**File**: `.env` or `.env.production`
```bash
# Add or update:
MCP_SERVER_URL=http://localhost:5002
```

### 3. Update Docker Compose (if applicable)
If using Docker Compose, update the MCP service configuration to use port 5002.

### 4. Update Deployment Scripts
Any deployment scripts that reference the old MCP server location or service name need to be updated:
- Change references from `mcp-server.service` to `proethica-mcp-home.service`
- Update paths from `/var/www/proethica/mcp/` to `/home/chris/proethica-mcp/`

### 5. Update nginx Configuration (if needed)
If nginx proxies to the MCP server, update the proxy_pass directive:
```nginx
# Change from:
proxy_pass http://localhost:5001;

# To:
proxy_pass http://localhost:5002;
```

## Rollback Instructions
If you need to rollback to the old MCP server:

1. Stop new service: `sudo systemctl stop proethica-mcp-home`
2. Disable new service: `sudo systemctl disable proethica-mcp-home`
3. Enable old service: `sudo systemctl enable mcp-server`
4. Start old service: `sudo systemctl start mcp-server`
5. Revert proethica.service to original configuration
6. Restart ProEthica: `sudo systemctl restart proethica`

## Testing the New Setup
```bash
# Check MCP server health
curl http://localhost:5002/health

# Test with authentication
curl -X POST http://localhost:5002/jsonrpc \
  -H "Authorization: Bearer nGkmBr1jlyYLi8ZKCeXEFMMD5KddiCMzAahi7j5G43c" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "list_tools", "id": 1}'
```

## Nginx Configuration for mcp.proethica.org

A separate nginx configuration has been created to serve the MCP API at https://mcp.proethica.org:

- Configuration file: `/etc/nginx/sites-available/mcp.proethica.org`
- SSL certificate managed by Let's Encrypt
- Endpoints:
  - `https://mcp.proethica.org/health` - Health check (no auth)
  - `https://mcp.proethica.org/jsonrpc` - JSONRPC API (requires auth token)
  - `https://mcp.proethica.org/api/*` - Direct API endpoints

### Using the Public MCP Endpoint
```python
mcp_servers = [{
    "url": "https://mcp.proethica.org",
    "authorization_token": "nGkmBr1jlyYLi8ZKCeXEFMMD5KddiCMzAahi7j5G43c"
}]
```

## Notes
- The MCP server is now running as user `chris` which may have different permissions than `www-data`
- The auth token has been regenerated for security
- All logs are now available via: `sudo journalctl -u proethica-mcp-home -f`
- Nginx access logs: `/var/log/nginx/mcp.proethica.org.access.log`
- Nginx error logs: `/var/log/nginx/mcp.proethica.org.error.log`