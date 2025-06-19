# ProEthica CI/CD Deployment Plan

## Overview
This plan outlines the steps to implement a complete CI/CD pipeline between your local WSL development environment and the DigitalOcean production server (209.38.62.85).

## Architecture
- **Production Server**: DigitalOcean droplet (209.38.62.85)
- **Domains**: proethica.org (main app), mcp.proethica.org (MCP server)
- **Local Dev**: WSL Ubuntu instance
- **CI/CD**: GitHub Actions
- **Branch Strategy**: `main` → `develop` → `deployment/production`

## Phase 1: Local Environment Tasks (WSL)

### 1.1 Repository Preparation
```bash
# Create deployment branch structure
git checkout -b deployment/production
git push -u origin deployment/production

# Ensure .gitignore includes sensitive files
echo ".env" >> .gitignore
echo "*.pyc" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "venv/" >> .gitignore
git add .gitignore
git commit -m "Update .gitignore for deployment"
```

### 1.2 Create GitHub Actions Workflow
Create `.github/workflows/deploy-production.yml`:
```yaml
name: Deploy to Production

on:
  push:
    branches: [ deployment/production ]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        pytest tests/ -v --cov=app

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/deployment/production'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to DigitalOcean
      uses: appleboy/ssh-action@v0.1.5
      with:
        host: ${{ secrets.DROPLET_HOST }}
        username: ${{ secrets.DROPLET_USER }}
        key: ${{ secrets.DROPLET_SSH_KEY }}
        script: |
          cd /home/chris/proethica
          git pull origin deployment/production
          source venv/bin/activate
          pip install -r requirements.txt
          
          # Run database migrations
          export FLASK_APP=run.py
          flask db upgrade
          
          # Restart services
          sudo systemctl restart proethica-app
          sudo systemctl restart proethica-mcp
          
          # Health check
          sleep 10
          curl -f http://localhost:5000/health || exit 1
          curl -f http://localhost:5002/health || exit 1
```

### 1.3 Create Deployment Scripts
Create `scripts/prepare-deployment.sh`:
```bash
#!/bin/bash
# Prepare code for deployment

echo "Preparing deployment..."

# Run tests
pytest tests/ -v

# Check for uncommitted changes
if [[ -n $(git status -s) ]]; then
    echo "ERROR: Uncommitted changes found"
    exit 1
fi

# Update requirements
pip freeze > requirements.txt

# Create deployment tag
VERSION=$(date +%Y%m%d%H%M%S)
git tag -a "deploy-$VERSION" -m "Deployment $VERSION"
git push origin "deploy-$VERSION"

echo "Ready for deployment: $VERSION"
```

### 1.4 Database Migration Setup
Create `scripts/create-migration.sh`:
```bash
#!/bin/bash
# Create database migration script

# Generate migration SQL
pg_dump -h localhost -U proethica_user -d proethica_db --schema-only > migrations/schema_latest.sql

# Create migration version
VERSION=$(date +%Y%m%d%H%M%S)
cp migrations/schema_latest.sql "migrations/migration_$VERSION.sql"

echo "Migration created: migration_$VERSION.sql"
```

## Phase 2: Remote Server Setup (DigitalOcean)

### 2.1 Initial Server Configuration
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3.11 python3.11-venv python3-pip nginx postgresql postgresql-contrib redis-server git

# Create application user
sudo useradd -m -s /bin/bash proethica
sudo usermod -aG sudo proethica

# Set up directory structure
sudo mkdir -p /home/chris/proethica
sudo mkdir -p /home/chris/proethica-mcp
sudo chown -R chris:chris /home/chris/proethica*
```

### 2.2 PostgreSQL Setup
```bash
# Create database and user
sudo -u postgres psql << EOF
CREATE USER proethica_user WITH PASSWORD 'secure_password';
CREATE DATABASE proethica_db OWNER proethica_user;
GRANT ALL PRIVILEGES ON DATABASE proethica_db TO proethica_user;
EOF

# Configure PostgreSQL for remote connections (if needed)
sudo nano /etc/postgresql/14/main/postgresql.conf
# Set: listen_addresses = 'localhost'

sudo systemctl restart postgresql
```

### 2.3 Nginx Configuration
Create `/etc/nginx/sites-available/proethica`:
```nginx
# Main ProEthica App
server {
    listen 80;
    server_name proethica.org www.proethica.org;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name proethica.org www.proethica.org;

    ssl_certificate /etc/letsencrypt/live/proethica.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/proethica.org/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /home/chris/proethica/app/static;
        expires 30d;
    }
}

# MCP Server
server {
    listen 80;
    server_name mcp.proethica.org;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name mcp.proethica.org;

    ssl_certificate /etc/letsencrypt/live/mcp.proethica.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.proethica.org/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2.4 Systemd Services
Create `/etc/systemd/system/proethica-app.service`:
```ini
[Unit]
Description=ProEthica Flask Application
After=network.target postgresql.service

[Service]
Type=simple
User=chris
Group=chris
WorkingDirectory=/home/chris/proethica
Environment="PATH=/home/chris/proethica/venv/bin"
Environment="FLASK_APP=run.py"
Environment="FLASK_ENV=production"
ExecStart=/home/chris/proethica/venv/bin/python run.py --port 5000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/proethica-mcp.service`:
```ini
[Unit]
Description=ProEthica MCP Server
After=network.target

[Service]
Type=simple
User=chris
Group=chris
WorkingDirectory=/home/chris/proethica-mcp
Environment="PATH=/home/chris/proethica-mcp/venv/bin"
ExecStart=/home/chris/proethica-mcp/venv/bin/python mcp/enhanced_ontology_server_with_guidelines.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2.5 SSL Setup with Let's Encrypt
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificates
sudo certbot --nginx -d proethica.org -d www.proethica.org
sudo certbot --nginx -d mcp.proethica.org

# Auto-renewal
sudo systemctl enable certbot.timer
```

## Phase 3: GitHub Configuration

### 3.1 Set up GitHub Secrets
Go to your repository settings and add these secrets:
- `DROPLET_HOST`: 209.38.62.85
- `DROPLET_USER`: chris
- `DROPLET_SSH_KEY`: (Your SSH private key)
- `ANTHROPIC_API_KEY`: (Your API key)
- `MCP_AUTH_TOKEN`: (Generate a secure token)

### 3.2 SSH Key Setup
On your local machine:
```bash
# Generate deployment key if needed
ssh-keygen -t ed25519 -f ~/.ssh/proethica_deploy -C "deployment@proethica.org"

# Copy public key to server
ssh-copy-id -i ~/.ssh/proethica_deploy.pub chris@209.38.62.85

# Test connection
ssh -i ~/.ssh/proethica_deploy chris@209.38.62.85
```

## Phase 4: Environment Configuration

### 4.1 Production .env file
Create on the server at `/home/chris/proethica/.env`:
```bash
# Flask Configuration
FLASK_APP=run.py
FLASK_ENV=production
SECRET_KEY=your-secure-secret-key

# Database
DATABASE_URL=postgresql://proethica_user:secure_password@localhost/proethica_db

# MCP Server
MCP_SERVER_URL=http://localhost:5002
MCP_AUTH_TOKEN=your-secure-token

# API Keys
ANTHROPIC_API_KEY=your-api-key
OPENAI_API_KEY=your-api-key

# Security
BYPASS_AUTH=false
DEBUG=false
```

## Phase 5: Deployment Testing

### 5.1 Initial Manual Deployment
```bash
# On the server
cd /home/chris/proethica
git clone https://github.com/yourusername/proethica.git .
git checkout deployment/production

# Set up Python environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initialize database
export FLASK_APP=run.py
flask db init
flask db migrate
flask db upgrade

# Start services
sudo systemctl daemon-reload
sudo systemctl enable proethica-app proethica-mcp
sudo systemctl start proethica-app proethica-mcp

# Check status
sudo systemctl status proethica-app
sudo systemctl status proethica-mcp
```

### 5.2 Test CI/CD Pipeline
```bash
# On local machine
git checkout deployment/production
echo "# Test deployment" >> README.md
git add README.md
git commit -m "Test CI/CD deployment"
git push origin deployment/production

# Monitor GitHub Actions for deployment
```

## Phase 6: Monitoring Setup

### 6.1 Health Check Script
Create `/home/chris/proethica/scripts/health-check.sh`:
```bash
#!/bin/bash

# Check Flask app
FLASK_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health)
if [ $FLASK_STATUS -ne 200 ]; then
    echo "Flask app health check failed: $FLASK_STATUS"
    sudo systemctl restart proethica-app
fi

# Check MCP server
MCP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5002/health)
if [ $MCP_STATUS -ne 200 ]; then
    echo "MCP server health check failed: $MCP_STATUS"
    sudo systemctl restart proethica-mcp
fi
```

### 6.2 Cron Job for Monitoring
```bash
# Add to crontab
crontab -e

# Add line:
*/5 * * * * /home/chris/proethica/scripts/health-check.sh >> /var/log/proethica-health.log 2>&1
```

## Rollback Procedure

### Manual Rollback
```bash
# On the server
cd /home/chris/proethica
git log --oneline -n 10  # Find previous working commit
git checkout <commit-hash>

# Restart services
sudo systemctl restart proethica-app proethica-mcp
```

### Automated Rollback in CI/CD
Add to the deployment workflow:
```yaml
- name: Rollback on failure
  if: failure()
  uses: appleboy/ssh-action@v0.1.5
  with:
    host: ${{ secrets.DROPLET_HOST }}
    username: ${{ secrets.DROPLET_USER }}
    key: ${{ secrets.DROPLET_SSH_KEY }}
    script: |
      cd /home/chris/proethica
      git reset --hard HEAD~1
      sudo systemctl restart proethica-app proethica-mcp
```

## Security Checklist

- [ ] SSH key authentication only (disable password auth)
- [ ] Firewall configured (ufw or iptables)
- [ ] SSL certificates installed and auto-renewing
- [ ] Environment variables secured
- [ ] Database passwords strong and unique
- [ ] Regular security updates scheduled
- [ ] Backup strategy implemented
- [ ] Log rotation configured
- [ ] Fail2ban installed for brute force protection

## Next Steps

1. **Testing**: Thoroughly test the deployment pipeline in a staging environment
2. **Documentation**: Update README with deployment instructions
3. **Backup**: Implement automated database backups
4. **Scaling**: Consider containerization with Docker for easier scaling
5. **CDN**: Add CloudFlare or similar for static assets
6. **Monitoring**: Set up comprehensive monitoring (Prometheus, Grafana, etc.)