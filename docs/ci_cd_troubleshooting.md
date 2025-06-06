# CI/CD Troubleshooting Guide

This document records common issues encountered during CI/CD setup and their solutions for future reference.

## 🔧 GitHub Actions Deployment Issues

### 1. SSH Connection Failures

**Problem**: `Permission denied (publickey)` errors in GitHub Actions

**Symptoms**:
```
ssh chris@209.38.62.85 "ps aux | grep -i deploy"
chris@209.38.62.85: Permission denied (publickey).
```

**Root Cause**: GitHub Actions can't authenticate to the server

**Solution**:
1. Generate SSH key pair:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/proethica-deploy -C "github-actions@proethica"
   ```

2. Add public key to server:
   ```bash
   ssh chris@209.38.62.85
   echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF9kmXx1D/9qK2Z1EZIJ77OAFFNpPf+fHPBQZkNhbG2o github-actions@proethica" >> ~/.ssh/authorized_keys
   ```

3. Add private key to GitHub secrets as `DROPLET_SSH_KEY`

**Prevention**: Test SSH connection before deployment:
```bash
ssh -i ~/.ssh/proethica-deploy chris@209.38.62.85 "echo 'Connection test'"
```

### 2. Environment Variable Issues

**Problem**: Empty variables in deployment script causing git errors

**Symptoms**:
```
Branch: 
Environment: 
fatal: empty string is not a valid pathspec
```

**Root Cause**: GitHub Actions environment variables not passed to deployment script

**Original Bad Approach**:
```yaml
cat > deploy_mcp.sh << 'EOF'  # Single quotes prevent interpolation
```

**Fixed Approach**:
```yaml
cat > deploy_mcp.sh << 'EOF'
#!/bin/bash
DEPLOY_BRANCH="$1"  # Accept as arguments
ENVIRONMENT="$2"
EOF

# Execute with arguments
ssh user@host "bash -s $DEPLOY_BRANCH $ENVIRONMENT" < deploy_mcp.sh
```

**Prevention**: Always test variable interpolation in workflow scripts

### 3. Dependency Issues

**Problem**: `ModuleNotFoundError: No module named 'sqlalchemy'`

**Symptoms**:
```
Traceback (most recent call last):
  File "/home/chris/proethica-mcp/mcp/http_ontology_mcp_server.py", line 10, in <module>
    from sqlalchemy import create_engine
ModuleNotFoundError: No module named 'sqlalchemy'
```

**Root Cause**: `requirements-mcp.txt` missing Flask/SQLAlchemy dependencies

**Solution**: Add missing dependencies to `requirements-mcp.txt`:
```
flask>=2.3.0
sqlalchemy>=2.0.0
flask-sqlalchemy>=3.0.0
psycopg2-binary>=2.9.0
```

**Prevention**: 
- Include all runtime dependencies in requirements files
- Test import validation in workflow before deployment

### 4. Port Configuration Issues

**Problem**: 502 Bad Gateway - nginx can't reach MCP server

**Symptoms**:
```html
<center><h1>502 Bad Gateway</h1></center>
```

**Root Cause**: Port mismatch between server and nginx configuration

**Investigation Steps**:
1. Check server port: `ps aux | grep mcp`
2. Test local access: `curl http://localhost:5001/health`
3. Check environment variables

**Solution**: Ensure correct environment variable name
- **Wrong**: `PORT=5002` (ignored by server)
- **Correct**: `MCP_SERVER_PORT=5002` (used by server)

**Server Code Reference**: `http_ontology_mcp_server.py:18`
```python
PORT = int(os.environ.get("MCP_SERVER_PORT", 5001))
```

### 5. Systemd Service Issues

**Problem**: Service restart requires sudo password

**Symptoms**:
```
sudo: a terminal is required to read the password
```

**Solution**: Configure passwordless sudo for specific commands:
```bash
echo "chris ALL=(ALL) NOPASSWD: /bin/systemctl start proethica-mcp-home.service, /bin/systemctl stop proethica-mcp-home.service, /bin/systemctl restart proethica-mcp-home.service" | sudo tee -a /etc/sudoers
```

**Alternative**: Use manual process management for deployments

## 🏗️ Server Configuration Issues

### 1. Directory Structure Problems

**Problem**: Deployment expects directories that don't exist

**Symptoms**:
```
cp: target '/home/chris/proethica-mcp/mcp/': No such file or directory
```

**Root Cause**: MCP server directory structure not initialized

**Solution**: Create expected directory structure:
```bash
mkdir -p /home/chris/proethica-mcp/{mcp,logs}
cp -r /home/chris/proethica-repo/mcp/* /home/chris/proethica-mcp/mcp/
```

**Current Server Structure**:
```
/home/chris/
├── proethica-repo/          # Git repository clone
├── proethica-mcp/           # Running MCP server
│   ├── mcp/                 # MCP server code
│   ├── mcp-venv/           # Python virtual environment
│   ├── mcp.env             # Environment configuration
│   └── logs/               # Log files
└── mcp-server/             # Deployment releases (future)
```

### 2. Virtual Environment Issues

**Problem**: Python packages not found when server starts

**Root Cause**: Virtual environment not properly created or activated

**Solution**: Ensure proper venv setup:
```bash
cd /home/chris/proethica-mcp
python3 -m venv mcp-venv
./mcp-venv/bin/pip install -r requirements-mcp.txt
```

**Systemd Service Configuration**:
```ini
[Service]
ExecStart=/home/chris/proethica-mcp/mcp-venv/bin/python /home/chris/proethica-mcp/mcp/http_ontology_mcp_server.py
Environment="PATH=/home/chris/proethica-mcp/mcp-venv/bin:..."
```

## 🔍 Testing and Validation

### 1. MCP Server Health Checks

**Basic Health Check**:
```bash
curl -s https://mcp.proethica.org/health
# Expected: {"status": "ok", "message": "Ontology MCP server is running"}
```

**Tool Listing**:
```bash
curl -s -X POST https://mcp.proethica.org/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "list_tools",
    "params": {},
    "id": 1
  }'
# Expected: {"jsonrpc": "2.0", "result": {"tools": ["get_world_entities"]}, "id": 1}
```

**Tool Execution Test**:
```bash
curl -s -X POST https://mcp.proethica.org/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call_tool",
    "params": {
      "name": "get_world_entities",
      "arguments": {}
    },
    "id": 1
  }'
# Expected: Structured JSON with entities data
```

### 2. Service Status Checks

**Systemd Service**:
```bash
systemctl status proethica-mcp-home.service
# Should show: Active: active (running)
```

**Process Check**:
```bash
ps aux | grep mcp
# Should show python process running MCP server
```

**Port Check**:
```bash
ss -tlnp | grep 5002
# Should show listening socket on port 5002
```

## 🚨 Common Error Patterns

### 1. Git Repository Issues

**Branch Mismatch**:
- Problem: Server on wrong branch
- Solution: `git checkout develop && git pull origin develop`

**Repository Not Found**:
- Problem: Wrong path in deployment script
- Solution: Verify `/home/chris/proethica-repo` exists and is git repository

### 2. Workflow File Issues

**Workflow Not Appearing**:
- Problem: GitHub Actions cache
- Solution: Make small change to trigger refresh, wait 2-3 minutes

**Secret Name Mismatches**:
- Check exact secret names in GitHub repository settings
- Common mismatches: `SSH_HOST` vs `DROPLET_HOST`

### 3. Service Startup Failures

**Environment File Issues**:
- Verify `/home/chris/proethica-mcp/mcp.env` exists
- Check `MCP_SERVER_PORT=5002` (not just `PORT=5002`)

**Database Connection Issues**:
- Ensure PostgreSQL service is running
- Check database credentials in environment

## 📋 Quick Recovery Procedures

### 1. Manual MCP Server Restart

```bash
ssh chris@209.38.62.85
sudo systemctl restart proethica-mcp-home.service
systemctl status proethica-mcp-home.service
curl -s https://mcp.proethica.org/health
```

### 2. Full Deployment Reset

```bash
# Run the working simple deployment script
./scripts/simple-deploy-mcp.sh
```

### 3. Emergency Rollback

If new deployment breaks:
```bash
ssh chris@209.38.62.85
cd /home/chris/proethica-repo
git checkout HEAD~1  # Go back one commit
sudo systemctl restart proethica-mcp-home.service
```

## 🎯 Prevention Checklist

Before deploying changes:

- [ ] Test SSH connection: `ssh -i ~/.ssh/proethica-deploy chris@209.38.62.85 "echo test"`
- [ ] Verify dependencies in `requirements-mcp.txt`
- [ ] Test MCP server import locally: `python -c "from mcp.enhanced_ontology_server_with_guidelines import OntologyMCPServer"`
- [ ] Check environment variables in `mcp.env`
- [ ] Validate workflow YAML syntax
- [ ] Test deployment with simple script first: `./scripts/simple-deploy-mcp.sh`

## 📞 Emergency Contacts

- **GitHub Actions**: Check repository Actions tab for detailed logs
- **Server Access**: SSH key location `~/.ssh/proethica-deploy`
- **MCP Health**: https://mcp.proethica.org/health
- **Service Logs**: `journalctl -u proethica-mcp-home.service -f`

---

**Last Updated**: 2025-06-01
**Next Review**: When Flask app CI/CD is implemented