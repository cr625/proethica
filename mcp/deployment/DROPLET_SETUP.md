# Setting Up MCP Server on Your Existing Droplet

Since you already have ProEthica running with gunicorn and nginx, here's how to add the MCP server:

## Quick Start Commands

```bash
# SSH into your droplet
ssh your-droplet

# Navigate to your repo
cd /path/to/ai-ethical-dm

# Pull latest changes to get deployment files
git pull

# Make setup script executable
chmod +x mcp/deployment/setup-mcp-on-droplet.sh

# Edit the script to set your paths
nano mcp/deployment/setup-mcp-on-droplet.sh
# Update REPO_PATH and VENV_PATH variables

# Run the setup
./mcp/deployment/setup-mcp-on-droplet.sh
```

## Manual Steps

### 1. Configure Environment

```bash
# Edit the MCP environment file
sudo nano /etc/proethica/mcp.env
```

Add your values:
```env
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://same-as-your-main-app
MCP_AUTH_TOKEN=<token-from-setup-script>
```

### 2. Update Nginx

Edit your existing nginx config:
```bash
sudo nano /etc/nginx/sites-available/proethica.org
```

Add inside your `server { }` block:
```nginx
# MCP Server endpoints
location /mcp/ {
    proxy_pass http://localhost:5001/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_cache_bypass $http_upgrade;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    rewrite ^/mcp/(.*) /$1 break;
}

location /mcp/health {
    proxy_pass http://localhost:5001/health;
    access_log off;
}
```

Test and reload:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 3. Add Authentication to MCP Server

Edit the server file:
```bash
nano mcp/enhanced_ontology_server_with_guidelines.py
```

Add after the imports:
```python
import hmac
```

In the `handle_jsonrpc` method, add at the beginning:
```python
async def handle_jsonrpc(self, request):
    # Check authentication
    auth_token = os.environ.get('MCP_AUTH_TOKEN')
    if auth_token:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return web.json_response(
                {"error": {"code": -32001, "message": "Unauthorized"}}, 
                status=401
            )
        
        provided_token = auth_header[7:]
        if not hmac.compare_digest(provided_token, auth_token):
            return web.json_response(
                {"error": {"code": -32001, "message": "Invalid token"}}, 
                status=401
            )
    
    # ... rest of existing method
```

Add health endpoint in `run_server()` function:
```python
async def health_check(request):
    return web.json_response({"status": "healthy", "service": "ProEthica MCP"})

app.router.add_get('/health', health_check)
```

### 4. Start the Service

```bash
# Enable and start
sudo systemctl enable proethica-mcp
sudo systemctl start proethica-mcp

# Check status
sudo systemctl status proethica-mcp

# View logs
sudo journalctl -u proethica-mcp -f
```

## Testing

### 1. Test Health Endpoint
```bash
curl https://proethica.org/mcp/health
```

### 2. Test JSON-RPC with Auth
```bash
curl -X POST https://proethica.org/mcp/jsonrpc \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}'
```

### 3. Test with Python
```python
import requests

response = requests.post(
    "https://proethica.org/mcp/jsonrpc",
    headers={"Authorization": "Bearer YOUR_AUTH_TOKEN"},
    json={
        "jsonrpc": "2.0",
        "method": "call_tool",
        "params": {
            "name": "get_world_entities",
            "arguments": {"ontology_source": "engineering-ethics"}
        },
        "id": 1
    }
)
print(response.json())
```

## Using with Anthropic API

```python
import anthropic

client = anthropic.Anthropic()

mcp_servers = [{
    "url": "https://proethica.org/mcp",
    "authorization_token": "YOUR_AUTH_TOKEN"
}]

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1000,
    messages=[{
        "role": "user",
        "content": "List engineering ethics principles from the ontology"
    }],
    mcp_servers=mcp_servers,
    headers={"anthropic-beta": "mcp-client-2025-04-04"}
)
```

## Troubleshooting

1. **Port 5001 already in use**: 
   ```bash
   sudo lsof -i :5001
   # Kill the process if needed
   ```

2. **Service won't start**:
   ```bash
   # Check logs
   sudo journalctl -u proethica-mcp -n 50
   
   # Check environment file permissions
   ls -la /etc/proethica/mcp.env
   ```

3. **502 Bad Gateway**:
   - MCP server not running
   - Check systemctl status

4. **401 Unauthorized**:
   - Check auth token in env file
   - Ensure Bearer prefix in header

## Security Checklist

- [ ] Auth token is secure (32+ characters)
- [ ] Environment file has restricted permissions (600)
- [ ] Database credentials are not exposed
- [ ] API keys are kept secret
- [ ] nginx rate limiting is configured
- [ ] SSL certificate is valid