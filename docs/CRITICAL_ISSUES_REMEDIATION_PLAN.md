# Critical Issues Remediation Plan

## Executive Summary
This plan addresses the 3 critical issues identified in the MCP deployment infrastructure:
1. Repository fragmentation
2. Branch divergence crisis  
3. Security exposure

**Timeline**: 2-3 days for critical fixes, 1 week for complete remediation  
**Risk Level**: High - requires careful execution to avoid downtime  
**Prerequisites**: Database backup, current process documentation

---

## 🔴 CRITICAL ISSUE #1: Repository Fragmentation

### Problem
- Production MCP runs from `/home/chris/proethica-mcp/` (not git-tracked)
- Source code in `/home/chris/proethica-repo/` (git-tracked, develop branch)
- Manual file copying creates configuration drift

### Solution Strategy: Git-Based Deployment

#### Phase 1A: Immediate Consolidation (Day 1, 2-3 hours)

**Step 1: Backup Current State**
```bash
# Create emergency backup
sudo tar -czf /tmp/mcp-backup-$(date +%Y%m%d-%H%M%S).tar.gz \
  /home/chris/proethica-mcp/ \
  /home/chris/proethica-repo/mcp/

# Document current process PID for rollback
ps aux | grep mcp > /tmp/current-mcp-processes.txt
```

**Step 2: Consolidate to Git Repository**
```bash
# Stop current MCP service
pkill -f "python3 mcp/http_ontology_mcp_server.py"

# Copy unique configs from deployment to source repo
cp /home/chris/proethica-mcp/mcp.env /home/chris/proethica-repo/mcp/mcp.env.production
cp /home/chris/proethica-mcp/start-mcp.sh /home/chris/proethica-repo/mcp/scripts/
cp /home/chris/proethica-mcp/logs/*.log /home/chris/proethica-repo/mcp/logs/ 2>/dev/null || true

# Create symlink for transition period
mv /home/chris/proethica-mcp /home/chris/proethica-mcp.backup
ln -s /home/chris/proethica-repo /home/chris/proethica-mcp

# Test startup from git location
cd /home/chris/proethica-repo/mcp
./start-mcp.sh
```

**Step 3: Validate Migration**
```bash
# Health check
curl -f http://localhost:5002/health || echo "FAILED - Rollback needed"

# Process verification
ps aux | grep "http_ontology_mcp_server.py" | grep -v grep
```

**Rollback Procedure (if needed)**
```bash
# Stop new service
pkill -f "python3 mcp/http_ontology_mcp_server.py"

# Restore original
rm /home/chris/proethica-mcp
mv /home/chris/proethica-mcp.backup /home/chris/proethica-mcp

# Restart original service
cd /home/chris/proethica-mcp && ./start-mcp.sh
```

#### Phase 1B: Deployment Automation (Day 1, 1-2 hours)

**Create Proper Deployment Script**
```bash
# /home/chris/proethica-repo/mcp/deployment/deploy-production.sh
#!/bin/bash
set -euo pipefail

REPO_DIR="/home/chris/proethica-repo"
MCP_DIR="$REPO_DIR/mcp"
BRANCH="develop"  # Current production branch

echo "🚀 Deploying MCP Server from git repository..."

# Ensure we're on correct branch
cd "$REPO_DIR"
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

# Stop current service
echo "🛑 Stopping current MCP service..."
pkill -f "http_ontology_mcp_server.py" || true
sleep 2

# Start new service
echo "🔄 Starting MCP service..."
cd "$MCP_DIR"
nohup python3 http_ontology_mcp_server.py > logs/mcp-$(date +%Y%m%d-%H%M%S).log 2>&1 &

# Health check
echo "🏥 Health check..."
sleep 5
if curl -f http://localhost:5002/health; then
    echo "✅ Deployment successful"
else
    echo "❌ Deployment failed - manual intervention required"
    exit 1
fi
```

---

## 🔴 CRITICAL ISSUE #2: Branch Divergence Crisis

### Problem
- Documentation references "simple" branch (457 commits ahead)
- Current repo has "develop" and "main" branches only
- Deployment scripts expect different branches

### Solution Strategy: Branch Reconciliation

#### Phase 2A: Branch Analysis (Day 1, 30 minutes)

**Investigate Missing Branch**
```bash
cd /home/chris/proethica-repo

# Check if simple branch exists remotely
git ls-remote origin | grep simple

# Check for other repositories that might have simple branch
find /home/chris -name ".git" -type d -exec dirname {} \; | \
  xargs -I {} sh -c 'cd "{}" && echo "=== {} ===" && git branch -a 2>/dev/null | grep simple || true'

# Compare develop vs main
git log --oneline main..develop | wc -l
git log --oneline develop..main | wc -l
```

#### Phase 2B: Branch Strategy Decision (Day 1, 1 hour)

**Option A: Use Develop as Production (Recommended)**
- Current MCP is working from develop branch content
- No merge conflicts to resolve
- Fastest path to stability

**Option B: Merge Develop to Main**
- Better long-term for standard git workflow
- Requires testing merged state
- Higher risk of conflicts

**Decision Matrix:**
```
Criteria              | Option A (develop) | Option B (merge)
Risk Level           | Low               | Medium
Time to Resolution   | 30 minutes        | 2-4 hours
Long-term Benefits   | Low               | High
Immediate Stability  | High              | Medium

RECOMMENDATION: Option A for immediate fix, plan Option B for next sprint
```

#### Phase 2C: Update Deployment Scripts (Day 1, 1 hour)

**Standardize All Scripts to Use Develop Branch**
```bash
cd /home/chris/proethica-repo/mcp/deployment

# Update all deployment scripts
sed -i 's/BRANCH="simple"/BRANCH="develop"/g' *.sh
sed -i 's/BRANCH="main"/BRANCH="develop"/g' *.sh
sed -i 's/git checkout simple/git checkout develop/g' *.sh
sed -i 's/git checkout main/git checkout develop/g' *.sh

# Update documentation
sed -i 's/simple branch/develop branch/g' *.md
sed -i 's/`simple`/`develop`/g' *.md
```

---

## 🔴 CRITICAL ISSUE #3: Security Exposure

### Problem
- MCP server exposed to internet with vulnerability scans
- No intrusion detection or rate limiting
- User-space deployment without proper isolation

### Solution Strategy: Security Hardening

#### Phase 3A: Immediate Security Measures (Day 2, 1-2 hours)

**Step 1: Network Protection**
```bash
# Install and configure fail2ban
sudo apt update && sudo apt install -y fail2ban

# Create MCP jail configuration
sudo tee /etc/fail2ban/jail.d/mcp-server.conf << 'EOF'
[mcp-server]
enabled = true
port = 5002
filter = mcp-server
logpath = /home/chris/proethica-repo/mcp/logs/*.log
maxretry = 5
bantime = 3600
findtime = 600
EOF

# Create filter for MCP attacks
sudo tee /etc/fail2ban/filter.d/mcp-server.conf << 'EOF'
[Definition]
failregex = ^.*\[.*\] "GET /\..*" 404 .*$
            ^.*\[.*\] "POST /[^/]*\.php.*" 404 .*$
            ^.*\[.*\] "GET /vendor/.*" 404 .*$
ignoreregex =
EOF

# Start fail2ban
sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
```

**Step 2: Firewall Configuration**
```bash
# Configure UFW firewall
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow necessary services
sudo ufw allow ssh
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS

# Restrict MCP port to local access only
sudo ufw allow from 127.0.0.1 to any port 5002
sudo ufw reload
```

**Step 3: Nginx Reverse Proxy (Production)**
```bash
# Install nginx if not present
sudo apt install -y nginx

# Create secure MCP proxy configuration
sudo tee /etc/nginx/sites-available/mcp-secure << 'EOF'
server {
    listen 443 ssl http2;
    server_name mcp.proethica.org;
    
    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/mcp.proethica.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.proethica.org/privkey.pem;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self'" always;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=mcp:10m rate=10r/m;
    limit_req zone=mcp burst=5 nodelay;
    
    # Proxy to MCP server
    location / {
        proxy_pass http://127.0.0.1:5002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Block common attack vectors
    location ~ /\. {
        deny all;
        return 404;
    }
    
    location ~ \.(php|asp|jsp|cgi)$ {
        deny all;
        return 404;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name mcp.proethica.org;
    return 301 https://$server_name$request_uri;
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/mcp-secure /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

#### Phase 3B: Process Isolation (Day 2, 2-3 hours)

**Step 1: Create Dedicated Service User**
```bash
# Create MCP service user
sudo useradd -r -s /bin/false -d /opt/proethica-mcp proethica-mcp

# Create proper directory structure
sudo mkdir -p /opt/proethica-mcp/{app,config,logs,data}
sudo chown -R proethica-mcp:proethica-mcp /opt/proethica-mcp
```

**Step 2: Systemd Service Creation**
```bash
# Create systemd service file
sudo tee /etc/systemd/system/proethica-mcp.service << 'EOF'
[Unit]
Description=ProEthica MCP Server
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=proethica-mcp
Group=proethica-mcp
WorkingDirectory=/home/chris/proethica-repo/mcp
ExecStart=/usr/bin/python3 http_ontology_mcp_server.py
ExecReload=/bin/kill -USR1 $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=proethica-mcp

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/chris/proethica-repo/mcp/logs

# Environment
Environment=PYTHONPATH=/home/chris/proethica-repo
EnvironmentFile=/home/chris/proethica-repo/mcp/mcp.env.production

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable proethica-mcp
sudo systemctl start proethica-mcp
sudo systemctl status proethica-mcp
```

---

## 🛡️ Risk Mitigation & Rollback Plans

### Pre-Execution Checklist
- [ ] Database backup completed
- [ ] Current MCP process documented
- [ ] Emergency contact list ready
- [ ] Rollback scripts tested

### Rollback Triggers
- Health check failures for >5 minutes
- Database connection errors
- Memory/CPU usage >90%
- Any HTTP 5xx errors on health endpoint

### Emergency Procedures

**Complete Rollback to Original State**
```bash
#!/bin/bash
# /tmp/emergency-rollback.sh

echo "🚨 EMERGENCY ROLLBACK INITIATED"

# Stop all new services
sudo systemctl stop proethica-mcp 2>/dev/null || true
pkill -f "http_ontology_mcp_server.py" || true

# Restore original deployment
if [ -d "/home/chris/proethica-mcp.backup" ]; then
    rm -f /home/chris/proethica-mcp
    mv /home/chris/proethica-mcp.backup /home/chris/proethica-mcp
    cd /home/chris/proethica-mcp
    ./start-mcp.sh
    echo "✅ Original service restored"
else
    echo "❌ Backup not found - manual intervention required"
fi

# Health check
sleep 10
if curl -f http://localhost:5002/health; then
    echo "✅ Rollback successful"
else
    echo "❌ Rollback failed - critical manual intervention required"
fi
```

---

## 📋 Execution Timeline

### Day 1: Repository & Branch Issues (4-6 hours)
- **09:00-10:00**: Backup and risk assessment
- **10:00-12:00**: Repository consolidation (Phase 1A)
- **13:00-14:00**: Deployment automation (Phase 1B)  
- **14:00-15:00**: Branch analysis and standardization (Phase 2A-C)
- **15:00-16:00**: Testing and validation

### Day 2: Security Hardening (4-5 hours)  
- **09:00-11:00**: Network security measures (Phase 3A)
- **11:00-14:00**: Process isolation setup (Phase 3B)
- **14:00-15:00**: Security testing and validation

### Day 3: Monitoring & Documentation (2-3 hours)
- **09:00-10:00**: Health monitoring setup
- **10:00-11:00**: Documentation updates
- **11:00-12:00**: Team handover and training

---

## ✅ Success Criteria

### Technical Validation
- [ ] MCP server runs from git repository location
- [ ] Single source of truth for all deployments
- [ ] All deployment scripts use consistent branch
- [ ] Security scans blocked by fail2ban
- [ ] Service runs under dedicated user account
- [ ] Automated health monitoring active

### Operational Validation  
- [ ] Zero-downtime deployment process
- [ ] Emergency rollback tested and documented
- [ ] Team can execute deployments independently
- [ ] Monitoring alerts configured and tested

### Performance Validation
- [ ] Response time <500ms for health endpoint
- [ ] Memory usage <1GB under normal load
- [ ] No HTTP errors in logs for 24 hours post-deployment

---

## 📞 Support & Escalation

### Immediate Support
- **Technical Issues**: Check logs in `/home/chris/proethica-repo/mcp/logs/`
- **Service Issues**: `sudo systemctl status proethica-mcp`
- **Security Issues**: `sudo fail2ban-client status`

### Escalation Path
1. **Level 1**: Execute rollback procedures
2. **Level 2**: Contact system administrator  
3. **Level 3**: Database team for data integrity issues

---

**Document Version**: 1.0  
**Created**: June 8, 2025  
**Owner**: DevOps Team  
**Review Date**: June 15, 2025