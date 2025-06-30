# MCP Server Deployment Best Practices

## Current State Analysis

### Server Configuration
- **Server**: DigitalOcean droplet (209.38.62.85)
- **Repository Location**: `/home/chris/proethica-repo` (develop branch)
- **MCP Location**: `/home/chris/proethica-mcp/`
- **Current Branch**: `develop` (not `simple` as scripts expect)
- **MCP Port**: 5002
- **Status**: MCP server not currently running

### Key Issues Identified
1. **No systemd service**: MCP runs manually via shell script
2. **User space deployment**: Running in home directory as user `chris`
3. **No nginx proxy**: mcp.proethica.org not configured
4. **Branch mismatch**: Scripts expect `simple` branch, repo is on `develop`
5. **Manual process**: No automated deployment or monitoring

## Recommended Architecture

### Directory Structure
```
/opt/proethica-mcp/                 # Production MCP server
├── current/                        # Symlink to active release
├── releases/                       # Versioned releases
│   └── 20250108_120000/           # Timestamp-based releases
├── shared/                         # Shared between releases
│   ├── .env                       # Environment variables
│   ├── logs/                      # Application logs
│   └── data/                      # Persistent data
├── scripts/                        # Deployment scripts
└── config/                         # Configuration files
    ├── mcp.env                    # MCP environment
    └── nginx.conf                 # Nginx snippets

/home/chris/proethica-repo/         # Git repository (development)
```

### User and Permissions
```bash
# Create dedicated user
sudo useradd -r -s /bin/bash -d /opt/proethica-mcp proethica-mcp

# Directory permissions
sudo chown -R proethica-mcp:proethica-mcp /opt/proethica-mcp
sudo chmod 750 /opt/proethica-mcp
```

## Step-by-Step Implementation Plan

### Phase 1: Prepare Infrastructure (Day 1)

#### 1.1 Create Directory Structure
```bash
# Create directories
sudo mkdir -p /opt/proethica-mcp/{releases,shared/{logs,data},scripts,config}

# Create service user
sudo useradd -r -s /bin/bash -d /opt/proethica-mcp proethica-mcp
sudo usermod -a -G proethica-mcp chris  # Allow chris to deploy

# Set permissions
sudo chown -R proethica-mcp:proethica-mcp /opt/proethica-mcp
sudo chmod -R 750 /opt/proethica-mcp
sudo chmod 770 /opt/proethica-mcp/releases  # Allow deployments
```

#### 1.2 Create Systemd Service
```ini
# /etc/systemd/system/proethica-mcp.service
[Unit]
Description=ProEthica MCP Server
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=proethica-mcp
Group=proethica-mcp
WorkingDirectory=/opt/proethica-mcp/current
Environment="PATH=/opt/proethica-mcp/current/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/opt/proethica-mcp/shared/.env
ExecStart=/opt/proethica-mcp/current/venv/bin/python mcp/http_ontology_mcp_server.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/proethica-mcp/shared/logs/mcp.log
StandardError=append:/opt/proethica-mcp/shared/logs/mcp-error.log

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/proethica-mcp/shared

[Install]
WantedBy=multi-user.target
```

#### 1.3 Configure Nginx
```nginx
# /etc/nginx/sites-available/mcp.proethica.org
server {
    listen 80;
    server_name mcp.proethica.org;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name mcp.proethica.org;

    # SSL (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/mcp.proethica.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.proethica.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=mcp_api:10m rate=30r/m;
    limit_req zone=mcp_api burst=10 nodelay;

    # Logging
    access_log /var/log/nginx/mcp.proethica.org.access.log;
    error_log /var/log/nginx/mcp.proethica.org.error.log;

    location / {
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
        
        # CORS headers (if needed)
        add_header Access-Control-Allow-Origin "https://proethica.org" always;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Authorization, Content-Type" always;
    }

    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:5002/health;
    }
}
```

### Phase 2: Deployment Script (Day 1-2)

#### 2.1 Create Deployment Script
```bash
#!/bin/bash
# /opt/proethica-mcp/scripts/deploy.sh

set -e

# Configuration
REPO_URL="https://github.com/cr625/proethica.git"
BRANCH="${1:-develop}"
DEPLOY_USER="proethica-mcp"
DEPLOY_BASE="/opt/proethica-mcp"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RELEASE_DIR="$DEPLOY_BASE/releases/$TIMESTAMP"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}ProEthica MCP Deployment${NC}"
echo -e "Branch: $BRANCH"
echo -e "Timestamp: $TIMESTAMP"

# Clone repository
echo -e "${YELLOW}Cloning repository...${NC}"
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$RELEASE_DIR"

# Setup Python environment
echo -e "${YELLOW}Setting up Python environment...${NC}"
cd "$RELEASE_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-mcp.txt || pip install -r requirements.txt

# Copy shared files
echo -e "${YELLOW}Linking shared files...${NC}"
ln -s "$DEPLOY_BASE/shared/.env" "$RELEASE_DIR/.env"
ln -s "$DEPLOY_BASE/shared/logs" "$RELEASE_DIR/logs"

# Test import
echo -e "${YELLOW}Testing MCP server...${NC}"
python -c "import sys; sys.path.insert(0, 'mcp'); from http_ontology_mcp_server import *"

# Update symlink
echo -e "${YELLOW}Updating current symlink...${NC}"
ln -sfn "$RELEASE_DIR" "$DEPLOY_BASE/current"

# Restart service
echo -e "${YELLOW}Restarting service...${NC}"
sudo systemctl restart proethica-mcp

# Health check
echo -e "${YELLOW}Health check...${NC}"
sleep 5
if curl -f http://localhost:5002/health; then
    echo -e "${GREEN}Deployment successful!${NC}"
else
    echo -e "${RED}Health check failed!${NC}"
    exit 1
fi

# Cleanup old releases (keep last 5)
echo -e "${YELLOW}Cleaning up old releases...${NC}"
cd "$DEPLOY_BASE/releases"
ls -1t | tail -n +6 | xargs rm -rf

echo -e "${GREEN}Deployment complete!${NC}"
```

### Phase 3: CI/CD Integration (Day 2-3)

#### 3.1 GitHub Actions Workflow
```yaml
# .github/workflows/deploy-mcp.yml
name: Deploy MCP Server

on:
  push:
    branches: [develop, main]
    paths:
      - 'mcp/**'
      - 'requirements-mcp.txt'
      - '.github/workflows/deploy-mcp.yml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to production
      uses: appleboy/ssh-action@v0.1.5
      with:
        host: ${{ secrets.DEPLOY_HOST }}
        username: ${{ secrets.DEPLOY_USER }}
        key: ${{ secrets.DEPLOY_KEY }}
        script: |
          sudo -u proethica-mcp /opt/proethica-mcp/scripts/deploy.sh develop
```

### Phase 4: Security Hardening (Day 3)

#### 4.1 Environment Configuration
```bash
# /opt/proethica-mcp/shared/.env
# MCP Server Configuration
MCP_SERVER_PORT=5002
ENVIRONMENT=production
USE_MOCK_GUIDELINE_RESPONSES=false

# Database
DATABASE_URL=postgresql://proethica_user:SECURE_PASS@localhost:5433/ai_ethical_dm

# API Keys (encrypted at rest)
ANTHROPIC_API_KEY=sk-ant-...
MCP_AUTH_TOKEN=SECURE_RANDOM_TOKEN

# Security
ALLOWED_ORIGINS=https://proethica.org,http://localhost:3000
RATE_LIMIT_PER_MINUTE=60

# Paths
ONTOLOGY_DIR=/opt/proethica-mcp/current/ontologies
LOG_LEVEL=INFO
```

#### 4.2 Firewall Rules
```bash
# Only allow localhost to access MCP port
sudo ufw deny 5002/tcp
sudo ufw allow from 127.0.0.1 to any port 5002

# Allow HTTPS
sudo ufw allow 443/tcp
```

### Phase 5: Monitoring and Logging (Day 4)

#### 5.1 Log Rotation
```bash
# /etc/logrotate.d/proethica-mcp
/opt/proethica-mcp/shared/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 proethica-mcp proethica-mcp
    sharedscripts
    postrotate
        systemctl reload proethica-mcp >/dev/null 2>&1 || true
    endscript
}
```

#### 5.2 Health Monitoring Script
```bash
#!/bin/bash
# /opt/proethica-mcp/scripts/health-check.sh

HEALTH_URL="http://localhost:5002/health"
SLACK_WEBHOOK="your-slack-webhook-url"

if ! curl -sf "$HEALTH_URL" > /dev/null; then
    MESSAGE="MCP Server health check failed at $(date)"
    curl -X POST -H 'Content-type: application/json' \
         --data "{\"text\":\"$MESSAGE\"}" \
         "$SLACK_WEBHOOK"
    
    # Try to restart
    sudo systemctl restart proethica-mcp
fi
```

Add to crontab:
```bash
*/5 * * * * /opt/proethica-mcp/scripts/health-check.sh
```

## Migration Plan

### Step 1: Backup Current Setup
```bash
# Backup current MCP
tar -czf ~/mcp-backup-$(date +%Y%m%d).tar.gz ~/proethica-mcp/

# Document current configuration
ssh digitalocean "cd ~/proethica-repo && git log -5 --oneline" > current-state.txt
```

### Step 2: Test New Setup
1. Deploy to `/opt/proethica-mcp` without stopping current service
2. Run on different port (5003) for testing
3. Verify all functionality works
4. Switch nginx to new service

### Step 3: Cutover
1. Update nginx to point to new service
2. Stop old service
3. Monitor logs for issues
4. Keep old setup for 1 week as fallback

## Best Practices Summary

1. **Infrastructure as Code**: All configuration in git
2. **Atomic Deployments**: Full release directories, symlink switching
3. **Zero-Downtime**: Health checks before switching
4. **Security First**: Dedicated user, minimal permissions, encrypted secrets
5. **Monitoring**: Health checks, log aggregation, alerts
6. **Rollback Ready**: Keep multiple releases, quick rollback capability

## Quick Commands

```bash
# Deploy
sudo -u proethica-mcp /opt/proethica-mcp/scripts/deploy.sh develop

# Check status
sudo systemctl status proethica-mcp

# View logs
sudo journalctl -u proethica-mcp -f

# Health check
curl https://mcp.proethica.org/health

# Rollback
cd /opt/proethica-mcp
sudo -u proethica-mcp ln -sfn releases/PREVIOUS_VERSION current
sudo systemctl restart proethica-mcp
```

## Next Steps

1. Review and approve this plan
2. Create SSL certificate for mcp.proethica.org
3. Implement Phase 1 (infrastructure)
4. Test deployment process
5. Migrate from current setup
6. Set up monitoring and alerts