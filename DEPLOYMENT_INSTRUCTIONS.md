# ProEthica Production Deployment Instructions

## Deployment Status
**Date**: 2025-09-29
**Changes Deployed**:
- Enhanced entity review interfaces
- Updated extraction interfaces
- Case detail improvements
- Agent updates for Step 3
- Step 3 enhancements

## Pre-Deployment Steps Completed
1. ✓ Pushed development branch to origin/development (18 commits)
2. ✓ Merged development branch into main
3. ✓ Pushed main branch to GitHub repository

## Manual Production Deployment Steps

### SSH to Production Server
```bash
ssh digitalocean
# or
ssh chris@209.38.62.85
```

### Option 1: Run Deployment Script
```bash
cd /opt/proethica
wget https://raw.githubusercontent.com/cr625/proethica/main/deploy_production.sh
chmod +x deploy_production.sh
./deploy_production.sh
```

### Option 2: Manual Deployment Commands
```bash
# Navigate to ProEthica directory
cd /opt/proethica

# Check current status
git status
git branch

# Pull latest changes from main
git fetch origin
git pull origin main

# Check for dependency updates
if git diff HEAD@{1} HEAD --name-only | grep -q "requirements.txt"; then
    source venv/bin/activate
    pip install -r requirements.txt
    deactivate
fi

# Check if database migrations needed
# (Review new models added)
if [ -d "migrations" ]; then
    source venv/bin/activate
    flask db upgrade
    deactivate
fi

# Restart ProEthica service
sudo systemctl restart proethica

# Check service status
sudo systemctl status proethica

# Verify application is running
curl -I http://localhost:5000
```

## New Database Tables (May Need Migration)
Based on the deployment, these new models were added:
- `candidate_role_classes` - For role class validation
- `extraction_prompts` - For storing extraction prompts
- `temporary_rdf_storage` - For RDF data staging

Run migrations if needed:
```bash
cd /opt/proethica
source venv/bin/activate
flask db migrate -m "Add new extraction models"
flask db upgrade
deactivate
```

## Service Verification
After deployment, verify:
1. Service is running: `sudo systemctl status proethica`
2. Application responds: `curl http://localhost:5000`
3. nginx proxy works: `curl https://proethica.org`
4. Check logs if issues: `sudo journalctl -u proethica -n 100`

## Rollback Procedure
If deployment fails:
```bash
cd /opt/proethica
git log --oneline -5  # Note the previous commit hash
git reset --hard <previous-commit-hash>
sudo systemctl restart proethica
```

## Production URLs
- Main Application: https://proethica.org
- Local Access: http://localhost:5000

## Key Changes in This Deployment
1. **Enhanced Entity Review System**: New multi-pass entity review interfaces at `/scenarios/entity-review/`
2. **Dual Extraction System**: New extractors for all 9 concept types with dual role/individual extraction
3. **OntServe Integration**: Enhanced integration with OntServe for ontology commits
4. **Case Entity Storage**: New service for managing case-specific entity storage
5. **UI Improvements**: Updated templates for better streaming and multi-section displays

## Environment Variables to Verify
Ensure these are set in production:
- `FLASK_ENV=production`
- `DATABASE_URL` - PostgreSQL connection
- `ANTHROPIC_API_KEY` - For Claude integration
- `ONTSERVE_URL` - For ontology service integration

## Post-Deployment Testing
1. Create a test case
2. Run extraction on test case
3. Verify entity review works
4. Check OntServe integration
5. Test case detail view