/**
 * Document Annotation Viewer - Minimal working version for LLM annotations
 */
class DocumentAnnotationViewer {
    constructor(documentId, documentType, options = {}) {
        this.documentId = documentId;
        this.documentType = documentType;
        this.annotations = [];
        this.activeOntology = 'all';
        this.isLoading = false;

        this.options = {
            containerSelector: options.containerSelector || '#documentContent',
            apiBaseUrl: options.apiBaseUrl || '/annotations/api',
            ...options
        };

        this.container = document.querySelector(this.options.containerSelector);

        // Set up event listeners
        this.setupEventListeners();

        // Load initial annotations
        this.loadAnnotations();
    }

    setupEventListeners() {
        // Standard annotation button
        const annotateBtn = document.getElementById('annotateBtn');
        if (annotateBtn) {
            annotateBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.triggerAnnotation();
            });
        }

        // Enhanced LLM annotation
        const enhancedBtn = document.getElementById('enhancedAnnotateBtn');
        if (enhancedBtn) {
            enhancedBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.triggerEnhancedAnnotation();
            });
        }

        // Definition-based annotation
        const definitionBtn = document.getElementById('definitionAnnotateBtn');
        if (definitionBtn) {
            definitionBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.triggerDefinitionAnnotation();
            });
        }

        // Simplified with validation
        const simplifiedBtn = document.getElementById('simplifiedAnnotateBtn');
        if (simplifiedBtn) {
            simplifiedBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.triggerSimplifiedAnnotation();
            });
        }
    }

    async loadAnnotations() {
        try {
            const url = `${this.options.apiBaseUrl}/${this.documentType}/${this.documentId}`;
            const response = await fetch(url);
            const data = await response.json();
            this.annotations = data.annotations || [];
            console.log(`Loaded ${this.annotations.length} annotations`);
        } catch (error) {
            console.error('Error loading annotations:', error);
        }
    }

    async triggerAnnotation() {
        if (this.isLoading) return;
        this.setLoading(true);

        try {
            const url = `/api/llm-annotations/guideline/${this.documentId}/annotate-simplified`;
            const csrfToken = this.getCSRFToken();

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({})
            });

            const data = await response.json();
            if (data.success) {
                const stats = data.statistics;
                this.showMessage(`Created ${stats.annotations_created} annotations. Redirecting...`, 'success');
                // Redirect to annotations view page
                setTimeout(() => {
                    window.location.href = `/worlds/${window.location.pathname.split('/')[2]}/guidelines/${this.documentId}/annotations`;
                }, 1500);
            }
        } catch (error) {
            this.showMessage('Error: ' + error.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }

    async triggerEnhancedAnnotation() {
        if (this.isLoading) return;
        this.setLoading(true);

        try {
            const url = `/api/llm-annotations/guideline/${this.documentId}/annotate`;
            const csrfToken = this.getCSRFToken();

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({})
            });

            const data = await response.json();
            if (data.success) {
                const stats = data.statistics;
                this.showMessage(
                    `Enhanced Annotation Complete! Created ${stats.annotations_created} annotations. Redirecting...`,
                    'success'
                );
                // Redirect to annotations view page
                setTimeout(() => {
                    window.location.href = `/worlds/${window.location.pathname.split('/')[2]}/guidelines/${this.documentId}/annotations`;
                }, 1500);
            }
        } catch (error) {
            this.showMessage('Error: ' + error.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }

    async triggerDefinitionAnnotation() {
        if (this.isLoading) return;
        this.setLoading(true);

        try {
            const url = `/api/llm-annotations/guideline/${this.documentId}/annotate-definitions`;
            const csrfToken = this.getCSRFToken();

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({})
            });

            const data = await response.json();
            if (data.success) {
                const stats = data.statistics;
                this.showMessage(
                    `Definition-Based Complete! Created ${stats.annotations_created} annotations. Redirecting...`,
                    'success'
                );
                // Redirect to annotations view page
                setTimeout(() => {
                    window.location.href = `/worlds/${window.location.pathname.split('/')[2]}/guidelines/${this.documentId}/annotations`;
                }, 1500);
            }
        } catch (error) {
            this.showMessage('Error: ' + error.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }

    async triggerSimplifiedAnnotation() {
        if (this.isLoading) return;
        this.setLoading(true);

        try {
            const url = `/api/llm-annotations/guideline/${this.documentId}/annotate-simplified`;
            const csrfToken = this.getCSRFToken();

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({})
            });

            const data = await response.json();
            if (data.success) {
                const stats = data.statistics;
                this.showMessage(
                    `Simplified + Validation Complete! Created ${stats.annotations_created} annotations. Redirecting...`,
                    'success'
                );
                // Redirect to annotations view page
                setTimeout(() => {
                    window.location.href = `/worlds/${window.location.pathname.split('/')[2]}/guidelines/${this.documentId}/annotations`;
                }, 1500);
            }
        } catch (error) {
            this.showMessage('Error: ' + error.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }

    setLoading(isLoading) {
        this.isLoading = isLoading;

        const annotateBtn = document.getElementById('annotateBtn');
        const llmDropdown = document.getElementById('llmAnnotateDropdown');

        if (isLoading) {
            if (annotateBtn) annotateBtn.disabled = true;
            if (llmDropdown) {
                llmDropdown.disabled = true;
                llmDropdown.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
            }
        } else {
            if (annotateBtn) annotateBtn.disabled = false;
            if (llmDropdown) {
                llmDropdown.disabled = false;
                llmDropdown.innerHTML = '<i class="fas fa-magic"></i> LLM Annotate';
            }
        }
    }

    showMessage(message, type = 'info', duration = 5000) {
        const alertClass = type === 'success' ? 'alert-success' :
            type === 'error' ? 'alert-danger' : 'alert-info';

        const alert = document.createElement('div');
        alert.className = `alert ${alertClass} alert-dismissible fade show`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        if (this.container && this.container.parentElement) {
            this.container.parentElement.insertBefore(alert, this.container);
        }

        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, duration);
    }

    getCSRFToken() {
        // Try meta tag first
        const metaToken = document.querySelector('meta[name=csrf-token]')?.getAttribute('content');
        if (metaToken) return metaToken;

        // Try cookie as fallback
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrf_token') {
                return decodeURIComponent(value);
            }
        }

        console.warn('CSRF token not found');
        return '';
    }

    clearAnnotations() {
        // Simple clear function
        document.querySelectorAll('.ontology-annotation').forEach(el => el.remove());
    }

    updateControls() {
        // Update button text if needed
        const annotateBtn = document.getElementById('annotateBtn');
        if (annotateBtn) {
            const hasAnnotations = this.annotations.length > 0;
            annotateBtn.innerHTML = hasAnnotations ?
                '<i class="fas fa-sync"></i> Re-annotate' :
                '<i class="fas fa-tag"></i> Annotate with Ontology';
        }
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
    const documentData = document.querySelector('[data-document-type][data-document-id]');

    if (documentData) {
        const documentType = documentData.dataset.documentType;
        const documentId = parseInt(documentData.dataset.documentId);

        // Initialize annotation viewer
        window.annotationViewer = new DocumentAnnotationViewer(documentId, documentType);

        console.log(`Initialized DocumentAnnotationViewer for ${documentType} ${documentId}`);
    }
});
