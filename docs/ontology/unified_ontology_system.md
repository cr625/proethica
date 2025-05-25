# Unified Ontology System Documentation

## Overview

The ProEthica system uses a comprehensive ontology system to define the structure of engineering ethics principles, roles, resources, conditions, actions, and events. This document describes the database-backed ontology storage and access system that has replaced the previous file-based approach.

## Database-Backed Ontologies

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

### Ontology Entities

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

## API for Accessing Ontologies

The system provides RESTful API endpoints to access ontologies and their entities:

- **GET /api/ontologies** - List all available ontologies
- **GET /api/ontologies/{id}** - Get a specific ontology
- **GET /api/ontologies/{id}/versions** - List versions of an ontology
- **GET /api/ontologies/{id}/entities** - List all entities in an ontology
- **GET /api/ontologies/{id}/entities/{type}** - List entities of a specific type

These API endpoints support filtering, pagination, and search operations.

## Ontology Editor

The system includes a web-based ontology editor that provides:

- Visual editing of ontology entities
- Parent-child relationship management
- Version control with commits and rollback
- Entity validation

## MCP Server Integration

The Model Context Protocol (MCP) server has been updated to load ontologies from the database instead of files. This maintains backward compatibility with LLM services while providing the benefits of database storage:

1. **Database Loading**: The MCP server loads ontology data from the database on startup
2. **Caching**: Implemented for performance optimization
3. **Real-time Updates**: Changes to ontologies are immediately available to connected LLMs

### MCP API Endpoints

- **/api/guidelines/{ontology-name}** - Access ontology as guidance for LLMs
- **/api/entities/{entity-type}** - Get entities of a specific type across ontologies
- **/api/temporal/{version}** - Access temporal aspects of entities (for simulation)

## Database to File System Synchronization (Optional)

While the primary storage is now database-based, the system maintains an optional synchronization mechanism to export ontologies to the file system for:

1. External tool compatibility
2. Version control system integration
3. Backup purposes

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

## Migration Path

Previous file-based ontologies have been imported into the database. The archived files are maintained in the `ontologies_archive_YYYYMMDD_HHMMSS` directory for reference, but all active development should use the database-backed editor.
