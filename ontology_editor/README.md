# Ontology Editor

A modular BFO-based ontology editor for the ProEthica system with database-driven storage.

## Overview

The Ontology Editor is a web-based tool for creating, editing, and visualizing ontologies built on the Basic Formal Ontology (BFO) framework. It provides:

- A form-based editor for TTL (Turtle) ontology content
- BFO compliance validation with warnings
- Hierarchical visualization of ontology classes and relationships
- Version control with commit history
- Integration with ProEthica's authentication system
- Database-driven storage for all ontology content

## Database Integration

The editor works exclusively with database-stored ontologies:

- All ontology content is stored in the database
- Version history is tracked with full content snapshots
- Import relationships between ontologies are explicitly modeled
- Entity extraction is performed directly from database content

This database-driven approach provides several benefits:

- Single source of truth for ontology data
- Proper version control and history tracking
- Consistent entity extraction across the application
- Protection for base ontologies (BFO, Intermediate)

## Installation

The Ontology Editor is designed to be integrated with the ProEthica system but can also be used as a standalone module.

### As part of ProEthica

The editor is already included in the ProEthica system. To enable it, simply register the blueprint in your Flask application:

```python
from ontology_editor import create_ontology_editor_blueprint

# Create the ontology editor blueprint
ontology_editor_bp = create_ontology_editor_blueprint(
    config={
        'require_auth': True,  # Enable authentication
        'admin_only': True     # Admin-only editing
    }
)

# Register the blueprint with your Flask app
app.register_blueprint(ontology_editor_bp)
```

### As a standalone module

To use the Ontology Editor as a standalone module:

1. Copy the `ontology_editor` directory to your project
2. Install required dependencies:
   ```
   pip install rdflib flask flask-login sqlalchemy
   ```
3. Set up the database for ontology storage
4. Register the blueprint with your Flask application as shown above

## Usage

### Accessing the Editor

Once integrated, the editor can be accessed at:

- `/ontology-editor` - Main editor interface
- `/ontology-editor/visualize/<ontology_id>` - Hierarchical visualization

### Creating an Ontology

1. Click the "New" button in the sidebar
2. Enter basic information:
   - **Title**: Display name for the ontology
   - **Domain ID**: The unique identifier (e.g., engineering-ethics)
   - **Description**: Optional description of the ontology
3. Click "Create" to create the ontology with a basic template

### Editing an Ontology

1. Select an ontology from the sidebar
2. Edit the TTL content in the editor
3. Click "Validate" to check BFO compliance
4. Click "Save" to save changes and create a new version

### Visualizing an Ontology

1. Select an ontology from the sidebar
2. Click the "Visualize" button
3. Explore the hierarchical visualization:
   - Click nodes to expand/collapse them
   - Use filters to focus on specific entity types
   - View entity details by hovering on nodes

### Version Control

The editor maintains a version history for each ontology:

1. View versions in the sidebar when an ontology is loaded
2. Click a version to load it in the editor
3. Add commit messages when saving changes to document the changes made

## Entity Extraction

The editor uses the `OntologyEntityService` to extract entities directly from database-stored ontologies. This service:

- Parses TTL content using RDFLib
- Extracts entities of different types (Roles, Conditions, Resources, etc.)
- Provides caching for performance optimization
- Offers consistent extraction logic across the application

## Architecture

The Ontology Editor follows a modular architecture:

- **API**: RESTful endpoints for CRUD operations on ontologies
- **Models**: Data structures for ontologies and versions
- **Services**: Core functionality such as database access and validation
- **Templates**: HTML templates for the UI
- **Static**: CSS, JavaScript, and other assets

### Database Models

The editor uses the following database models:

1. **Ontology**: Stores ontology metadata and content
2. **OntologyVersion**: Tracks version history for ontologies
3. **OntologyImport**: Manages import relationships between ontologies

## Documentation

For comprehensive documentation, see:

- `docs/ontology_system.md`: Main documentation of the ontology system
- `docs/unified_ontology_system.md`: Overview of the unified system
- `docs/ontology_visualization.md`: Information about the visualization feature

## License

GPL-3.0
