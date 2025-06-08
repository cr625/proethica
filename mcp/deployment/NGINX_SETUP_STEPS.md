# Nginx Setup Steps for MCP Server

## Current Status
✅ MCP server running on localhost:5002  
✅ Health endpoint responding: `{"status": "ok", "message": "Ontology MCP server is running"}`

## Step 1: Copy Nginx Configuration

```bash
# Copy the nginx config file to sites-available
sudo cp /home/chris/proethica-repo/mcp/deployment/nginx-mcp-ssl.conf /etc/nginx/sites-available/mcp.proethica.org

# Enable the site
sudo ln -s /etc/nginx/sites-available/mcp.proethica.org /etc/nginx/sites-enabled/

# Test nginx configuration
sudo nginx -t
```

## Step 2: Initial Setup (HTTP only)

First, let's get HTTP working, then add SSL:

```bash
# Create a basic HTTP-only config for initial testing
sudo tee /etc/nginx/sites-available/mcp.proethica.org << 'EOF'
server {
    listen 80;
    server_name mcp.proethica.org;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=mcp_api:10m rate=30r/m;
    
    # Logging
    access_log /var/log/nginx/mcp.proethica.org.access.log;
    error_log /var/log/nginx/mcp.proethica.org.error.log;

    location / {
        limit_req zone=mcp_api burst=10 nodelay;
        
        proxy_pass http://127.0.0.1:5002;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:5002/health;
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/mcp.proethica.org /etc/nginx/sites-enabled/

# Test and reload
sudo nginx -t && sudo systemctl reload nginx
```

## Step 3: Test HTTP Access

```bash
# Test locally
curl -H "Host: mcp.proethica.org" http://localhost/health

# Test externally (if DNS is configured)
curl http://mcp.proethica.org/health
```

## Step 4: Setup SSL with Certbot

```bash
# Install certbot if not already installed
sudo apt update
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d mcp.proethica.org

# Certbot will automatically update the nginx config for HTTPS
```

## Step 5: Update to Full SSL Configuration

After certbot, replace with the full production config:

```bash
# Copy the full SSL configuration
sudo cp /home/chris/proethica-repo/mcp/deployment/nginx-mcp-ssl.conf /etc/nginx/sites-available/mcp.proethica.org

# Test and reload
sudo nginx -t && sudo systemctl reload nginx
```

## Step 6: Test Final Setup

```bash
# Test HTTPS health endpoint
curl https://mcp.proethica.org/health

# Test API functionality
curl -X POST https://mcp.proethica.org/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"health","params":{},"id":1}'
```

## Troubleshooting

### DNS Check
```bash
# Verify DNS points to your server
dig mcp.proethica.org
nslookup mcp.proethica.org
```

### Firewall Check
```bash
# Ensure ports are open
sudo ufw status
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### Nginx Logs
```bash
# Check nginx logs if issues
sudo tail -f /var/log/nginx/mcp.proethica.org.error.log
sudo tail -f /var/log/nginx/error.log
```

### Check SSL
```bash
# Test SSL configuration
openssl s_client -connect mcp.proethica.org:443 -servername mcp.proethica.org
```

## Expected Results

After setup:
- ✅ http://mcp.proethica.org/health → redirects to HTTPS
- ✅ https://mcp.proethica.org/health → `{"status": "ok", "message": "Ontology MCP server is running"}`
- ✅ Rate limiting in place
- ✅ Security headers configured
- ✅ SSL A+ rating

## Notes

- The MCP server runs on port 5002 internally
- Nginx proxies external traffic from 80/443 to 5002
- CORS is configured for proethica.org domains
- Rate limiting prevents abuse
- Security headers protect against common attacks