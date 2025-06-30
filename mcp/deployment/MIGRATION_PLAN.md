# MCP Server Migration Plan

## Overview
This document outlines the migration from the current user-space deployment to a production-ready architecture.

## Current State
- **Location**: `/home/chris/proethica-mcp/`
- **User**: chris (personal user)
- **Process**: Manual startup script
- **Port**: 5002
- **Branch**: develop (not simple as scripts expect)

## Target State
- **Location**: `/opt/proethica-mcp/`
- **User**: proethica-mcp (dedicated service user)
- **Process**: systemd service
- **Port**: 5002 (internal), 443 (external via nginx)
- **Branch**: develop → main (after consolidation)

## Migration Phases

### Phase 1: Immediate Stabilization (Day 1)
1. **Deploy using quick script**
   ```bash
   chmod +x mcp/deployment/quick-deploy-mcp.sh
   ./mcp/deployment/quick-deploy-mcp.sh digitalocean develop
   ```

2. **Configure nginx**
   ```bash
   # On server
   sudo cp nginx-mcp-ssl.conf /etc/nginx/sites-available/mcp.proethica.org
   sudo ln -s /etc/nginx/sites-available/mcp.proethica.org /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

3. **Setup SSL**
   ```bash
   sudo certbot --nginx -d mcp.proethica.org
   ```

### Phase 2: Infrastructure Setup (Day 2)
1. **Create production structure**
   ```bash
   sudo mkdir -p /opt/proethica-mcp/{releases,shared/{logs,data},scripts,config}
   sudo useradd -r -s /bin/bash -d /opt/proethica-mcp proethica-mcp
   sudo chown -R proethica-mcp:proethica-mcp /opt/proethica-mcp
   ```

2. **Test deployment to new location**
   ```bash
   chmod +x mcp/deployment/deploy-mcp-production.sh
   ./mcp/deployment/deploy-mcp-production.sh
   ```

3. **Run parallel for testing**
   - Keep existing service on 5002
   - Run new service on 5003
   - Test thoroughly

### Phase 3: Service Migration (Day 3)
1. **Install systemd service**
   ```bash
   sudo cp proethica-mcp-modern.service /etc/systemd/system/proethica-mcp.service
   sudo systemctl daemon-reload
   sudo systemctl enable proethica-mcp
   ```

2. **Migrate configuration**
   - Copy working .env to `/opt/proethica-mcp/shared/.env`
   - Update paths and permissions
   - Test service startup

3. **Cutover**
   - Stop old service
   - Start new service
   - Update nginx to point to new service
   - Monitor logs

### Phase 4: Automation (Week 2)
1. **GitHub Actions**
   - Setup deployment keys
   - Configure secrets
   - Enable automated deployment

2. **Monitoring**
   - Setup health checks
   - Configure alerts
   - Log rotation

## Rollback Plan
At each phase, maintain ability to rollback:

1. **Phase 1**: Original start script still works
2. **Phase 2**: Both locations functional
3. **Phase 3**: Keep old setup for 1 week
4. **Phase 4**: Git revert and manual deployment

## Risk Mitigation
- **Database Access**: Ensure new user can access PostgreSQL
- **File Permissions**: Test all file access before cutover
- **API Keys**: Securely transfer all credentials
- **Network Access**: Verify firewall rules

## Success Criteria
- [ ] MCP server accessible at https://mcp.proethica.org
- [ ] Health endpoint responding
- [ ] Logs properly collected
- [ ] Automated deployment working
- [ ] Monitoring in place
- [ ] Documentation updated

## Commands Reference
```bash
# Quick deployment (current setup)
./mcp/deployment/quick-deploy-mcp.sh digitalocean develop

# Production deployment (new setup)
./mcp/deployment/deploy-mcp-production.sh

# Health check
./mcp/deployment/check-mcp-health.sh digitalocean

# Service management
sudo systemctl status proethica-mcp
sudo systemctl restart proethica-mcp
sudo journalctl -u proethica-mcp -f

# Manual testing
curl https://mcp.proethica.org/health
```