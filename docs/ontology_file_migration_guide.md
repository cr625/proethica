# Ontology File Migration Guide

This document explains the process of migrating ontology files from the filesystem to the database, and how to safely remove the original TTL files after migration.

## Background

Originally, ontologies in the ProEthica system were stored as TTL files in the `mcp/ontology/` directory. With the recent database-driven ontology storage implementation, these files have been imported into the database. However, the MCP server still attempts to load ontologies from the filesystem first, which can cause inconsistencies if files are edited outside the proper editor.

This guide explains how to fully migrate to database-only storage while maintaining backward compatibility.

## Prerequisites

Before proceeding with the migration, ensure that:

1. All ontology files have been successfully imported into the database using:
   ```bash
   python scripts/migrate_ontologies_to_db.py
   ```

2. The ontology editor has been updated to work with database-stored ontologies

3. You have verified that ontologies are accessible through the database by running:
   ```bash
   python scripts/check_ontologies_in_db.py
   ```

## Migration Process

The migration involves three main steps:

### 1. Archive the Original TTL Files

Before making any changes, we create a backup of all ontology TTL files:

```bash
python scripts/archive_ontology_files.py
```

This script:
- Creates a timestamped archive directory (`ontologies_archive_YYYYMMDD_HHMMSS`)
- Copies all TTL files from `mcp/ontology/` to this archive
- Includes documentation and README files
- Creates an archive README explaining the contents

You can specify a custom archive location using the `--dir` parameter:

```bash
python scripts/archive_ontology_files.py --dir path/to/archive
```

### 2. Update the MCP Server

The MCP server needs to be updated to prioritize loading ontologies from the database:

```bash
python scripts/update_ontology_mcp_server.py
```

This script:
- Creates a patch file (`mcp/load_from_db.py`) that overrides the `_load_graph_from_file` method
- Updates the MCP server's `__init__.py` to import this patch
- The updated method will:
  1. First attempt to load the ontology from the database
  2. Fall back to the filesystem only if not found in the database (for backward compatibility)

### 3. Replace TTL Files with Placeholders

Now that we have a backup and updated the MCP server, we can safely replace the original TTL files:

```bash
python scripts/remove_ontology_files.py
```

This script:
- Replaces all TTL files with empty placeholder files
- Creates empty `metadata.json` and `versions.json` files
- Each placeholder file contains a comment explaining that the ontology is now stored in the database
- Preserves the directory structure for backward compatibility

### 4. Restart the MCP Server

For the changes to take effect, restart the MCP server:

```bash
./scripts/restart_mcp_server.sh
```

## Verification

After completing the migration, verify that:

1. The ontology editor works correctly with database-stored ontologies
2. Worlds can still be created and accessed with their ontologies
3. The MCP server doesn't report any errors related to ontology loading

## Rollback Procedure

If issues arise, you can restore the original files from the archive:

1. Copy all TTL files from the archive back to `mcp/ontology/`
2. Remove the patch from `mcp/__init__.py`
3. Restart the MCP server

## Additional Information

- The system will continue to maintain database versions even if files are restored
- Any changes made via the ontology editor will only affect the database version
- Maintaining a single source of truth (database) is recommended for consistency
