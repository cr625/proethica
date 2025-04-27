# ProEthica Ontology System

This document provides a comprehensive overview of the ontology system in the ProEthica platform, explaining how ontologies are stored, managed, and accessed throughout the application.

## Overview

ProEthica uses ontologies to define the entity types (roles, conditions, resources, etc.) available within worlds. The ontology system consists of several components:

1. **Database Storage**: Primary storage for ontologies and their versions
2. **Ontology Editor**: UI for editing ontologies and their entities
3. **Entity Editor**: Card-based interface for managing specific entities
4. **MCP Server Integration**: Makes ontologies accessible to LLMs via the Model Context Protocol
5. **Ontology Entity Service**: Extracts entities from ontologies for use in the application

## Database-Driven Architecture

As of April 2025, ProEthica uses a database-first approach for ontology management:

### Ontology Tables

- `ontologies`: Stores metadata about each ontology (name, description, domain ID)
- `ontology_versions`: Stores version history and actual TTL content
- `ontology_imports`: Tracks import relationships between ontologies

### Benefits of Database Storage

1. **Single Source of Truth**: Eliminates inconsistencies between different parts of the system
2. **Version Control**: Proper tracking of ontology changes over time
3. **Improved Performance**: Faster access to ontology data
4. **Better Integration**: Easier integration with other parts of the application

## Ontology Structure

ProEthica ontologies follow a layered approach:

1. **Base Ontology (BFO)**: Fundamental upper-level categories like Entity, Continuant, Occurrent
2. **Intermediate Ontology**: Domain-independent but application-specific concepts
3. **Domain Ontologies**: Specialized ontology for specific domains (e.g., engineering ethics)

## Editing Entities

The Entity Editor provides an intuitive interface for managing entities within ontologies:

### Entity Types

- **Roles**: Positions or functions that entities can have (e.g., Engineer, Client)
- **Conditions**: States or situations (e.g., Licensed, Under Construction)
- **Resources**: Physical or virtual items (e.g., Bridge, Building Plans)
- **Actions**: Activities that can be performed (e.g., Inspect, Design)
- **Events**: Occurrences in time (e.g., Failure, Completion)
- **Capabilities**: Abilities associated with roles (e.g., Structural Analysis, Project Management)

### Protection System

The Entity Editor implements protection for core ontology elements:

1. **Base BFO Entities**: Cannot be modified (read-only)
2. **Intermediate Ontology Entities**: Cannot be modified in the entity editor (use full ontology editor)
3. **Domain-specific Entities**: Fully editable

### Entity Management Features

- **Inline Editing**: Click "Edit" to transform entity cards into edit forms
- **Add New Entities**: "Add [Entity Type]" buttons for each category
- **Delete Entities**: Remove domain-specific entities when no longer needed
- **Parent Selection**: Choose appropriate parent classes for proper inheritance
- **Capability Assignment**: Link capabilities to roles for richer semantic relationships

## Accessing Ontologies in Code

### From Web UI

```python
# Example of accessing entities for a world
from app.services.ontology_entity_service import OntologyEntityService

entity_service = OntologyEntityService.get_instance()
entities = entity_service.get_entities_for_world(world)
```

### From MCP Server

```python
# MCP server loading ontology from database
from app.models.ontology import Ontology
from rdflib import Graph

ontology = Ontology.query.filter_by(domain_id=domain_id).first()
if ontology:
    g = Graph()
    g.parse(data=ontology.content, format="turtle")
    # Process graph...
```

## MCP Server Integration

The Model Context Protocol (MCP) server provides ontology access to LLMs:

1. **Loading**: Ontologies are loaded from the database
2. **Enhancing**: Additional context may be added for LLM consumption
3. **Resources**: Ontologies are exposed as MCP resources
4. **Tools**: Specialized tools may use ontology data for operations

## Versioning System

When entities are modified through the Entity Editor:

1. A new version of the ontology is created
2. The version is stored in the `ontology_versions` table
3. The parent ontology record is updated to reference the latest version
4. Entity URIs remain consistent across versions

## Best Practices

1. **Entity Naming**: Use CamelCase for class names, following BFO conventions
2. **Description Quality**: Provide detailed descriptions for all entities
3. **Proper Hierarchy**: Ensure entities have appropriate parent classes
4. **Capabilities**: Use capabilities to enrich role definitions
5. **Consistency**: Maintain consistent terminology across entity types

## Troubleshooting

### Common Issues

1. **Entity Not Showing**: May need to clear browser cache or reload page
2. **Entity Relationships Missing**: Check parent class assignments
3. **Protected Entity Editing**: Use full ontology editor for intermediate entities
4. **Validation Errors**: Check for syntax issues in TTL content

## Future Enhancements

1. **Relationship Editing**: Direct editing of relationships between entities
2. **Visual Graph**: Interactive graph visualization of entity relationships
3. **Entity Search**: Advanced search and filtering capabilities
4. **Bulk Operations**: Batch import/export of entities
5. **Validation Rules**: Advanced validation for entity properties

---

*Last Updated: April 25, 2025*
