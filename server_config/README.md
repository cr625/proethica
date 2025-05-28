# Server Configuration and Deployment

This directory contains all scripts and configuration for deploying the ProEthica application and MCP server to production.

## Quick Start

### Deploy MCP Server to Production
```bash
# From your local development machine
./sync-mcp-to-production.sh
```

### Check MCP Server Status
```bash
./check-mcp-status.sh
```

## Production Environment

### Server Details
- **Host**: DigitalOcean Droplet
- **IP**: 209.38.62.85
- **SSH Config**: `digitalocean` (configured in ~/.ssh/config)
- **User**: chris
- **Main App Location**: `/home/chris/proethica`

### Services
1. **MCP Server** (https://mcp.proethica.org)
   - Port: 5002
   - Service: proethica-mcp.service
   - Config: /etc/proethica/mcp.env

2. **Main Flask App** (https://proethica.org) - Currently outdated
   - Port: 5000
   - Service: proethica.service
   - Location: /var/www/proethica (old)

3. **PostgreSQL Database**
   - Service: postgresql
   - Database: ai_ethical_dm
   - With pgvector extension

## Deployment Scripts

### For MCP Server

1. **sync-mcp-to-production.sh** (Run locally)
   - Pushes current branch to GitHub
   - SSHs to server and runs deployment
   - Performs health check

2. **deploy-mcp-guidelines.sh** (Runs on server)
   - Backs up current MCP directory
   - Pulls latest from guidelines-enhancement branch
   - Updates dependencies
   - Restarts service
   - Performs health check
   - Rollback on failure

3. **check-mcp-status.sh** (Run locally)
   - Shows local and remote branch info
   - Checks service status
   - Tests health endpoint
   - Shows recent logs

### Legacy Scripts (for reference)
- `deploy-mcp-simple-branch.sh` - Old deployment from 'simple' branch
- `setup-mcp-standalone.sh` - Initial setup script
- Various service restart scripts

## Configuration Files

### Nginx
- **nginx-mcp.conf** - MCP server configuration for mcp.proethica.org
- **nginx-mcp-location.conf** - Location block for MCP endpoints

### Systemd Services
- **proethica-mcp.service** - MCP server service
- **proethica.service** - Main Flask app service (outdated)
- **proethica-postgres.service** - PostgreSQL service wrapper

## Environment Variables

MCP server expects these in `/etc/proethica/mcp.env`:
```bash
FLASK_ENV=production
MCP_PORT=5002
DATABASE_URL=postgresql://proethica:password@localhost/ai_ethical_dm
ANTHROPIC_API_KEY=your-key-here
PYTHONPATH=/home/chris/proethica
```

## Deployment Workflow

1. **Development**: Work on `guidelines-enhancement` branch locally
2. **Test**: Test MCP server locally on port 5001
3. **Deploy**: Run `./sync-mcp-to-production.sh`
4. **Verify**: Run `./check-mcp-status.sh`
5. **Use**: Access at https://mcp.proethica.org

## Troubleshooting

### Common Issues

1. **Service won't start**
   ```bash
   ssh digitalocean
   sudo journalctl -u proethica-mcp -f
   ```

2. **Port conflict**
   ```bash
   sudo netstat -tlnp | grep 5002
   ```

3. **Permission issues**
   - MCP runs as user 'chris', not 'www-data'
   - Check file ownership in /home/chris/proethica

4. **Database connection**
   - Ensure PostgreSQL is running
   - Check credentials in /etc/proethica/mcp.env

### Rollback Procedure

If deployment fails:
1. Backups are stored in `/home/chris/backups/mcp/`
2. The deployment script auto-rollback on failure
3. Manual rollback:
   ```bash
   cd /home/chris/proethica
   tar -xzf /home/chris/backups/mcp/mcp_backup_TIMESTAMP.tar.gz -C .
   sudo systemctl restart proethica-mcp
   ```

## Security Notes

1. **API Keys**: Never commit API keys. Store in environment files
2. **SSL**: Managed by Let's Encrypt via Nginx
3. **Firewall**: Only ports 80, 443, and 22 are open
4. **Rate Limiting**: Configured in Nginx (100 req/min)

## Future Improvements

1. **CI/CD Pipeline**: Automate with GitHub Actions
2. **Blue-Green Deployment**: Zero-downtime updates
3. **Monitoring**: Add Prometheus/Grafana
4. **Staging Environment**: Test before production
5. **Main App Update**: Bring Flask app up to date with guidelines-enhancement branch

## Dependencies

The following Python packages are required:
- PyPDF2
- python-docx
- beautifulsoup4
- anthropic
- langchain_anthropic
