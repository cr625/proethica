# Ontology Editor Integration Plan for ProEthica

This document outlines the detailed implementation plan for integrating the ontology editor module with the ProEthica system, focusing on connecting ontologies with worlds and their entities.

## Overview

The ontology editor is already implemented as a standalone module, and we need to integrate it with the main ProEthica system. This integration will allow users to edit ontologies directly from the World view, manage entities (roles, conditions, resources, events, actions), and ensure proper synchronization between ontologies and worlds.

## Implementation Stages

The integration will be implemented in three stages, each building on the previous one:

1. **Initial Integration & UI Enhancement**: Basic integration and UI updates
2. **MCP Integration & Entity Management**: Connection with the MCP client and entity handling
3. **Advanced Features**: Additional features for a complete integration

## Stage 1: Initial Integration & UI Enhancement

### 1.1 Blueprint Registration & Configuration
- Register ontology editor blueprint with admin-only access
- Configure the editor to focus on standard entity types
- Import existing ontologies from MCP ontology directory

```python
# In app/__init__.py
from ontology_editor import create_ontology_editor_blueprint

def create_app(config_name=None):
    # ... existing app creation code ...
    
    # Register ontology editor blueprint
    ontology_editor_bp = create_ontology_editor_blueprint(
        config={
            'require_auth': True,
            'admin_only': True,  # Admin-only access
            'entity_types': ['roles', 'conditions', 'resources', 'events', 'actions']
        }
    )
    app.register_blueprint(ontology_editor_bp)
    
    return app
```

### 1.2 World Detail Page UI Updates
- Add "Edit Ontology" button next to the ontology source
- Add deprecation warning for outdated ontologies
- Add ontology status indicator

```html
<!-- In app/templates/world_detail.html -->
<!-- Add after the ontology source line -->
<p>
  <strong>Ontology Source:</strong> {{ world.ontology_source or 'Not specified' }}
  {% if world.ontology_source %}
    <a href="/ontology-editor?source={{ world.ontology_source }}" class="btn btn-sm btn-primary ms-2">
      <i class="fas fa-edit"></i> Edit Ontology
    </a>
    {% if ontology_status == 'deprecated' %}
      <span class="badge bg-warning ms-2" data-bs-toggle="tooltip" 
            title="This world uses an outdated version of the ontology">
        <i class="fas fa-exclamation-triangle"></i> Deprecated
      </span>
    {% endif %}
  {% endif %}
</p>
```

### 1.3 Entity Details Modal Enhancement
- Add "Edit in Ontology" button to entity details modal
- Implement linking to the correct entity in the ontology editor

```html
<!-- In app/templates/world_detail.html -->
<!-- Add to the entity details modal footer -->
<div class="modal-footer">
  <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
  <a href="/ontology-editor/entity?entity_id={{entity.id}}&type={{entityType}}&source={{world.ontology_source}}" 
     class="btn btn-primary">
    <i class="fas fa-edit"></i> Edit in Ontology
  </a>
</div>
```

### 1.4 Backend Support Function for World Detail Page
- Add function to check if world ontology is current or deprecated

```python
# In app/routes/worlds.py
# Add to the view_world function

def view_world(id):
    world = World.query.get_or_404(id)
    # ... existing code ...
    
    # Check ontology status
    ontology_status = 'current'
    if world.ontology_source:
        try:
            ontology_status = mcp_client.get_ontology_status(world.ontology_source)
        except Exception as e:
            print(f"Error checking ontology status: {str(e)}")
    
    # ... existing code ...
    
    return render_template('world_detail.html', world=world, entities=entities, 
                         guidelines=guidelines, case_studies=case_studies,
                         ontology_status=ontology_status)
```

## Stage 2: MCP Integration & Entity Management

### 2.1 MCP Client Enhancement
- Add methods to interact with ontologies
- Implement version checking and comparison
- Update world entities after ontology changes

```python
# In app/services/mcp_client.py
# Add these methods to the MCPClient class

def get_ontology_status(self, ontology_source):
    """Check if an ontology is current or deprecated."""
    try:
        # Check if source is in the form of a filename
        if ontology_source.endswith('.ttl'):
            # Check versions against latest
            # Implementation details would depend on how versioning is tracked
            return 'current'  # or 'deprecated'
        return 'current'  # Default to current if can't determine
    except Exception as e:
        print(f"Error checking ontology status: {str(e)}")
        return 'unknown'

def get_ontology_content(self, ontology_source):
    """Get the content of an ontology file."""
    try:
        # Implementation using existing code patterns
        # This would read the TTL file content
        pass
    except Exception as e:
        print(f"Error getting ontology content: {str(e)}")
        raise

def update_ontology_content(self, ontology_source, content):
    """Update the content of an ontology file."""
    try:
        # Implementation using existing code patterns
        # This would write to the TTL file
        pass
    except Exception as e:
        print(f"Error updating ontology content: {str(e)}")
        raise

def refresh_world_entities(self, world_id):
    """Refresh world entities after ontology changes."""
    try:
        world = World.query.get(world_id)
        if not world or not world.ontology_source:
            return False
            
        # Re-fetch entities from the updated ontology
        # Clear any cached entity data
        return True
    except Exception as e:
        print(f"Error refreshing world entities: {str(e)}")
        return False
```

### 2.2 Ontology Editor Entity Routes
- Add routes to handle entity-specific editing
- Implement direct linking from world entity to ontology editor

```python
# In ontology_editor/api/routes.py

@bp.route('/entity', methods=['GET'])
def edit_entity():
    """Edit a specific entity from a world context."""
    entity_id = request.args.get('entity_id')
    entity_type = request.args.get('type')
    ontology_source = request.args.get('source')
    
    if not entity_id or not entity_type or not ontology_source:
        flash('Missing required parameters', 'error')
        return redirect(url_for('ontology_editor.index'))
    
    # Get the ontology ID from the source
    try:
        ontology_id = get_ontology_id_from_source(ontology_source)
    except Exception as e:
        flash(f'Error finding ontology: {str(e)}', 'error')
        return redirect(url_for('ontology_editor.index'))
    
    # Redirect to the editor with entity highlighted
    return redirect(url_for('ontology_editor.edit', 
                           ontology_id=ontology_id,
                           highlight_entity=entity_id,
                           entity_type=entity_type))
```

### 2.3 Entity Creation from World View
- Add UI for creating new entities of each type
- Implement handler for entity creation

```html
<!-- In app/templates/world_detail.html -->
<!-- Add at the top of each entity type tab -->
<div class="d-flex justify-content-between mb-3">
  <h5>{{entityType|capitalize}}</h5>
  <button class="btn btn-sm btn-success create-entity" data-entity-type="{{entityType}}">
    <i class="fas fa-plus"></i> New {{entityType|capitalize|singularize}}
  </button>
</div>
```

```javascript
// In app/static/js/world.js
// Add handler for entity creation

document.querySelectorAll('.create-entity').forEach(button => {
  button.addEventListener('click', function() {
    const entityType = this.getAttribute('data-entity-type');
    window.location.href = `/ontology-editor/new-entity?world_id=${worldId}&type=${entityType}`;
  });
});
```

## Stage 3: Advanced Features & Polishing

### 3.1 Ontology Version Management
- Implement ontology version tracking
- Add UI for viewing and selecting ontology versions
- Enable world to specify which version to use

```python
# In app/routes/worlds.py
# Add to the update_world function

@worlds_bp.route('/<int:id>/ontology/version', methods=['POST'])
def update_world_ontology_version(id):
    """Update the ontology version used by a world."""
    world = World.query.get_or_404(id)
    version_id = request.form.get('version_id')
    
    if not version_id:
        flash('Version ID is required', 'error')
        return redirect(url_for('worlds.view_world', id=id))
    
    try:
        # Get the ontology source for this version
        ontology_source = mcp_client.get_ontology_source_for_version(version_id)
        
        # Update the world
        world.ontology_source = ontology_source
        db.session.commit()
        
        flash('Ontology version updated successfully', 'success')
    except Exception as e:
        flash(f'Error updating ontology version: {str(e)}', 'error')
    
    return redirect(url_for('worlds.view_world', id=id))
```

### 3.2 World-Specific Entity Types Note
- Add information about standard vs. custom entity types
- Provide guidance on using entity types in the ontology editor

```html
<!-- In ontology_editor/templates/editor.html -->
<!-- Add this note in the editor interface -->

<div class="alert alert-info">
  <h5><i class="fas fa-info-circle"></i> Working with Entity Types</h5>
  <p>This editor focuses on the standard entity types used in ProEthica worlds:</p>
  <ul>
    <li><strong>Roles:</strong> Character roles and actors in the world</li>
    <li><strong>Conditions:</strong> States and circumstances</li>
    <li><strong>Resources:</strong> Physical or virtual assets</li>
    <li><strong>Events:</strong> Occurrences and happenings</li>
    <li><strong>Actions:</strong> Activities and operations</li>
  </ul>
  <p>While you can add other entity types, they may not automatically appear in the world interface.</p>
</div>
```

### 3.3 Quick Edit Feature for Entity Properties
- Implement in-place editing of basic entity properties
- Add save/cancel buttons for editing
- Provide visual feedback during save operations

```html
<!-- In app/templates/world_detail.html -->
<!-- Add to the entity details modal -->

<div class="entity-edit-panel mt-3" style="display: none;">
  <hr>
  <h5>Quick Edit</h5>
  <form id="quickEditForm">
    <input type="hidden" name="entity_id" id="editEntityId">
    <input type="hidden" name="entity_type" id="editEntityType">
    
    <div class="mb-3">
      <label class="form-label">Label</label>
      <input type="text" class="form-control" name="label" id="editEntityLabel">
    </div>
    
    <div class="mb-3">
      <label class="form-label">Description</label>
      <textarea class="form-control" name="description" id="editEntityDescription" rows="3"></textarea>
    </div>
    
    <div class="d-flex justify-content-end">
      <button type="button" class="btn btn-secondary me-2" id="cancelQuickEdit">Cancel</button>
      <button type="button" class="btn btn-primary" id="saveQuickEdit">Save Changes</button>
    </div>
  </form>
</div>

<button type="button" class="btn btn-sm btn-warning mt-2" id="toggleQuickEdit">
  <i class="fas fa-pencil-alt"></i> Quick Edit
</button>
```

```javascript
// In app/static/js/world.js
// Add handlers for quick editing

document.getElementById('toggleQuickEdit')?.addEventListener('click', function() {
  const editPanel = document.querySelector('.entity-edit-panel');
  if (editPanel.style.display === 'none') {
    editPanel.style.display = 'block';
    this.innerHTML = '<i class="fas fa-times"></i> Cancel Edit';
    
    // Populate form with current entity data
    const entityData = getCurrentEntityData();
    document.getElementById('editEntityId').value = entityData.id;
    document.getElementById('editEntityType').value = entityData.type;
    document.getElementById('editEntityLabel').value = entityData.label;
    document.getElementById('editEntityDescription').value = entityData.description;
  } else {
    editPanel.style.display = 'none';
    this.innerHTML = '<i class="fas fa-pencil-alt"></i> Quick Edit';
  }
});

document.getElementById('saveQuickEdit')?.addEventListener('click', function() {
  // Get form data
  const formData = new FormData(document.getElementById('quickEditForm'));
  const entityData = {
    id: formData.get('entity_id'),
    type: formData.get('entity_type'),
    label: formData.get('label'),
    description: formData.get('description')
  };
  
  // Show saving indicator
  this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
  this.disabled = true;
  
  // Send update request
  fetch(`/worlds/${worldId}/entities/update`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(entityData)
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      // Hide edit panel
      document.querySelector('.entity-edit-panel').style.display = 'none';
      document.getElementById('toggleQuickEdit').innerHTML = '<i class="fas fa-pencil-alt"></i> Quick Edit';
      
      // Update UI with new data
      updateEntityDisplay(data.entity);
      
      // Show success message
      showToast('Entity updated successfully', 'success');
    } else {
      showToast(`Error: ${data.message}`, 'error');
    }
  })
  .catch(error => {
    showToast(`Error: ${error.message}`, 'error');
  })
  .finally(() => {
    // Reset button
    this.innerHTML = 'Save Changes';
    this.disabled = false;
  });
});
```

## Implementation Timeline

1. **Stage 1 (Initial Integration)**
   - Week 1: Blueprint registration and configuration
   - Week 2: World detail page UI updates and entity details modal enhancement
   - Week 3: Testing and debugging of initial integration

2. **Stage 2 (MCP Integration)**
   - Week 4: MCP client enhancement and testing
   - Week 5: Ontology editor entity routes
   - Week 6: Entity creation from world view and testing

3. **Stage 3 (Advanced Features)**
   - Week 7: Ontology version management
   - Week 8: World-specific entity types note and quick edit feature
   - Week 9: Final testing, bug fixes, and documentation

## Testing Considerations

1. **Authentication Testing**
   - Verify admin-only access to ontology editing
   - Test different user roles and permissions

2. **Ontology CRUD Testing**
   - Test creating, reading, updating, and deleting ontologies
   - Verify proper version tracking and history

3. **Entity Management Testing**
   - Test creating and editing entities from the world view
   - Test entity property updates and synchronization

4. **Integration Testing**
   - Test navigation between world view and ontology editor
   - Verify proper data flow between components

5. **Error Handling Testing**
   - Test error scenarios such as invalid ontology files
   - Verify useful error messages and recovery options

## Documentation Updates

Once implementation is complete, the following documentation should be updated:

1. **CLAUDE.md**
   - Add a section about the ontology editor integration
   - Document the new features and workflow

2. **README.md**
   - Update section about working with ontologies
   - Add information about the integration with worlds

3. **User Documentation**
   - Create a dedicated guide for working with ontologies
   - Include screenshots and step-by-step instructions
