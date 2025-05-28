# ProEthica MCP Server Deployment Guide

## Overview

This directory contains the deployment infrastructure for the ProEthica MCP (Model Context Protocol) server. The MCP server provides ontology and guideline analysis capabilities accessible via HTTPS at mcp.proethica.org.

## Current Production Setup

### Infrastructure
- **Server**: DigitalOcean Droplet (209.38.62.85)
- **Domain**: mcp.proethica.org (HTTPS with Let's Encrypt)
- **SSH Access**: `ssh digitalocean` (configured in ~/.ssh/config)

### Deployment Details
- **Location**: `/home/chris/proethica/` (home directory, NOT /var/www/)
- **Port**: 5002 (production), 5001 (local development)
- **User**: chris (not www-data)
- **Service**: Manual process management (no systemd service currently)

### Branch Status (CRITICAL)
- **Production Branch**: `simple` (457 commits ahead of main)
- **Development Branch**: `guidelines-enhancement` (your current branch)
- **Main Branch**: Outdated, DO NOT deploy from main

## Quick Start Guide

### Check Server Status
```bash
# From local machine
./health-check.sh production
```

### Deploy from Simple Branch (Current Process)
```bash
# From local machine - in mcp/deployment/ directory
./deploy-mcp-simple-branch.sh production
```

### Manual Deployment (Emergency)
```bash
ssh digitalocean
cd /home/chris/proethica/ai-ethical-dm
git checkout simple  # or guidelines-enhancement
git pull origin simple
cd /home/chris/proethica/mcp-server/current
pkill -f enhanced_ontology
nohup python enhanced_ontology_server_with_guidelines.py > ../logs/mcp.log 2>&1 &
```

## Directory Structure

### Production Server Layout
```
/home/chris/proethica/              # Home directory deployment
├── ai-ethical-dm/                  # Repository clone
│   └── mcp/                        # MCP server code
└── mcp-server/                     # Deployment directory
    ├── current/                    # Symlink to active release
    ├── releases/                   # Versioned releases
    │   ├── 20250124_143022/
    │   └── 20250124_162318/
    ├── config/                     # Configuration files
    └── logs/                       # Server logs
```

### Local Development
```
ai-ethical-dm/
├── mcp/                            # MCP server code
│   ├── deployment/                 # Deployment scripts (this directory)
│   ├── enhanced_ontology_server_with_guidelines.py
│   └── modules/                    # MCP modules
└── server_config/                  # Legacy config (archived)
    └── archived/                   # Outdated files
```

## Deployment Scripts

### Active Scripts
1. **deploy-mcp-simple-branch.sh**
   - Deploys from 'simple' branch to production
   - Handles versioned releases with rollback
   - Includes health checks

2. **health-check.sh**
   - Comprehensive health monitoring
   - Tests all MCP endpoints
   - Monitors system resources

### Planned Scripts
- **deploy-mcp-guidelines.sh** - For deploying guidelines-enhancement branch (TODO)

## Configuration

### Environment Variables
Required in `/home/chris/proethica/mcp-server/config/.env`:
```bash
MCP_SERVER_PORT=5002
DATABASE_URL=postgresql://proethica:password@localhost/ai_ethical_dm
ANTHROPIC_API_KEY=your-key-here
USE_MOCK_GUIDELINE_RESPONSES=false
ENVIRONMENT=production
```

### Nginx Configuration
The MCP server is proxied through Nginx:
- Domain: mcp.proethica.org
- SSL: Let's Encrypt auto-renewal
- Rate limiting: 100 requests/minute
- Proxy to: localhost:5002

## Health Monitoring

### Endpoints
- `/health` - Basic server health
- `/list_tools` - MCP tools availability
- `/ontology/sources` - Ontology system status
- `/guidelines/analyze` - Guidelines functionality

### Monitoring Commands
```bash
# Full health check
./health-check.sh production

# Quick status check
curl https://mcp.proethica.org/health

# View logs
ssh digitalocean 'tail -f /home/chris/proethica/mcp-server/logs/mcp_*.log'

# Check process
ssh digitalocean 'ps aux | grep enhanced_ontology'
```

## Troubleshooting

### Common Issues

1. **Server Not Responding**
   ```bash
   ssh digitalocean
   cd /home/chris/proethica/mcp-server/current
   pkill -f enhanced_ontology
   nohup python enhanced_ontology_server_with_guidelines.py &
   ```

2. **Wrong Branch Deployed**
   ```bash
   ssh digitalocean
   cd /home/chris/proethica/ai-ethical-dm
   git branch  # Check current branch
   git checkout simple  # or guidelines-enhancement
   git pull
   ```

3. **Port Already in Use**
   ```bash
   ssh digitalocean
   netstat -tlnp | grep 5002
   pkill -f "python.*5002"
   ```

4. **Database Connection Issues**
   - Check PostgreSQL is running: `sudo systemctl status postgresql`
   - Verify credentials in .env file
   - Check pgvector extension is installed

### Rollback Procedure
```bash
# Automatic rollback happens on deployment failure
# Manual rollback:
ssh digitalocean
cd /home/chris/proethica/mcp-server
ls -la releases/  # List available versions
ln -sfn releases/PREVIOUS_VERSION current
cd current && pkill -f enhanced_ontology
nohup python enhanced_ontology_server_with_guidelines.py &
```

## Security Considerations

1. **API Keys**: Store in .env files, never commit
2. **Access**: SSH key authentication only
3. **Firewall**: Only ports 22, 80, 443 open
4. **SSL**: Enforced via Nginx
5. **Rate Limiting**: Configured in Nginx

## Development Workflow

### Local Development
1. Work on `guidelines-enhancement` branch
2. Test MCP server locally: 
   ```bash
   cd mcp
   python enhanced_ontology_server_with_guidelines.py
   ```
3. Access at http://localhost:5001

### Testing with Production Data
```bash
# SSH tunnel to production database
ssh -L 5433:localhost:5432 digitalocean

# Set DATABASE_URL to use tunnel
export DATABASE_URL="postgresql://proethica:password@localhost:5433/ai_ethical_dm"
```

### Deployment Process
1. Push changes to GitHub
2. SSH to server and pull changes
3. Run deployment script
4. Verify with health check

## Future Improvements

### Immediate Needs
1. **Branch Reconciliation**: Merge or align simple/main/guidelines-enhancement branches
2. **Systemd Service**: Create proper service file for automatic restart
3. **Automated Deployment**: Update GitHub Actions for current branch structure

### Long-term Goals
1. **CI/CD Pipeline**: Automated testing and deployment
2. **Blue-Green Deployment**: Zero-downtime updates
3. **Monitoring**: Prometheus/Grafana integration
4. **Containerization**: Docker deployment option

## Branch Migration Plan

To deploy guidelines-enhancement branch:

1. **Test Deployment**
   ```bash
   # Deploy to parallel instance
   ssh digitalocean
   cd /home/chris/proethica-test
   git clone -b guidelines-enhancement https://github.com/yourusername/ai-ethical-dm.git
   # Test on port 5003
   ```

2. **Create Migration Script**
   - Copy deploy-mcp-simple-branch.sh
   - Update to use guidelines-enhancement branch
   - Test thoroughly

3. **Switch Production**
   - Update Nginx to new port/location
   - Monitor closely
   - Have rollback plan ready

## Support & Contacts

- **Logs**: `/home/chris/proethica/mcp-server/logs/`
- **Config**: `/home/chris/proethica/mcp-server/config/`
- **Health Check**: `./health-check.sh production`
- **SSH Access**: `ssh digitalocean`

## Important Notes

1. **Never deploy from main branch** - It's 457 commits behind
2. **Always run health checks** after deployment
3. **Keep backups** of working releases
4. **Monitor logs** during deployment
5. **Document any changes** to deployment process