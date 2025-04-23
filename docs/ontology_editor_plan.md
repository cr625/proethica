# Ontology Editor Implementation Plan

## Overview

This document outlines the implementation plan for a modular interactive ontology editor based on BFO (Basic Formal Ontology) for the ProEthica system. The editor will provide tools for creating and managing ethical ontologies across multiple domains with a focus on simplicity and BFO compliance.

## Project Goals

1. Create a simplified, forms-based editor for TTL ontology files
2. Support hierarchical visualization of ontology structures
3. Implement basic version control with branch management
4. Provide BFO compliance validation with warnings
5. Enable integration with other ontologies like SNOMED CT
6. Design a modular architecture that can be expanded over time

## Target Users

- Ontology experts who need to create and maintain ethical domain ontologies
- Administrators who manage the ontological foundation of the ProEthica system

## Architecture

The ontology editor will be implemented as a separate service that communicates with the main ProEthica application via APIs:

```
ontology_editor/
├── __init__.py
├── README.md
├── api/
│   ├── __init__.py
│   ├── routes.py           # Simple CRUD API endpoints
│   └── auth.py             # Authentication adapter (admin/non-admin)
├── models/
│   ├── __init__.py
│   ├── ontology.py         # Basic ontology data models
│   └── metadata.py         # Version metadata for database storage
├── services/
│   ├── __init__.py
│   ├── file_storage.py     # File-based ontology storage
│   ├── validator.py        # BFO compliance validator (warning only)
│   └── formatter.py        # TTL format handler
└── templates/
│   ├── editor.html         # Main form-based editor interface
│   ├── validation.html     # Validation results display
│   └── hierarchy.html      # Tree-based visualization
└── static/
    ├── css/                # Stylesheets
    ├── js/                 # Client-side scripts
    └── img/                # Images and icons
```

## Implementation Phases

### Phase 1: Minimum Viable Product (MVP)

#### Core Features

1. **Form-Based TTL Editing**
   - Load engineering ethics .ttl files
   - Present editable forms for classes, properties, and individuals
   - Save changes back to .ttl files
   - Basic syntax validation

2. **Simple Version Control**
   - File-based version history
   - Database metadata tracking revisions
   - Admin-only commit permissions
   - Basic file diff viewing

3. **Hierarchical Visualization**
   - Tree-based view of class hierarchies
   - Expandable/collapsible nodes
   - Basic filtering options
   - Linkage to editor forms

4. **Authentication Integration**
   - Reuse existing auth system
   - Admin/non-admin role distinction
   - Secure API endpoints

5. **BFO Compliance Warnings**
   - Validate against BFO constraints
   - Display warnings without blocking edits
   - Provide suggestions for alignment

#### Timeline

1. **Backend Development** (Weeks 1-3)
   - Create file storage service with version tracking
   - Implement TTL parsing and generation
   - Build simple API endpoints
   - Integrate authentication system
   - Develop BFO validation service

2. **Frontend Development** (Weeks 4-6)
   - Create form-based editor interface
   - Implement hierarchical visualization 
   - Build validation display
   - Develop metadata management UI

3. **Testing and Integration** (Weeks 7-8)
   - Test with engineering ethics ontology
   - Implement feedback mechanism
   - Document usage instructions
   - Deploy as separate service

### Phase 2: Enhanced Features

After the MVP is complete, Phase 2 will introduce additional capabilities:

1. **Additional Ontology Support**
   - Support for SNOMED CT
   - Integration with ethical ontologies
   - Improved import/export capabilities

2. **Improved Version Control**
   - Domain-specific branching
   - More detailed change tracking
   - Better conflict visualization
   - Manual merge tools

3. **Enhanced Visualization**
   - More interactive tree views
   - Optional graph visualization for relationships
   - Custom styling options

4. **Template System**
   - Pre-built ethical concept templates
   - Custom template creation
   - Template-based instance generation

5. **Protégé Export**
   - Export compatible with Protégé
   - Import from Protégé XML format
   - Format conversion utilities

### Phase 3: Advanced Features

Future enhancements planned for Phase 3:

1. **Persona Service Integration**
   - Basic mapping between personas and characters
   - Persona trait to BFO quality mapping
   - Bidirectional update capability

2. **Reasoning Support**
   - Integration with a reasoner
   - Inference visualization
   - Consistency checking

3. **Advanced Collaboration**
   - Enhanced manual merge tools
   - Change proposals system
   - Review workflows

4. **Interactive Query Builder**
   - Simple query construction (no direct SPARQL)
   - Saved queries
   - Result visualization

## Technical Implementation Details

### API Design

Key API endpoints for the ontology editor service:

```
GET    /api/ontologies                # List available ontologies
GET    /api/ontologies/{id}           # Get ontology content
PUT    /api/ontologies/{id}           # Update ontology
POST   /api/ontologies                # Create new ontology
DELETE /api/ontologies/{id}           # Delete ontology

GET    /api/versions/{ontology_id}    # List versions for an ontology
GET    /api/versions/{id}             # Get specific version
POST   /api/versions/{ontology_id}    # Create new version (commit)

GET    /api/validate/{ontology_id}    # Validate ontology against BFO
```

### Authentication Integration

The ontology editor will authenticate against the main application's system:

1. Use the same session cookies/tokens
2. Verify admin status through the shared auth system
3. Limit edit operations to admin users
4. Allow read-only access to non-admin users

### Database Schema

For tracking metadata while keeping ontologies in files:

```sql
CREATE TABLE ontology_metadata (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    domain TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id)
);

CREATE TABLE ontology_versions (
    id SERIAL PRIMARY KEY,
    ontology_id INTEGER REFERENCES ontology_metadata(id),
    version_number INTEGER NOT NULL,
    commit_message TEXT,
    file_path TEXT NOT NULL,
    committed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    committed_by INTEGER REFERENCES users(id)
);
```

### File Storage Structure

The ontology files will be stored in an organized directory structure:

```
ontologies/
├── domains/                      # Domain folders
│   ├── engineering_ethics/       # Engineering ethics domain
│   │   ├── main/                 # Main branch
│   │   │   ├── current.ttl       # Current version
│   │   │   └── versions/         # Historical versions
│   │   │       ├── v1.ttl
│   │   │       ├── v2.ttl
│   │   │       └── ...
│   │   └── experimental/         # Experimental branch
│   │       ├── current.ttl
│   │       └── versions/
│   ├── legal_ethics/             # Legal ethics domain
│   └── ...
└── imports/                      # Imported ontologies
    ├── bfo/                      # BFO import
    ├── snomed/                   # SNOMED CT import
    └── ...
```

## Integration with Existing Systems

### MCP Server Integration

The ontology editor will integrate with the existing MCP server by:

1. Extending the HTTP ontology MCP server with additional endpoints
2. Updating the MCP client to support ontology editing operations
3. Ensuring backward compatibility with existing MCP API calls

### Persona Service Integration (Future)

In Phase 3, integration with the persona service (https://github.com/savingads/persona-service) will:

1. Map persona traits to BFO qualities
2. Connect persona state to continuant entities
3. Link persona actions to BFO processes
4. Enable bidirectional updates between ontologies and personas

## Success Criteria

The ontology editor implementation will be considered successful when:

1. Users can open and edit the engineering ethics .ttl files using a forms interface
2. Changes are properly saved with version control
3. The editor provides helpful BFO compliance warnings
4. The hierarchical visualization makes ontology structure clear
5. The system integrates smoothly with the existing ProEthica authentication

## Milestones and Tracking

1. **Milestone 1: Basic Editing** (End of Month 1)
   - Form-based editor for TTL files
   - Basic CRUD operations
   - Simple validation

2. **Milestone 2: Visualization and Versioning** (End of Month 2)
   - Tree visualization
   - Basic version control
   - BFO validation warnings

3. **Milestone 3: Complete MVP** (End of Month 3)
   - Full integration with authentication
   - Admin controls
   - Documentation
   - Deployment scripts

Progress will be tracked in the project management system and recorded in CLAUDE.md updates.
