# MCP Server Deployment & Sync Pipeline

This directory contains automated deployment and synchronization tools for the ProEthica MCP server.

## 📚 Consolidated Documentation

**See [README_CONSOLIDATED.md](./README_CONSOLIDATED.md) for the complete deployment guide.**

## ⚠️ Important: Current Branch Status

**The `simple` branch is currently 457 commits ahead of `main`**. All deployments must use the `simple` branch until branches are reconciled.

**Development is happening on `guidelines-enhancement` branch** - deployment scripts for this branch are being developed.

## Overview

The MCP (Model Context Protocol) server provides ontology and guideline analysis capabilities to the ProEthica application. This deployment pipeline ensures the production server stays in sync with the repository while maintaining high availability.

## Current Production Setup

- **Branch**: `simple` (not `main`)
- **MCP Location**: `/home/chris/proethica/` (home directory)
- **Main App Location**: `/var/www/proethica/` (web directory)
- **Port**: 5002
- **User**: `chris` (not `www-data`)

## Files

### Active Deployment Scripts
- **`deploy-mcp-simple-branch.sh`** - Current deployment script using simple branch
- **`health-check.sh`** - Health monitoring and diagnostics
- **`DEPLOYMENT_STRATEGY_REVISED.md`** - Updated strategy addressing branch issues

### Future/Planning Scripts
- **`deploy-mcp-manual.sh`** - Manual deployment script (for use after branch merge)
- **`sync-pipeline-design.md`** - Original technical design
- **`../.github/workflows/deploy-mcp.yml`** - GitHub Actions workflow (needs update for simple branch)

### Legacy Files
- **`deploy-droplet.sh`** - Initial server setup script
- **`auth_improvements.py`** - Security enhancements

## Quick Start

### 1. Manual Deployment (Current Process)

```bash
# Deploy to production from simple branch
./deploy-mcp-simple-branch.sh production
```

### ⚠️ Do NOT use these until branch reconciliation:
```bash
# These assume main branch (currently outdated)
# ./deploy-mcp-manual.sh production  
# GitHub Actions deployment
```

### 2. Health Check

```bash
# Check production server
./health-check.sh production

# Check local development server
./health-check.sh local
```

### 3. Automated Deployment

Automatic deployment triggers on:
- Push to `main` branch with changes in `mcp/` directory
- Manual trigger via GitHub Actions

## Deployment Architecture

### Directory Structure (Production - Current Reality)
```
/home/chris/proethica/              # Chris's home directory deployment
├── ai-ethical-dm/                  # Repository (simple branch)
└── mcp-server/                     # MCP server deployment
    ├── current/                    # Symlink to active release
    ├── releases/                   # Versioned releases
    │   ├── 20250124_143022/
    │   ├── 20250124_151045/
    │   └── 20250124_162318/
    ├── config/                     # Configuration files
    └── logs/                       # Server logs

/var/www/proethica/                 # Web server directory (separate)
└── ai-ethical-dm/                  # Main web application (if needed)
```

### Zero-Downtime Deployment Process

1. **Validation**: Syntax check and dependency validation
2. **Package**: Create new release directory with updated files
3. **Test**: Start server on alternate port and health check
4. **Switch**: Stop old server, update symlink, start new server
5. **Verify**: Final health check and cleanup old releases

## Configuration

### Environment Variables

Production server requires these environment variables in `.env`:

```bash
MCP_SERVER_PORT=5002
USE_MOCK_GUIDELINE_RESPONSES=false
DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
ANTHROPIC_API_KEY=your-anthropic-api-key
MCP_AUTH_TOKEN=your-secure-token
ENVIRONMENT=production
```

### GitHub Secrets (for automated deployment)

Required secrets in GitHub repository settings:

- `SSH_PRIVATE_KEY` - SSH key for server access
- `SSH_HOST` - Server hostname (proethica.org)
- `SSH_USER` - SSH username (chris)
- `ANTHROPIC_API_KEY` - Anthropic API key
- `MCP_AUTH_TOKEN` - MCP authentication token

## Monitoring & Health Checks

### Health Check Endpoints

- **`/health`** - Basic server health
- **`/list_tools`** - MCP tools availability
- **`/ontology/sources`** - Ontology system status
- **`/guidelines/analyze`** - Guidelines functionality

### Health Check Script Features

- **Connectivity**: Basic HTTP connectivity test
- **Functionality**: MCP and ontology endpoint validation
- **Performance**: Response time measurement
- **System Resources**: CPU, memory, and process monitoring

### Example Health Check Output

```bash
🏥 ProEthica MCP Server Health Check
====================================
Environment: production

🌐 Basic Connectivity
  Health endpoint... ✅ OK

🧠 MCP Functionality
  List tools endpoint... ✅ OK
  List resources endpoint... ✅ OK

🔗 Ontology Endpoints
  Ontology sources... ✅ OK
  Ontology entities... ✅ OK

📋 Guidelines Functionality
  Guidelines analysis... ✅ OK

⚡ Performance Check
  Response time... ✅ 245ms

🖥️ Server Status
  SSH connectivity... ✅ OK
  MCP process status... ✅ Running (1 processes)
  System load... ✅ 0.5
  Memory usage... ✅ 45.2%

📊 Health Check Summary
=======================
✅ All checks passed - MCP server is healthy!
```

## Troubleshooting

### Common Issues

1. **Server not responding**
   ```bash
   ssh chris@proethica.org 'cd /home/chris/proethica/mcp-server/current && python enhanced_ontology_server_with_guidelines.py'
   ```

2. **Check server logs**
   ```bash
   ssh chris@proethica.org 'tail -f /home/chris/proethica/mcp-server/logs/mcp_*.log'
   ```

3. **Restart MCP server**
   ```bash
   ./deploy-mcp-manual.sh production
   ```

4. **Health check failed**
   ```bash
   ./health-check.sh production
   ```

### Rollback Procedure

If deployment fails, automatic rollback:

1. Health check failure detected
2. Stop new server
3. Restore previous release symlink
4. Restart previous version
5. Verify rollback success

Manual rollback:
```bash
ssh chris@proethica.org
cd /home/chris/proethica/mcp-server
ln -sfn releases/PREVIOUS_TIMESTAMP current
cd current && pkill -f enhanced_ontology && nohup python enhanced_ontology_server_with_guidelines.py &
```

## Security

### Authentication
- MCP server uses token-based authentication
- Tokens stored securely in GitHub Secrets
- Regular token rotation recommended

### Network Security
- Server runs on port 5002
- Firewall rules limit access
- SSL termination via nginx proxy

### Access Control
- SSH key-based authentication only
- Limited user permissions
- Audit logging enabled

## Development Workflow

### Local Testing
1. Make changes to MCP server code
2. Test locally: `python mcp/enhanced_ontology_server_with_guidelines.py`
3. Run health check: `./mcp/deployment/health-check.sh local`

### Staging Deployment
1. Deploy to staging: `./mcp/deployment/deploy-mcp-manual.sh staging`
2. Test staging server: `./mcp/deployment/health-check.sh staging`

### Production Deployment
1. **Automatic**: Push to main branch (if MCP files changed)
2. **Manual**: Run `./mcp/deployment/deploy-mcp-manual.sh production`
3. **Verify**: Run `./mcp/deployment/health-check.sh production`

## Maintenance

### Regular Tasks
- **Weekly**: Review server logs and performance metrics
- **Monthly**: Rotate authentication tokens
- **Quarterly**: Update system dependencies

### Monitoring Setup
- Health checks run every 5 minutes via cron
- Alerts sent to team on failures
- Performance metrics tracked and graphed

## Critical Issues & Solutions

### Branch Divergence Problem
- **Issue**: `simple` branch is 436 commits ahead of `main`
- **Impact**: Automated deployments from `main` would deploy outdated code
- **Current Solution**: Use `deploy-mcp-simple-branch.sh` for all deployments
- **Long-term Solution**: Merge `simple` into `main` or create separate deployment branch

### Directory Structure Mismatch
- **Issue**: MCP in home directory, main app in /var/www
- **Impact**: Different permissions, security contexts, and deployment processes
- **Current Solution**: Separate deployment scripts for each location
- **Long-term Solution**: Standardize deployment location

### Quick Sync Command (Emergency Use)
```bash
# Direct sync from simple branch (use with caution)
ssh chris@proethica.org '
  cd ~/proethica/ai-ethical-dm && 
  git checkout simple && 
  git pull origin simple && 
  cd ~/proethica/mcp-server/current &&
  source venv/bin/activate &&
  pkill -f enhanced_ontology &&
  nohup python enhanced_ontology_server_with_guidelines.py > ../logs/mcp_emergency.log 2>&1 &
'
```

## GitHub Actions CI/CD

**New!** Automated CI/CD workflows are now available. See `.github/workflows/README.md` for complete documentation.

### Quick Start with GitHub Actions

1. **Set up secrets**: Run `./scripts/setup-github-secrets.sh` to configure required GitHub secrets
2. **Deploy automatically**: Push to `main`, `develop`, or `guidelines-enhancement` branches
3. **Deploy manually**: Use GitHub Actions UI → Deploy MCP Server → Run workflow
4. **Monitor health**: Automated health checks run every 15 minutes

### Available Workflows

- **deploy-mcp.yml**: Production deployment with zero-downtime and rollback
- **test-mcp.yml**: Automated testing for pull requests
- **build-mcp-docker.yml**: Docker image builds
- **monitor-mcp.yml**: Health monitoring with alerting

## Support

For deployment issues:
1. Check GitHub Actions logs if using CI/CD
2. Check the health check output for specific failure points
3. Review server logs for error details
4. Consult the troubleshooting section above
5. Verify you're using the correct branch
6. Contact the development team if issues persist