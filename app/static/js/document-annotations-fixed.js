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

        // Definition-based annotation button
        const definitionAnnotateBtn = document.getElementById('definitionAnnotateBtn');
        if (definitionAnnotateBtn) {
            definitionAnnotateBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.triggerDefinitionAnnotation();
            });
        }

        // Simplified annotation button with validation
        const simplifiedAnnotateBtn = document.getElementById('simplifiedAnnotateBtn');
        if (simplifiedAnnotateBtn) {
            simplifiedAnnotateBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.triggerSimplifiedAnnotation();
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

        console.log(`Rendering ${filteredAnnotations.length} annotations`);
    }

    async triggerEnhancedAnnotation() {
        if (this.isLoading) return;

        this.setLoading(true, 'enhanced');

        try {
            // Use LLM-enhanced annotation endpoint
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

            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                throw new Error(errorMessage);
            }

            const data = await response.json();

            if (data.success) {
                this.showEnhancedResults(data);
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

    async triggerDefinitionAnnotation() {
        if (this.isLoading) return;

        this.setLoading(true, 'definition');

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

            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                throw new Error(errorMessage);
            }

            const data = await response.json();

            if (data.success) {
                this.showDefinitionResults(data);
                await this.loadAnnotations();
            } else {
                throw new Error(data.error || 'Definition-based annotation failed');
            }

        } catch (error) {
            console.error('Error triggering definition-based annotation:', error);
            this.showMessage('Error during definition-based annotation: ' + error.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }

    async triggerSimplifiedAnnotation() {
        if (this.isLoading) return;

        this.setLoading(true, 'simplified');

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

            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                throw new Error(errorMessage);
            }

            const data = await response.json();

            if (data.success) {
                this.showSimplifiedResults(data);
                await this.loadAnnotations();
            } else {
                throw new Error(data.error || 'Simplified annotation failed');
            }

        } catch (error) {
            console.error('Error triggering simplified annotation:', error);
            this.showMessage('Error during simplified annotation: ' +
