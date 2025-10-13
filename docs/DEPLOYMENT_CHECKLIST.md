# ProEthica Production Deployment Checklist

Quick reference checklist for deploying ProEthica to production (proethica.org).

## Pre-Deployment

### Code Preparation
- [ ] All changes committed locally
- [ ] Tests passing: `./tests/smoke_test_phase1.sh` (if applicable)
- [ ] No uncommitted changes: `git status`
- [ ] Requirements.txt updated (if dependencies changed)
- [ ] Migration files created (if schema changed): `flask db migrate`

### Demo Cases Preparation (if deploying database)
- [ ] Identify demo cases to include (e.g., Cases 8, 10, 13)
- [ ] Run complete analysis on each demo case:
  - [ ] Pass 1: Roles, States, Resources
  - [ ] Pass 2: Principles, Obligations, Constraints, Capabilities
  - [ ] Pass 3: Actions, Events
  - [ ] Step 4: Whole-Case Synthesis
- [ ] Verify all extractions completed successfully
- [ ] Check Step 4 review page displays correctly

### Database Backup
- [ ] Create local database backup: `./scripts/backup_demo_database.sh`
- [ ] Note backup filename: `backups/proethica_demo_YYYYMMDD_HHMMSS.sql`
- [ ] Verify backup file size is reasonable

## Git Operations

- [ ] Commit changes: `git add . && git commit -m "Deployment: <description>"`
- [ ] Push to develop: `git push origin develop`
- [ ] Switch to main: `git checkout main`
- [ ] Merge develop: `git merge develop`
- [ ] Push main: `git push origin main`
- [ ] Verify GitHub shows latest commit on main branch

## Production Deployment

### Transfer Files (if deploying database)
- [ ] Transfer database backup to production:
  ```bash
  scp backups/proethica_demo_*.sql digitalocean:/tmp/
  ```

### Deploy Code
- [ ] SSH to production: `ssh digitalocean`
- [ ] Navigate to app: `cd /opt/proethica`
- [ ] Run deployment script: `./scripts/deploy_production.sh`
- [ ] OR manual steps:
  - [ ] Pull changes: `git pull origin main`
  - [ ] Install dependencies: `source venv/bin/activate && pip install -r requirements.txt`
  - [ ] Run migrations: `flask db upgrade` (if needed)
  - [ ] Restart service: `sudo systemctl restart proethica`

### Restore Database (if deploying database)
- [ ] Run restore script: `./scripts/restore_demo_database.sh /tmp/proethica_demo_*.sql`
- [ ] Confirm restore when prompted (type 'yes')
- [ ] Verify document/entity counts
- [ ] Restart service: `sudo systemctl restart proethica`

## Verification

### Service Status
- [ ] ProEthica running: `sudo systemctl status proethica`
- [ ] Nginx running: `sudo systemctl status nginx`
- [ ] No errors in logs: `sudo journalctl -u proethica -n 50`

### Application Testing
- [ ] Local endpoint responds: `curl http://localhost:5000`
- [ ] Public endpoint responds: `curl https://proethica.org`
- [ ] Homepage loads in browser: https://proethica.org
- [ ] Demo cases are accessible:
  - [ ] Case 8: https://proethica.org/scenario_pipeline/case/8/step4
  - [ ] Case 10: https://proethica.org/scenario_pipeline/case/10/step4
  - [ ] Case 13: https://proethica.org/scenario_pipeline/case/13/step4
- [ ] Step 4 review pages display correctly
- [ ] Entity graphs render properly
- [ ] No JavaScript errors in browser console

### Database Verification
- [ ] Test database query:
  ```bash
  PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c \
    "SELECT id, title FROM documents ORDER BY id LIMIT 5;"
  ```
- [ ] Verify demo cases exist in database

## Rollback (if needed)

### Code Rollback
- [ ] SSH to production: `ssh digitalocean`
- [ ] Navigate to app: `cd /opt/proethica`
- [ ] Find previous commit: `git log --oneline -5`
- [ ] Reset to previous: `git reset --hard <commit-hash>`
- [ ] Restart service: `sudo systemctl restart proethica`

### Database Rollback
- [ ] Find pre-restore backup: `ls -lh backups/pre_restore_backup_*.sql`
- [ ] Restore previous database:
  ```bash
  PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm < backups/pre_restore_backup_*.sql
  ```
- [ ] Restart service: `sudo systemctl restart proethica`

## Post-Deployment

- [ ] Update deployment log in docs/DEPLOYMENT_INSTRUCTIONS.md
- [ ] Document any issues encountered
- [ ] Clean up temporary files:
  - [ ] Remove `/tmp/proethica_demo_*.sql` on production
  - [ ] Archive local backups (optional)
- [ ] Notify stakeholders of deployment (if applicable)

## Quick Commands Reference

```bash
# Local - create backup
cd /home/chris/onto/proethica
./scripts/backup_demo_database.sh

# Local - commit and push
git add .
git commit -m "Deployment: description"
git push origin main

# Local - transfer database
scp backups/proethica_demo_*.sql digitalocean:/tmp/

# Production - deploy code
ssh digitalocean "cd /opt/proethica && ./scripts/deploy_production.sh"

# Production - restore database
ssh digitalocean "cd /opt/proethica && ./scripts/restore_demo_database.sh /tmp/proethica_demo_*.sql"

# Production - check status
ssh digitalocean "sudo systemctl status proethica"

# Production - check logs
ssh digitalocean "sudo journalctl -u proethica -n 100 --follow"
```

## Notes

- Always create database backup before deploying
- Pre-restore backup is automatically created during restore
- Keep backup files for at least 30 days
- Test on local first before deploying to production
- Monitor logs for first 5-10 minutes after deployment
