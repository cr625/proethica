# ProEthica CI/CD Implementation Plan

## Overview
This plan outlines the complete CI/CD setup for ProEthica, addressing server restructuring, deployment automation, database synchronization, and development workflow improvements.

## 1. Server Directory Restructuring

### Current Issues
- Flask app in `/var/www/proethica` requires sudo for updates
- MCP server in `/home/chris/proethica-mcp` has different permissions
- Potential permission conflicts during automated deployments

### Recommended Structure
```
/home/chris/proethica/
├── app/              # Main Flask application (moved from /var/www)
├── mcp/              # MCP server (already here)
├── deployments/      # Deployment scripts and configs
├── backups/          # Automated backups
├── logs/             # Application logs
└── nginx/            # Nginx configurations
```

### Migration Steps
1. **Create unified directory structure**:
   ```bash
   mkdir -p /home/chris/proethica/{deployments,logs,nginx}
   ```

2. **Move Flask app** (with zero downtime):
   ```bash
   # Create new systemd service pointing to new location
   sudo cp /home/chris/proethica/server_config/proethica-app.service /etc/systemd/system/
   
   # Update nginx to proxy to new location
   sudo cp /home/chris/proethica/server_config/nginx-proethica.conf /etc/nginx/sites-available/
   
   # Sync application files
   rsync -av /var/www/proethica/ /home/chris/proethica/app/
   
   # Switch over
   sudo systemctl stop proethica-old
   sudo systemctl start proethica-app
   sudo systemctl reload nginx
   ```

3. **Update environment variables**:
   ```bash
   # /home/chris/proethica/.env
   FLASK_APP_ROOT=/home/chris/proethica/app
   MCP_SERVER_ROOT=/home/chris/proethica/mcp
   ```

## 2. SSH Key Setup

### Generate Deployment Key
```bash
# On your WSL development machine
ssh-keygen -t ed25519 -f ~/.ssh/proethica-deploy -C "github-actions@proethica"

# Add to authorized_keys on server
ssh-copy-id -i ~/.ssh/proethica-deploy.pub chris@209.38.62.85

# Test connection
ssh -i ~/.ssh/proethica-deploy chris@209.38.62.85
```

### Configure GitHub Secrets
1. Copy the private key:
   ```bash
   cat ~/.ssh/proethica-deploy
   ```

2. Add to GitHub repository settings:
   - Go to Settings → Secrets and variables → Actions
   - Add new secret: `DROPLET_SSH_KEY` with the private key content
   - Add: `DROPLET_HOST` = `209.38.62.85`
   - Add: `DROPLET_USER` = `chris`

## 3. Database Synchronization Strategy

### Development to Production Sync
1. **Schema Sync Script** (`scripts/sync-db-schema.sh`):
   ```bash
   #!/bin/bash
   # Export schema from dev
   docker exec proethica-postgres pg_dump -U postgres -d ai_ethical_dm --schema-only > schema.sql
   
   # Apply to production
   ssh $DROPLET_USER@$DROPLET_HOST "psql -U postgres -d ai_ethical_dm" < schema.sql
   ```

2. **Selective Data Sync** (`scripts/sync-db-data.sh`):
   ```bash
   # Sync only reference data (worlds, ontologies, etc.)
   TABLES="worlds ontologies ontology_versions"
   for table in $TABLES; do
     docker exec proethica-postgres pg_dump -U postgres -d ai_ethical_dm -t $table --data-only | \
     ssh $DROPLET_USER@$DROPLET_HOST "psql -U postgres -d ai_ethical_dm"
   done
   ```

3. **Automated Migrations**:
   - Use Alembic for database migrations
   - Run migrations automatically during deployment
   - Keep migration history in git

## 4. Development Environment Configuration

### Use Remote MCP Server
1. **Environment Configuration** (`.env.development`):
   ```bash
   # Use production MCP server from dev
   MCP_SERVER_URL=https://mcp.proethica.org
   MCP_API_KEY=<generate-api-key>
   
   # Or use local MCP with port forwarding
   MCP_SERVER_URL=http://localhost:5002
   ```

2. **SSH Port Forwarding for Development**:
   ```bash
   # Forward remote MCP to local port
   ssh -L 5002:localhost:5002 chris@209.38.62.85
   ```

3. **VS Code Remote Development**:
   - Configure `.vscode/settings.json`:
   ```json
   {
     "remote.SSH.defaultForwardedPorts": [
       {
         "name": "MCP Server",
         "localPort": 5002,
         "remotePort": 5002
       }
     ]
   }
   ```

## 5. GitHub Actions Workflows

### Main Deployment Workflow
Already created at `.github/workflows/deploy-mcp.yml` with:
- Automatic deployment on push to main/develop
- Manual deployment with environment selection
- Zero-downtime deployment
- Automatic rollback on failure

### Database Migration Workflow
Create `.github/workflows/db-migrate.yml`:
```yaml
name: Database Migration
on:
  workflow_dispatch:
    inputs:
      migration:
        description: 'Migration to run'
        required: true
        type: choice
        options:
          - sync-schema
          - sync-reference-data
          - run-alembic

jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run migration
        run: |
          case "${{ inputs.migration }}" in
            sync-schema) ./scripts/sync-db-schema.sh ;;
            sync-reference-data) ./scripts/sync-db-data.sh ;;
            run-alembic) ./scripts/run-alembic-migration.sh ;;
          esac
```

## 6. Implementation Timeline

### Phase 1: Preparation (Week 1)
- [ ] Set up SSH keys and GitHub secrets
- [ ] Create backup of current production setup
- [ ] Test workflows in staging environment

### Phase 2: Server Restructuring (Week 2)
- [ ] Move Flask app to home directory
- [ ] Update systemd services
- [ ] Update nginx configuration
- [ ] Test zero-downtime deployment

### Phase 3: Database Sync (Week 3)
- [ ] Implement schema sync scripts
- [ ] Set up Alembic migrations
- [ ] Test data synchronization

### Phase 4: Full CI/CD (Week 4)
- [ ] Enable all GitHub Actions workflows
- [ ] Set up monitoring and alerts
- [ ] Document processes for team

## 7. Monitoring and Maintenance

### Health Checks
- MCP server: `https://mcp.proethica.org/health`
- Flask app: `https://proethica.org/api/health`
- Database: Connection pool monitoring

### Automated Backups
```bash
# Daily backup cron job
0 2 * * * /home/chris/proethica/scripts/backup-all.sh
```

### Log Aggregation
- Centralize logs in `/home/chris/proethica/logs/`
- Rotate logs daily with logrotate
- Monitor for errors with fail2ban

## 8. Security Considerations

### API Key Management
- Generate API keys for MCP server access
- Store in GitHub secrets for CI/CD
- Rotate keys quarterly

### Network Security
- Restrict SSH to GitHub Actions IPs
- Use firewall rules for service ports
- Enable fail2ban for brute force protection

### SSL/TLS
- Auto-renew Let's Encrypt certificates
- Monitor certificate expiration
- Use strong cipher suites

## Next Steps

1. **Immediate Actions**:
   - Generate and configure SSH keys
   - Run `./scripts/setup-github-secrets.sh`
   - Test manual deployment workflow

2. **This Week**:
   - Begin server restructuring
   - Create database sync scripts
   - Test in staging environment

3. **Ongoing**:
   - Monitor deployment metrics
   - Optimize deployment times
   - Gather team feedback