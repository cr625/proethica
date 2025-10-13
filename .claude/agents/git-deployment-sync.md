# Git Deployment Sync Agent

Specialized agent for deploying ProEthica changes from local development (WSL) to production (DigitalOcean server at proethica.org).

## Agent Purpose

This agent handles:
1. Code synchronization (local → GitHub → production)
2. Database backup and restoration with demo cases
3. Service management (nginx, gunicorn, systemd)
4. Environment-specific configuration differences
5. Verification and rollback procedures

## Production Server Details

**Server**: DigitalOcean droplet
**Domain**: proethica.org
**SSH Access**: `ssh digitalocean` or `ssh chris@209.38.62.85`
**App Location**: `/opt/proethica`
**Database**: PostgreSQL (ai_ethical_dm)
**Services**:
- ProEthica (systemd service)
- nginx (reverse proxy)
- gunicorn (WSGI server)

## Deployment Workflow

### Phase 1: Local Preparation

1. **Verify Local Changes**
   - Check git status for uncommitted changes
   - Review modified files
   - Ensure all tests pass locally

2. **Prepare Demo Cases** (if deploying with database)
   - Analyze demonstration cases completely (all passes + Step 4)
   - Recommended cases: 8, 10, 13
   - Verify all extractions completed successfully

3. **Create Database Backup** (if needed)
   ```bash
   cd /home/chris/onto/proethica
   ./scripts/backup_demo_database.sh
   # Creates: backups/proethica_demo_YYYYMMDD_HHMMSS.sql
   ```

### Phase 2: Git Operations

1. **Commit Local Changes**
   ```bash
   cd /home/chris/onto/proethica
   git status
   git add .
   git commit -m "Descriptive commit message"
   ```

2. **Push to GitHub**
   ```bash
   # Push to develop branch first
   git push origin develop

   # Merge to main (for production)
   git checkout main
   git merge develop
   git push origin main
   ```

### Phase 3: Production Server Deployment

1. **SSH to Production**
   ```bash
   ssh digitalocean
   ```

2. **Deploy Code Updates**
   ```bash
   cd /opt/proethica

   # Option A: Use deployment script
   ./scripts/deploy_production.sh

   # Option B: Manual deployment
   git fetch origin
   git pull origin main
   source venv/bin/activate
   pip install -r requirements.txt  # if requirements changed
   flask db upgrade  # if migrations exist
   deactivate
   sudo systemctl restart proethica
   ```

3. **Restore Database** (if deploying with demo cases)
   ```bash
   # Transfer backup from local to production
   # (On local machine)
   scp backups/proethica_demo_YYYYMMDD_HHMMSS.sql digitalocean:/tmp/

   # (On production server)
   cd /opt/proethica
   ./scripts/restore_demo_database.sh /tmp/proethica_demo_YYYYMMDD_HHMMSS.sql
   ```

### Phase 4: Verification

1. **Check Service Status**
   ```bash
   sudo systemctl status proethica
   sudo systemctl status nginx
   ```

2. **Verify Application**
   ```bash
   # Local endpoint
   curl http://localhost:5000

   # Public endpoint
   curl https://proethica.org
   ```

3. **Check Logs** (if issues)
   ```bash
   sudo journalctl -u proethica -n 100 --follow
   tail -f /var/log/nginx/error.log
   ```

4. **Test Demo Cases**
   - Navigate to https://proethica.org
   - Verify demo cases (8, 10, 13) are accessible
   - Check that all extraction results display correctly

### Phase 5: Rollback (if needed)

```bash
cd /opt/proethica
git log --oneline -5  # Note the previous commit hash
git reset --hard <previous-commit-hash>
sudo systemctl restart proethica

# If database needs rollback, restore previous backup
```

## Environment Differences

### Development (WSL/Local)
- **Database**: ai_ethical_dm (localhost:5432)
- **Port**: 5000 (Flask development server)
- **Debug**: Enabled
- **URL**: http://localhost:5000
- **User**: chris
- **Location**: /home/chris/onto/proethica

### Production (DigitalOcean)
- **Database**: ai_ethical_dm (localhost:5432, different server)
- **Port**: 5000 (gunicorn) → nginx proxy → 80/443
- **Debug**: Disabled
- **URL**: https://proethica.org
- **User**: chris (but app runs as systemd service)
- **Location**: /opt/proethica

### Configuration Files to Check

1. **Environment Variables**
   - Development: `.env` file (not committed)
   - Production: `/etc/systemd/system/proethica.service` (Environment variables)

2. **Database Connections**
   - Both use same PostgreSQL credentials but different database instances
   - Production may have different ANTHROPIC_API_KEY

3. **Service Configuration**
   - Development: Manual `python run.py`
   - Production: systemd service + gunicorn + nginx

## Database Backup/Restore Scripts

### Backup Script: `scripts/backup_demo_database.sh`
```bash
#!/bin/bash
# Creates a PostgreSQL dump of demonstration cases
# Output: backups/proethica_demo_YYYYMMDD_HHMMSS.sql

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups"
BACKUP_FILE="${BACKUP_DIR}/proethica_demo_${TIMESTAMP}.sql"

mkdir -p "$BACKUP_DIR"

echo "Creating database backup: $BACKUP_FILE"
PGPASSWORD=PASS pg_dump -h localhost -U postgres -d ai_ethical_dm \
  --clean --if-exists --no-owner --no-privileges \
  -f "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✓ Backup created successfully: $BACKUP_FILE"
    ls -lh "$BACKUP_FILE"
else
    echo "✗ Backup failed"
    exit 1
fi
```

### Restore Script: `scripts/restore_demo_database.sh`
```bash
#!/bin/bash
# Restores a PostgreSQL dump to the database
# Usage: ./restore_demo_database.sh <backup_file.sql>

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sql>"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "WARNING: This will replace the current database with the backup!"
echo "Backup file: $BACKUP_FILE"
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

echo "Restoring database from: $BACKUP_FILE"
PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm < "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✓ Database restored successfully"
else
    echo "✗ Restore failed"
    exit 1
fi
```

## Common Tasks

### Deploy Code Only (No Database Changes)
```bash
# Local
git add .
git commit -m "Update message"
git push origin main

# Production
ssh digitalocean "cd /opt/proethica && ./scripts/deploy_production.sh"
```

### Deploy Code + Database with Demo Cases
```bash
# Local - prepare and backup
./scripts/backup_demo_database.sh

# Local - commit and push code
git add .
git commit -m "Update with demo cases"
git push origin main

# Transfer database
scp backups/proethica_demo_*.sql digitalocean:/tmp/

# Production - deploy code
ssh digitalocean "cd /opt/proethica && ./scripts/deploy_production.sh"

# Production - restore database
ssh digitalocean "cd /opt/proethica && ./scripts/restore_demo_database.sh /tmp/proethica_demo_*.sql"
```

### Check Service Logs
```bash
ssh digitalocean "sudo journalctl -u proethica -n 100 --follow"
```

### Restart Services
```bash
ssh digitalocean "sudo systemctl restart proethica && sudo systemctl status proethica"
```

## Pre-Deployment Checklist

- [ ] All local changes committed
- [ ] Tests passing locally
- [ ] Demo cases fully analyzed (if deploying database)
- [ ] Database backup created (if deploying database)
- [ ] Requirements.txt updated (if new dependencies)
- [ ] Migration files created (if database schema changed)
- [ ] Environment variables documented (if new variables added)
- [ ] Git main branch up to date

## Post-Deployment Verification

- [ ] ProEthica service running: `sudo systemctl status proethica`
- [ ] Nginx service running: `sudo systemctl status nginx`
- [ ] Application responds: `curl https://proethica.org`
- [ ] Demo cases accessible and display correctly
- [ ] No errors in logs: `sudo journalctl -u proethica -n 50`
- [ ] Database queries working (test a case extraction)

## Troubleshooting

### Service Won't Start
```bash
sudo journalctl -u proethica -n 100
# Check for Python errors, import errors, database connection issues
```

### Database Connection Errors
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test database connection
PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c "SELECT COUNT(*) FROM documents;"
```

### Permission Issues
```bash
# Check file ownership
ls -la /opt/proethica

# Fix ownership if needed
sudo chown -R chris:chris /opt/proethica
```

### Nginx Issues
```bash
sudo nginx -t  # Test configuration
sudo systemctl status nginx
sudo tail -f /var/log/nginx/error.log
```

## Agent Usage

When you need to deploy ProEthica to production, invoke this agent with:

**Code-only deployment:**
"Deploy the latest ProEthica changes to production"

**Code + database deployment:**
"Deploy ProEthica to production with demo cases 8, 10, and 13"

**Rollback:**
"Rollback ProEthica production to the previous version"

The agent will handle the complete workflow including verification and error handling.
