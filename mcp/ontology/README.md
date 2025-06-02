# MCP Ontology Configuration

## Updated Configuration (June 2025)

**IMPORTANT**: This directory no longer contains ontology TTL files. 

## Current Setup

The MCP server now uses a **database-first approach** with file fallback to the main project's synchronized ontology directory:

1. **Primary Source**: Database (`ontologies` table)
2. **File Fallback**: `/home/chris/proethica/ontologies/` directory

## Configuration

The MCP server uses the `ONTOLOGY_DIR` environment variable which defaults to:
```
/home/chris/proethica/ontologies/
```

This ensures the MCP server uses the same synchronized ontology files as the main application.

## Available Ontologies

- **proethica-intermediate**: Core ethical concepts extending BFO
- **bfo**: Basic Formal Ontology (upper-level ontology)  
- **engineering-ethics**: Engineering-specific ethical concepts

## Synchronization

Ontology synchronization is managed by:
- `scripts/sync_ontology_to_database.py` - Syncs TTL files to database
- Git post-commit hook - Automatically syncs when TTL files change
- See `/docs/ontology/ontology_sync_plan.md` for details

## Production Deployment

Production MCP servers should set:
```bash
ONTOLOGY_DIR=/home/chris/proethica/ontologies
```

This ensures consistent ontology access across development and production environments.

## Legacy Files Removed

This directory previously contained:
- Symbolic links to old repository paths
- Duplicate TTL files
- Legacy backup files

These have been cleaned up to prevent confusion and ensure the MCP server uses the centralized, synchronized ontology files.