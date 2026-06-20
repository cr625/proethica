document.addEventListener('DOMContentLoaded', function() {
    const caseId = (window.ENTITY_REVIEW_PASS2 || {}).caseId;
    const sectionType = (window.ENTITY_REVIEW_PASS2 || {}).sectionType;
    const isAuthenticated = (window.ENTITY_REVIEW_PASS2 || {}).isAuthenticated;
    const loginUrl = (window.ENTITY_REVIEW_PASS2 || {}).loginUrl;

    // Load session count
    appFetch(`/scenario_pipeline/case/${caseId}/entities/sessions`)
        .then(response => response.json())
        .then(data => {
            const sessionCountElement = document.getElementById('sessionCount');
            if (sessionCountElement && data.total_sessions !== undefined) {
                sessionCountElement.textContent = data.total_sessions;
            }
        })
        .catch(error => {
            const sessionCountElement = document.getElementById('sessionCount');
            if (sessionCountElement) {
                sessionCountElement.textContent = 'Error';
            }
            console.error('Error loading sessions:', error);
        });

    // Auto-select all uncommitted entities on page load
    // and update their selection status in the database
    const uncommittedCheckboxes = document.querySelectorAll('.rdf-entity-checkbox:checked');
    uncommittedCheckboxes.forEach(checkbox => {
        const entityId = checkbox.dataset.entityId;
        const entityType = checkbox.dataset.entityType;
        // Update selection status in database for pre-checked items
        updateRDFEntitySelection(entityId, entityType, true);
    });

    // Also update the select-all checkboxes to match the state
    document.querySelectorAll('.rdf-class-select-all').forEach(selectAll => {
        const conceptType = selectAll.dataset.conceptType;
        const allClassBoxes = document.querySelectorAll(`.rdf-entity-checkbox[data-entity-type="class"][data-concept-type="${conceptType}"]`);
        const checkedClassBoxes = document.querySelectorAll(`.rdf-entity-checkbox[data-entity-type="class"][data-concept-type="${conceptType}"]:checked`);
        if (allClassBoxes.length > 0 && allClassBoxes.length === checkedClassBoxes.length) {
            selectAll.checked = true;
        }
    });

    document.querySelectorAll('.rdf-individual-select-all').forEach(selectAll => {
        const conceptType = selectAll.dataset.conceptType;
        const allIndivBoxes = document.querySelectorAll(`.rdf-entity-checkbox[data-entity-type="individual"][data-concept-type="${conceptType}"]`);
        const checkedIndivBoxes = document.querySelectorAll(`.rdf-entity-checkbox[data-entity-type="individual"][data-concept-type="${conceptType}"]:checked`);
        if (allIndivBoxes.length > 0 && allIndivBoxes.length === checkedIndivBoxes.length) {
            selectAll.checked = true;
        }
    });

    // Entity selection handling
    document.querySelectorAll('.entity-select').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const entityId = this.dataset.entityId;
            const selected = this.checked;
            updateEntitySelection(entityId, selected);
        });
    });

    // RDF Entity selection handling
    document.querySelectorAll('.rdf-entity-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const entityId = this.dataset.entityId;
            const entityType = this.dataset.entityType;
            const selected = this.checked;
            updateRDFEntitySelection(entityId, entityType, selected);
        });
    });

    // RDF Class select all handling - per concept type
    document.querySelectorAll('.rdf-class-select-all').forEach(selectAll => {
        selectAll.addEventListener('change', function() {
            const checked = this.checked;
            const conceptType = this.dataset.conceptType;
            // Only select checkboxes within the same concept type
            document.querySelectorAll(`.rdf-entity-checkbox[data-entity-type="class"][data-concept-type="${conceptType}"]`).forEach(checkbox => {
                checkbox.checked = checked;
                updateRDFEntitySelection(checkbox.dataset.entityId, 'class', checked);
            });
        });
    });

    // RDF Individual select all handling - per concept type
    document.querySelectorAll('.rdf-individual-select-all').forEach(selectAll => {
        selectAll.addEventListener('change', function() {
            const checked = this.checked;
            const conceptType = this.dataset.conceptType;
            // Only select checkboxes within the same concept type
            document.querySelectorAll(`.rdf-entity-checkbox[data-entity-type="individual"][data-concept-type="${conceptType}"]`).forEach(checkbox => {
                checkbox.checked = checked;
                updateRDFEntitySelection(checkbox.dataset.entityId, 'individual', checked);
            });
        });
    });

    // Section select all handling
    document.querySelectorAll('.section-select-all').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const section = this.dataset.section;
            const checked = this.checked;

            const card = this.closest('.card');
            card.querySelectorAll('.entity-select').forEach(entityCheckbox => {
                entityCheckbox.checked = checked;
                const entityId = entityCheckbox.dataset.entityId;
                updateEntitySelection(entityId, checked);
            });
        });
    });

    // Edit entity handling (placeholder for future functionality)
    document.querySelectorAll('.edit-entity').forEach(button => {
        button.addEventListener('click', function() {
            const entityId = this.dataset.entityId;
            // For now, just show a placeholder modal
            document.getElementById('editEntityId').value = entityId;
            // Note: Bootstrap modal would need to be handled differently without jQuery
            console.log('Edit entity:', entityId);
        });
    });

    // Foundation for property editing (future functionality)
    // This code prepares for inline property editing capability
    function preparePropertyEditing() {
        // Add data attributes to property items for future editing
        document.querySelectorAll('.property-item').forEach(item => {
            const entityRow = item.closest('tr');
            const entityCheckbox = entityRow?.querySelector('.rdf-entity-checkbox');
            if (entityCheckbox) {
                item.setAttribute('data-entity-id', entityCheckbox.dataset.entityId);
                item.setAttribute('data-entity-type', entityCheckbox.dataset.entityType);
            }

            // Double-click handler (currently disabled)
            item.addEventListener('dblclick', function(e) {
                // Uncomment when edit functionality is implemented
                // e.preventDefault();
                // startPropertyEdit(this);
            });
        });
    }

    // Call preparation function
    preparePropertyEditing();

    // Future edit functions (placeholders)
    function startPropertyEdit(propertyElement) {
        // Will be implemented to enable inline editing
        console.log('Property editing will be available in future update');
    }

    function savePropertyEdit(propertyElement, newValue) {
        // Will be implemented to save edited properties
        console.log('Property saving will be available in future update');
    }

    function cancelPropertyEdit(propertyElement) {
        // Will be implemented to cancel property editing
        console.log('Cancel editing will be available in future update');
    }

    // Delete entity buttons
    document.querySelectorAll('.delete-entity-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const entityId = this.dataset.entityId;
            const entityLabel = this.dataset.entityLabel;

            // Check authentication first
            if (!isAuthenticated) {
                // Show login required modal
                const loginModal = new bootstrap.Modal(document.getElementById('loginRequiredModal'));
                loginModal.show();
                return;
            }

            if (confirm(`Remove entity "${entityLabel}" from this case?`)) {
                const btnElement = this;
                btnElement.disabled = true;
                btnElement.innerHTML = '<i class="bi bi-hourglass"></i>';

                appFetch(`/scenario_pipeline/case/${caseId}/rdf_entities/${entityId}/delete`, {
                    method: 'DELETE'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Remove the row from the table
                        const row = btnElement.closest('tr');
                        if (row) {
                            row.remove();
                        }
                        console.log(`Deleted entity: ${entityLabel}`);
                    } else {
                        alert(`Error: ${data.error}`);
                        btnElement.disabled = false;
                        btnElement.innerHTML = '<i class="bi bi-x-lg"></i>';
                    }
                })
                .catch(error => {
                    console.error('Delete error:', error);
                    alert(`Error deleting entity: ${error}`);
                    btnElement.disabled = false;
                    btnElement.innerHTML = '<i class="bi bi-x-lg"></i>';
                });
            }
        });
    });

    // Legacy: Commit button code removed - publishing moved to Step 4 Review

    function updateEntitySelection(entityId, selected) {
        appFetch(`/scenario_pipeline/case/${caseId}/entities/update_selection`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                entity_id: entityId,
                selected: selected,
                review_notes: ''
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update selected count
                updateSelectedCount();
            } else {
                console.error('Error updating selection:', data.error);
            }
        })
        .catch(error => {
            console.error('Error updating selection:', error);
        });
    }

    function updateRDFEntitySelection(entityId, entityType, selected) {
        appFetch(`/scenario_pipeline/case/${caseId}/rdf_entities/update_selection`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
            },
            body: JSON.stringify({
                entity_id: entityId,
                entity_type: entityType,
                selected: selected
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update selected count
                updateSelectedCount();
            } else {
                console.error('Error updating RDF entity selection:', data.error);
            }
        })
        .catch(error => {
            console.error('Error updating RDF entity selection:', error);
        });
    }

    function updateSelectedCount() {
        const selectedCount = document.querySelectorAll('.entity-select:checked').length;
        const rdfSelectedCount = document.querySelectorAll('.rdf-entity-checkbox:checked').length;
        const totalSelected = selectedCount + rdfSelectedCount;
        const selectedCountElement = document.getElementById('selectedCount');
        if (selectedCountElement) {
            selectedCountElement.textContent = totalSelected;
        }
    }

    // Match Details Modal handling
    const matchDetailsModal = document.getElementById('matchDetailsModal');
    if (matchDetailsModal) {
        matchDetailsModal.addEventListener('show.bs.modal', function(event) {
            const trigger = event.relatedTarget;
            if (!trigger) return;

            // Get data from the trigger element
            const entityId = trigger.dataset.entityId;
            const entityLabel = trigger.dataset.entityLabel;
            const matchedUri = trigger.dataset.matchedUri;
            const matchedLabel = trigger.dataset.matchedLabel;
            const confidence = parseFloat(trigger.dataset.confidence) || 0;
            const method = trigger.dataset.method || 'unknown';
            const reasoning = trigger.dataset.reasoning || '';

            // Populate modal fields
            document.getElementById('matchEntityId').value = entityId;
            document.getElementById('matchEntityLabel').textContent = entityLabel;

            // Matched class info
            if (matchedUri) {
                document.getElementById('matchedClassLabel').textContent = matchedLabel || 'Unknown';
                document.getElementById('matchedClassUri').textContent = matchedUri;
            } else {
                document.getElementById('matchedClassLabel').textContent = 'No match';
                document.getElementById('matchedClassUri').textContent = 'Entity marked as new class';
            }

            // Confidence - only show when there's a match
            const confidenceSection = document.getElementById('matchConfidenceSection');
            if (matchedUri) {
                confidenceSection.style.display = 'block';
                const confidencePercent = Math.round(confidence * 100);
                document.getElementById('matchConfidenceValue').textContent = `${confidencePercent}%`;
                const confidenceBar = document.getElementById('matchConfidenceBar');
                confidenceBar.style.width = `${confidencePercent}%`;
                confidenceBar.className = 'progress-bar';
                if (confidence >= 0.90) {
                    confidenceBar.classList.add('bg-success');
                } else if (confidence >= 0.75) {
                    confidenceBar.classList.add('bg-warning');
                } else if (confidence > 0) {
                    confidenceBar.classList.add('bg-danger');
                } else {
                    confidenceBar.classList.add('bg-secondary');
                }
            } else {
                confidenceSection.style.display = 'none';
            }

            // Method - only show when there's a match
            const methodSection = document.getElementById('matchMethodSection');
            if (matchedUri) {
                methodSection.style.display = 'block';
                const methodDisplay = {
                    'llm': 'LLM Extraction',
                    'embedding': 'Embedding Similarity',
                    'manual': 'Manual Override',
                    'label_match': 'Label Match'
                };
                document.getElementById('matchMethodValue').textContent = methodDisplay[method] || method || 'Not specified';
            } else {
                methodSection.style.display = 'none';
            }

            // Status badge
            const statusBadge = document.getElementById('matchStatusBadge');
            if (matchedUri) {
                if (confidence >= 0.90) {
                    statusBadge.innerHTML = '<span class="badge bg-success">Auto-Linked</span>';
                } else if (confidence >= 0.75) {
                    statusBadge.innerHTML = '<span class="badge bg-warning text-dark">Needs Review</span>';
                } else {
                    statusBadge.innerHTML = '<span class="badge bg-secondary">Low Confidence</span>';
                }
            } else {
                statusBadge.innerHTML = '<span class="badge bg-secondary">New Class</span>';
            }

            // Reasoning
            const reasoningSection = document.getElementById('matchReasoningSection');
            const reasoningValue = document.getElementById('matchReasoningValue');
            if (reasoning) {
                reasoningSection.style.display = 'block';
                reasoningValue.textContent = reasoning;
            } else {
                reasoningSection.style.display = 'none';
            }

            // Show/hide action buttons based on match status
            const actionButtons = document.getElementById('matchActionButtons');
            const confirmBtn = document.getElementById('confirmMatchBtn');
            if (matchedUri) {
                // Has a match - show buttons, enable confirm
                if (actionButtons) actionButtons.style.display = 'flex';
                if (confirmBtn) confirmBtn.disabled = false;
            } else {
                // No match - hide both buttons (they're redundant)
                if (actionButtons) actionButtons.style.display = 'none';
            }
        });

        // Search for alternative matches
        const searchBtn = document.getElementById('searchMatchBtn');
        const searchInput = document.getElementById('searchMatchInput');
        const searchResults = document.getElementById('searchResults');

        if (searchBtn && searchInput && searchResults) {
            searchBtn.addEventListener('click', function() {
                const query = searchInput.value.trim();
                if (!query) return;

                searchBtn.disabled = true;
                searchBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Searching...';

                appFetch(`/scenario_pipeline/case/${caseId}/entities/search_ontserve?q=${encodeURIComponent(query)}`)
                    .then(response => response.json())
                    .then(data => {
                        searchResults.innerHTML = '';
                        searchResults.style.display = 'block';

                        if (data.success && data.results && data.results.length > 0) {
                            data.results.forEach(result => {
                                const item = document.createElement('div');
                                item.className = 'border rounded p-2 mb-2 search-result-item';
                                item.style.cursor = 'pointer';
                                item.innerHTML = `
                                    <strong>${result.label}</strong>
                                    <br/><small class="text-muted">${result.uri}</small>
                                    ${result.description ? `<br/><small>${result.description.substring(0, 100)}...</small>` : ''}
                                `;
                                item.addEventListener('click', function() {
                                    // Highlight selected
                                    document.querySelectorAll('.search-result-item').forEach(el => el.classList.remove('border-primary'));
                                    this.classList.add('border-primary');

                                    // Store selected match
                                    searchResults.dataset.selectedUri = result.uri;
                                    searchResults.dataset.selectedLabel = result.label;

                                    // Enable save button
                                    const saveBtn = document.getElementById('saveMatchBtn');
                                    if (saveBtn) saveBtn.disabled = false;
                                });
                                searchResults.appendChild(item);
                            });
                        } else {
                            searchResults.innerHTML = '<div class="text-muted">No matching classes found</div>';
                        }
                    })
                    .catch(error => {
                        console.error('Search error:', error);
                        searchResults.innerHTML = '<div class="text-danger">Search failed</div>';
                        searchResults.style.display = 'block';
                    })
                    .finally(() => {
                        searchBtn.disabled = false;
                        searchBtn.innerHTML = '<i class="bi bi-search"></i> Search';
                    });
            });

            // Search on Enter key
            searchInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    searchBtn.click();
                }
            });
        }

        // Confirm current match
        const confirmMatchBtn = document.getElementById('confirmMatchBtn');
        if (confirmMatchBtn) {
            confirmMatchBtn.addEventListener('click', function() {
                const entityId = document.getElementById('matchEntityId').value;
                if (!entityId) return;

                this.disabled = true;
                this.innerHTML = '<i class="bi bi-hourglass-split"></i> Confirming...';

                appFetch(`/scenario_pipeline/case/${caseId}/entities/${entityId}/confirm_match`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Close modal and reload to show updated status
                        const modal = bootstrap.Modal.getInstance(document.getElementById('matchDetailsModal'));
                        if (modal) modal.hide();
                        location.reload();
                    } else {
                        alert(`Error: ${data.error}`);
                    }
                })
                .catch(error => {
                    console.error('Confirm match error:', error);
                    alert(`Error: ${error}`);
                })
                .finally(() => {
                    this.disabled = false;
                    this.innerHTML = '<i class="bi bi-check-circle"></i> Confirm Current Match';
                });
            });
        }

        // Save match changes
        const saveMatchBtn = document.getElementById('saveMatchBtn');
        if (saveMatchBtn) {
            saveMatchBtn.addEventListener('click', function() {
                const entityId = document.getElementById('matchEntityId').value;
                const selectedUri = searchResults?.dataset.selectedUri;
                const selectedLabel = searchResults?.dataset.selectedLabel;

                if (!entityId || !selectedUri) {
                    alert('Please select a match from the search results first');
                    return;
                }

                this.disabled = true;
                this.innerHTML = '<i class="bi bi-hourglass-split"></i> Saving...';

                appFetch(`/scenario_pipeline/case/${caseId}/entities/${entityId}/set_match`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        matched_uri: selectedUri,
                        matched_label: selectedLabel,
                        method: 'manual',
                        confidence: 1.0
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Match updated successfully');
                        location.reload();
                    } else {
                        alert(`Error: ${data.error}`);
                    }
                })
                .catch(error => {
                    console.error('Save match error:', error);
                    alert(`Error: ${error}`);
                })
                .finally(() => {
                    this.disabled = false;
                    this.innerHTML = '<i class="bi bi-save"></i> Save Changes';
                });
            });
        }
    }
});
