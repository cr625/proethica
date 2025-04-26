# Unified Ontology System

This document provides a comprehensive overview of the ontology system in the ProEthica project, focusing on the database-driven storage approach and integration with other components.

## Overview

The ProEthica ontology system provides structured knowledge representation for different ethical domains through:

1. **Database-driven storage** for all ontologies and their versions
2. **Entity extraction services** for world building and visualization
3. **MCP server integration** to make ontologies available to LLMs
4. **Ontology editor** for creating and modifying ontologies

## Database Storage Architecture

The system uses a sophisticated database storage model for all ontology data:

### Core Models

1. **Ontology**:
   - Stores basic ontology information and content
   - Fields include: `id`, `name`, `domain_id`, `description`, `content`, `is_base`, `is_editable`, `base_uri`
   - See `app/models/ontology.py`

2. **OntologyVersion**:
   - Tracks version history for ontologies
   - Each version maintains a complete copy of the ontology content at that point in time
   - See `app/models/ontology_version.py`

3. **OntologyImport**:
   - Maps relationships between ontologies
   - Tracks which ontologies import/extend others
   - See `app/models/ontology_import.py`

### Entity Types and Hierarchy

Ontologies define several entity types that can be used in world building:

1. **Roles**: Positions or responsibilities that characters can assume
2. **Conditions**: States or situations that can be applied to characters
3. **Resources**: Objects or assets available in the world
4. **Events**: Occurrences that take place in the timeline
5. **Actions**: Activities that characters can perform
6. **Capabilities**: Skills or abilities possessed by roles

## Entity Extraction

The system provides two complementary mechanisms for entity extraction:

### Direct Database Extraction

The `OntologyEntityService` (in `app/services/ontology_entity_service.py`) provides direct extraction from database-stored ontologies:

- Loads ontology content from the database
- Parses TTL content using RDFLib
- Extracts entities of different types
- Provides caching for performance optimization

This is used primarily by:
- The world detail page
- The ontology editor entity viewer

### MCP Server Integration

The Model Context Protocol (MCP) server makes ontology data available to LLMs:

- Loads ontologies from the database (with filesystem fallback)
- Provides entity extraction via the `get_world_entities` tool
- Supports both development and production modes

## Ontology Editor

The web-based ontology editor provides:

- TTL editing with syntax highlighting
- Ontology validation
- Entity visualization
- Version control

The editor works directly with database-stored ontologies through:

- API routes for CRUD operations
- Entity extraction for visualization
- Import/export capabilities

## User Workflows

### Viewing World Entities

1. User navigates to a world detail page
2. `OntologyEntityService` extracts entities from the database
3. Entities are displayed in the world view

### Editing Ontologies

1. User opens the ontology editor
2. Editor loads ontology content from database
3. User makes changes and validates
4. Changes are saved to database with version tracking

### LLM Access to Ontologies

1. LLM makes a request through the MCP server
2. MCP server loads ontology from database
3. Entities are extracted and returned to the LLM

## Technical Implementation Details

### Entity Extraction Logic

Entity extraction follows these steps:

1. Parse ontology content using RDFLib
2. Detect appropriate namespace for the ontology
3. Extract entities of each type using SPARQL-like queries
4. Format entity data into consistent structures

### MCP Server Database Access

The MCP server's database access is implemented through:

1. A patched `_load_ontology_from_db` method in `mcp/load_from_db.py`
2. The patch overrides the original file-loading method
3. It first attempts to load from database by domain ID
4. Falls back to file system loading if not found in database

### Security and Access Control

The system implements access controls:

1. Base ontologies are marked as non-editable (`is_editable=False`)
2. The ontology editor checks this flag before allowing modifications
3. API endpoints enforce authentication based on configuration

## Common Troubleshooting

1. **Entity extraction issues**:
   - Check that ontologies are properly loaded in the database
   - Verify entity class definitions follow the correct pattern
   - Inspect the ontology for syntax errors

2. **MCP server issues**:
   - Ensure the server is running (`ps aux | grep ontology_mcp_server`)
   - Check logs at `mcp/server.log`
   - Verify database connectivity

3. **Ontology editor issues**:
   - Check browser console for JavaScript errors
   - Validate ontology content syntax
   - Inspect server logs for API errors

## Best Practices

1. Always use the ontology editor for making changes to ensure proper versioning
2. Back up the database regularly to avoid data loss
3. Use the validation feature before saving ontologies
4. Maintain proper import relationships between ontologies
5. Document new entity types and their purpose
