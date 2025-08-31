/**
 * Document Annotation Viewer - Frontend component for displaying and managing ontology concept annotations
 */
class DocumentAnnotationViewer {
    constructor(documentId, documentType, options = {}) {
        this.documentId = documentId;
        this.documentType = documentType;
        this.annotations = [];
        this.activeOntology = 'all';
        this.viewMode = 'inline'; // 'inline' or 'sidebar'

        // Configuration
        this.options = {
            containerSelector: options.containerSelector || '#documentContent',
            sidebarSelector: options.sidebarSelector || '#annotationSidebar',
            controlsSelector: options.controlsSelector || '.annotation-controls',
            apiBaseUrl: options.apiBaseUrl || '/annotations/api',
            enableTooltips: options.enableTooltips !== false,
            enableSidebar: options.enableSidebar !== false,
            ...options
        };

        // State
        this.isLoading = false;
        this.originalContent = null;

        // Initialize
        this.init();
    }

    init() {
        this.container = document.querySelector(this.options.containerSelector);
        this.sidebar = document.querySelector(this.options.sidebarSelector);
        this.controls = document.querySelector(this.options.controlsSelector);

        if (!this.container) {
            console.error('Document container not found:', this.options.containerSelector);
            return;
        }

        // Store original content
        this.originalContent = this.container.innerHTML;

        // Set up event listeners
        this.setupEventListeners();

        // Load annotations
        this.loadAnnotations();
    }

    setupEventListeners() {
        // Annotation button
        const annotateBtn = document.getElementById('annotateBtn');
        if (annotateBtn) {
            annotateBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.triggerAnnotation();
            });
        }

        // Enhanced annotation button (LLM-powered)
        const enhancedAnnotateBtn = document.getElementById('enhancedAnnotateBtn');
        if (enhancedAnnotateBtn) {
            enhancedAnnotateBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.triggerEnhancedAnnotation();
            });
        }

        // Ontology filter
        const ontologyFilter = document.getElementById('ontologyFilter');
        if (ontologyFilter) {
            ontologyFilter.addEventListener('change', (e) => {
                this.activeOntology = e.target.value;
                this.renderAnnotations();
            });
        }

        // View mode toggles
        const viewButtons = document.querySelectorAll('[data-view]');
        viewButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const newMode = e.currentTarget.dataset.view;
                this.setViewMode(newMode);

                // Update active button
                viewButtons.forEach(b => b.classList.remove('active'));
                e.currentTarget.classList.add('active');
            });
        });

        // Global click handler for annotation details
        document.addEventListener('click', (e) => {
            if (e.target.closest('.ontology-annotation')) {
                e.preventDefault();
                const annotationElement = e.target.closest('.ontology-annotation');
                const annotationId = annotationElement.dataset.annotationId;
                if (annotationId) {
                    this.showAnnotationDetails(parseInt(annotationId));
                }
            }
        });
    }

    async loadAnnotations() {
        if (this.isLoading) return;

        this.setLoading(true);

        try {
            const url = `${this.options.apiBaseUrl}/${this.documentType}/${this.documentId}`;
            const response = await fetch(url);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.annotations = data.annotations || [];

            console.log(`Loaded ${this.annotations.length} annotations`);

            // Render annotations
            this.renderAnnotations();

            // Update controls
            this.updateControls();

        } catch (error) {
            console.error('Error loading annotations:', error);
            this.showMessage('Error loading annotations: ' + error.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }

    renderAnnotations() {
        // Clear existing annotations
        this.clearAnnotations();

        if (!this.annotations.length) {
            this.showMessage('No annotations found. Click "Annotate with Ontology" to create annotations.', 'info');
            return;
        }

        // Filter annotations by active ontology
        const filteredAnnotations = this.activeOntology === 'all'
            ? this.annotations
            : this.annotations.filter(ann => ann.ontology_name === this.activeOntology);

        if (!filteredAnnotations.length) {
            this.showMessage(`No annotations found for ontology: ${this.activeOntology}`, 'info');
            return;
        }

        // Sort by start offset
        filteredAnnotations.sort((a, b) => (a.start_offset || 0) - (b.start_offset || 0));

        // Apply inline annotations
        this.applyInlineAnnotations(filteredAnnotations);

        // Render sidebar if enabled
        if (this.options.enableSidebar && this.sidebar) {
            this.renderSidebar(filteredAnnotations);
        }

        // Update view mode display
        this.updateViewMode();
    }

    applyInlineAnnotations(annotations) {
        if (!this.container || !this.originalContent) return;

        // Reset to original content
        this.container.innerHTML = this.originalContent;

        // Get plain text content for position mapping
        const textContent = this.container.textContent || this.container.innerText;

        // Sort annotations by start position (descending) to avoid offset issues
        const sortedAnnotations = [...annotations].sort((a, b) => (b.start_offset || 0) - (a.start_offset || 0));

        // Track successfully applied annotations
        let appliedCount = 0;

        for (const annotation of sortedAnnotations) {
            try {
                if (this.applyInlineAnnotation(annotation, textContent)) {
                    appliedCount++;
                }
            } catch (error) {
                console.warn('Error applying annotation:', annotation.text_segment, error);
            }
        }

        // Initialize tooltips if enabled
        if (this.options.enableTooltips) {
            this.initializeTooltips();
        }

        console.log(`Applied ${appliedCount}/${annotations.length} inline annotations`);
    }

    applyInlineAnnotation(annotation, textContent) {
        const textSegment = annotation.text_segment;
        if (!textSegment) return false;

        // Find text in current DOM
        const walker = document.createTreeWalker(
            this.container,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );

        let textNode;
        while (textNode = walker.nextNode()) {
            const nodeText = textNode.textContent;
            const index = nodeText.indexOf(textSegment);

            if (index !== -1) {
                // Create annotation span
                const span = document.createElement('span');
                span.className = this.getAnnotationClasses(annotation);
                span.dataset.annotationId = annotation.id;
                // Set up rich popover instead of simple title
                span.dataset.bsToggle = 'popover';
                span.dataset.bsHtml = 'true';
                span.dataset.bsContent = this.formatRichTooltipContent(annotation);
                span.dataset.bsTrigger = 'hover focus';
                span.dataset.bsPlacement = 'top';
                span.dataset.bsDelay = '{"show":500,"hide":100}';

                // Split text node and wrap the matching part
                const beforeText = nodeText.substring(0, index);
                const afterText = nodeText.substring(index + textSegment.length);

                // Create new text nodes
                const beforeNode = beforeText ? document.createTextNode(beforeText) : null;
                const afterNode = afterText ? document.createTextNode(afterText) : null;
                const matchNode = document.createTextNode(textSegment);

                // Insert span with matched text
                span.appendChild(matchNode);

                // Replace original text node
                const parent = textNode.parentNode;
                if (beforeNode) parent.insertBefore(beforeNode, textNode);
                parent.insertBefore(span, textNode);
                if (afterNode) parent.insertBefore(afterNode, textNode);
                parent.removeChild(textNode);

                return true;
            }
        }

        return false;
    }

    getAnnotationClasses(annotation) {
        const baseClass = 'ontology-annotation';
        const ontologyClass = `ontology-${annotation.ontology_name}`;
        const confidenceClass = `confidence-${annotation.confidence_level || 'unknown'}`;
        const statusClass = `status-${annotation.validation_status || 'pending'}`;

        return `${baseClass} ${ontologyClass} ${confidenceClass} ${statusClass}`;
    }

    formatTooltipText(annotation) {
        const confidence = annotation.confidence ? Math.round(annotation.confidence * 100) : 'N/A';
        return `${annotation.concept_label}\n${annotation.concept_definition || 'No definition available'}\nConfidence: ${confidence}%`;
    }

    formatRichTooltipContent(annotation) {
        const confidence = annotation.confidence ? Math.round(annotation.confidence * 100) : 'N/A';
        const confidenceBadge = this.getConfidenceBadgeClass(annotation.confidence);

        // Format the ontology URI for display
        const shortUri = this.formatUriForDisplay(annotation.concept_uri);

        // Create rich HTML content
        return `
            <div class="annotation-popup" style="max-width: 350px;">
                <div class="popup-header mb-2">
                    <h6 class="mb-1 text-primary fw-bold">${this.escapeHtml(annotation.concept_label)}</h6>
                    <div class="d-flex align-items-center gap-2 mb-1">
                        <span class="badge bg-secondary">${this.escapeHtml(annotation.concept_type)}</span>
                        <span class="badge ${confidenceBadge}">${confidence}%</span>
                        <small class="text-muted">${this.escapeHtml(annotation.ontology_name)}</small>
                    </div>
                </div>
                
                <div class="popup-content">
                    ${annotation.concept_definition ?
                `<p class="mb-2"><small>${this.escapeHtml(annotation.concept_definition)}</small></p>` :
                '<p class="mb-2 text-muted"><small><em>No description available</em></small></p>'
            }
                    
                    <div class="popup-footer">
                        <div class="d-flex align-items-center justify-content-between">
                            <small class="text-muted font-monospace" title="${this.escapeHtml(annotation.concept_uri)}">
                                ${shortUri}
                            </small>
                            <button class="btn btn-outline-primary btn-sm" onclick="navigator.clipboard.writeText('${this.escapeHtml(annotation.concept_uri)}')">
                                <i class="fas fa-copy"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    formatUriForDisplay(uri) {
        if (!uri) return 'No URI';

        // Extract the meaningful part of the URI for display
        if (uri.includes('#')) {
            const parts = uri.split('#');
            const base = parts[0].replace(/^https?:\/\//, '').replace(/^www\./, '');
            return `${base}#${parts[1]}`;
        } else if (uri.includes('/')) {
            return uri.replace(/^https?:\/\//, '').replace(/^www\./, '');
        }
        return uri;
    }

    getConfidenceBadgeClass(confidence) {
        if (!confidence) return 'bg-secondary';
        if (confidence >= 0.9) return 'bg-success';
        if (confidence >= 0.7) return 'bg-warning';
        return 'bg-danger';
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    renderSidebar(annotations) {
        if (!this.sidebar) return;

        const sidebarContent = `
            <div class="annotation-sidebar-header">
                <h5><i class="fas fa-tags"></i> Concept Annotations</h5>
                <p class="text-muted small">${annotations.length} annotations found</p>
            </div>
            <div class="annotation-list">
                ${annotations.map(ann => this.renderSidebarItem(ann)).join('')}
            </div>
        `;

        this.sidebar.innerHTML = sidebarContent;

        // Add click handlers for sidebar items
        this.sidebar.querySelectorAll('.annotation-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const annotationId = parseInt(item.dataset.annotationId);
                this.showAnnotationDetails(annotationId);

                // Highlight corresponding inline annotation
                this.highlightInlineAnnotation(annotationId);
            });
        });
    }

    renderSidebarItem(annotation) {
        const confidence = annotation.confidence ? Math.round(annotation.confidence * 100) : 'N/A';
        const badgeClass = annotation.confidence_badge_class || 'badge-secondary';

        return `
            <div class="annotation-item" data-annotation-id="${annotation.id}">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="annotation-text">
                        <strong>"${this.truncateText(annotation.text_segment, 40)}"</strong>
                        <br>
                        <span class="text-primary">${annotation.concept_label}</span>
                        <br>
                        <small class="text-muted">${annotation.ontology_name}</small>
                    </div>
                    <div class="annotation-badges">
                        <span class="badge ${badgeClass}">${confidence}%</span>
                        <span class="badge badge-${this.getStatusBadgeClass(annotation.validation_status)}">
                            ${annotation.validation_status}
                        </span>
                    </div>
                </div>
                ${annotation.concept_definition ?
                `<p class="annotation-definition mt-2 small text-muted">${this.truncateText(annotation.concept_definition, 100)}</p>`
                : ''
            }
            </div>
        `;
    }

    getStatusBadgeClass(status) {
        const statusMap = {
            'approved': 'success',
            'rejected': 'danger',
            'pending': 'warning'
        };
        return statusMap[status] || 'secondary';
    }

    truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    setViewMode(mode) {
        this.viewMode = mode;
        this.updateViewMode();
    }

    updateViewMode() {
        const container = this.container?.parentElement;
        if (!container) return;

        if (this.viewMode === 'sidebar' && this.sidebar) {
            // Show sidebar
            container.classList.remove('col-md-12');
            container.classList.add('col-md-8');
            this.sidebar.style.display = 'block';
        } else {
            // Hide sidebar
            container.classList.remove('col-md-8');
            container.classList.add('col-md-12');
            if (this.sidebar) {
                this.sidebar.style.display = 'none';
            }
        }
    }

    async triggerEnhancedAnnotation() {
        if (this.isLoading) return;

        this.setLoading(true, 'enhanced');

        try {
            // Use LLM-enhanced annotation endpoint
            const url = `/api/llm-annotations/guideline/${this.documentId}/annotate`;
            const csrfToken = this.getCSRFToken();

            if (!csrfToken) {
                throw new Error('CSRF token not found. Please refresh the page and try again.');
            }

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({})
            });

            if (!response.ok) {
                // Try to get error details from response
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                try {
                    const responseText = await response.text();
                    if (responseText.includes('<')) {
                        // HTML response indicates server error
                        if (response.status === 400 && responseText.includes('CSRF')) {
                            errorMessage = 'CSRF token validation failed. Please refresh the page and try again.';
                        } else {
                            errorMessage = `Server returned an error page (${response.status})`;
                        }
                    } else {
                        // Try to parse as JSON for API error
                        const errorData = JSON.parse(responseText);
                        errorMessage = errorData.error || errorMessage;
                    }
                } catch (parseError) {
                    // Keep original error if we can't parse response
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();

            if (data.success) {
                // Show detailed results
                this.showEnhancedResults(data);
                // Reload annotations
                await this.loadAnnotations();
            } else {
                throw new Error(data.error || 'Enhanced annotation failed');
            }

        } catch (error) {
            console.error('Error triggering enhanced annotation:', error);
            this.showMessage('Error during enhanced annotation: ' + error.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }

    showEnhancedResults(data) {
        // Create a detailed results message
        const stats = data.statistics;
        const successRate = stats.success_rate ? stats.success_rate.toFixed(1) : '0';

        let message = `
            <strong>Enhanced Annotation Complete!</strong><br>
            <ul class="mb-0">
                <li>Terms extracted: ${stats.terms_extracted}</li>
                <li>Successful matches: ${stats.successful_matches}</li>
                <li>Annotations created: ${stats.annotations_created}</li>
                <li>Success rate: ${successRate}%</li>
                <li>Processing time: ${stats.processing_time_ms}ms</li>
            </ul>
        `;

        if (data.ontology_gaps && data.ontology_gaps.length > 0) {
            message += `
                <hr class="my-2">
                <strong>Ontology Gaps Found:</strong><br>
                <small>${data.ontology_gaps.slice(0, 5).join(', ')}${data.ontology_gaps.length > 5 ? ', ...' : ''}</small>
            `;
        }

        this.showMessage(message, 'success', 10000); // Show for 10 seconds
    }

    async triggerAnnotation(forceRefresh = false) {
        if (this.isLoading) return;

        this.setLoading(true);

        try {
            // Use intelligent annotation endpoint for guidelines
            const url = this.documentType === 'guideline'
                ? `/api/annotations/intelligent/guideline/${this.documentId}/annotate`
                : `/annotations/${this.documentType}/${this.documentId}/annotate`;
            const csrfToken = this.getCSRFToken();

            if (!csrfToken) {
                throw new Error('CSRF token not found. Please refresh the page and try again.');
            }

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ force_refresh: forceRefresh })
            });

            if (!response.ok) {
                // Try to get error details from response
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                try {
                    const responseText = await response.text();
                    if (responseText.includes('<')) {
                        // HTML response indicates server error (likely CSRF or authentication issue)
                        if (response.status === 400 && responseText.includes('CSRF')) {
                            errorMessage = 'CSRF token validation failed. Please refresh the page and try again.';
                        } else {
                            errorMessage = `Server returned an error page (${response.status})`;
                        }
                    } else {
                        // Try to parse as JSON for API error
                        const errorData = JSON.parse(responseText);
                        errorMessage = errorData.error || errorMessage;
                    }
                } catch (parseError) {
                    // Keep original error if we can't parse response
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();

            if (data.success) {
                this.showMessage(`Successfully created ${data.annotation_count} annotations`, 'success');
                // Reload annotations
                await this.loadAnnotations();
            } else {
                throw new Error(data.error || 'Annotation failed');
            }

        } catch (error) {
            console.error('Error triggering annotation:', error);
            this.showMessage('Error during annotation: ' + error.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }

    showAnnotationDetails(annotationId) {
        const annotation = this.annotations.find(a => a.id === annotationId);
        if (!annotation) return;

        // Create modal content
        const confidence = annotation.confidence ? Math.round(annotation.confidence * 100) : 'N/A';
        const modalContent = `
            <div class="modal fade" id="annotationModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-tag"></i> ${annotation.concept_label}
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="row">
                                <div class="col-md-8">
                                    <h6>Text Segment</h6>
                                    <p class="alert alert-light">"${annotation.text_segment}"</p>
                                    
                                    <h6>Concept Definition</h6>
                                    <p>${annotation.concept_definition || 'No definition available'}</p>
                                    
                                    ${annotation.llm_reasoning ? `
                                        <h6>AI Reasoning</h6>
                                        <p class="text-muted small">${annotation.llm_reasoning}</p>
                                    ` : ''}
                                </div>
                                <div class="col-md-4">
                                    <h6>Details</h6>
                                    <dl class="small">
                                        <dt>Ontology</dt>
                                        <dd>${annotation.ontology_name}</dd>
                                        
                                        <dt>Concept Type</dt>
                                        <dd>${annotation.concept_type || 'Unknown'}</dd>
                                        
                                        <dt>Confidence</dt>
                                        <dd>
                                            <span class="badge ${annotation.confidence_badge_class}">${confidence}%</span>
                                        </dd>
                                        
                                        <dt>Status</dt>
                                        <dd>
                                            <span class="badge badge-${this.getStatusBadgeClass(annotation.validation_status)}">
                                                ${annotation.validation_status}
                                            </span>
                                        </dd>
                                        
                                        <dt>Created</dt>
                                        <dd>${new Date(annotation.created_at).toLocaleDateString()}</dd>
                                    </dl>
                                    
                                    ${annotation.validation_status === 'pending' ? `
                                        <hr>
                                        <h6>Validation</h6>
                                        <div class="btn-group-vertical w-100">
                                            <button class="btn btn-success btn-sm" onclick="annotationViewer.validateAnnotation(${annotation.id}, 'approve')">
                                                <i class="fas fa-check"></i> Approve
                                            </button>
                                            <button class="btn btn-danger btn-sm" onclick="annotationViewer.validateAnnotation(${annotation.id}, 'reject')">
                                                <i class="fas fa-times"></i> Reject
                                            </button>
                                        </div>
                                    ` : ''}
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <a href="${annotation.concept_uri}" target="_blank" class="btn btn-outline-primary">
                                <i class="fas fa-external-link-alt"></i> View in Ontology
                            </a>
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal
        const existingModal = document.getElementById('annotationModal');
        if (existingModal) {
            existingModal.remove();
        }

        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', modalContent);

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('annotationModal'));
        modal.show();

        // Clean up on hide
        document.getElementById('annotationModal').addEventListener('hidden.bs.modal', function () {
            this.remove();
        });
    }

    async validateAnnotation(annotationId, action) {
        try {
            const response = await fetch(`/annotations/api/annotation/${annotationId}/validate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ action })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            if (data.success) {
                this.showMessage(data.message, 'success');
                // Reload annotations to update status
                await this.loadAnnotations();
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('annotationModal'));
                if (modal) modal.hide();
            } else {
                throw new Error(data.error || 'Validation failed');
            }

        } catch (error) {
            console.error('Error validating annotation:', error);
            this.showMessage('Error during validation: ' + error.message, 'error');
        }
    }

    highlightInlineAnnotation(annotationId) {
        // Remove existing highlights
        document.querySelectorAll('.ontology-annotation.highlighted').forEach(el => {
            el.classList.remove('highlighted');
        });

        // Add highlight to target annotation
        const target = document.querySelector(`[data-annotation-id="${annotationId}"]`);
        if (target) {
            target.classList.add('highlighted');
            target.scrollIntoView({ behavior: 'smooth', block: 'center' });

            // Remove highlight after a delay
            setTimeout(() => {
                target.classList.remove('highlighted');
            }, 3000);
        }
    }

    clearAnnotations() {
        // Remove existing annotation spans
        document.querySelectorAll('.ontology-annotation').forEach(span => {
            const parent = span.parentNode;
            parent.insertBefore(document.createTextNode(span.textContent), span);
            parent.removeChild(span);
        });

        // Normalize text nodes
        this.container?.normalize();
    }

    initializeTooltips() {
        // Initialize rich popovers for annotations
        const popoverElements = document.querySelectorAll('.ontology-annotation[data-bs-toggle="popover"]');
        popoverElements.forEach(element => {
            new bootstrap.Popover(element, {
                placement: 'top',
                trigger: 'hover focus',
                delay: { show: 500, hide: 100 },
                html: true,
                sanitize: false, // Allow custom HTML content
                container: 'body' // Append to body to avoid clipping issues
            });
        });

        // Also support legacy tooltip elements if any exist
        const tooltipElements = document.querySelectorAll('.ontology-annotation[title]:not([data-bs-toggle="popover"])');
        tooltipElements.forEach(element => {
            new bootstrap.Tooltip(element, {
                placement: 'top',
                trigger: 'hover',
                delay: { show: 500, hide: 100 }
            });
        });
    }

    updateControls() {
        const annotateBtn = document.getElementById('annotateBtn');
        if (annotateBtn) {
            const hasAnnotations = this.annotations.length > 0;
            annotateBtn.innerHTML = hasAnnotations
                ? '<i class="fas fa-sync"></i> Re-annotate'
                : '<i class="fas fa-tag"></i> Annotate with Ontology';
        }

        // Update ontology filter options
        const ontologyFilter = document.getElementById('ontologyFilter');
        if (ontologyFilter && this.annotations.length > 0) {
            const ontologies = [...new Set(this.annotations.map(a => a.ontology_name))];

            // Clear existing options (keep 'all')
            const allOption = ontologyFilter.querySelector('option[value="all"]');
            ontologyFilter.innerHTML = '';
            if (allOption) ontologyFilter.appendChild(allOption);

            // Add ontology-specific options
            ontologies.forEach(ontology => {
                const option = document.createElement('option');
                option.value = ontology;
                option.textContent = ontology;
                ontologyFilter.appendChild(option);
            });
        }
    }

    setLoading(isLoading, mode = 'normal') {
        this.isLoading = isLoading;

        const annotateBtn = document.getElementById('annotateBtn');
        const enhancedAnnotateBtn = document.getElementById('enhancedAnnotateBtn');

        if (mode === 'enhanced' && enhancedAnnotateBtn) {
            if (isLoading) {
                enhancedAnnotateBtn.disabled = true;
                enhancedAnnotateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> LLM Processing...';
                if (annotateBtn) annotateBtn.disabled = true;
            } else {
                enhancedAnnotateBtn.disabled = false;
                enhancedAnnotateBtn.innerHTML = '<i class="fas fa-magic"></i> Enhanced Annotate (LLM)';
                if (annotateBtn) annotateBtn.disabled = false;
            }
        } else if (annotateBtn) {
            if (isLoading) {
                annotateBtn.disabled = true;
                annotateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
                if (enhancedAnnotateBtn) enhancedAnnotateBtn.disabled = true;
            } else {
                annotateBtn.disabled = false;
                this.updateControls();
                if (enhancedAnnotateBtn) enhancedAnnotateBtn.disabled = false;
            }
        }

        // Show/hide loading indicator
        const existingLoader = document.querySelector('.annotation-loader');
        if (isLoading && !existingLoader && this.container) {
            const loader = document.createElement('div');
            loader.className = 'annotation-loader alert alert-info';
            loader.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading annotations...';
            this.container.parentElement?.insertBefore(loader, this.container);
        } else if (!isLoading && existingLoader) {
            existingLoader.remove();
        }
    }

    showMessage(message, type = 'info', duration = 5000) {
        // Create alert
        const alertClass = {
            'success': 'alert-success',
            'error': 'alert-danger',
            'warning': 'alert-warning',
            'info': 'alert-info'
        }[type] || 'alert-info';

        const alert = document.createElement('div');
        alert.className = `alert ${alertClass} alert-dismissible fade show annotation-alert`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // Insert at top of container
        if (this.container?.parentElement) {
            this.container.parentElement.insertBefore(alert, this.container);
        }

        // Auto-dismiss after specified duration
        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, duration);
    }

    getCSRFToken() {
        const token = document.querySelector('meta[name=csrf-token]')?.getAttribute('content');
        if (!token) {
            console.warn('CSRF token not found in meta tag');
        }
        return token || '';
    }

    // Public API methods
    refresh() {
        return this.loadAnnotations();
    }

    getAnnotations() {
        return this.annotations;
    }

    getFilteredAnnotations() {
        return this.activeOntology === 'all'
            ? this.annotations
            : this.annotations.filter(ann => ann.ontology_name === this.activeOntology);
    }
}

// Global instance for access from inline scripts
let annotationViewer = null;

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
    // Check if we're on a page with document content
    const contentContainer = document.querySelector('#documentContent, .document-content');
    const documentData = document.querySelector('[data-document-type][data-document-id]');

    if (contentContainer && documentData) {
        const documentType = documentData.dataset.documentType;
        const documentId = parseInt(documentData.dataset.documentId);

        // Initialize annotation viewer
        annotationViewer = new DocumentAnnotationViewer(documentId, documentType);

        // Make it globally accessible
        window.annotationViewer = annotationViewer;

        console.log(`Initialized DocumentAnnotationViewer for ${documentType} ${documentId}`);
    }
});
