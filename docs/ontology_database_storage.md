Ontology Database Storage
=======================

## Overview

The A-Proxy system now stores all ontologies exclusively in the database, rather than using a combination of file-based storage and database storage. This document covers the technical implementation of this change, how ontologies are stored, and how to manage them.

## Architecture

### Database Models

1. **Ontology Model (`app/models/ontology.py`)**:
   ```python
   class Ontology(db.Model):
       __tablename__ = 'ontologies'
       
       id = db.Column(db.Integer, primary_key=True)
       name = db.Column(db.String(255), nullable=False)
       description = db.Column(db.Text, nullable=True)
       domain_id = db.Column(db.String(255), nullable=False, unique=True)
       content = db.Column(db.Text, nullable=False)  # The actual ontology content
       created_at = db.Column(db.DateTime, default=datetime.utcnow)
       updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
       
       # Relationship to worlds
       worlds = db.relationship('World', backref='ontology', lazy=True)
       # Relationship to versions
       versions = db.relationship('OntologyVersion', backref='ontology', lazy=True)
   ```

2. **OntologyVersion Model (`app/models/ontology_version.py`)**:
   ```python
   class OntologyVersion(db.Model):
       __tablename__ = 'ontology_versions'
       
       id = db.Column(db.Integer, primary_key=True)
       ontology_id = db.Column(db.Integer, db.ForeignKey('ontologies.id'), nullable=False)
       version_number = db.Column(db.Integer, nullable=False)
       content = db.Column(db.Text, nullable=False)  # The version-specific content
       commit_message = db.Column(db.String(255), nullable=True)
       created_at = db.Column(db.DateTime, default=datetime.utcnow)
   ```

3. **World Model (Updated) (`app/models/world.py`)**:
   ```python
   # In World model, added:
   ontology_id = db.Column(db.Integer, db.ForeignKey('ontologies.id'), nullable=True)
   ```

### API Changes

All API routes now exclusively use database queries and no longer attempt to read from or write to the file system. The file paths are still stored for backward compatibility but contain empty placeholder files.

## Migration

### Migration Steps Performed

1. **Initial Database Migration**:
   - Created and ran the script `scripts/migrate_ontologies_to_db.py` to move all ontologies from files to database
   - Each ontology received a database record in the `ontologies` table
   - File versions were migrated to the `ontology_versions` table

2. **Complete Removal of File Fallback**:
   - Ran `scripts/update_ontology_editor_for_db_only.py` to modify code to use database exclusively
   - Original ontology files moved to `ontologies_removed` as a backup
   - Empty placeholder files created in the original locations

### Checking Migration Status

To verify ontologies are properly migrated and working in database-only mode:

1. **Check Database Records**:
   ```bash
   python scripts/check_ontologies_in_db.py
   ```

2. **Verify Application Function**:
   - Access ontologies through the web interface
   - All ontology operations should work without errors
   - The application should not attempt to read or write ontology files

## API Usage

### Fetching Ontology Content

```python
from app.models.ontology import Ontology

def get_ontology_content(ontology_id):
    ontology = Ontology.query.get(ontology_id)
    if not ontology:
        return None
    return ontology.content
```

### Creating a New Version

```python
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from app import db

def create_new_version(ontology_id, content, commit_message):
    ontology = Ontology.query.get(ontology_id)
    if not ontology:
        return False
        
    # Update ontology content
    ontology.content = content
    
    # Create new version
    versions = OntologyVersion.query.filter_by(ontology_id=ontology_id).all()
    new_version_number = len(versions) + 1
    
    version = OntologyVersion(
        ontology_id=ontology_id,
        version_number=new_version_number,
        content=content,
        commit_message=commit_message
    )
    db.session.add(version)
    db.session.commit()
    
    return True
```

## Troubleshooting

### Common Issues

1. **Ontology Not Found**:
   - Check that the ontology ID exists in the database
   - Ensure references in the world model point to valid ontology IDs

2. **Version History Issues**:
   - If version history seems inconsistent, check the `ontology_versions` table directly
   - Version numbers should be sequential starting from 1

3. **Database Connection Issues**:
   - Ensure database connection parameters are correct
   - Check database logs for any connection or query errors

### Recovery Options

In case of database issues, the original ontology files are preserved in the `ontologies_removed` directory. These can be used to repopulate the database if needed.

## Future Enhancements

- Implementation of database indexing for large ontologies
- Optimization of queries for frequent ontology operations
- Addition of version comparison and rollback UI
- Enhanced backup and restore functionality for ontologies

## Related Documentation

- See `docs/ontology_editor_changes.md` for UI and general editor improvements
- Refer to `CLAUDE.md` for complete history of all ontology-related changes
