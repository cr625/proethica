/**
 * Case Detail Page Interactions
 * -----------------------------
 * Handle interactive elements on the case detail page:
 * 1. Triple label selection for finding related cases
 * 2. Show more/less toggle for case description
 * 3. Clear selection button for triple labels
 * 4. Color coding for different triple sources (McLaren vs. Engineering Ethics)
 */

// Global variables
let documentId = null;

document.addEventListener('DOMContentLoaded', function () {
    try {
        // Store the selected triples
        const selectedTriples = new Set();

        // Try to get the document ID from the page
        const docIdEl = document.getElementById('document-id');
        if (docIdEl) {
            documentId = parseInt(docIdEl.value);
        } else {
            // Extract from URL if element not found
            const pathParts = window.location.pathname.split('/');
            if (pathParts.length > 2 && pathParts[1] === 'cases') {
                documentId = parseInt(pathParts[2]);
            }
        }

        // Initialize color coding for triples by source
        initTripleColorCoding();

        // Get DOM elements - with null checks and fallbacks
        const tripleLabels = document.querySelectorAll('.triple-label') || [];
        const relatedCasesContainer = document.getElementById('relatedCasesContainer');
        const relatedCasesContent = document.getElementById('relatedCasesContent');
        const relatedCasesList = document.getElementById('relatedCasesList');
        const clearSelectionBtn = document.getElementById('clearSelection');

        // Description container elements
        const descriptionContainer = document.getElementById('description-container');
        const descriptionContent = document.getElementById('description-content');

        // Add click event to all triple labels
        if (tripleLabels.length > 0) {
            tripleLabels.forEach(label => {
                label.addEventListener('click', function () {
                    // Toggle selection
                    const selected = this.classList.toggle('selected');
                    const tripleKey = getTripleKey(this);

                    if (selected) {
                        selectedTriples.add(tripleKey);
                        this.classList.replace('bg-info', 'bg-primary');
                        this.classList.replace('text-dark', 'text-white');
                    } else {
                        selectedTriples.delete(tripleKey);
                        this.classList.replace('bg-primary', 'bg-info');
                        this.classList.replace('text-white', 'text-dark');
                    }

                    // Update UI
                    if (selectedTriples.size > 0) {
                        if (clearSelectionBtn) clearSelectionBtn.style.display = 'block';
                        if (relatedCasesContainer) relatedCasesContainer.style.display = 'block';
                        fetchRelatedCases();
                    } else {
                        if (clearSelectionBtn) clearSelectionBtn.style.display = 'none';
                        if (relatedCasesContainer) relatedCasesContainer.style.display = 'none';
                    }
                });
            });
        }

        // Add show more/less toggle for description
        if (descriptionContainer && descriptionContent) {
            setupShowMoreLessToggle();
        }

        // Clear selection button
        if (clearSelectionBtn) {
            clearSelectionBtn.addEventListener('click', function () {
                selectedTriples.clear();
                tripleLabels.forEach(label => {
                    label.classList.remove('selected');
                    label.classList.replace('bg-primary', 'bg-info');
                    label.classList.replace('text-white', 'text-dark');
                });
                clearSelectionBtn.style.display = 'none';
                if (relatedCasesContainer) relatedCasesContainer.style.display = 'none';
            });
        }

        /**
         * Initialize color coding for triples by source
         */
        function initTripleColorCoding() {
            const tripleLabels = document.querySelectorAll('.triple-label');

            tripleLabels.forEach(label => {
                // Read metadata to determine the triple source
                const metadata = label.getAttribute('data-metadata');
                if (metadata) {
                    try {
                        const metaObj = JSON.parse(metadata);
                        if (metaObj && metaObj.triple_type) {
                            // Apply different styling based on triple type
                            if (metaObj.triple_type === 'mclaren_extensional') {
                                label.classList.remove('bg-info');
                                label.classList.add('bg-success', 'text-white');
                                label.setAttribute('data-source', 'mclaren');
                                label.setAttribute('title', 'McLaren Extensional Definition');
                            } else if (metaObj.triple_type === 'engineering_ethics') {
                                label.classList.remove('bg-info');
                                label.classList.add('bg-primary', 'text-white');
                                label.setAttribute('data-source', 'engineering');
                                label.setAttribute('title', 'Engineering Ethics Ontology');
                            }
                        }
                    } catch (e) {
                        console.error('Error parsing triple metadata:', e);
                    }
                }

                // Check predicate for RDF type indicators if metadata is not available
                if (!label.hasAttribute('data-source')) {
                    const predicateText = label.textContent.trim().toLowerCase();

                    // Try to identify source by predicate naming pattern
                    if (predicateText.includes('mclaren') ||
                        predicateText.includes('instantiation') ||
                        predicateText.includes('conflict')) {
                        label.classList.remove('bg-info');
                        label.classList.add('bg-success', 'text-white');
                        label.setAttribute('data-source', 'mclaren');
                        label.setAttribute('title', 'McLaren Extensional Definition');
                    } else if (predicateText.includes('engineering') ||
                        predicateText.includes('role') ||
                        predicateText.includes('action') ||
                        predicateText.includes('dilemma')) {
                        label.classList.remove('bg-info');
                        label.classList.add('bg-primary', 'text-white');
                        label.setAttribute('data-source', 'engineering');
                        label.setAttribute('title', 'Engineering Ethics Ontology');
                    }
                }
            });
        }

        /**
         * Set up show more/less toggle for description content
         */
        /**
         * Helper function to safely add an event listener with error handling
         */
        function safeAddEventListener(element, event, handler) {
            if (element) {
                try {
                    element.addEventListener(event, handler);
                    return true;
                } catch (error) {
                    console.error(`Error adding ${event} event listener:`, error);
                    return false;
                }
            }
            return false;
        }

        /**
         * Set up show more/less toggle for description content with enhanced error handling
         */
        function setupShowMoreLessToggle() {
            // Safety check - return early if elements aren't available
            if (!descriptionContainer || !descriptionContent) {
                console.warn('setupShowMoreLessToggle: Missing container or content element');
                return;
            }

            // Skip show more/less toggle for extraction style formatted cases
            if (document.querySelector('[data-extraction-style="true"]')) {
                return;
            }

            try {
                // Need to make sure the element has been rendered to get accurate height
                // Use setTimeout with a longer delay to ensure proper rendering
                setTimeout(() => {
                    try {
                        const contentHeight = descriptionContent.scrollHeight;
                        const maxHeight = 300; // Default max height

                        // Only add show more/less toggle if the content is tall enough
                        if (contentHeight > maxHeight) {

                            // Set initial height to full height (expanded by default)
                            descriptionContent.style.maxHeight = contentHeight + 'px';
                            descriptionContent.style.overflow = 'hidden';
                            descriptionContent.style.transition = 'max-height 0.3s ease-out';

                            // Create the toggle button (initially "Show Less")
                            const toggleBtn = document.createElement('button');
                            if (!toggleBtn) {
                                console.warn('Failed to create toggle button');
                                return;
                            }

                            toggleBtn.classList.add('btn', 'btn-link', 'mt-2', 'p-0');
                            toggleBtn.textContent = 'Show Less';

                            // Append button only if container exists and isn't null
                            if (descriptionContainer) {
                                descriptionContainer.appendChild(toggleBtn);

                                // Add click event listener to button with null check
                                safeAddEventListener(toggleBtn, 'click', function () {
                                    if (descriptionContent.style.maxHeight === maxHeight + 'px') {
                                        descriptionContent.style.maxHeight = contentHeight + 'px';
                                        this.textContent = 'Show Less';
                                    } else {
                                        descriptionContent.style.maxHeight = maxHeight + 'px';
                                        this.textContent = 'Show More';
                                    }
                                });
                            } else {
                                console.warn('Cannot append Show More button: container is null');
                            }
                        }
                    } catch (innerError) {
                        console.error('Error in setTimeout callback:', innerError);
                    }
                }, 50); // Longer timeout for more reliable rendering
            } catch (error) {
                console.error('Error setting up show more/less toggle:', error);
            }
        }

        /**
         * Get a unique key for a triple
         * @param {HTMLElement} label The triple label element
         * @returns {string} A JSON string representing the triple
         */
        function getTripleKey(label) {
            if (!label) return "{}";
            return JSON.stringify({
                predicate: label.getAttribute('data-predicate'),
                object: label.getAttribute('data-object'),
                is_literal: label.getAttribute('data-is-literal') === 'true'
            });
        }

        /**
         * Fetch related cases based on selected triples
         */
        function fetchRelatedCases() {
            // Return early if required elements don't exist
            if (!relatedCasesContent && !relatedCasesList) {
                return;
            }

            // Show loading state
            if (relatedCasesContent) {
                relatedCasesContent.innerHTML = '<p class="text-muted">Loading related cases...</p>';
            }
            if (relatedCasesList) {
                relatedCasesList.innerHTML = '';
            }

            // Convert selected triples to array of objects
            const triples = Array.from(selectedTriples).map(key => JSON.parse(key));

            // Make API request
            fetch('/cases/api/related-cases', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    document_id: documentId,
                    selected_triples: triples
                }),
            })
                .then(response => response.json())
                .then(data => {

                    if (data.error) {
                        if (relatedCasesContent) {
                            relatedCasesContent.innerHTML = `<p class="text-danger">Error: ${data.error}</p>`;
                        }
                        return;
                    }

                    // Update the related cases content
                    const cases = data.related_cases || [];
                    if (cases.length === 0) {
                        if (relatedCasesContent) {
                            relatedCasesContent.innerHTML = '<p class="text-muted">No related cases found for the selected triple(s).</p>';
                        }
                    } else {
                        if (relatedCasesContent) {
                            relatedCasesContent.innerHTML = `<p>Found ${cases.length} case(s) that match all selected triple labels:</p>`;
                        }

                        // Build the list of cases
                        let caseListHTML = '';
                        cases.forEach(caseData => {
                            let caseNumber = '';
                            if (caseData.case_number) {
                                caseNumber = `<span class="badge bg-primary me-2">Case #${caseData.case_number}</span>`;
                            }

                            let yearBadge = '';
                            if (caseData.year) {
                                yearBadge = `<span class="badge bg-secondary">${caseData.year}</span>`;
                            }

                            caseListHTML += `
                            <a href="/cases/${caseData.id}" class="list-group-item list-group-item-action">
                                <div class="d-flex justify-content-between align-items-center">
                                    <h6 class="mb-1">${caseData.title}</h6>
                                    <div>
                                        ${caseNumber}
                                        ${yearBadge}
                                    </div>
                                </div>
                                <p class="mb-1 small text-muted">${caseData.description || ''}</p>
                            </a>
                        `;
                        });

                        if (relatedCasesList) {
                            relatedCasesList.innerHTML = caseListHTML;
                        }
                    }
                })
                .catch(error => {
                    console.error('Error fetching related cases:', error);
                    if (relatedCasesContent) {
                        relatedCasesContent.innerHTML = `<p class="text-danger">Error: ${error.message}</p>`;
                    }
                });
        }
        // Initialize annotation highlighting functionality
        initAnnotationHighlighting();

    } catch (error) {
        console.error('Error initializing case detail page:', error);
    }

    /**
     * Initialize annotation-based highlighting and toggle functionality
     */
    function initAnnotationHighlighting() {
        const toggleCheckbox = document.getElementById('toggleAnnotationHighlighting');
        if (!toggleCheckbox) {
            return;
        }

        let annotationsData = null;
        let isHighlightingEnabled = false;

        // Add event listener to the checkbox
        toggleCheckbox.addEventListener('change', function () {
            if (this.checked && !isHighlightingEnabled) {
                // Enable highlighting - fetch annotations if we don't have them
                if (!annotationsData) {
                    fetchAnnotationsAndHighlight();
                } else {
                    applyAnnotationHighlighting(annotationsData);
                    isHighlightingEnabled = true;
                }
            } else if (!this.checked && isHighlightingEnabled) {
                // Disable highlighting
                removeAnnotationHighlighting();
                isHighlightingEnabled = false;
            }
        });

        /**
         * Fetch annotations from API and apply highlighting
         */
        function fetchAnnotationsAndHighlight() {
            // Show loading state
            toggleCheckbox.disabled = true;
            const label = document.querySelector('label[for="toggleAnnotationHighlighting"]');
            const originalText = label.innerHTML;
            label.innerHTML = '<i class="bi bi-hourglass-split"></i> Loading annotations...';

            // Get case ID
            const caseId = documentId || parseInt(document.getElementById('document-id')?.value);
            if (!caseId) {
                console.error('Could not determine case ID for annotation fetching');
                toggleCheckbox.checked = false;
                toggleCheckbox.disabled = false;
                label.innerHTML = originalText;
                return;
            }

            // Fetch annotations from API
            fetch(`/api/document-annotations/case/${caseId}/annotations`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success && data.annotations_by_ontology) {
                        // Flatten all annotations from all ontologies into a single array
                        let allAnnotations = [];
                        Object.keys(data.annotations_by_ontology).forEach(ontologyKey => {
                            allAnnotations = allAnnotations.concat(data.annotations_by_ontology[ontologyKey]);
                        });

                        annotationsData = allAnnotations;
                        applyAnnotationHighlighting(annotationsData);
                        isHighlightingEnabled = true;
                    } else {
                        console.error('Failed to fetch annotations:', data.error || 'No annotations available');
                        alert('Failed to load annotations for highlighting');
                        toggleCheckbox.checked = false;
                    }
                })
                .catch(error => {
                    console.error('Error fetching annotations:', error);
                    alert('Error loading annotations: ' + error.message);
                    toggleCheckbox.checked = false;
                })
                .finally(() => {
                    toggleCheckbox.disabled = false;
                    label.innerHTML = originalText;
                });
        }

        /**
         * Apply highlighting to annotated text segments
         */
        function applyAnnotationHighlighting(annotations) {
            // Clear any existing highlights first
            removeAnnotationHighlighting();

            // Group annotations by text segment to avoid duplicates
            const annotationsByText = new Map();
            annotations.forEach(annotation => {
                if (annotation.text_segment && annotation.text_segment.trim()) {
                    const text = annotation.text_segment.trim();
                    if (!annotationsByText.has(text)) {
                        annotationsByText.set(text, []);
                    }
                    annotationsByText.get(text).push(annotation);
                }
            });

            // Find all text-containing elements to search within
            const contentElements = findContentElements();

            let highlightCount = 0;
            annotationsByText.forEach((annotationGroup, textSegment) => {
                contentElements.forEach(element => {
                    highlightCount += highlightTextInElement(element, textSegment, annotationGroup);
                });
            });

            // Add styles if not already present
            addAnnotationHighlightingStyles();
        }

        /**
         * Remove all annotation highlighting
         */
        function removeAnnotationHighlighting() {
            const highlights = document.querySelectorAll('.annotation-highlight');
            highlights.forEach(highlight => {
                const parent = highlight.parentNode;
                parent.replaceChild(document.createTextNode(highlight.textContent), highlight);
                parent.normalize(); // Merge adjacent text nodes
            });
        }

        /**
         * Find content elements that may contain annotated text
         */
        function findContentElements() {
            const elements = [];

            // Primary content areas
            const descriptionContent = document.getElementById('description-content');
            if (descriptionContent) elements.push(descriptionContent);

            // Sections for structured cases
            const factsSectionContent = document.querySelector('#facts-section .section-content');
            if (factsSectionContent) elements.push(factsSectionContent);

            const discussionSectionContent = document.querySelector('#discussion-section .section-content');
            if (discussionSectionContent) elements.push(discussionSectionContent);

            // Other content fields - use proper DOM traversal instead of :contains()
            const headings = document.querySelectorAll('h4, h5, h6');
            headings.forEach(heading => {
                const text = heading.textContent.toLowerCase();
                if (text.includes('decision') || text.includes('outcome') || text.includes('ethical analysis')) {
                    // Get the next element after the heading
                    const nextElement = heading.nextElementSibling;
                    if (nextElement && nextElement.tagName === 'DIV') {
                        elements.push(nextElement);
                    }
                }
            });

            // Fallback to main card body if no specific elements found
            if (elements.length === 0) {
                const cardBody = document.querySelector('#case-details .card-body');
                if (cardBody) elements.push(cardBody);
            }

            return elements;
        }

        /**
         * Highlight specific text within an element
         */
        function highlightTextInElement(element, textSegment, annotations) {
            if (!element || !textSegment) return 0;

            let highlightCount = 0;

            // Create a tree walker to find text nodes
            const walker = document.createTreeWalker(
                element,
                NodeFilter.SHOW_TEXT,
                {
                    acceptNode: function (node) {
                        // Skip text nodes that are already inside highlights
                        if (node.parentNode.classList && node.parentNode.classList.contains('annotation-highlight')) {
                            return NodeFilter.FILTER_REJECT;
                        }
                        return NodeFilter.FILTER_ACCEPT;
                    }
                },
                false
            );

            const textNodes = [];
            let node;
            while (node = walker.nextNode()) {
                textNodes.push(node);
            }

            // Process each text node
            textNodes.forEach(textNode => {
                const text = textNode.textContent;

                // Create a case-insensitive regex for the text segment
                // Escape special regex characters and use word boundaries
                const escapedText = textSegment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const regex = new RegExp(`\\b${escapedText}\\b`, 'gi');

                const matches = text.match(regex);
                if (matches && matches.length > 0) {
                    // Split the text and create highlighted spans
                    const fragments = text.split(regex);
                    const docFragment = document.createDocumentFragment();

                    for (let i = 0; i < fragments.length; i++) {
                        // Add the text fragment
                        if (fragments[i]) {
                            docFragment.appendChild(document.createTextNode(fragments[i]));
                        }

                        // Add the highlighted match (if it exists)
                        if (i < matches.length) {
                            const span = document.createElement('span');
                            span.className = 'annotation-highlight';
                            span.setAttribute('data-text-segment', textSegment);
                            span.setAttribute('data-annotation-count', annotations.length.toString());

                            // Store annotation data
                            const primaryAnnotation = annotations[0];
                            if (primaryAnnotation.concept_uri) {
                                span.setAttribute('data-concept-uri', primaryAnnotation.concept_uri);
                            }
                            if (primaryAnnotation.concept_label) {
                                span.setAttribute('data-concept-label', primaryAnnotation.concept_label);
                            }

                            span.textContent = matches[i];

                            // Add hover events for tooltip
                            addAnnotationHoverEvents(span, annotations);

                            docFragment.appendChild(span);
                            highlightCount++;
                        }
                    }

                    textNode.parentNode.replaceChild(docFragment, textNode);
                }
            });

            return highlightCount;
        }

        // Add styles for annotation highlighting
        addAnnotationHighlightingStyles();
    }

    /**
     * Add hover events to a highlighted annotation
     */
    function addAnnotationHoverEvents(annotationElement, annotations) {
        let tooltip = null;

        annotationElement.addEventListener('mouseenter', function (e) {
            // Create and show tooltip
            tooltip = createAnnotationTooltip(this, annotations);
            document.body.appendChild(tooltip);
            positionTooltip(tooltip, e);
        });

        annotationElement.addEventListener('mouseleave', function () {
            // Remove tooltip
            if (tooltip && tooltip.parentNode) {
                tooltip.parentNode.removeChild(tooltip);
                tooltip = null;
            }
        });

        annotationElement.addEventListener('mousemove', function (e) {
            // Update tooltip position
            if (tooltip) {
                positionTooltip(tooltip, e);
            }
        });
    }

    /**
     * Create a floating tooltip for annotation data
     */
    function createAnnotationTooltip(annotationElement, annotations) {
        const tooltip = document.createElement('div');
        tooltip.className = 'annotation-tooltip';

        const textSegment = annotationElement.getAttribute('data-text-segment');
        const conceptUri = annotationElement.getAttribute('data-concept-uri');
        const conceptLabel = annotationElement.getAttribute('data-concept-label');
        const annotationCount = annotations.length;

        // Build tooltip content
        let tooltipContent = `
            <div class="tooltip-header">
                <strong>Annotation</strong>
            </div>
            <div class="tooltip-content">
                <div class="annotation-info">
                    <div><strong>Text:</strong> ${escapeHtml(textSegment)}</div>
        `;

        if (conceptLabel) {
            tooltipContent += `<div><strong>Concept:</strong> ${escapeHtml(conceptLabel)}</div>`;
        }

        if (conceptUri) {
            tooltipContent += `<div><strong>URI:</strong> <code>${escapeHtml(conceptUri)}</code></div>`;
        }

        if (annotationCount > 1) {
            tooltipContent += `<div><strong>Annotations:</strong> ${annotationCount} found</div>`;
        }

        // Show first few annotations details
        const primaryAnnotation = annotations[0];
        if (primaryAnnotation.confidence !== undefined) {
            tooltipContent += `<div><strong>Confidence:</strong> ${Math.round(primaryAnnotation.confidence * 100)}%</div>`;
        }

        if (primaryAnnotation.context_snippet) {
            const snippet = primaryAnnotation.context_snippet.length > 100
                ? primaryAnnotation.context_snippet.substring(0, 100) + '...'
                : primaryAnnotation.context_snippet;
            tooltipContent += `<div><strong>Context:</strong> <em>${escapeHtml(snippet)}</em></div>`;
        }

        tooltipContent += `
                </div>
            </div>
        `;

        tooltip.innerHTML = tooltipContent;
        return tooltip;
    }

    /**
     * Add CSS styles for annotation highlighting
     */
    function addAnnotationHighlightingStyles() {
        if (document.getElementById('annotation-highlighting-styles')) return;

        const style = document.createElement('style');
        style.id = 'annotation-highlighting-styles';
        style.textContent = `
            .annotation-highlight {
                background-color: rgba(255, 193, 7, 0.4);
                border-bottom: 2px dotted #0d6efd;
                cursor: help;
                transition: all 0.2s ease;
                border-radius: 3px;
                padding: 1px 3px;
                font-weight: 500;
            }
            
            .annotation-highlight:hover {
                background-color: rgba(13, 110, 253, 0.3);
                border-bottom: 2px solid #0d6efd;
                transform: translateY(-1px);
            }
            
            .annotation-tooltip {
                position: absolute;
                background: white;
                border: 1px solid #ccc;
                border-radius: 8px;
                box-shadow: 0 6px 16px rgba(0, 0, 0, 0.25);
                padding: 0;
                z-index: 10001;
                max-width: 450px;
                font-size: 0.875rem;
                line-height: 1.4;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
            }
            
            .annotation-tooltip .tooltip-header {
                background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
                color: white;
                padding: 10px 14px;
                border-radius: 8px 8px 0 0;
                font-weight: 600;
                font-size: 0.9rem;
            }
            
            .annotation-tooltip .tooltip-content {
                padding: 14px;
            }
            
            .annotation-tooltip .annotation-info > div {
                margin-bottom: 8px;
                color: #333;
            }
            
            .annotation-tooltip .annotation-info > div:last-child {
                margin-bottom: 0;
            }
            
            .annotation-tooltip .annotation-info strong {
                color: #495057;
                font-weight: 600;
            }
            
            .annotation-tooltip .annotation-info code {
                background: #f1f3f4;
                border: 1px solid #dadce0;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 0.8rem;
                color: #1a73e8;
                font-family: 'SF Mono', Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
            }
            
            .annotation-tooltip .annotation-info em {
                color: #6c757d;
                font-style: italic;
            }
        `;

        document.head.appendChild(style);
    }

    /**
     * Find the DOM element containing a specific section's content
     */
    function findSectionElement(sectionName) {
        // Try different strategies to find the section

        // Strategy 1: Look for section by ID
        let element = document.getElementById(`${sectionName}-section`);
        if (element) return element;

        // Strategy 2: Look for facts/discussion sections in structured format
        if (sectionName === 'facts') {
            element = document.querySelector('[data-section="facts"]');
            if (element) return element;

            // Fallback: Look for Facts heading and get the next element
            const factsHeadings = document.querySelectorAll('h4, h5, h6');
            for (let heading of factsHeadings) {
                if (heading.textContent.toLowerCase().includes('facts')) {
                    const nextElement = heading.nextElementSibling;
                    if (nextElement) return nextElement;
                }
            }
        }

        if (sectionName === 'discussion') {
            element = document.querySelector('[data-section="discussion"]');
            if (element) return element;

            // Fallback: Look for Discussion heading and get the next element
            const discussionHeadings = document.querySelectorAll('h4, h5, h6');
            for (let heading of discussionHeadings) {
                if (heading.textContent.toLowerCase().includes('discussion')) {
                    const nextElement = heading.nextElementSibling;
                    if (nextElement) return nextElement;
                }
            }
        }

        // Strategy 3: Look for card structure with heading text
        const cards = document.querySelectorAll('.card');
        for (let card of cards) {
            const header = card.querySelector('.card-header h5, .card-header h4, .card-header h6');
            if (header && header.textContent.toLowerCase().includes(sectionName)) {
                const cardBody = card.querySelector('.card-body');
                if (cardBody) return cardBody;
            }
        }

        // Strategy 4: Look in sections_dual metadata structure
        const factsSection = document.querySelector('#facts-section .section-content');
        const discussionSection = document.querySelector('#discussion-section .section-content');

        if (sectionName === 'facts' && factsSection) {
            return factsSection;
        }

        if (sectionName === 'discussion' && discussionSection) {
            return discussionSection;
        }

        // Strategy 4: Fall back to the main description container for any section
        return document.getElementById('description-content');
    }

    /**
     * Highlight terms in a section element
     */
    function highlightTermsInSection(sectionElement, termLinks) {
        if (!sectionElement) return;

        // Clear any existing highlights first
        const existingHighlights = sectionElement.querySelectorAll('.ontology-term-highlight');
        existingHighlights.forEach(highlight => {
            const parent = highlight.parentNode;
            parent.replaceChild(document.createTextNode(highlight.textContent), highlight);
            parent.normalize(); // Merge adjacent text nodes
        });

        // Get the clean text content
        const textContent = sectionElement.textContent;

        // Group terms by their text to avoid duplicate highlights
        const termsByText = new Map();
        termLinks.forEach(link => {
            if (!termsByText.has(link.term_text)) {
                termsByText.set(link.term_text, []);
            }
            termsByText.get(link.term_text).push(link);
        });

        // Apply highlighting for each unique term
        let highlightedCount = 0;
        termsByText.forEach((links, termText) => {
            // Use the first link's data for the highlight (they should be similar)
            const link = links[0];

            // Find all text nodes and highlight the term
            const walker = document.createTreeWalker(
                sectionElement,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );

            const textNodes = [];
            let node;
            while (node = walker.nextNode()) {
                textNodes.push(node);
            }

            // Process text nodes for this term
            textNodes.forEach(textNode => {
                const text = textNode.textContent;
                const regex = new RegExp(`\\b${escapeRegex(termText)}\\b`, 'gi');

                if (regex.test(text)) {
                    // Split the text and create highlighted spans
                    const fragments = text.split(regex);
                    const matches = text.match(regex) || [];

                    if (matches.length > 0) {
                        const parent = textNode.parentNode;
                        const docFragment = document.createDocumentFragment();

                        for (let i = 0; i < fragments.length; i++) {
                            // Add the text fragment
                            if (fragments[i]) {
                                docFragment.appendChild(document.createTextNode(fragments[i]));
                            }

                            // Add the highlighted match (if it exists)
                            if (i < matches.length) {
                                const span = document.createElement('span');
                                span.className = 'ontology-term-highlight';
                                span.setAttribute('data-term', termText);
                                span.setAttribute('data-uri', link.ontology_uri);
                                span.setAttribute('data-label', link.ontology_label);
                                span.setAttribute('data-definition', link.definition || '');
                                // Remove conflicting title attribute - use modal instead
                                span.textContent = matches[i];

                                // Add hover events for floating modal
                                addTermHoverEvents(span);

                                docFragment.appendChild(span);
                                highlightedCount++;
                            }
                        }

                        parent.replaceChild(docFragment, textNode);
                    }
                }
            });
        });
    }


    /**
     * Add hover events to a highlighted term
     */
    function addTermHoverEvents(termElement) {
        let tooltip = null;

        termElement.addEventListener('mouseenter', function (e) {
            // Create and show tooltip
            tooltip = createFloatingTooltip(this);
            document.body.appendChild(tooltip);
            positionTooltip(tooltip, e);
        });

        termElement.addEventListener('mouseleave', function () {
            // Remove tooltip
            if (tooltip && tooltip.parentNode) {
                tooltip.parentNode.removeChild(tooltip);
                tooltip = null;
            }
        });

        termElement.addEventListener('mousemove', function (e) {
            // Update tooltip position
            if (tooltip) {
                positionTooltip(tooltip, e);
            }
        });
    }

    /**
     * Create a floating tooltip with Term, Label, URI, definition format
     */
    function createFloatingTooltip(termElement) {
        const tooltip = document.createElement('div');
        tooltip.className = 'ontology-term-tooltip';

        const termText = termElement.getAttribute('data-term');
        const uri = termElement.getAttribute('data-uri');
        const label = termElement.getAttribute('data-label');
        const definition = termElement.getAttribute('data-definition');

        tooltip.innerHTML = `
            <div class="tooltip-header">
                <strong>Ontology Term</strong>
            </div>
            <div class="tooltip-content">
                <div class="term-info">
                    <div><strong>Term:</strong> ${escapeHtml(termText)}</div>
                    <div><strong>Label:</strong> ${escapeHtml(label)}</div>
                    <div><strong>URI:</strong> <code>${escapeHtml(uri)}</code></div>
                    ${definition ? `<div><strong>Definition:</strong> ${escapeHtml(definition)}</div>` : ''}
                </div>
            </div>
        `;

        return tooltip;
    }

    /**
     * Position tooltip near the mouse cursor
     */
    function positionTooltip(tooltip, event) {
        const mouseX = event.clientX;
        const mouseY = event.clientY;
        const offset = 10;

        // Position tooltip to the right and below the cursor
        let left = mouseX + offset;
        let top = mouseY + offset;

        // Adjust if tooltip would go off-screen
        const tooltipRect = tooltip.getBoundingClientRect();
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;

        if (left + tooltipRect.width > windowWidth) {
            left = mouseX - tooltipRect.width - offset;
        }

        if (top + tooltipRect.height > windowHeight) {
            top = mouseY - tooltipRect.height - offset;
        }

        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
    }

    /**
     * Add CSS styles for term highlighting
     */
    function addTermHighlightingStyles() {
        if (document.getElementById('term-highlighting-styles')) return;

        const style = document.createElement('style');
        style.id = 'term-highlighting-styles';
        style.textContent = `
            .ontology-term-highlight {
                background-color: rgba(255, 193, 7, 0.3);
                border-bottom: 1px dotted #0d6efd;
                cursor: help;
                transition: all 0.2s ease;
                border-radius: 2px;
                padding: 1px 2px;
            }
            
            .ontology-term-highlight:hover {
                background-color: rgba(13, 110, 253, 0.2);
                border-bottom: 1px solid #0d6efd;
            }
            
            .ontology-term-tooltip {
                position: absolute;
                background: white;
                border: 1px solid #ccc;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
                padding: 0;
                z-index: 10000;
                max-width: 400px;
                font-size: 0.875rem;
                line-height: 1.4;
            }
            
            .ontology-term-tooltip .tooltip-header {
                background: #f8f9fa;
                padding: 8px 12px;
                border-bottom: 1px solid #dee2e6;
                border-radius: 8px 8px 0 0;
                color: #495057;
                font-weight: 600;
            }
            
            .ontology-term-tooltip .tooltip-content {
                padding: 12px;
            }
            
            .ontology-term-tooltip .term-info {
                margin-bottom: 12px;
            }
            
            .ontology-term-tooltip .term-info > div {
                margin-bottom: 6px;
            }
            
            .ontology-term-tooltip .term-info code {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 0.8rem;
                color: #0d6efd;
            }
        `;

        document.head.appendChild(style);
    }

    /**
     * Escape HTML special characters
     */
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Escape regex special characters
     */
    function escapeRegex(text) {
        return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
});
