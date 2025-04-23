# Ontology Editor

A modular BFO-based ontology editor for the ProEthica system.

## Overview

The Ontology Editor is a web-based tool for creating, editing, and visualizing ontologies built on the Basic Formal Ontology (BFO) framework. It provides:

- A form-based editor for TTL (Turtle) ontology files
- BFO compliance validation with warnings
- Hierarchical visualization of ontology classes and relationships
- Version control with commit history
- Integration with ProEthica's authentication system

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
   pip install rdflib flask flask-login
   ```
3. Create a directory for ontologies:
   ```
   mkdir -p ontologies/domains ontologies/imports
   ```
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
   - **Filename**: The filename (e.g., engineering_ethics.ttl)
   - **Domain**: Domain identifier (e.g., engineering_ethics)
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
   - View entity details by clicking on nodes

### Version Control

The editor maintains a version history for each ontology:

1. View versions in the sidebar when an ontology is loaded
2. Click a version to load it in the editor
3. Add commit messages when saving changes to document the changes made

## Architecture

The Ontology Editor follows a modular architecture:

- **API**: RESTful endpoints for CRUD operations on ontologies
- **Models**: Data structures for ontologies and versions
- **Services**: Core functionality such as file storage and validation
- **Templates**: HTML templates for the UI
- **Static**: CSS, JavaScript, and other assets

## Extending

### Adding Custom Validators

To add custom validators, extend the `validator.py` service:

1. Create a new validation function in `services/validator.py`
2. Add the validator to the API routes in `api/routes.py`
3. Update the UI to display the validation results

### Supporting Additional Formats

To support additional ontology formats:

1. Add format conversion in `services/formatter.py` (create this file)
2. Extend the API routes to support the new format
3. Update the UI to allow selecting the format

## License

GPL-3.0
