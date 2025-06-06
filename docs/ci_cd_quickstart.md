# CI/CD Quick Start Guide

## Overview
This guide will get your ProEthica CI/CD pipeline up and running quickly.

## Prerequisites
- WSL development environment
- Digital Ocean droplet access
- GitHub repository access
- Docker and docker-compose installed

## Quick Setup (5 minutes)

### 1. Run the Setup Script
```bash
./scripts/setup-ci-cd.sh
```

This will:
- Generate SSH keys
- Set up directory structure
- Show you the GitHub secrets to configure

### 2. Configure GitHub Secrets
Go to your GitHub repository:
- **Settings** → **Secrets and variables** → **Actions**
- Add the secrets shown by the setup script:
  - `DROPLET_SSH_KEY` (private SSH key)
  - `DROPLET_HOST` (209.38.62.85)
  - `DROPLET_USER` (chris)
  - `MCP_API_KEY` (generated API key)

### 3. Test Deployment
Go to GitHub Actions and manually run the "Deploy MCP Server" workflow.

## Development Workflow

### Use Remote MCP Server
Configure your dev environment to use the production MCP server:
```bash
./scripts/setup-remote-mcp-dev.sh
```

Choose option 1 for direct HTTPS connection to `mcp.proethica.org`.

### Database Synchronization
Sync schema changes to production:
```bash
./scripts/sync-db-schema.sh
```

Sync reference data:
```bash
./scripts/sync-db-data.sh
```

## Deployment Process

### Automatic Deployment
Push to these branches for automatic deployment:
- `main` → Production
- `develop` → Staging  
- `guidelines-enhancement` → Production (current branch)

### Manual Deployment
Go to GitHub Actions → "Deploy MCP Server" → "Run workflow"

## Server Structure (After Migration)

```
/home/chris/proethica/
├── app/              # Flask application (moved from /var/www)
├── mcp/              # MCP server
├── logs/             # All application logs
├── deployments/      # Deployment configs
├── server_config/    # Systemd & nginx configs
└── .env              # Environment variables
```

## Key Files Created

### GitHub Workflows
- `.github/workflows/deploy-mcp.yml` - Main deployment
- `.github/workflows/test-mcp.yml` - Testing
- `.github/workflows/monitor-mcp.yml` - Health monitoring
- `.github/workflows/build-mcp-docker.yml` - Docker builds

### Scripts
- `scripts/setup-ci-cd.sh` - Main setup script
- `scripts/sync-db-schema.sh` - Database schema sync
- `scripts/sync-db-data.sh` - Reference data sync
- `scripts/setup-remote-mcp-dev.sh` - Remote MCP setup

### Configuration
- `server_config/proethica-app.service` - Systemd service
- `server_config/nginx-proethica.conf` - Nginx configuration
- `docs/ci_cd_plan.md` - Complete implementation plan

## Troubleshooting

### SSH Connection Issues
```bash
ssh -i ~/.ssh/proethica-deploy chris@209.38.62.85
```

### Workflow Failures
1. Check GitHub Actions logs
2. Verify secrets are configured
3. Check server health: `https://mcp.proethica.org/health`

### Database Sync Issues
- Check PostgreSQL connection
- Verify table permissions
- Review sync logs

## Next Steps

1. **Week 1**: Set up CI/CD and test workflows
2. **Week 2**: Migrate server structure (see `docs/ci_cd_plan.md`)
3. **Week 3**: Implement database automation
4. **Week 4**: Full production rollout

## Support

For detailed implementation: `docs/ci_cd_plan.md`
For workflow documentation: `.github/workflows/README.md`