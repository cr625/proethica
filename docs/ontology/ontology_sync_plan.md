# Ontology Synchronization Plan

## Current State (June 1, 2025)

Successfully synced all ontologies from filesystem to database:
- **ProEthica Intermediate**: Version 2 created
- **BFO**: Version 1 created  
- **Engineering Ethics**: Version 12 created

### MCP Server Integration ✅
- **Database-first loading**: MCP server loads from database with file fallback
- **Shared fallback directory**: Uses `/ontologies/` instead of `/mcp/ontology/`
- **Production configuration**: Updated deployment scripts to set `ONTOLOGY_DIR`
- **Legacy cleanup**: Removed duplicate files from `/mcp/ontology/` directory

## Synchronization Strategy

### 1. Primary Source of Truth
- **Filesystem (`/ontologies/` directory)** should be the primary source
- Database serves as versioned storage and for application access
- All manual edits should be made to filesystem files

### 2. Automatic Synchronization

#### Option A: Git Hook (Recommended)
Create a post-commit hook that syncs ontologies when TTL files change:

```bash
#!/bin/bash
# .git/hooks/post-commit

# Check if any ontology files were changed
if git diff-tree --no-commit-id --name-only -r HEAD | grep -E "ontologies/.*\.ttl$"; then
    echo "Ontology files changed, syncing to database..."
    cd /home/chris/proethica
    PYTHONPATH=/home/chris/proethica python scripts/sync_ontology_to_database.py --all
fi
```

#### Option B: Cron Job
Set up a daily cron job to sync ontologies:

```bash
# Add to crontab
0 2 * * * cd /home/chris/proethica && PYTHONPATH=/home/chris/proethica python scripts/sync_ontology_to_database.py --all >> /var/log/ontology_sync.log 2>&1
```

#### Option C: Application Startup
Add sync check during application initialization:

```python
# In app/__init__.py or similar
def check_ontology_sync():
    """Check if filesystem ontologies are newer than database versions"""
    for domain, config in DEFAULT_ONTOLOGIES.items():
        file_mtime = os.path.getmtime(config['path'])
        db_ontology = Ontology.query.filter_by(domain_id=domain).first()
        if db_ontology and file_mtime > db_ontology.updated_at.timestamp():
            sync_ontology(domain, config['path'], config)
```

### 3. Manual Sync Procedures

#### Adding New Ontologies
1. Place TTL file in `/ontologies/` directory
2. Add configuration to `DEFAULT_ONTOLOGIES` in sync script
3. Run: `python scripts/sync_ontology_to_database.py --domain [new-domain]`

#### Emergency Sync
If automatic sync fails:
```bash
cd /home/chris/proethica
PYTHONPATH=/home/chris/proethica python scripts/sync_ontology_to_database.py --all
```

### 4. Validation Workflow

Before syncing:
1. **Syntax Validation**: Parse TTL with RDFLib
2. **Consistency Check**: Verify BFO alignment
3. **Version Backup**: Automatic (already implemented)

After syncing:
1. **Verification**: Triple count matches
2. **Application Test**: Load ontology in app
3. **Log Review**: Check for warnings/errors

### 5. Monitoring and Alerts

#### Health Checks
- Monitor sync script logs for failures
- Check database/filesystem modification times weekly
- Verify triple counts remain consistent

#### Alert Conditions
- Sync failure (exit code != 0)
- File/database mismatch > 24 hours
- Parsing errors in TTL files

### 6. Best Practices

1. **Always edit filesystem files** - Never modify database content directly
2. **Test locally first** - Validate TTL syntax before committing
3. **Document changes** - Update ontology comments with change descriptions
4. **Version meaningfully** - Sync creates automatic version with timestamp
5. **Regular backups** - Database versions serve as backup history

### 7. Implementation Timeline

**Week 1:**
- [ ] Fix sync script BFO path permanently
- [ ] Set up git hooks for automatic sync
- [ ] Add engineering-ethics to DEFAULT_ONTOLOGIES

**Week 2:**
- [ ] Implement startup sync check
- [ ] Create monitoring dashboard/script
- [ ] Document sync procedures in README

**Week 3:**
- [ ] Test disaster recovery procedures
- [ ] Set up automated alerts
- [ ] Train team on sync workflow

### 8. Emergency Procedures

**If sync fails:**
1. Check Python environment and dependencies
2. Verify database connectivity
3. Validate TTL file syntax
4. Review sync script logs
5. Restore from version backup if needed

**If data corruption:**
1. Stop application
2. Identify last good version in database
3. Export good version to filesystem
4. Re-sync from clean state
5. Investigate root cause

### 9. Future Enhancements

- **Two-way sync**: Allow approved database edits to sync back
- **Conflict resolution**: Handle simultaneous edits
- **CI/CD integration**: Sync as part of deployment pipeline
- **Multi-environment**: Separate dev/staging/prod sync configs
- **API endpoint**: REST API for triggering sync operations

## Configuration Updates Needed

1. Update `scripts/sync_ontology_to_database.py`:
```python
DEFAULT_ONTOLOGIES = {
    'proethica-intermediate': {
        'path': 'ontologies/proethica-intermediate.ttl',
        'name': 'ProEthica Intermediate Ontology',
        'description': 'Intermediate ontology extending BFO for professional ethics modeling',
        'base_uri': 'http://www.semanticweb.org/proethica/proethica-intermediate#',
        'is_base': True,
        'is_editable': True
    },
    'bfo': {
        'path': 'ontologies/bfo.ttl',  # Fixed from bfo.owl
        'name': 'Basic Formal Ontology (BFO)',
        'description': 'Upper-level ontology for information integration',
        'base_uri': 'http://purl.obolibrary.org/obo/bfo.owl#',
        'is_base': True,
        'is_editable': False
    },
    'engineering-ethics': {
        'path': 'ontologies/engineering-ethics.ttl',
        'name': 'Engineering Ethics Ontology',
        'description': 'Domain-specific ontology for engineering ethics',
        'base_uri': 'http://www.semanticweb.org/proethica/engineering-ethics#',
        'is_base': False,
        'is_editable': True
    }
}
```

2. Fix deprecation warning:
```python
# Replace datetime.utcnow() with
from datetime import datetime, timezone
ontology.updated_at = datetime.now(timezone.utc)
```