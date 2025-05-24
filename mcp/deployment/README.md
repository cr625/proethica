# MCP Server Deployment Guide

This guide covers deploying the ProEthica MCP server to make it accessible for the Anthropic API.

## Deployment Options

### Option A: Digital Ocean App Platform (Recommended for Simplicity)

**Pros**: Managed platform, automatic SSL, easy scaling, built-in CI/CD
**Cons**: Less control, slightly more expensive

1. **Create App**: 
   - Go to Digital Ocean App Platform
   - Connect your GitHub repository
   - Use the provided `app.yaml` specification

2. **Configure Environment**:
   - Set `ANTHROPIC_API_KEY` and `DATABASE_URL` as encrypted environment variables
   - Add `MCP_AUTH_TOKEN` for security

3. **Deploy**: Push to main branch auto-deploys

**Cost**: ~$5-12/month for basic tier

### Option B: Digital Ocean Droplet (Recommended for Control)

**Pros**: Full control, cheaper, can host multiple services
**Cons**: Manual setup, you manage updates

1. **Create Droplet**:
   - Ubuntu 22.04 LTS
   - Basic droplet ($6/month)
   - Enable backups

2. **Run Deployment Script**:
   ```bash
   chmod +x deploy-droplet.sh
   sudo ./deploy-droplet.sh
   ```

3. **Configure Environment**:
   ```bash
   sudo cp /opt/proethica-mcp/.env.template /opt/proethica-mcp/.env
   sudo nano /opt/proethica-mcp/.env  # Add your keys
   ```

4. **Start Service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable proethica-mcp
   sudo systemctl start proethica-mcp
   ```

## DNS Configuration

Add these records to your domain:

```
Type  Name  Value                   TTL
A     mcp   your-droplet-ip        3600
# OR for App Platform:
CNAME mcp   your-app.ondigitalocean.app  3600
```

## Security Implementation

### 1. Add Authentication to Server

Edit `enhanced_ontology_server_with_guidelines.py`:

```python
# At the top of the file
from aiohttp import web
import os
import hmac

# In the EnhancedOntologyServerWithGuidelines class
def __init__(self):
    # ... existing code ...
    self.auth_token = os.environ.get('MCP_AUTH_TOKEN')

# Modify handle_jsonrpc method
async def handle_jsonrpc(self, request):
    # Check authentication
    if self.auth_token:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return web.json_response({"error": "Unauthorized"}, status=401)
        
        token = auth_header[7:]
        if not hmac.compare_digest(token, self.auth_token):
            return web.json_response({"error": "Unauthorized"}, status=401)
    
    # ... rest of existing method ...
```

### 2. Generate Secure Token

```bash
# Generate a secure token
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Using with Anthropic API

Once deployed:

```python
import anthropic
import os

client = anthropic.Anthropic()

# Your deployed MCP server
mcp_servers = [{
    "url": "https://mcp.proethica.org",
    "authorization_token": os.environ.get("MCP_AUTH_TOKEN")
}]

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1000,
    messages=[{
        "role": "user",
        "content": "List the engineering ethics ontology entities"
    }],
    mcp_servers=mcp_servers,
    headers={"anthropic-beta": "mcp-client-2025-04-04"}
)
```

## Testing Your Deployment

1. **Test health endpoint**:
   ```bash
   curl https://mcp.proethica.org/health
   ```

2. **Test with authentication**:
   ```bash
   curl -X POST https://mcp.proethica.org/jsonrpc \
     -H "Authorization: Bearer your-token" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}'
   ```

3. **Test with Anthropic API** using the Python code above

## Monitoring

### For Droplet:
```bash
# View logs
sudo journalctl -u proethica-mcp -f

# Check status
sudo systemctl status proethica-mcp

# Restart if needed
sudo systemctl restart proethica-mcp
```

### For App Platform:
- Use Digital Ocean dashboard
- Set up alerts for downtime

## Troubleshooting

1. **Connection refused**: Check if service is running
2. **401 Unauthorized**: Verify auth token matches
3. **502 Bad Gateway**: MCP server crashed, check logs
4. **SSL issues**: Ensure certbot ran successfully

## Next Steps

1. Deploy using either option
2. Add authentication to your server code
3. Test with curl commands
4. Update your Anthropic API code to use the public URL
5. Monitor logs for first 24 hours

## Cost Estimate

- **Droplet**: $6-12/month (depending on size)
- **App Platform**: $5-12/month (basic tier)
- **Domain**: Already owned (proethica.org)
- **SSL**: Free with Let's Encrypt