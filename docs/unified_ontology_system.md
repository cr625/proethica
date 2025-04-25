# Unified Ontology System

This document provides a consolidated overview of the ontology system in the ProEthica project, including the database storage architecture, visualization features, and management tools.

## System Architecture

The ontology system uses a database-driven storage approach for all ontology data with the following key components:

### Core Database Models

1. **Ontology**: Main model for ontology metadata and content
   - Stores full ontology content, name, description, domain ID
   - Tracks base/editable status for special ontologies

2. **OntologyVersion**: Tracks version history
   - Maintains historical snapshots of ontologies
   - Includes commit messages and timestamps

3. **OntologyImport**: Maps relationships between ontologies
   - Tracks which ontologies import others
   - Enables dependency management

### User Interface Components

1. **Ontology Editor**: Web-based editor for ontology content 
   - Full ACE editor with Turtle syntax highlighting
   - Validation for syntax and BFO compliance
   - Version history and comparison

2. **Visualization Interface**: Interactive ontology explorer
   - Hierarchical view of classes
   - Entity type view with categorization
   - Color-coding for different entity types

## Management Tools

The system includes several scripts for managing ontologies:

### Core Management Scripts

- **scripts/setup_ontology_db_only.sh**: Master script for database migration
- **scripts/check_ontologies_in_db.py**: Verify ontologies in database
- **scripts/update_ontology_mcp_server.py**: Update MCP server for database loading

### Maintenance Scripts

- **scripts/archive_ontology_files.py**: Safely archive original TTL files
- **scripts/remove_ontology_files.py**: Replace TTL files with placeholders

## API Routes

The system provides a comprehensive API:

- `/ontology-editor/api/ontologies` - List all ontologies
- `/ontology-editor/api/ontology/<id>` - Get ontology by ID
- `/ontology-editor/api/versions/<id>` - List/get versions
- `/ontology-editor/api/ontology/<id>/hierarchy` - Get class hierarchy for visualization

## Best Practices

1. **Database Operations**
   - Always use transactions for updates to maintain consistency
   - Create new version entries when modifying ontologies

2. **Visualization**
   - Use filtering options for large ontologies
   - Consider caching for frequently accessed hierarchies

3. **Development**
   - Update visualization when making significant ontology changes
   - Test with both small and large ontologies

## Migration from File-Based Storage

The system has been migrated from file-based storage to database storage. Key aspects of this migration:

1. **Database as Single Source of Truth**: All ontology data now stored in database
2. **Compatibility Layer**: MCP server patch to prioritize database loading
3. **Safe Migration Process**: Archived original files before replacement
4. **Fallback Mechanism**: Database-first with file fallback for backward compatibility

## Future Development

Planned enhancements to the ontology system:

1. **Improved Visualization**: Enhanced relationship visualization
2. **Collaborative Editing**: Multi-user editing capabilities
3. **Advanced Querying**: Better search and filtering of ontology entities
4. **Performance Optimization**: Better handling of large ontologies
