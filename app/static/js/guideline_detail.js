/**
 * Guideline Detail Page Interactions
 * ----------------------------------
 * Handle interactive elements on the guideline detail page:
 * 1. Annotation-based highlighting functionality
 * 2. Document ID extraction and setup
 */

// Global variables
let documentId = null;

document.addEventListener('DOMContentLoaded', function () {
    try {
        console.log('Initializing guideline detail page interactions...');

        // Try to get the document ID from the page
        const pageRoot = document.getElementById('page-root');
        if (pageRoot && pageRoot.dataset.documentId) {
            documentId = parseInt(pageRoot.dataset.documentId);
        } else {
            // Extract from URL as fallback
            const pathParts = window.location.pathname.split('/');
            // URLs are like /worlds/1/guidelines/12
            if (pathParts.length >= 4 && pathParts[2] === 'guidelines') {
                documentId = parseInt(pathParts[3]);
            }
        }

        console.log('Document ID:', documentId);

        // Initialize annotation highlighting functionality
        initAnnotationHighlighting();

    } catch (error) {
        console.error('Error initializing guideline detail page:', error);
    }

    /**
     * Initialize annotation-based highlighting and toggle functionality
     */
    function initAnnotationHighlighting() {
        console.log('Initializing annotation highlighting...');

        const toggleCheckbox = document.getElementById('toggleAnnotationHighlighting');
        if (!toggleCheckbox) {
            console.log('No annotation highlighting toggle found for this guideline');
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
            console.log('Fetching annotations for highlighting...');

            // Show loading state
            toggleCheckbox.disabled = true;
            const label = document.querySelector('label[for="toggleAnnotationHighlighting"]');
            const originalText = label.innerHTML;
            label.innerHTML = '<i class="bi bi-hourglass-split"></i> Loading annotations...';

            // Get guideline ID
            const guidelineId = documentId;
            if (!guidelineId) {
                console.error('Could not determine guideline ID for annotation fetching');
                toggleCheckbox.checked = false;
                toggleCheckbox.disabled = false;
                label.innerHTML = originalText;
                return;
            }

            // Fetch annotations from API
            fetch(`/api/document-annotations/guideline/${guidelineId}/annotations`, {
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

                        console.log(`Fetched ${allAnnotations.length} annotations for highlighting from ${Object.keys(data.annotations_by_ontology).length} ontologies`);
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
            console.log('Applying annotation highlighting...');

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

            console.log(`Applied highlighting to ${highlightCount} text segments`);

            // Add styles if not already present
            addAnnotationHighlightingStyles();
        }

        /**
         * Remove all annotation highlighting
         */
        function removeAnnotationHighlighting() {
            console.log('Removing annotation highlighting...');

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

            // Primary guideline content area
            const guidelineContent = document.getElementById('documentContent');
            if (guidelineContent) elements.push(guidelineContent);

            // Also check for markdown content div
            const markdownContent = document.querySelector('.markdown-content');
            if (markdownContent) elements.push(markdownContent);

            // Fallback to any .guideline-content class
            const guidelineContentAlt = document.querySelector('.guideline-content');
            if (guidelineContentAlt && !elements.includes(guidelineContentAlt)) {
                elements.push(guidelineContentAlt);
            }

            // If nothing found, use the main card body
            if (elements.length === 0) {
                const cardBody = document.querySelector('.card-body');
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
     * Escape HTML special characters
     */
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
