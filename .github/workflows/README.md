# GitHub Actions CI/CD Workflows

This directory contains GitHub Actions workflows for continuous integration and deployment of the ProEthica MCP server.

## Workflows Overview

### 1. Deploy MCP Server (`deploy-mcp.yml`)

**Purpose**: Automated deployment of the MCP server to production/staging environments.

**Triggers**:
- Push to `main`, `develop`, or `guidelines-enhancement` branches (when MCP files change)
- Manual workflow dispatch with options for force deployment and environment selection

**Key Features**:
- Zero-downtime deployment with health checks
- Automatic rollback on failure
- Support for multiple branches and environments
- Post-deployment validation
- Keeps last 5 releases for rollback

**Required Secrets**:
- `SSH_PRIVATE_KEY`: SSH key for server access
- `SSH_HOST`: Server hostname (proethica.org)
- `SSH_USER`: SSH username (chris)
- `ANTHROPIC_API_KEY`: Anthropic API key
- `MCP_AUTH_TOKEN`: MCP authentication token
- `DATABASE_URL`: PostgreSQL connection string

### 2. Test MCP Server (`test-mcp.yml`)

**Purpose**: Run tests on MCP server code for pull requests.

**Triggers**:
- Pull requests that modify MCP files
- Manual workflow dispatch

**Key Features**:
- Syntax validation
- Import tests
- Server startup tests
- Endpoint testing
- Code quality checks (linting)
- Security scanning with bandit

### 3. Build MCP Docker Image (`build-mcp-docker.yml`)

**Purpose**: Build and publish Docker images for containerized deployments.

**Triggers**:
- Push to `main` or `develop` branches (when MCP files change)
- Manual workflow dispatch with custom tag option

**Key Features**:
- Multi-architecture builds
- Automatic tagging based on branch/commit
- Push to GitHub Container Registry
- Health check included
- Generates deployment instructions

### 4. Monitor MCP Server (`monitor-mcp.yml`)

**Purpose**: Continuous monitoring of MCP server health.

**Triggers**:
- Every 15 minutes (cron schedule)
- Manual workflow dispatch

**Key Features**:
- Health endpoint checks
- Performance monitoring
- Automatic issue creation on failure
- Issue auto-close on recovery
- Notification hooks (Slack, email, etc.)

### 5. Setup Environment (`setup-env.yml`)

**Purpose**: Create environment configuration files from secrets.

**Triggers**:
- Manual workflow dispatch
- Pull requests
- Push to main/develop branches

**Key Features**:
- Generates `.env` file from GitHub secrets
- Uploads as artifact for download
- Secure handling of sensitive data

## Setup Instructions

### 1. Configure GitHub Secrets

Navigate to Settings → Secrets and variables → Actions, then add:

```bash
# Required for deployment
SSH_PRIVATE_KEY=<your-ssh-private-key>
SSH_HOST=proethica.org
SSH_USER=chris
ANTHROPIC_API_KEY=<your-anthropic-api-key>
MCP_AUTH_TOKEN=<generate-secure-token>
DATABASE_URL=postgresql://user:pass@host:port/db

# Optional for monitoring
MCP_URL=https://mcp.proethica.org
SLACK_WEBHOOK=<your-slack-webhook-url>

# For environment setup
FLASK_APP=run.py
FLASK_ENV=production
SECRET_KEY=<your-secret-key>
# ... (see setup-env.yml for full list)
```

### 2. Generate SSH Key for Deployment

```bash
# Generate new SSH key pair
ssh-keygen -t ed25519 -C "github-actions@proethica" -f deploy_key

# Add public key to server
ssh-copy-id -i deploy_key.pub chris@proethica.org

# Add private key to GitHub secrets as SSH_PRIVATE_KEY
cat deploy_key
```

### 3. Enable Workflows

1. Ensure Actions are enabled in repository settings
2. Workflows will automatically trigger based on their conditions
3. Manual deployments can be triggered from Actions tab

## Usage Examples

### Manual Deployment

1. Go to Actions tab
2. Select "Deploy MCP Server"
3. Click "Run workflow"
4. Select branch and options:
   - Force deploy: Yes/No
   - Environment: production/staging
5. Click "Run workflow"

### Monitoring Setup

The monitoring workflow runs automatically every 15 minutes. To set up notifications:

1. Add notification service credentials to secrets
2. Uncomment relevant notification code in `monitor-mcp.yml`
3. Test by manually triggering the workflow

### Docker Deployment

After the Docker build workflow runs:

```bash
# Pull latest image
docker pull ghcr.io/your-username/ai-ethical-dm-mcp:latest

# Run with environment variables
docker run -d \
  --name proethica-mcp \
  -p 5002:5002 \
  -e MCP_SERVER_PORT=5002 \
  -e DATABASE_URL=$DATABASE_URL \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e MCP_AUTH_TOKEN=$MCP_AUTH_TOKEN \
  ghcr.io/your-username/ai-ethical-dm-mcp:latest
```

## Troubleshooting

### Deployment Failures

1. Check workflow logs in Actions tab
2. Verify all required secrets are set
3. Check server connectivity: `ssh chris@proethica.org`
4. Review deployment logs: `ssh chris@proethica.org 'tail -100 /home/chris/proethica/mcp-server/logs/mcp_*.log'`

### Health Check Failures

1. Check if server is accessible: `curl https://mcp.proethica.org/health`
2. Review server logs for errors
3. Check system resources on server
4. Manually run health check: `./mcp/deployment/health-check.sh production`

### Branch Issues

The deployment currently expects the server to have the deployment branch. If you see branch-related errors:

1. Ensure the branch exists on the remote repository
2. Check that the server can access the branch
3. Consider using the `force_deploy` option

## Best Practices

1. **Test Before Deploy**: Always test changes in a pull request before merging
2. **Monitor After Deploy**: Check the monitoring workflow after deployments
3. **Use Staging First**: Test deployments to staging before production
4. **Keep Secrets Secure**: Rotate tokens and keys regularly
5. **Review Logs**: Check deployment and server logs after each deployment

## Maintenance

### Regular Tasks

- **Weekly**: Review monitoring alerts and close stale issues
- **Monthly**: 
  - Rotate authentication tokens
  - Update GitHub Actions to latest versions
  - Clean up old Docker images
- **Quarterly**: 
  - Review and update deployment scripts
  - Update Python and dependency versions

### Updating Workflows

1. Test workflow changes in a feature branch
2. Use workflow dispatch to test manually
3. Monitor first automated run after merging
4. Document any new secrets or configuration needed

## Support

For issues with CI/CD:

1. Check workflow run logs in GitHub Actions
2. Review this documentation
3. Check deployment scripts in `mcp/deployment/`
4. Contact the development team if issues persist

## Future Enhancements

- [ ] Add staging environment deployment
- [ ] Implement blue-green deployments
- [ ] Add database migration automation
- [ ] Integrate with external monitoring services
- [ ] Add automated rollback triggers
- [ ] Implement canary deployments
- [ ] Add performance benchmarking