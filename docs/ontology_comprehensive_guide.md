# Comprehensive Ontology System Guide

This document provides a unified and comprehensive guide for the ProEthica ontology system, explaining how ontologies are stored, managed, and accessed throughout the application.

## Overview

ProEthica uses ontologies to define the entity types (roles, conditions, resources, actions, events, capabilities) available within worlds. The ontology system consists of several integrated components:

1. **Database Storage**: Primary storage for all ontologies and their versions
2. **Ontology Editor**: TTL-based editor for modifying ontology content
3. **Entity Editor**: Card-based interface for managing specific entities
4. **MCP Server Integration**: Makes ontologies accessible to LLMs via the Model Context Protocol
5. **Ontology Entity Service**: Extracts entities from ontologies for use in the application

## Database-Driven Architecture

ProEthica uses a database-first approach for ontology management:

### Storage Structure

All ontologies are stored in the PostgreSQL database with the following structure:

1. **Ontology** - Main table storing ontology metadata and content
   - Content stored as Turtle (TTL) format RDF
   - Metadata includes name, description, domain, editability flags
   
2. **OntologyVersion** - Table storing version history
   - Each change creates a new numbered version
   - Complete audit trail of ontology modifications
   
3. **OntologyImport** - Table tracking imported ontologies
   - Establishes relationships between ontologies
   - Enables inheritance of concepts across domain ontologies

### Benefits of Database Storage

1. **Single Source of Truth**: Eliminates inconsistencies between different parts of the system
2. **Version Control**: Proper tracking of ontology changes over time
3. **Improved Performance**: Faster access to ontology data
4. **Better Integration**: Easier integration with other parts of the application
5. **Protection**: Better control over which ontologies can be modified

## Ontology Structure and Hierarchy

ProEthica ontologies follow a layered approach:

1. **Base Ontology (BFO)**: Fundamental upper-level categories like Entity, Continuant, Occurrent
2. **Intermediate Ontology**: Domain-independent but application-specific concepts
3. **Domain Ontologies**: Specialized ontology for specific domains (e.g., engineering ethics)

### Base Ontologies

The system recognizes two types of base ontologies:

1. **BFO (Basic Formal Ontology)**:
   - Provides the foundational classes for all ontologies
   - Imported into the intermediate ontology
   - Marked as non-editable in the database

2. **ProEthica Intermediate Ontology**:
   - Defines core entity types used across all domain ontologies
   - Extends BFO with ethical-specific concepts
   - Defines `Role`, `Condition`, `Resource`, `Event`, and `Action` classes
   - Marked as non-editable in the database

### Import Relationships

Domain ontologies explicitly import base ontologies in the database:

1. **Direct Imports**:
   - Explicitly defined with `owl:imports` statements in the TTL
   - Stored in the database using the `OntologyImport` model

2. **Implicit Imports**:
   - Detected from prefix declarations and namespace usage
   - Added automatically during import processing

3. **Default Imports**:
   - When no imports are detected, the intermediate ontology is added by default
   - Ensures all domain ontologies have access to core types

## Entity Types and Hierarchies

The system defines several entity types:

- **Roles**: Persons or organizations involved in ethical scenarios (e.g., Engineer, Client)
- **Resources**: Documents, drawings, codes that are referenced (e.g., Engineering Report, Building Code)
- **Conditions**: States, principles or dilemmas that exist (e.g., Safety Principle, Conflict of Interest)
- **Actions**: Activities that can be performed (e.g., Report Preparation, Approval)
- **Events**: Occurrences that happen (e.g., Safety Reporting Event)
- **Capabilities**: Abilities that roles can possess (e.g., Technical Reporting Capability)

Each entity type has a hierarchy with base classes and specific instances:

```
ResourceType (base)
├── EngineeringDocument
│   ├── EngineeringDrawing
│   │   └── Design Drawings
│   ├── EngineeringSpecification
│   └── EngineeringReport
│       ├── Structural Report
│       └── Inspection Report
└── BuildingCode
    ├── NSPE Code of Ethics
    └── NSPE Code Section
```

```
ActionType (base)
├── EngineeringAction
    ├── ReportAction
    │   ├── Report Preparation Action
    │   └── Hazard Reporting Action
    ├── DesignAction
    │   ├── Design Revision Action
    │   └── Design Action
    ├── DecisionAction
    │   ├── Safety vs Confidentiality Decision
    │   │   ├── Confidentiality vs Safety Decision
    │   │   └── Public Safety vs Confidentiality Decision
    │   ├── Whistleblowing Decision
    │   └── Design Approval Decision
    ├── SafetyAction
    ├── ReviewAction
    └── ConsultationAction
```

```
EventType (base)
├── EngineeringEvent
    ├── MeetingEvent
    │   └── Client Meeting Event
    ├── ReportingEvent
    │   ├── Safety Reporting Event
    │   └── Confidential Report Delivery
    ├── DisclosureEvent
    │   └── Non-Disclosure Event
    ├── SafetyEvent
    │   └── Hazard Discovery Event
    ├── DiscoveryEvent
    └── InspectionEvent
        └── Structural Inspection Event
```

## Entity Editor

The Entity Editor provides an intuitive interface for managing entities within ontologies:

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

## API for Accessing Ontologies

The system provides RESTful API endpoints to access ontologies and their entities:

- **GET /api/ontologies** - List all available ontologies
- **GET /api/ontologies/{id}** - Get a specific ontology
- **GET /api/ontologies/{id}/versions** - List versions of an ontology
- **GET /api/ontologies/{id}/entities** - List all entities in an ontology
- **GET /api/ontologies/{id}/entities/{type}** - List entities of a specific type

These API endpoints support filtering, pagination, and search operations.

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

The Model Context Protocol (MCP) server has been updated to load ontologies from the database instead of files. This maintains backward compatibility with LLM services while providing the benefits of database storage:

1. **Database Loading**: The MCP server loads ontology data from the database on startup
2. **Caching**: Implemented for performance optimization
3. **Real-time Updates**: Changes to ontologies are immediately available to connected LLMs

### MCP API Endpoints

- **/api/guidelines/{ontology-name}** - Access ontology as guidance for LLMs
- **/api/entities/{entity-type}** - Get entities of a specific type across ontologies
- **/api/temporal/{version}** - Access temporal aspects of entities (for simulation)

## Entity Extraction and Caching

The system uses the `OntologyEntityService` to extract entities from database-stored ontologies:

- **Parsing**: Uses RDFLib to parse TTL content from database
- **Extraction**: Identifies entity types based on RDF structure
- **Caching**: Maintains a cache of extracted entities for performance
- **Invalidation**: Provides utilities to invalidate the cache when needed

### Cache Invalidation

When making changes to ontologies or entities, the cache may need to be invalidated:

```bash
python scripts/invalidate_ontology_cache.py [ontology_id]
```

## Versioning System

When entities are modified through the Entity Editor:

1. A new version of the ontology is created
2. The version is stored in the `ontology_versions` table
3. The parent ontology record is updated to reference the latest version
4. Entity URIs remain consistent across versions

## Best Practices

1. **Entity Creation**: 
   - Always specify appropriate parent classes
   - Provide clear labels and descriptions
   - Avoid circular references
   - Use meaningful, consistent naming patterns

2. **Relationship Management**:
   - Maintain proper hierarchy relationships
   - Use specialized parent classes rather than generic ones
   - For actions, prefer specific action types (e.g., ReportAction) over generic EngineeringAction
   - For events, prefer specific event types (e.g., MeetingEvent) over generic EngineeringEvent
   - Use multi-inheritance when appropriate (e.g., Hazard Reporting Action can inherit from both ReportAction and SafetyAction)
   - Ensure alignment between action and event hierarchies for related concepts

3. **Version Control**:
   - Provide meaningful commit messages
   - Create logical, discrete changes
   - Test changes before committing
   - Use proper scripts to invalidate caches after ontology changes

## Common Issues and Solutions

- **Parent Selection Errors**: If parent class selection fails, check that the entity service is recognizing the appropriate base classes
- **MCP Server Connection Issues**: Restart the MCP server to reload ontology data
- **Entity Type Confusion**: Review the entity type definitions to ensure proper classification
- **Cache Invalidation Needed**: When making changes to the ontology structure, use the `scripts/invalidate_ontology_cache.py` utility to force a refresh of the cached ontology data
- **Incorrect Action Hierarchy**: If actions are showing incorrect parent relationships, check that they're assigned to specialized action types (e.g., ReportAction) rather than generic ones or incorrect resource types
- **Event-Resource Confusion**: Ensure events aren't incorrectly inheriting from resources (e.g., a ReportingEvent should inherit from EventType hierarchy, not from EngineeringReport)
- **Multi-Inheritance Issues**: For entities with multiple parent classes, ensure all parent classes are properly defined in the ontology before assigning them

## Future Enhancements

1. **Relationship Editing**: Direct editing of relationships between entities
2. **Visual Graph**: Interactive graph visualization of entity relationships
3. **Entity Search**: Advanced search and filtering capabilities
4. **Bulk Operations**: Batch import/export of entities
5. **Validation Rules**: Advanced validation for entity properties

---

*Last Updated: April 26, 2025*
