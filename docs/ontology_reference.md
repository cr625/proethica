Ontology Reference Documentation
===========================

This document serves as the primary reference for all ontology-related functionality in the A-Proxy system.

## Core Documentation

For comprehensive information about the ontology system, please refer to these key documents:

1. **[Ontology Editor Changes](ontology_editor_changes.md)** - UI improvements, parameter handling, and recent changes
2. **[Ontology Database Storage](ontology_database_storage.md)** - Technical details about database storage architecture

## Quick Reference

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ontology-editor/api/ontologies` | GET | List all ontologies |
| `/ontology-editor/api/ontologies/<int:ontology_id>` | GET | Get ontology by ID |
| `/ontology-editor/api/ontologies/<int:ontology_id>` | PUT | Update ontology |
| `/ontology-editor/api/ontology/<path:source>` | GET | Get ontology by source |
| `/ontology-editor/api/versions/<int:ontology_id>` | GET | List versions for an ontology |
| `/ontology-editor/api/versions/<int:version_id>` | GET | Get specific version |
| `/ontology-editor/api/validate/<int:ontology_id>` | POST | Validate ontology content |

### URL Parameters

When accessing the ontology editor:

- `ontology_id`: Database ID of the ontology
- `view`: Editor view type - `full`, `entities`, or `entity`
- `highlight_entity`: (Optional) Entity to highlight/select
- `entity_type`: (Optional) Filter for specific entity type

### Database Models

- **Ontology** - Stores the primary ontology data and metadata
- **OntologyVersion** - Tracks version history of ontologies
- **World** - References ontologies through foreign key

## Migrations and Scripts

Key scripts for managing ontologies:

- `scripts/migrate_ontologies_to_db.py` - Migrates file-based ontologies to database
- `scripts/check_ontologies_in_db.py` - Verifies database storage
- `scripts/update_ontology_editor_for_db_only.py` - Removes file-based fallbacks

## Best Practices

1. **Database Operations**
   - Always use transactions for updates to ensure consistency
   - Create new version entries when updating ontologies
   
2. **Error Handling**
   - Check for ontology existence before operations
   - Validate ontology content before storing
   - Use custom error messages to help diagnose issues

3. **Performance Considerations**
   - Large ontologies may require pagination in UI display
   - Consider indexing frequently searched fields
   - Cache commonly accessed ontologies when appropriate

## Troubleshooting

Common issues and their solutions:

1. **Missing Ontologies**
   - Check database records directly
   - Verify world references are correct
   - Look for authentication/permission issues

2. **Version History Problems**
   - Check database integrity
   - Ensure version numbers are sequential

## Contact Information

For questions or assistance with the ontology system, please contact:

- Development Team: dev@proethica.org
- Technical Support: support@proethica.org
