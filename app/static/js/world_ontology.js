/**
 * JavaScript for handling ontology-related interactions in the world view
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get the edit link
    const editEntityBtn = document.getElementById('edit-entity-ontology-btn');
    
    if (editEntityBtn) {
        editEntityBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Get the current entity data from the modal
            const entityTypeElement = document.querySelector('.view-details[data-bs-toggle="modal"][aria-expanded="true"]');
            if (!entityTypeElement) {
                console.error('Could not determine current entity type and ID');
                alert('Could not determine which entity to edit. Please try again.');
                return;
            }
            
            const entityType = entityTypeElement.getAttribute('data-entity-type');
            const entityId = entityTypeElement.getAttribute('data-entity-id');
            const worldId = document.body.getAttribute('data-world-id') || 
                            window.location.pathname.split('/').filter(Boolean)[1];
            
            // Get the source
            const source = document.querySelector('a[href^="/ontology-editor?source="]')
                         .getAttribute('href').split('source=')[1];
            
            if (!entityType || !entityId || !source) {
                console.error('Missing required data', { entityType, entityId, source });
                alert('Missing information required to edit this entity. Please try again.');
                return;
            }
            
            // Redirect to the ontology editor with the entity highlighted
            window.location.href = `/ontology-editor/entity?entity_id=${entityId}&type=${entityType}&source=${source}`;
        });
    }
    
    // Add world ID to body for JavaScript reference
    const worldIdMatch = window.location.pathname.match(/\/worlds\/(\d+)/);
    if (worldIdMatch && worldIdMatch[1]) {
        document.body.setAttribute('data-world-id', worldIdMatch[1]);
    }
});
