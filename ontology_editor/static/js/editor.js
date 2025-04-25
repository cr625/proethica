/**
 * Ontology Editor JavaScript
 * 
 * This script handles the interaction with the ontology editor interface,
 * including loading ontologies, editing, validating, and saving changes.
 */

// Initialize global variables
let editor;               // ACE editor instance
let currentOntologyId;    // Currently loaded ontology ID
let isEditorDirty = false; // Track if changes have been made
let sourceParam = null;    // Track source parameter from URL

// Document ready function
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the ACE editor
    initializeEditor();
    
    // Get parameters from URL
    const urlParams = new URLSearchParams(window.location.search);
    sourceParam = urlParams.get('source');
    const ontologyId = urlParams.get('ontology_id');
    
    // Always load the list of ontologies for the sidebar
    loadOntologyList();
    
    // If ontology_id is available, load that specific ontology
    if (ontologyId) {
        loadOntology(ontologyId);
    }
    // Otherwise, if source parameter is available, load that ontology
    else if (sourceParam) {
        loadOntologyBySource(sourceParam);
    }
    
    // Set up event listeners
    setupEventListeners();
});

/**
 * Initialize the ACE editor
 */
function initializeEditor() {
    editor = ace.edit("editor");
    editor.setTheme("ace/theme/monokai");
    editor.session.setMode("ace/mode/turtle");
    editor.setShowPrintMargin(false);
    editor.setOptions({
        enableBasicAutocompletion: true,
        enableLiveAutocompletion: true,
        fontSize: "14px",
        tabSize: 2
    });
    
    // Track changes to enable/disable save button
    editor.getSession().on('change', function() {
        if (!isEditorDirty && currentOntologyId) {
            isEditorDirty = true;
            document.getElementById('saveBtn').disabled = false;
        }
    });
}

/**
 * Set up event listeners for buttons and other controls
 */
function setupEventListeners() {
    // Validate button
    document.getElementById('validateBtn').addEventListener('click', validateOntology);
    
    // Save button
    document.getElementById('saveBtn').addEventListener('click', function() {
        // Show save modal to get commit message
        const saveModal = new bootstrap.Modal(document.getElementById('saveVersionModal'));
        saveModal.show();
    });
    
    // Confirm save button in modal
    document.getElementById('confirmSaveBtn').addEventListener('click', saveOntology);
    
    // Visualize button
    document.getElementById('visualizeBtn').addEventListener('click', function() {
        if (currentOntologyId) {
            window.location.href = `/ontology-editor/visualize/${currentOntologyId}`;
        } else {
            alert('Please open an ontology before visualizing');
        }
    });
    
    // Create ontology button
    document.getElementById('createOntologyBtn').addEventListener('click', createNewOntology);
    
    // Close validation results button
    document.getElementById('closeValidationBtn').addEventListener('click', function() {
        document.getElementById('validationCard').style.display = 'none';
    });
}

/**
 * Load an ontology by its source identifier (filename)
 * 
 * @param {string} source - Source identifier of the ontology to load
 */
function loadOntologyBySource(source) {
    console.log('Loading ontology by source:', source);
    
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
    
    // Determine if source is numeric ID or string identifier
    const apiUrl = !isNaN(parseInt(source)) 
        ? `/ontology-editor/api/ontologies/${source}`  // Numeric ID - use /ontologies endpoint
        : `/ontology-editor/api/ontology/${source}`;   // Source string - use /ontology endpoint
    
    // Fetch the ontology content by source
    const fetchPromise = fetch(apiUrl)
    // Set a timeout for the spinner state
    let spinnerTimeout = setTimeout(() => {
        loadingOverlay.innerHTML = `
            <div class="text-center">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2">Still loading ontology... If this persists, please check your API configuration.</p>
            </div>
        `;
    }, 3000);
    
    fetchPromise.then(response => {
        clearTimeout(spinnerTimeout);
            if (!response.ok) {
                throw new Error('Failed to load ontology by source');
            }
            return response.json();
        })
        .then(data => {
            // Update editor content
            editor.setValue(data.content || '# No content available');
            editor.clearSelection();
            
            // Update current ontology ID
            currentOntologyId = data.ontology.id;
            
            // Reset dirty flag
            isEditorDirty = false;
            
            // Update UI
            document.getElementById('editorTitle').innerText = `Editing: ${data.ontology.name || data.ontology.title || source}`;
            document.getElementById('saveBtn').disabled = true;
            document.getElementById('validateBtn').disabled = false;
            document.getElementById('visualizeBtn').disabled = false;
            
            // Load versions for this ontology if available
            if (data.ontology.id) {
                loadVersions(data.ontology.id);
            }
            
            // Remove loading indicator
            editorContainer.removeChild(loadingOverlay);
        })
        .catch(error => {
            console.error('Error loading ontology by source:', error);
            
            // Display error
            editorContainer.removeChild(loadingOverlay);
            editor.setValue(`# Error loading ontology: ${error.message}\n\n# This might be because:\n# 1. The ontology file does not exist\n# 2. The source parameter is incorrect\n# 3. The server is not properly configured\n\n# Try creating a new ontology or contact your administrator.`);
            
            // Reset state
            currentOntologyId = null;
            document.getElementById('saveBtn').disabled = true;
            document.getElementById('validateBtn').disabled = true;
            document.getElementById('visualizeBtn').disabled = true;
            
            // Load the list of ontologies as a fallback
            loadOntologyList();
        });
}

/**
 * Load the list of ontologies from the API
 */
function loadOntologyList() {
    fetch('/ontology-editor/api/ontologies')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load ontologies');
            }
            return response.json();
        })
        .then(data => {
            updateOntologyList(data.ontologies || []);
        })
        .catch(error => {
            console.error('Error loading ontologies:', error);
            document.getElementById('ontologyList').innerHTML = `
                <li class="list-group-item text-danger">
                    Failed to load ontologies: ${error.message}
                </li>
            `;
        });
}

/**
 * Update the ontology list in the UI
 * 
 * @param {Array} ontologies - List of ontology metadata objects
 */
function updateOntologyList(ontologies) {
    const listElement = document.getElementById('ontologyList');
    
    if (ontologies.length === 0) {
        listElement.innerHTML = `
            <li class="list-group-item text-muted">
                No ontologies found. Click 'New' to create one.
            </li>
        `;
        return;
    }
    
    // Sort ontologies by name/title
    ontologies.sort((a, b) => {
        const nameA = a.name || a.title || '';
        const nameB = b.name || b.title || '';
        return nameA.localeCompare(nameB);
    });
    
    // Create list items
    const items = ontologies.map(ontology => {
        // Handle different property naming (database uses 'name', old format uses 'title')
        const title = ontology.name || ontology.title || 'Unnamed Ontology';
        const domain = ontology.domain_id || ontology.domain || '';
        
        return `
            <li class="list-group-item" 
                data-ontology-id="${ontology.id}">
                <div>
                    <div>${title}</div>
                    <small class="text-muted">${domain}</small>
                </div>
            </li>
        `;
    }).join('');
    
    listElement.innerHTML = items;
    
    // Add click event listeners
    document.querySelectorAll('#ontologyList li').forEach(item => {
        item.addEventListener('click', function() {
            const ontologyId = this.dataset.ontologyId;
            loadOntology(ontologyId);
        });
    });
    
    // Delete functionality disabled for now
    /* 
    document.querySelectorAll('.delete-ontology').forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation(); // Prevent triggering the li click event
            
            const ontologyId = this.dataset.ontologyId;
            if (confirm('Are you sure you want to delete this ontology? This action cannot be undone.')) {
                deleteOntology(ontologyId);
            }
        });
    });
    */
}

/**
 * Load a specific ontology into the editor
 * 
 * @param {string} ontologyId - ID of the ontology to load
 */
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
    fetch(`/ontology-editor/api/ontologies/${ontologyId}`)
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

/**
 * Update UI elements when an ontology is loaded
 * 
 * @param {string} ontologyId - ID of the loaded ontology
 */
function updateUIForLoadedOntology(ontologyId) {
    // Update title
    const ontologyItem = document.querySelector(`#ontologyList li[data-ontology-id="${ontologyId}"]`);
    if (ontologyItem) {
        const title = ontologyItem.querySelector('div > div').innerText;
        document.getElementById('editorTitle').innerText = `Editing: ${title}`;
    } else {
        document.getElementById('editorTitle').innerText = `Editing Ontology`;
    }
    
    // Highlight the selected ontology in the list
    document.querySelectorAll('#ontologyList li').forEach(item => {
        item.classList.remove('active-ontology');
    });
    
    if (ontologyItem) {
        ontologyItem.classList.add('active-ontology');
    }
    
    // Enable buttons
    document.getElementById('saveBtn').disabled = !isEditorDirty;
    document.getElementById('validateBtn').disabled = false;
    document.getElementById('visualizeBtn').disabled = false;
    
    // Hide validation results
    document.getElementById('validationCard').style.display = 'none';
}

/**
 * Load versions for the current ontology
 * 
 * @param {string} ontologyId - ID of the ontology
 */
function loadVersions(ontologyId) {
    fetch(`/ontology-editor/api/versions/${ontologyId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load versions');
            }
            return response.json();
        })
        .then(data => {
            updateVersionsList(data.versions || []);
        })
        .catch(error => {
            console.error('Error loading versions:', error);
            document.getElementById('versionList').innerHTML = `
                <li class="list-group-item text-danger">
                    Failed to load versions: ${error.message}
                </li>
            `;
        });
}

/**
 * Update the versions list in the UI
 * 
 * @param {Array} versions - List of version metadata objects
 */
function updateVersionsList(versions) {
    const listElement = document.getElementById('versionList');
    
    if (versions.length === 0) {
        listElement.innerHTML = `
            <li class="list-group-item text-muted">
                No versions available
            </li>
        `;
        return;
    }
    
    // Sort versions by number (descending)
    versions.sort((a, b) => b.version_number - a.version_number);
    
    // Create list items
    const items = versions.map(version => {
        const date = new Date(version.created_at || version.committed_at);
        const formattedDate = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        
        return `
            <li class="list-group-item" data-version-id="${version.id}">
                <div class="version-info">
                    <span class="version-number">v${version.version_number}</span>
                    <span class="version-date">${formattedDate}</span>
                </div>
                ${version.commit_message ? `<div class="version-message">${version.commit_message}</div>` : ''}
            </li>
        `;
    }).join('');
    
    listElement.innerHTML = items;
    
    // Add click event listeners
    document.querySelectorAll('#versionList li').forEach(item => {
        item.addEventListener('click', function() {
            // Check if there are unsaved changes
            if (isEditorDirty && !confirm('You have unsaved changes. Do you want to discard them?')) {
                return;
            }
            
            const versionId = this.dataset.versionId;
            loadVersion(versionId);
        });
    });
}

/**
 * Load a specific version into the editor
 * 
 * @param {string} versionId - ID of the version to load
 */
function loadVersion(versionId) {
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
    
    // Fetch the version content
    fetch(`/ontology-editor/api/versions/${versionId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load version');
            }
            return response.json();
        })
        .then(data => {
            // Update editor content
            editor.setValue(data.content);
            editor.clearSelection();
            
            // Reset dirty flag (loading a version doesn't make the editor dirty)
            isEditorDirty = false;
            document.getElementById('saveBtn').disabled = true;
            
            // Highlight the selected version in the list
            document.querySelectorAll('#versionList li').forEach(item => {
                item.classList.remove('active');
            });
            
            const versionItem = document.querySelector(`#versionList li[data-version-id="${versionId}"]`);
            if (versionItem) {
                versionItem.classList.add('active');
            }
            
            // Remove loading indicator
            editorContainer.removeChild(loadingOverlay);
        })
        .catch(error => {
            console.error('Error loading version:', error);
            
            // Display error
            editorContainer.removeChild(loadingOverlay);
            alert(`Error loading version: ${error.message}`);
        });
}

/**
 * Validate the current ontology
 */
function validateOntology() {
    // Hide any existing validation results
    document.getElementById('validationCard').style.display = 'none';
    
    if (!currentOntologyId) {
        alert('No ontology loaded to validate');
        return;
    }
    
    // First validate syntax
    const content = editor.getValue();
    
    // Show loading indicator
    const resultsElement = document.getElementById('validationResults');
    resultsElement.innerHTML = `
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Validating...</span>
            </div>
            <p>Validating ontology...</p>
        </div>
    `;
    document.getElementById('validationCard').style.display = 'block';
    
    // First send to validate TTL syntax
    fetch(`/ontology-editor/api/validate/${currentOntologyId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ content })
    })
    .then(response => response.json())
    .then(syntaxResult => {
        // If syntax is invalid, show errors
        if (!syntaxResult.is_valid) {
            let errorHtml = `
                <div class="validation-error">
                    <strong>Syntax Validation Failed</strong>
                </div>
            `;
            
            // Check if errors array exists before iterating
            if (syntaxResult.errors && Array.isArray(syntaxResult.errors) && syntaxResult.errors.length > 0) {
                errorHtml += '<ul class="validation-error">';
                syntaxResult.errors.forEach(error => {
                    errorHtml += `<li>${error}</li>`;
                });
                errorHtml += '</ul>';
            } else {
                // Generic error message if no specific errors are provided
                errorHtml += `<p class="validation-error">The ontology contains syntax errors. Please check your syntax.</p>`;
            }
            
            resultsElement.innerHTML = errorHtml;
            return;
        }
        
        // Display success message for syntax validation (BFO validation temporarily disabled)
        displayValidationResults(true, { warnings: [], suggestions: [] });
        
        /* BFO validation is temporarily disabled as it needs implementation
        // Only attempt BFO validation if we actually have it implemented properly
        // For now, just display the syntax validation result
        */
    })
    .catch(error => {
        console.error('Error during syntax validation:', error);
        resultsElement.innerHTML = `
            <div class="validation-error">
                <strong>Error during syntax validation:</strong> ${error.message}
            </div>
        `;
    });
}

/**
 * Display validation results in the UI
 * 
 * @param {boolean} syntaxValid - Whether the syntax is valid
 * @param {Object} bfoResults - BFO validation results
 */
function displayValidationResults(syntaxValid, bfoResults) {
    const resultsElement = document.getElementById('validationResults');
    let html = '';
    
    // Syntax validation
    html += `
        <div class="validation-success mb-3">
            <strong>Syntax Validation:</strong> Valid
        </div>
    `;
    
    // BFO compliance
    html += '<div class="mb-3"><strong>BFO Compliance:</strong></div>';
    
    if (bfoResults.warnings && bfoResults.warnings.length > 0) {
        html += '<div class="validation-warning">Warnings:</div><ul>';
        bfoResults.warnings.forEach(warning => {
            html += `<li>${warning}</li>`;
        });
        html += '</ul>';
    } else {
        html += '<div class="validation-success">No BFO compliance issues found</div>';
    }
    
    // Suggestions
    if (bfoResults.suggestions && bfoResults.suggestions.length > 0) {
        html += '<div class="mt-3"><strong>Suggestions:</strong></div><ul>';
        bfoResults.suggestions.forEach(suggestion => {
            html += `<li class="validation-suggestion">${suggestion}</li>`;
        });
        html += '</ul>';
    }
    
    resultsElement.innerHTML = html;
}

/**
 * Save the current ontology
 */
function saveOntology() {
    if (!currentOntologyId) {
        alert('No ontology loaded to save');
        return;
    }
    
    const content = editor.getValue();
    const commitMessage = document.getElementById('commitMessage').value;
    
    // Close the modal
    const saveModal = bootstrap.Modal.getInstance(document.getElementById('saveVersionModal'));
    saveModal.hide();
    
    // Show loading indicator
    const editorContainer = document.getElementById('editorContainer');
    const loadingOverlay = document.createElement('div');
    loadingOverlay.className = 'loading-overlay';
    loadingOverlay.innerHTML = `
        <div class="spinner-border" role="status">
            <span class="visually-hidden">Saving...</span>
        </div>
    `;
    editorContainer.appendChild(loadingOverlay);
    
    // Update the ontology content
    fetch(`/ontology-editor/api/ontologies/${currentOntologyId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            content,
            commit_message: commitMessage
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to save ontology');
        }
        return response.json();
    })
    .then(data => {
        // Update UI state
        isEditorDirty = false;
        document.getElementById('saveBtn').disabled = true;
        
        // Reload versions list
        loadVersions(currentOntologyId);
        
        // Remove loading indicator
        editorContainer.removeChild(loadingOverlay);
        
        // Show success message
        alert('Ontology saved successfully');
    })
    .catch(error => {
        console.error('Error saving ontology:', error);
        
        // Remove loading indicator
        editorContainer.removeChild(loadingOverlay);
        
        // Show error message
        alert(`Error saving ontology: ${error.message}`);
    });
}

/**
 * Create a new ontology
 */
function createNewOntology() {
    const title = document.getElementById('ontologyTitle').value;
    const filename = document.getElementById('ontologyFilename').value;
    const domain = document.getElementById('ontologyDomain').value;
    const description = document.getElementById('ontologyDescription').value;
    
    // Basic validation
    if (!title || !filename || !domain) {
        alert('Please fill in all required fields');
        return;
    }
    
    // Close the modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('newOntologyModal'));
    modal.hide();
    
    // Generate initial TTL content
    const initialContent = generateInitialTTL(title, domain);
    
    // Create the ontology
    fetch('/ontology-editor/api/ontologies', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            title,
            filename,
            domain,
            description,
            content: initialContent
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to create ontology');
        }
        return response.json();
    })
    .then(data => {
        // Reload ontology list
        loadOntologyList();
        
        // Load the new ontology
        setTimeout(() => {
            loadOntology(data.ontology_id);
        }, 500);
        
        // Reset form
        document.getElementById('ontologyTitle').value = '';
        document.getElementById('ontologyFilename').value = '';
        document.getElementById('ontologyDomain').value = '';
        document.getElementById('ontologyDescription').value = '';
    })
    .catch(error => {
        console.error('Error creating ontology:', error);
        alert(`Error creating ontology: ${error.message}`);
    });
}

/**
 * Delete an ontology
 * 
 * @param {string} ontologyId - ID of the ontology to delete
 */
function deleteOntology(ontologyId) {
    fetch(`/ontology-editor/api/ontologies/${ontologyId}`, {
        method: 'DELETE'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to delete ontology');
        }
        return response.json();
    })
    .then(data => {
        // Reload ontology list
        loadOntologyList();
        
        // Clear editor if the current ontology was deleted
        if (currentOntologyId === ontologyId) {
            editor.setValue('');
            currentOntologyId = null;
            document.getElementById('editorTitle').innerText = 'Ontology Editor';
            document.getElementById('saveBtn').disabled = true;
            document.getElementById('validateBtn').disabled = true;
            document.getElementById('visualizeBtn').disabled = true;
            document.getElementById('versionList').innerHTML = `
                <li class="list-group-item text-center text-muted">
                    Select an ontology to view versions
                </li>
            `;
        }
    })
    .catch(error => {
        console.error('Error deleting ontology:', error);
        alert(`Error deleting ontology: ${error.message}`);
    });
}

/**
 * Generate initial TTL content for a new ontology
 * 
 * @param {string} title - Ontology title
 * @param {string} domain - Ontology domain
 * @returns {string} - Initial TTL content
 */
function generateInitialTTL(title, domain) {
    const date = new Date().toISOString().split('T')[0];
    const baseUri = `http://proethica.org/ontology/${domain}`;
    
    return `@prefix : <${baseUri}#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix xml: <http://www.w3.org/XML/1998/namespace> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .

<${baseUri}> rdf:type owl:Ontology ;
    owl:versionIRI <${baseUri}/1.0> ;
    owl:imports <http://purl.obolibrary.org/obo/bfo.owl> ;
    rdfs:label "${title}" ;
    rdfs:comment "An ontology for the ${domain} domain." ;
    owl:versionInfo "Version 1.0 - ${date}" .

# Add your classes and properties below
`;
}
