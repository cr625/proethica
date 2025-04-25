/**
 * Fix for Ontology Editor URL Issues
 * 
 * This script updates the loadOntology function to properly update the URL
 * when switching between ontologies in the editor. This ensures that when a user
 * clicks on a different ontology in the sidebar, the URL is updated to reflect
 * the currently loaded ontology.
 */

// Original function:
/*
function loadOntology(ontologyId) {
    // Check if there are unsaved changes
    if (isEditorDirty && !confirm('You have unsaved changes. Do you want to discard them?')) {
        return;
    }
    
    // Show loading indicator
    const editorContainer = document.getElementById('editorContainer');
    const loadingOverlay = document.createElement('div');
    loadingOverlay.className = 'loading-overlay';
    loadingOverlay.innerHTML = `
        <div class="spinner-border" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    `;
    editorContainer.appendChild(loadingOverlay);
    
    // Fetch the ontology content
    fetch(`/ontology-editor/api/ontology/${ontologyId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load ontology');
            }
            return response.json();
        })
        .then(data => {
            // Update editor content
            editor.setValue(data.content);
            editor.clearSelection();
            
            // Update current ontology ID
            currentOntologyId = ontologyId;
            
            // Reset dirty flag
            isEditorDirty = false;
            
            // Update UI
            updateUIForLoadedOntology(ontologyId);
            
            // Load versions for this ontology
            loadVersions(ontologyId);
            
            // Remove loading indicator
            editorContainer.removeChild(loadingOverlay);
        })
        .catch(error => {
            console.error('Error loading ontology:', error);
            
            // Display error
            editorContainer.removeChild(loadingOverlay);
            editor.setValue(`# Error loading ontology: ${error.message}`);
            
            // Reset state
            currentOntologyId = null;
            document.getElementById('saveBtn').disabled = true;
            document.getElementById('validateBtn').disabled = true;
            document.getElementById('visualizeBtn').disabled = true;
        });
}
*/

// Updated loadOntology function with URL update
function loadOntology(ontologyId) {
    // Check if there are unsaved changes
    if (isEditorDirty && !confirm('You have unsaved changes. Do you want to discard them?')) {
        return;
    }
    
    // Show loading indicator
    const editorContainer = document.getElementById('editorContainer');
    const loadingOverlay = document.createElement('div');
    loadingOverlay.className = 'loading-overlay';
    loadingOverlay.innerHTML = `
        <div class="spinner-border" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    `;
    editorContainer.appendChild(loadingOverlay);
    
    // Fetch the ontology content
    fetch(`/ontology-editor/api/ontology/${ontologyId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load ontology');
            }
            return response.json();
        })
        .then(data => {
            // Update editor content
            editor.setValue(data.content);
            editor.clearSelection();
            
            // Update current ontology ID
            currentOntologyId = ontologyId;
            
            // Reset dirty flag
            isEditorDirty = false;
            
            // Update UI
            updateUIForLoadedOntology(ontologyId);
            
            // Load versions for this ontology
            loadVersions(ontologyId);
            
            // Update URL to reflect the current ontology
            updateURLWithCurrentOntology(ontologyId);
            
            // Remove loading indicator
            editorContainer.removeChild(loadingOverlay);
        })
        .catch(error => {
            console.error('Error loading ontology:', error);
            
            // Display error
            editorContainer.removeChild(loadingOverlay);
            editor.setValue(`# Error loading ontology: ${error.message}`);
            
            // Reset state
            currentOntologyId = null;
            document.getElementById('saveBtn').disabled = true;
            document.getElementById('validateBtn').disabled = true;
            document.getElementById('visualizeBtn').disabled = true;
        });
}

// New helper function to update the URL
function updateURLWithCurrentOntology(ontologyId) {
    // Get current URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    
    // Update ontology_id parameter
    urlParams.set('ontology_id', ontologyId);
    
    // Preserve the current view parameter if it exists
    const currentView = urlParams.get('view');
    if (!currentView) {
        // Default to "full" view if no view is specified
        urlParams.set('view', 'full');
    }
    
    // Update the URL without reloading the page
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ ontologyId: ontologyId }, '', newUrl);
}

// Instructions for applying the fix:
/*
To apply this fix:

1. Replace the loadOntology function in editor.js with the updated version above
2. Add the new updateURLWithCurrentOntology helper function

This ensures that when users navigate between ontologies, the URL is always 
updated to reflect the currently loaded ontology, which improves:
- Sharability: Users can share links to specific ontologies
- Navigation: Browser history works correctly with back/forward buttons
- Consistency: The URL always matches the displayed content
*/
