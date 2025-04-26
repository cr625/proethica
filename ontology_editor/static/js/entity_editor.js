/**
 * Entity Editor JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get the ontology ID and editable status
    const editorContainer = document.getElementById('editor-container');
    const ontologyId = editorContainer.dataset.ontologyId;
    const isEditable = editorContainer.dataset.editable === 'true';
    
    // Elements for toast notifications
    const successToast = new bootstrap.Toast(document.getElementById('success-toast'));
    const errorToast = new bootstrap.Toast(document.getElementById('error-toast'));
    const successMessage = document.getElementById('success-message');
    const errorMessage = document.getElementById('error-message');
    
    // Tab loading management
    const loadedTabs = new Set(['roles', 'conditions']); // Preloaded tabs
    
    // Function to load tab content
    function loadTabContent(tabId) {
        // Skip if already loaded
        if (loadedTabs.has(tabId)) {
            return;
        }
        
        // Get tab content element
        const tabContent = document.getElementById(tabId);
        
        // Show loading spinner
        tabContent.innerHTML = `
            <div class="d-flex justify-content-center my-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `;
        
        // Fetch tab content via AJAX
        fetch(`/ontology-editor/api/entities/${ontologyId}/partial/${tabId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.html) {
                    // Update tab content
                    tabContent.innerHTML = data.html;
                    
                    // Re-initialize event listeners for this tab
                    initializeEntityButtons(tabContent);
                    
                    // Mark as loaded
                    loadedTabs.add(tabId);
                } else {
                    throw new Error('Invalid response format');
                }
            })
            .catch(error => {
                console.error('Error loading tab content:', error);
                tabContent.innerHTML = `
                    <div class="alert alert-danger" role="alert">
                        <i class="bi bi-exclamation-circle"></i> Failed to load content. Please try again.
                        <button class="btn btn-outline-danger btn-sm ms-3" onclick="loadTabContent('${tabId}')">
                            <i class="bi bi-arrow-clockwise"></i> Retry
                        </button>
                    </div>
                `;
            });
    }
    
    // Initialize event listeners for tab clicks
    document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
        tab.addEventListener('shown.bs.tab', function (event) {
            // Get the activated tab id
            const tabId = event.target.getAttribute('data-bs-target').replace('#', '');
            
            // Load content if not already loaded
            loadTabContent(tabId);
        });
    });
    
    // Function to initialize entity buttons for a specific container
    function initializeEntityButtons(container) {
        // Edit entity button
        container.querySelectorAll('.edit-entity-btn').forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                const card = this.closest('.entity-item');
                card.querySelector('.card-view-mode').style.display = 'none';
                card.querySelector('.card-edit-mode').style.display = 'block';
            });
        });
        
        // Cancel edit button
        container.querySelectorAll('.cancel-edit-btn').forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                const card = this.closest('.entity-item');
                card.querySelector('.card-edit-mode').style.display = 'none';
                card.querySelector('.card-view-mode').style.display = 'block';
            });
        });
        
        // Save entity button (form submit)
        container.querySelectorAll('.entity-edit-form').forEach(form => {
            form.addEventListener('submit', async function(e) {
                e.preventDefault();
                
                const entityId = this.dataset.entityId;
                const entityType = this.dataset.entityType;
                
                // Clear previous validation errors
                this.querySelectorAll('.validation-error').forEach(el => {
                    el.textContent = '';
                });
                
                // Collect form data
                const formData = {
                    label: this.querySelector('[name="label"]').value,
                    description: this.querySelector('[name="description"]').value,
                    parent_class: this.querySelector('[name="parent_class"]').value
                };
                
                // Add capabilities for roles
                if (entityType === 'role' && this.querySelector('[name="capabilities"]')) {
                    const capabilitiesSelect = this.querySelector('[name="capabilities"]');
                    formData.capabilities = Array.from(capabilitiesSelect.selectedOptions).map(opt => opt.value);
                }
                
                // Update entity via API
                try {
                    const response = await fetch(`/ontology-editor/api/entities/${ontologyId}/${entityType}/${entityId}`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(formData)
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        // Show success message
                        successMessage.textContent = result.message || 'Entity updated successfully';
                        successToast.show();
                        
                        // Reload the page to show updated entities
                        setTimeout(() => {
                            window.location.reload();
                        }, 1000);
                    } else {
                        // Show error message
                        errorMessage.textContent = result.error || 'Error updating entity';
                        errorToast.show();
                    }
                } catch (error) {
                    console.error('Error updating entity:', error);
                    errorMessage.textContent = 'Network error updating entity';
                    errorToast.show();
                }
            });
        });
        
        // Delete entity button
        container.querySelectorAll('.delete-entity-btn').forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                
                const card = this.closest('.entity-item');
                const form = this.closest('.entity-edit-form');
                const entityId = form.dataset.entityId;
                const entityType = form.dataset.entityType;
                const entityLabel = form.querySelector('[name="label"]').value;
                
                // Show delete confirmation
                document.getElementById('deleteEntityInfo').textContent = `${entityType.charAt(0).toUpperCase() + entityType.slice(1)}: ${entityLabel}`;
                
                // Setup confirm delete button
                const confirmDeleteBtn = document.getElementById('confirmDeleteEntityBtn');
                confirmDeleteBtn.onclick = async () => {
                    try {
                        const response = await fetch(`/ontology-editor/api/entities/${ontologyId}/${entityType}/${entityId}`, {
                            method: 'DELETE'
                        });
                        
                        const result = await response.json();
                        
                        // Hide modal
                        const deleteModal = bootstrap.Modal.getInstance(document.getElementById('deleteConfirmationModal'));
                        deleteModal.hide();
                        
                        if (response.ok) {
                            // Show success message
                            successMessage.textContent = result.message || 'Entity deleted successfully';
                            successToast.show();
                            
                            // Reload the page to update entity list
                            setTimeout(() => {
                                window.location.reload();
                            }, 1000);
                        } else {
                            // Show error message
                            errorMessage.textContent = result.error || 'Error deleting entity';
                            errorToast.show();
                        }
                    } catch (error) {
                        console.error('Error deleting entity:', error);
                        errorMessage.textContent = 'Network error deleting entity';
                        errorToast.show();
                    }
                };
                
                // Show modal
                const deleteModal = new bootstrap.Modal(document.getElementById('deleteConfirmationModal'));
                deleteModal.show();
            });
        });
        
        // Add new entity buttons
        container.querySelectorAll('.add-entity-btn').forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                
                const entityType = this.dataset.entityType;
                
                // Set entity type in form
                document.getElementById('newEntityType').value = entityType;
                
                // Update modal title
                document.getElementById('newEntityModalLabel').textContent = `Add New ${entityType.charAt(0).toUpperCase() + entityType.slice(1)}`;
                
                // Show capabilities field only for roles
                const capabilitiesContainer = document.getElementById('newEntityCapabilitiesContainer');
                capabilitiesContainer.style.display = entityType === 'role' ? 'block' : 'none';
                
                // Populate parent class options
                const parentSelect = document.getElementById('newEntityParent');
                parentSelect.innerHTML = '';
                
                try {
                    // Get the parent classes data from the template
                    const parentsDataElement = document.getElementById(`${entityType}-parents-data`);
                    const parentsData = parentsDataElement ? JSON.parse(parentsDataElement.textContent) : [];
                    
                    // Add options
                    parentsData.forEach(parent => {
                        const option = document.createElement('option');
                        option.value = parent.id;
                        option.textContent = parent.label;
                        parentSelect.appendChild(option);
                    });
                    
                } catch (error) {
                    console.error('Error loading parent classes:', error);
                    // Add a placeholder option
                    const option = document.createElement('option');
                    option.value = '';
                    option.textContent = 'Error loading parent classes';
                    parentSelect.appendChild(option);
                }
                
                // For roles, populate capabilities options
                if (entityType === 'role') {
                    const capabilitiesSelect = document.getElementById('newEntityCapabilities');
                    capabilitiesSelect.innerHTML = '';
                    
                    try {
                        // Get capabilities data
                        const capabilitiesDataElement = document.getElementById('capabilities-data');
                        const capabilitiesData = capabilitiesDataElement ? JSON.parse(capabilitiesDataElement.textContent) : [];
                        
                        // Add options
                        capabilitiesData.forEach(capability => {
                            const option = document.createElement('option');
                            option.value = capability.id;
                            option.textContent = capability.label;
                            capabilitiesSelect.appendChild(option);
                        });
                        
                    } catch (error) {
                        console.error('Error loading capabilities:', error);
                    }
                }
                
                // Show modal
                const newEntityModal = new bootstrap.Modal(document.getElementById('newEntityModal'));
                newEntityModal.show();
            });
        });
    }
    
    // Initialize event listeners for the preloaded tabs
    initializeEntityButtons(document);
    
    // Initialize save new entity button (shared between tabs)
    document.getElementById('saveNewEntityBtn').addEventListener('click', async function(e) {
        e.preventDefault();
        
        const form = document.getElementById('newEntityForm');
        
        // Clear previous validation errors
        form.querySelectorAll('.validation-error').forEach(el => {
            el.textContent = '';
        });
        
        // Get form data
        const entityType = form.elements['entity_type'].value;
        const formData = {
            label: form.elements['label'].value,
            description: form.elements['description'].value,
            parent_class: form.elements['parent_class'].value
        };
        
        // Validate form
        let isValid = true;
        
        if (!formData.label) {
            form.querySelector('[name="label"] + .validation-error').textContent = 'Label is required';
            isValid = false;
        }
        
        if (!formData.description) {
            form.querySelector('[name="description"] + .validation-error').textContent = 'Description is required';
            isValid = false;
        }
        
        if (!formData.parent_class) {
            form.querySelector('[name="parent_class"] + .validation-error').textContent = 'Parent class is required';
            isValid = false;
        }
        
        if (!isValid) {
            return;
        }
        
        // Add capabilities for roles
        if (entityType === 'role' && form.elements['capabilities']) {
            const capabilitiesSelect = form.elements['capabilities'];
            formData.capabilities = Array.from(capabilitiesSelect.selectedOptions).map(opt => opt.value);
        }
        
        // Create entity via API
        try {
            const response = await fetch(`/ontology-editor/api/entities/${ontologyId}/${entityType}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });
            
            const result = await response.json();
            
            // Hide modal
            const newEntityModal = bootstrap.Modal.getInstance(document.getElementById('newEntityModal'));
            newEntityModal.hide();
            
            if (response.ok) {
                // Show success message
                successMessage.textContent = result.message || 'Entity created successfully';
                successToast.show();
                
                // Reload the page to show new entity
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                // Show error message
                errorMessage.textContent = result.error || 'Error creating entity';
                errorToast.show();
            }
        } catch (error) {
            console.error('Error creating entity:', error);
            errorMessage.textContent = 'Network error creating entity';
            errorToast.show();
        }
    });
    
    // =====================================
    // Initialize Bootstrap components
    // =====================================
    
    // Initialize all tooltips
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(tooltip => new bootstrap.Tooltip(tooltip));
});
