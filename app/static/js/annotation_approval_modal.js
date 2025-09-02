/**
 * Annotation Approval Modal Component
 * 
 * Provides a rich interface for users to review, edit, and approve annotations
 * that have been processed by the LLM approval system.
 * 
 * Features:
 * - Display annotation details with full context
 * - Edit concept matches and confidence levels
 * - View version history 
 * - Approve, edit, or reject annotations
 * - Batch approval capabilities
 */

class AnnotationApprovalModal {
    constructor(modalSelector = '#annotationApprovalModal', csrfToken = '') {
        this.currentAnnotation = null;
        this.modalElement = null;
        this.isInitialized = false;
        this.onApprovalCallback = null;
        this.modalSelector = modalSelector;
        this.csrfToken = csrfToken;

        // Initialize the modal
        this.init();
    }

    init() {
        if (this.isInitialized) return;

        // Find existing modal or create one
        this.modalElement = document.querySelector(this.modalSelector);

        if (!this.modalElement) {
            // Create modal HTML structure if it doesn't exist
            this.createModalHTML();
            this.modalElement = document.querySelector(this.modalSelector);
        } else {
            // If modal exists but doesn't have the full content, enhance it
            this.enhanceExistingModal();
        }

        // Set up event listeners
        this.setupEventListeners();

        this.isInitialized = true;
        console.log('AnnotationApprovalModal initialized');
    }

    enhanceExistingModal() {
        // Check if the modal has the required content elements
        const modalBody = this.modalElement.querySelector('.modal-body');
        if (!modalBody.querySelector('#modalContent')) {
            // Replace the simple modal content with the full interface
            modalBody.innerHTML = `
                <!-- Loading State -->
                <div id="modalLoading" class="text-center py-4">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-2">Loading annotation details...</p>
                </div>

                <!-- Main Content -->
                <div id="modalContent" style="display: none;">
                    <!-- Annotation Overview -->
                    <div class="card mb-3">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h6 class="mb-0">Annotation Details</h6>
                            <div id="annotationStageIndicator"></div>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-8">
                                    <h6>Text Segment</h6>
                                    <div id="textSegmentDisplay" class="border rounded p-2 mb-3 bg-light"></div>
                                    
                                    <h6>Document Context</h6>
                                    <div id="documentContextDisplay" class="border rounded p-2 small text-muted"></div>
                                </div>
                                <div class="col-md-4">
                                    <h6>Current Match</h6>
                                    <div id="currentConceptDisplay"></div>
                                    
                                    <h6 class="mt-3">Confidence</h6>
                                    <div id="confidenceDisplay"></div>
                                    
                                    <h6 class="mt-3">Version Info</h6>
                                    <div id="versionInfo" class="small text-muted"></div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Edit Interface -->
                    <div class="card mb-3">
                        <div class="card-header">
                            <h6 class="mb-0">Edit Annotation</h6>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-8">
                                    <div class="mb-3">
                                        <label for="conceptSearch" class="form-label">Search for Different Concept</label>
                                        <input type="text" class="form-control" id="conceptSearch" placeholder="Type to search ontology concepts...">
                                        <div id="conceptSearchResults" class="dropdown-menu w-100" style="display: none;"></div>
                                    </div>
                                    
                                    <div class="mb-3">
                                        <label for="reasoningEdit" class="form-label">Reasoning/Justification</label>
                                        <textarea class="form-control" id="reasoningEdit" rows="3" placeholder="Why does this concept match the text segment?"></textarea>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="mb-3">
                                        <label for="confidenceSlider" class="form-label">Confidence Level: <span id="confidenceValue">0.8</span></label>
                                        <input type="range" class="form-range" id="confidenceSlider" min="0" max="1" step="0.01" value="0.8">
                                        <div class="d-flex justify-content-between small text-muted">
                                            <span>Low</span>
                                            <span>Medium</span>
                                            <span>High</span>
                                        </div>
                                    </div>
                                    
                                    <div class="mb-3">
                                        <label class="form-label">Selected Concept</label>
                                        <div id="selectedConceptDisplay" class="border rounded p-2 bg-light small"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Version History -->
                    <div class="card mb-3">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h6 class="mb-0">Version History</h6>
                            <button class="btn btn-sm btn-outline-secondary" id="toggleVersionHistory">
                                <i class="fas fa-history"></i> Show History
                            </button>
                        </div>
                        <div class="card-body" id="versionHistoryContent" style="display: none;">
                            <div id="versionHistoryList"></div>
                        </div>
                    </div>
                </div>
            `;
        }

        // Update modal actions if needed
        const modalActions = this.modalElement.querySelector('#modalActions');
        if (modalActions) {
            modalActions.innerHTML = `
                <button type="button" class="btn btn-danger me-2" id="rejectAnnotationBtn">
                    <i class="fas fa-times"></i> Reject
                </button>
                <button type="button" class="btn btn-warning me-2" id="saveEditsBtn">
                    <i class="fas fa-save"></i> Save Edits
                </button>
                <button type="button" class="btn btn-success" id="approveAnnotationBtn">
                    <i class="fas fa-check"></i> Approve
                </button>
            `;
        }

        // Set up event listeners for the enhanced content
        this.setupContentEventListeners();
    }

    createModalHTML() {
        // Create modal HTML structure
        const modalHTML = `
            <div class="modal fade" id="annotationApprovalModal" tabindex="-1" aria-labelledby="annotationApprovalModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="annotationApprovalModalLabel">
                                <i class="fas fa-check-circle me-2"></i>Review Annotation
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <!-- Content will be added by enhanceExistingModal -->
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <div id="modalActions">
                                <!-- Action buttons will be populated -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    setupEventListeners() {
        // Modal events only - content-specific listeners will be set up when modal content is enhanced
        this.modalElement?.addEventListener('show.bs.modal', () => {
            this.onModalShow();
        });

        this.modalElement?.addEventListener('hidden.bs.modal', () => {
            this.onModalHide();
        });
    }

    setupContentEventListeners() {
        // This is called after modal content is enhanced to ensure elements exist

        // Confidence slider
        const confidenceSlider = document.getElementById('confidenceSlider');
        const confidenceValue = document.getElementById('confidenceValue');

        confidenceSlider?.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            if (confidenceValue) {
                confidenceValue.textContent = value.toFixed(2);
            }
            this.updateConfidenceDisplay(value);
        });

        // Concept search
        const conceptSearch = document.getElementById('conceptSearch');
        conceptSearch?.addEventListener('input', debounce((e) => {
            this.searchConcepts(e.target.value);
        }, 300));

        // Version history toggle
        const toggleBtn = document.getElementById('toggleVersionHistory');
        toggleBtn?.addEventListener('click', () => {
            this.toggleVersionHistory();
        });

        // Action buttons
        const approveBtn = document.getElementById('approveAnnotationBtn');
        approveBtn?.addEventListener('click', () => {
            this.approveAnnotation();
        });

        const saveBtn = document.getElementById('saveEditsBtn');
        saveBtn?.addEventListener('click', () => {
            this.saveEdits();
        });

        const rejectBtn = document.getElementById('rejectAnnotationBtn');
        rejectBtn?.addEventListener('click', () => {
            this.rejectAnnotation();
        });
    }

    /**
     * Show the approval modal for a specific annotation
     */
    async showApproval(annotationId, callback = null) {
        this.onApprovalCallback = callback;

        // Show loading state
        this.showLoading(true);

        // Show modal
        const modal = new bootstrap.Modal(this.modalElement);
        modal.show();

        try {
            // Load annotation data
            const annotation = await this.loadAnnotation(annotationId);
            this.currentAnnotation = annotation;

            // Populate modal with annotation data
            await this.populateModal(annotation);

            // Hide loading state
            this.showLoading(false);

        } catch (error) {
            console.error('Error loading annotation for approval:', error);
            this.showError('Failed to load annotation details');
        }
    }

    async loadAnnotation(annotationId) {
        const response = await fetch(`/api/annotations/${annotationId}?include_versions=true&include_reasoning=true`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    }

    async populateModal(annotation) {
        // Text segment
        document.getElementById('textSegmentDisplay').innerHTML = `
            <strong>"${annotation.text_segment}"</strong>
        `;

        // Document context (if available)
        if (annotation.document_context) {
            document.getElementById('documentContextDisplay').textContent = annotation.document_context;
        } else {
            document.getElementById('documentContextDisplay').innerHTML = '<em>No additional context available</em>';
        }

        // Current concept match
        document.getElementById('currentConceptDisplay').innerHTML = `
            <div class="d-flex align-items-center mb-2">
                <i class="fas fa-tag me-2 text-primary"></i>
                <strong>${annotation.concept_label}</strong>
            </div>
            <div class="small text-muted mb-2">${annotation.ontology_name}</div>
            <div class="small">${annotation.concept_definition || 'No definition available'}</div>
        `;

        // Confidence display
        this.updateConfidenceDisplay(annotation.confidence);
        document.getElementById('confidenceSlider').value = annotation.confidence || 0.5;
        document.getElementById('confidenceValue').textContent = (annotation.confidence || 0.5).toFixed(2);

        // Version info
        document.getElementById('versionInfo').innerHTML = `
            Version ${annotation.version_number}<br>
            Stage: ${annotation.approval_stage}<br>
            Created: ${new Date(annotation.created_at).toLocaleString()}
        `;

        // Stage indicator
        this.updateStageIndicator(annotation.approval_stage);

        // Reasoning
        document.getElementById('reasoningEdit').value = annotation.llm_reasoning || '';

        // Selected concept (initially same as current)
        this.updateSelectedConcept(annotation);

        // Load version history if available
        if (annotation.version_history && annotation.version_history.length > 1) {
            this.populateVersionHistory(annotation.version_history);
        }
    }

    updateConfidenceDisplay(confidence) {
        const display = document.getElementById('confidenceDisplay');
        let badgeClass = 'secondary';
        let level = 'Unknown';

        if (confidence >= 0.8) {
            badgeClass = 'success';
            level = 'High';
        } else if (confidence >= 0.6) {
            badgeClass = 'info';
            level = 'Medium';
        } else if (confidence >= 0.4) {
            badgeClass = 'warning';
            level = 'Low';
        } else if (confidence > 0) {
            badgeClass = 'danger';
            level = 'Very Low';
        }

        display.innerHTML = `
            <div class="d-flex align-items-center">
                <span class="badge bg-${badgeClass} me-2">${level}</span>
                <span class="text-muted">${(confidence * 100).toFixed(0)}%</span>
            </div>
        `;
    }

    updateStageIndicator(stage) {
        const indicator = document.getElementById('annotationStageIndicator');
        let badgeClass = 'secondary';
        let displayText = stage;

        switch (stage) {
            case 'llm_extracted':
                badgeClass = 'warning';
                displayText = 'LLM Extracted';
                break;
            case 'llm_approved':
                badgeClass = 'info';
                displayText = 'LLM Approved';
                break;
            case 'user_approved':
                badgeClass = 'success';
                displayText = 'User Approved';
                break;
        }

        indicator.innerHTML = `<span class="badge bg-${badgeClass}">${displayText}</span>`;
    }

    updateSelectedConcept(concept) {
        const display = document.getElementById('selectedConceptDisplay');
        display.innerHTML = `
            <div><strong>${concept.concept_label}</strong></div>
            <div class="text-muted small">${concept.ontology_name}</div>
            <div class="small mt-1">${concept.concept_definition || 'No definition'}</div>
        `;
    }

    async searchConcepts(query) {
        if (!query || query.length < 2) {
            document.getElementById('conceptSearchResults').style.display = 'none';
            return;
        }

        try {
            const response = await fetch(`/api/annotations/search/concepts?q=${encodeURIComponent(query)}&limit=10`);
            const results = await response.json();

            this.displaySearchResults(results.concepts || []);
        } catch (error) {
            console.error('Error searching concepts:', error);
        }
    }

    displaySearchResults(concepts) {
        const resultsContainer = document.getElementById('conceptSearchResults');

        if (!concepts.length) {
            resultsContainer.style.display = 'none';
            return;
        }

        const resultsHTML = concepts.map(concept => `
            <div class="dropdown-item concept-search-result" data-concept='${JSON.stringify(concept)}'>
                <div><strong>${concept.label}</strong></div>
                <div class="small text-muted">${concept.ontology_name}</div>
                <div class="small">${concept.definition ? concept.definition.substring(0, 100) + '...' : 'No definition'}</div>
            </div>
        `).join('');

        resultsContainer.innerHTML = resultsHTML;
        resultsContainer.style.display = 'block';

        // Add click handlers
        resultsContainer.querySelectorAll('.concept-search-result').forEach(item => {
            item.addEventListener('click', (e) => {
                const concept = JSON.parse(e.currentTarget.dataset.concept);
                this.selectConcept(concept);
                resultsContainer.style.display = 'none';
                document.getElementById('conceptSearch').value = concept.label;
            });
        });
    }

    selectConcept(concept) {
        this.selectedConcept = concept;
        this.updateSelectedConcept(concept);
    }

    populateVersionHistory(versions) {
        const container = document.getElementById('versionHistoryList');

        const versionsHTML = versions.map((version, index) => `
            <div class="version-item border rounded p-2 mb-2 ${index === 0 ? 'border-primary' : ''}">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <strong>Version ${version.version_number}</strong>
                    <span class="badge bg-${this.getStageColor(version.approval_stage)}">${version.approval_stage}</span>
                </div>
                <div class="small text-muted mb-1">
                    ${new Date(version.created_at).toLocaleString()}
                </div>
                <div class="small">
                    <strong>Concept:</strong> ${version.concept_label}<br>
                    <strong>Confidence:</strong> ${(version.confidence * 100).toFixed(0)}%
                </div>
                ${version.llm_reasoning ? `<div class="small mt-1"><em>"${version.llm_reasoning.substring(0, 150)}..."</em></div>` : ''}
            </div>
        `).join('');

        container.innerHTML = versionsHTML;
    }

    getStageColor(stage) {
        switch (stage) {
            case 'llm_extracted': return 'warning';
            case 'llm_approved': return 'info';
            case 'user_approved': return 'success';
            default: return 'secondary';
        }
    }

    toggleVersionHistory() {
        const content = document.getElementById('versionHistoryContent');
        const button = document.getElementById('toggleVersionHistory');

        if (content.style.display === 'none') {
            content.style.display = 'block';
            button.innerHTML = '<i class="fas fa-eye-slash"></i> Hide History';
        } else {
            content.style.display = 'none';
            button.innerHTML = '<i class="fas fa-history"></i> Show History';
        }
    }

    async approveAnnotation() {
        if (!this.currentAnnotation) return;

        try {
            this.setButtonLoading('approveAnnotationBtn', true);

            const edits = this.gatherEdits();

            const response = await fetch(`/api/annotations/${this.currentAnnotation.id}/approve`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(edits)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();

            this.showSuccess('Annotation approved successfully!');

            // Call callback if provided
            if (this.onApprovalCallback) {
                this.onApprovalCallback('approved', result);
            }

            // Close modal after delay
            setTimeout(() => {
                bootstrap.Modal.getInstance(this.modalElement)?.hide();
            }, 1500);

        } catch (error) {
            console.error('Error approving annotation:', error);
            this.showError('Failed to approve annotation');
        } finally {
            this.setButtonLoading('approveAnnotationBtn', false);
        }
    }

    async saveEdits() {
        if (!this.currentAnnotation) return;

        try {
            this.setButtonLoading('saveEditsBtn', true);

            const edits = this.gatherEdits();

            const response = await fetch(`/api/annotations/${this.currentAnnotation.id}/edit`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(edits)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();

            this.showSuccess('Changes saved successfully!');

            // Update current annotation with new version
            this.currentAnnotation = result.annotation;

            // Call callback if provided
            if (this.onApprovalCallback) {
                this.onApprovalCallback('edited', result);
            }

        } catch (error) {
            console.error('Error saving edits:', error);
            this.showError('Failed to save changes');
        } finally {
            this.setButtonLoading('saveEditsBtn', false);
        }
    }

    async rejectAnnotation() {
        if (!this.currentAnnotation) return;

        if (!confirm('Are you sure you want to reject this annotation?')) {
            return;
        }

        try {
            this.setButtonLoading('rejectAnnotationBtn', true);

            const response = await fetch(`/api/annotations/${this.currentAnnotation.id}/reject`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();

            this.showSuccess('Annotation rejected');

            // Call callback if provided
            if (this.onApprovalCallback) {
                this.onApprovalCallback('rejected', result);
            }

            // Close modal after delay
            setTimeout(() => {
                bootstrap.Modal.getInstance(this.modalElement)?.hide();
            }, 1500);

        } catch (error) {
            console.error('Error rejecting annotation:', error);
            this.showError('Failed to reject annotation');
        } finally {
            this.setButtonLoading('rejectAnnotationBtn', false);
        }
    }

    gatherEdits() {
        const edits = {};

        // Confidence
        const confidence = parseFloat(document.getElementById('confidenceSlider').value);
        if (confidence !== this.currentAnnotation.confidence) {
            edits.confidence = confidence;
        }

        // Reasoning
        const reasoning = document.getElementById('reasoningEdit').value.trim();
        if (reasoning && reasoning !== this.currentAnnotation.llm_reasoning) {
            edits.llm_reasoning = reasoning;
        }

        // Selected concept
        if (this.selectedConcept && this.selectedConcept.uri !== this.currentAnnotation.concept_uri) {
            edits.concept_uri = this.selectedConcept.uri;
            edits.concept_label = this.selectedConcept.label;
            edits.concept_definition = this.selectedConcept.definition;
        }

        return edits;
    }

    // Utility methods
    showLoading(show) {
        const spinner = document.getElementById('modalLoading');
        const content = document.getElementById('modalContent');

        if (spinner && content) {
            if (show) {
                spinner.style.display = 'block';
                content.style.display = 'none';
            } else {
                spinner.style.display = 'none';
                content.style.display = 'block';
            }
        }
    }

    setButtonLoading(buttonId, loading) {
        const button = document.getElementById(buttonId);
        if (!button) return;

        if (loading) {
            button.disabled = true;
            button.dataset.originalContent = button.innerHTML;
            button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
        } else {
            button.disabled = false;
            button.innerHTML = button.dataset.originalContent || button.innerHTML;
        }
    }

    showSuccess(message) {
        this.showAlert(message, 'success');
    }

    showError(message) {
        this.showAlert(message, 'danger');
    }

    showAlert(message, type) {
        const alertHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

        const container = this.modalElement.querySelector('.modal-body');
        container.insertAdjacentHTML('afterbegin', alertHTML);

        // Auto-dismiss after 3 seconds
        setTimeout(() => {
            const alert = container.querySelector('.alert');
            if (alert) {
                bootstrap.Alert.getInstance(alert)?.close();
            }
        }, 3000);
    }

    getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    }

    onModalShow() {
        // Reset any previous state - only if elements exist
        const searchResults = document.getElementById('conceptSearchResults');
        if (searchResults) {
            searchResults.style.display = 'none';
        }
    }

    onModalHide() {
        // Clean up
        this.currentAnnotation = null;
        this.selectedConcept = null;
        this.onApprovalCallback = null;
    }
}

// Utility function for debouncing
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize global instance
window.annotationApprovalModal = new AnnotationApprovalModal();
