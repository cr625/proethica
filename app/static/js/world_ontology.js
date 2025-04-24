/**
 * World Ontology Integration JavaScript
 * 
 * This file contains JavaScript code for integrating the ontology editor
 * with the world details page, specifically for entity editing.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Entity details modal
    const entityDetailsModal = document.getElementById('entityDetailsModal');
    const entityDetailsContent = document.getElementById('entityDetailsContent');
    const editEntityBtn = document.getElementById('edit-entity-ontology-btn');
    
    if (entityDetailsModal) {
        // Store the currently selected entity when the modal is opened
        let currentEntityId = null;
        let currentEntityType = null;
        
        // Listen for modal open event
        entityDetailsModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            currentEntityId = button.getAttribute('data-entity-id');
            currentEntityType = button.getAttribute('data-entity-type');
            
            // Get the entity details from the data attribute
            const entityType = currentEntityType;
            const entityIndex = currentEntityId;
            
            // Get the entity data from the global window object (populated by server-side)
            const entities = window.worldEntities || {};
            
            // Find the entity in the correct collection
            let entity = null;
            if (entities[entityType + 's'] && entities[entityType + 's'][entityIndex]) {
                entity = entities[entityType + 's'][entityIndex];
            }
            
            // Populate the modal with entity details
            if (entity) {
                let content = `
                    <h4>${entity.label || 'Unknown Entity'}</h4>
                    <hr>
                    <dl class="row">
                        <dt class="col-sm-3">ID</dt>
                        <dd class="col-sm-9">${entity.id || 'None'}</dd>
                        
                        <dt class="col-sm-3">Type</dt>
                        <dd class="col-sm-9">${capitalizeFirstLetter(entityType)}</dd>
                        
                        <dt class="col-sm-3">Description</dt>
                        <dd class="col-sm-9">${entity.description || 'No description available'}</dd>
                `;
                
                // Add additional properties as they exist
                if (entity.properties) {
                    for (const [key, value] of Object.entries(entity.properties)) {
                        if (key !== 'id' && key !== 'label' && key !== 'description') {
                            content += `
                                <dt class="col-sm-3">${capitalizeFirstLetter(key)}</dt>
                                <dd class="col-sm-9">${value}</dd>
                            `;
                        }
                    }
                }
                
                content += '</dl>';
                entityDetailsContent.innerHTML = content;
            } else {
                entityDetailsContent.innerHTML = '<div class="alert alert-warning">Entity details not available</div>';
            }
        });
        
        // Handle edit entity button click
        if (editEntityBtn) {
            editEntityBtn.addEventListener('click', function() {
                // Get the ontology source from the world details
                const worldOntologySource = document.getElementById('world-ontology-source')?.value || '';
                
                if (worldOntologySource && currentEntityId !== null && currentEntityType !== null) {
                    // Construct the URL for the ontology editor
                    const url = `/ontology/entity?entity_id=${encodeURIComponent(currentEntityId)}&type=${encodeURIComponent(currentEntityType)}&source=${encodeURIComponent(worldOntologySource)}`;
                    
                    // Navigate to the ontology editor
                    window.location.href = url;
                } else {
                    console.error('Missing required parameters for editing entity in ontology');
                    alert('Unable to edit entity: missing required parameters');
                }
            });
        }
    }
    
    // Helper function to capitalize the first letter of a string
    function capitalizeFirstLetter(string) {
        return string.charAt(0).toUpperCase() + string.slice(1);
    }
});
