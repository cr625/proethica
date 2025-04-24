# Ontology Editor Integration with Proethica

This document describes how the Ontology Editor has been integrated with the Proethica application.

## Architecture Overview

The integration between Proethica and the Ontology Editor involves several components:

1. **Ontology Editor Module**: A standalone Flask blueprint that provides the user interface and API for editing ontologies
2. **MCP Client**: Extended to support ontology operations
3. **Bridge Routes**: New routes in Proethica that connect to the ontology editor
4. **UI Integration**: Buttons and links in the Proethica UI that direct users to the ontology editor

## Integration Points

### 1. Ontology Editor Blueprint

The ontology editor is registered in `app/__init__.py` as a Flask blueprint:

```python
# Register ontology editor blueprint
ontology_editor_bp = create_ontology_editor_blueprint(
    config={
        'require_auth': True,
        'admin_only': True,  # Admin-only access
        'entity_types': ['roles', 'conditions', 'resources', 'events', 'actions']
    }
)
app.register_blueprint(ontology_editor_bp)
```

### 2. MCP Client Extensions

The MCPClient class in `app/services/mcp_client.py` has been extended with methods to:

- Get ontology status (current/deprecated)
- Get ontology content
- Update ontology content
- Refresh world entities after ontology changes

### 3. Bridge Routes

New routes have been added in `app/routes/ontology.py` to provide bridging functionality:

- **GET /ontology/[source]**: Redirects to the ontology editor with the source parameter
- **GET /ontology/[source]/content**: Get the raw content of an ontology
- **PUT /ontology/[source]/content**: Update the content of an ontology
- **GET /ontology/[source]/status**: Check if an ontology is current or deprecated
- **POST /ontology/[source]/refresh**: Refresh entities derived from an ontology

### 4. UI Integration Points

The World Detail page (`app/templates/world_detail.html`) has been updated with:

- Links to edit the ontology associated with a world
- Status indicator for deprecated ontologies
- Button to edit individual entities in the World Entities section

JavaScript in `app/static/js/world_ontology.js` enables the "Edit in Ontology" button to properly direct users to the ontology editor with the correct entity highlighted.

## Data Flow

1. Worlds in Proethica reference ontologies via the `ontology_source` attribute
2. When viewing a world, the MCP client retrieves entities from the ontology
3. The UI provides links to edit the ontology or specific entities
4. When an ontology is updated, the changes are saved and world entities are refreshed

## Usage

### Editing a World's Ontology

1. Navigate to a world's detail page
2. Click the "Edit Ontology" button next to the Ontology Source field
3. Make changes in the ontology editor
4. Save changes, which will automatically refresh the world's entities

### Editing a Specific Entity

1. Navigate to a world's detail page
2. In the "World Entities" section, click "Details" for an entity
3. Click the "Edit in Ontology" button in the entity details modal
4. The ontology editor will open with the entity highlighted
5. Make changes and save

## Technical Considerations

1. **Authentication**: The ontology editor is configured to require authentication
2. **Admin-only access**: Only admin users can edit ontologies
3. **Entity types**: The supported entity types are: roles, conditions, resources, events, and actions

## Deployment Notes

When deploying the integrated system:

1. Ensure the ontology directory structure exists
2. Set up proper permissions for the ontologies directory
3. Configure the MCP server to serve ontology-related endpoints

## Future Enhancements

Possible improvements to the integration:

1. Add versioning UI to show ontology history and allow reverting to previous versions
2. Implement a visual diff tool to compare ontology versions
3. Add collaboration features for multiple users editing the same ontology
4. Implement more sophisticated validation of ontology edits
5. Create a workflow for proposing and approving ontology changes
