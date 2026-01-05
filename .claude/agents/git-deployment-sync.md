# Git Deployment Sync Agent

Specialized agent for deploying ProEthica changes from local development (WSL) to production (DigitalOcean server at proethica.org).

## Agent Purpose

This agent handles:
1. Code synchronization (local -> GitHub -> production)
2. Database backup and restoration
3. Documentation compilation and deployment (MkDocs)
4. Service management (gunicorn, nginx)
5. Verification and rollback procedures

## Production Server Details

**Server**: DigitalOcean droplet
**Domain**: proethica.org
**SSH Access**: `ssh digitalocean` (alias) or `ssh chris@209.38.62.85`
**App Location**: `/opt/proethica`
**Venv Location**: `/opt/proethica/venv`
**Database**: PostgreSQL (ai_ethical_dm)
**Docs Location**: `/opt/proethica/site/` (served at /docs/)
**Services**:
- ProEthica runs via gunicorn (port 5000)
- nginx (reverse proxy on 80/443)
- No systemd service - gunicorn runs directly

## Server Directory Structure

```
/opt/
  proethica/          # ProEthica application
    venv/             # Python virtual environment
    site/             # MkDocs compiled documentation
  ontserve/           # OntServe application
  ontextract/         # OntExtract application
```

## Deployment Workflow

### Phase 1: Local Preparation

1. **Verify Local Changes**
   ```bash
   cd /home/chris/onto/proethica
   git status
   git diff
   ```

2. **Run Tests** (recommended)
   ```bash
   PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/ -v
   ```

3. **Create Database Dump** (if deploying database)
   ```bash
   PGPASSWORD=PASS pg_dump -h localhost -U postgres -d ai_ethical_dm \
     --clean --if-exists --no-owner --no-privileges \
     -f /tmp/proethica_dev_backup.sql
   ```

4. **Build Documentation** (REQUIRED for full deployments)
   ```bash
   source venv-proethica/bin/activate
   mkdocs build
   # Creates/updates site/ directory
   ```

### Phase 2: Git Operations

1. **Commit and Push** (if changes exist)
   ```bash
   git add .
   git commit -m "Descriptive commit message"
   git push origin development
   ```

2. **Merge to Main** (for production deployment)
   ```bash
   git checkout main
   git merge development
   git push origin main
   git checkout development
   ```

   Note: If branches are already in sync, skip the merge step.

### Phase 3: Production Code Deployment

1. **Pull Latest Code**
   ```bash
   ssh digitalocean "cd /opt/proethica && git fetch origin && git pull origin main"
   ```

2. **Install Dependencies** (if requirements.txt changed)
   ```bash
   ssh digitalocean "cd /opt/proethica && source venv/bin/activate && pip install -r requirements.txt"
   ```

3. **Restart Gunicorn**
   ```bash
   ssh digitalocean "pkill -f 'gunicorn.*proethica' || true"
   ssh digitalocean "cd /opt/proethica && source venv/bin/activate && nohup gunicorn -w 4 -b 127.0.0.1:5000 --timeout 300 --access-logfile - --error-logfile - 'app:create_app()' > /tmp/proethica.log 2>&1 &"
   ```

### Phase 4: Database Restore (if deploying database)

**IMPORTANT**: Always create a production backup before restoring.

1. **Create Production Backup First**
   ```bash
   ssh digitalocean "PGPASSWORD=PASS pg_dump -h localhost -U postgres -d ai_ethical_dm \
     --clean --if-exists --no-owner --no-privileges \
     -f /tmp/proethica_production_backup_\$(date +%Y%m%d_%H%M%S).sql"
   ```

2. **Transfer Local Dump to Production**
   ```bash
   scp /tmp/proethica_dev_backup.sql digitalocean:/tmp/
   ```

3. **Restore Database**

   For databases with circular foreign keys (like ProEthica), use this approach:
   ```bash
   ssh digitalocean "PGPASSWORD=PASS psql -h localhost -U postgres -c 'DROP DATABASE IF EXISTS ai_ethical_dm;'"
   ssh digitalocean "PGPASSWORD=PASS psql -h localhost -U postgres -c 'CREATE DATABASE ai_ethical_dm;'"
   ssh digitalocean "PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c 'SET session_replication_role = replica;' -f /tmp/proethica_dev_backup.sql"
   ```

   The `SET session_replication_role = replica` disables triggers during restore, avoiding foreign key constraint issues.

4. **Grant Permissions** (if using proethica_user)
   ```bash
   ssh digitalocean "PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c 'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO proethica_user;'"
   ssh digitalocean "PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c 'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO proethica_user;'"
   ```

### Phase 5: Documentation Deployment (REQUIRED)

**IMPORTANT**: Always compile and deploy docs as part of a full deployment.

1. **Build Locally** (if not done in Phase 1)
   ```bash
   cd /home/chris/onto/proethica
   source venv-proethica/bin/activate
   mkdocs build
   ```

2. **Sync to Production**
   ```bash
   rsync -avz --delete /home/chris/onto/proethica/site/ digitalocean:/opt/proethica/site/
   ```

   Note: The site/ directory will be created automatically if it doesn't exist.

3. **Verify Documentation**
   ```bash
   curl -s -o /dev/null -w '%{http_code}' https://proethica.org/docs/
   # Should return 200
   ```

### Phase 6: Verification

1. **Check Gunicorn Process**
   ```bash
   ssh digitalocean "ps aux | grep gunicorn | grep proethica"
   # Should show 4+ workers
   ```

2. **Test Application**
   ```bash
   curl -s -o /dev/null -w '%{http_code}' https://proethica.org/
   # Should return 200

   curl -s -o /dev/null -w '%{http_code}' https://proethica.org/cases/
   # Should return 200
   ```

3. **Verify Database Counts** (if database was restored)
   ```bash
   ssh digitalocean "PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c 'SELECT COUNT(*) as documents FROM documents;'"
   ssh digitalocean "PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c 'SELECT COUNT(*) as users FROM users;'"
   ```

4. **Check Error Logs**
   ```bash
   ssh digitalocean "tail -20 /tmp/proethica.log"
   ```

## Environment Differences

### Development (WSL/Local)
- **Location**: /home/chris/onto/proethica
- **Venv**: venv-proethica
- **Database**: ai_ethical_dm (postgres/PASS)
- **Port**: 5000 (Flask dev server)
- **URL**: http://localhost:5000
- **Branch**: development

### Production (DigitalOcean)
- **Location**: /opt/proethica
- **Venv**: venv (not venv-proethica)
- **Database**: ai_ethical_dm (postgres/PASS or proethica_user)
- **Port**: 5000 (gunicorn) -> nginx -> 80/443
- **URL**: https://proethica.org
- **Branch**: main

## Quick Reference Commands

### Code-Only Deployment
```bash
# Local
git push origin development
git checkout main && git merge development && git push origin main && git checkout development

# Server
ssh digitalocean "cd /opt/proethica && git pull origin main && pkill -f 'gunicorn.*proethica'"
ssh digitalocean "cd /opt/proethica && source venv/bin/activate && nohup gunicorn -w 4 -b 127.0.0.1:5000 --timeout 300 'app:create_app()' > /tmp/proethica.log 2>&1 &"
```

### Full Deployment (Code + Database + Docs)
```bash
# 1. Local: Create dump and build docs
PGPASSWORD=PASS pg_dump -h localhost -U postgres -d ai_ethical_dm --clean --if-exists --no-owner -f /tmp/proethica_dev_backup.sql
source venv-proethica/bin/activate && mkdocs build

# 2. Push code
git push origin development
git checkout main && git merge development && git push origin main && git checkout development

# 3. Deploy to server
ssh digitalocean "cd /opt/proethica && git pull origin main"
scp /tmp/proethica_dev_backup.sql digitalocean:/tmp/

# 4. Backup and restore database
ssh digitalocean "PGPASSWORD=PASS pg_dump -h localhost -U postgres -d ai_ethical_dm -f /tmp/prod_backup_\$(date +%Y%m%d).sql"
ssh digitalocean "PGPASSWORD=PASS psql -h localhost -U postgres -c 'DROP DATABASE IF EXISTS ai_ethical_dm; CREATE DATABASE ai_ethical_dm;'"
ssh digitalocean "PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c 'SET session_replication_role = replica;' -f /tmp/proethica_dev_backup.sql"

# 5. Sync docs
rsync -avz --delete site/ digitalocean:/opt/proethica/site/

# 6. Restart service
ssh digitalocean "pkill -f 'gunicorn.*proethica' || true"
ssh digitalocean "cd /opt/proethica && source venv/bin/activate && nohup gunicorn -w 4 -b 127.0.0.1:5000 --timeout 300 'app:create_app()' > /tmp/proethica.log 2>&1 &"

# 7. Verify
curl -s -o /dev/null -w '%{http_code}' https://proethica.org/
curl -s -o /dev/null -w '%{http_code}' https://proethica.org/docs/
```

### Documentation Only
```bash
cd /home/chris/onto/proethica
source venv-proethica/bin/activate
mkdocs build
rsync -avz --delete site/ digitalocean:/opt/proethica/site/
curl -s -o /dev/null -w '%{http_code}' https://proethica.org/docs/
```

### Case-Specific Database Sync

When syncing a specific case (e.g., after re-running a pipeline), sync BOTH tables:

**Tables Required for Complete Case Sync:**
- `temporary_rdf_storage` - Entity data (roles, states, arguments, etc.)
- `extraction_prompts` - Step completion tracking and LLM prompts/responses

```bash
# 1. Export case data from local (replace CASE_ID with actual ID)
PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c "
COPY (SELECT * FROM temporary_rdf_storage WHERE case_id = CASE_ID) TO STDOUT WITH CSV HEADER" > /tmp/case_entities.csv

PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c "
COPY (SELECT * FROM extraction_prompts WHERE case_id = CASE_ID) TO STDOUT WITH CSV HEADER" > /tmp/case_prompts.csv

# 2. Transfer to production
scp /tmp/case_entities.csv /tmp/case_prompts.csv digitalocean:/tmp/

# 3. On production: Delete old case data and import new
ssh digitalocean "cd /opt/proethica && source venv/bin/activate && python3 << 'PYEOF'
from app import create_app
from app.models import TemporaryRDFStorage, ExtractionPrompt, db
import csv

CASE_ID = 7  # Replace with actual case ID

app = create_app()
with app.app_context():
    # Delete old data
    old_entities = TemporaryRDFStorage.query.filter_by(case_id=CASE_ID).delete()
    old_prompts = ExtractionPrompt.query.filter_by(case_id=CASE_ID).delete()
    db.session.commit()
    print(f'Deleted {old_entities} entities, {old_prompts} prompts')

    # Import entities
    with open('/tmp/case_entities.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # ... import logic for TemporaryRDFStorage
            pass

    # Import prompts
    with open('/tmp/case_prompts.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ep = ExtractionPrompt(
                case_id=int(row['case_id']),
                concept_type=row['concept_type'],
                step_number=int(row['step_number']),
                section_type=row['section_type'] if row['section_type'] else None,
                # ... other fields
            )
            db.session.add(ep)
    db.session.commit()
PYEOF
"
```

**Why Both Tables Are Required:**
- `temporary_rdf_storage`: Contains the actual extracted entities (roles, states, arguments, etc.)
- `extraction_prompts`: Tracks which extraction steps are complete (facts_complete, discussion_complete)
- The pipeline status service checks `extraction_prompts` to determine step completion
- Without syncing `extraction_prompts`, production may show "Please complete Step X" messages even when entities exist

## Pre-Deployment Checklist

- [ ] All local changes committed
- [ ] Tests passing locally (recommended)
- [ ] Database dump created (if deploying database)
- [ ] Documentation built with `mkdocs build`
- [ ] main branch up to date with development

## Post-Deployment Verification

- [ ] Gunicorn running: `ps aux | grep gunicorn | grep proethica`
- [ ] Main site responds: https://proethica.org/ (HTTP 200)
- [ ] Cases page works: https://proethica.org/cases/
- [ ] Documentation serves: https://proethica.org/docs/ (HTTP 200)
- [ ] Error logs clean: `tail /tmp/proethica.log`
- [ ] Database counts match expected values

## Troubleshooting

### Gunicorn Won't Start
```bash
ssh digitalocean "tail -50 /tmp/proethica.log"
# Check for Python import errors, missing dependencies
```

### Database Connection Errors
```bash
ssh digitalocean "PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c 'SELECT 1;'"
```

### Foreign Key Errors During Restore
Use the `SET session_replication_role = replica;` approach shown in Phase 4 to disable triggers during restore.

### Permission Denied on Tables
```bash
ssh digitalocean "PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c 'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO proethica_user;'"
```

### Nginx Issues
```bash
ssh digitalocean "sudo nginx -t"
ssh digitalocean "sudo tail -20 /var/log/nginx/error.log"
```

## Agent Invocation Examples

**Code-only deployment:**
"Deploy the latest ProEthica changes to production"

**Code + database deployment:**
"Deploy ProEthica to production with a fresh database dump"

**Full deployment (code + database + docs):**
"Full deployment to production including database and documentation"

**Documentation only:**
"Deploy ProEthica documentation to production"

**Verify production:**
"Check the status of ProEthica on production"
