/**
 * Case Detail Page Interactions
 * -----------------------------
 * Handle interactive elements on the case detail page:
 * 1. Triple label selection for finding related cases
 * 2. Show more/less toggle for case description
 * 3. Clear selection button for triple labels
 * 4. Color coding for different triple sources (McLaren vs. Engineering Ethics)
 */

document.addEventListener('DOMContentLoaded', function() {
    try {
        console.log('Initializing case detail page interactions...');
        
        // Store the selected triples
        const selectedTriples = new Set();
        let documentId = null;
        
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
        
        console.log('Document ID:', documentId);
        
        // Get DOM elements - with null checks and fallbacks
        const tripleLabels = document.querySelectorAll('.triple-label') || [];
        const relatedCasesContainer = document.getElementById('relatedCasesContainer');
        const relatedCasesContent = document.getElementById('relatedCasesContent');
        const relatedCasesList = document.getElementById('relatedCasesList');
        const clearSelectionBtn = document.getElementById('clearSelection');
        
        // Description container elements
        const descriptionContainer = document.getElementById('description-container');
        const descriptionContent = document.getElementById('description-content');
        
        console.log('Initializing triple labels interaction...');
        console.log('Found ' + tripleLabels.length + ' triple labels');
    
        // Add click event to all triple labels
        if (tripleLabels.length > 0) {
            tripleLabels.forEach(label => {
                label.addEventListener('click', function() {
                    console.log('Triple label clicked:', this.textContent.trim());
            
                    // Toggle selection
                    const selected = this.classList.toggle('selected');
                    const tripleKey = getTripleKey(this);
                    
                    if (selected) {
                        selectedTriples.add(tripleKey);
                        this.classList.replace('bg-info', 'bg-primary');
                        this.classList.replace('text-dark', 'text-white');
                        console.log('Label selected, total selected:', selectedTriples.size);
                    } else {
                        selectedTriples.delete(tripleKey);
                        this.classList.replace('bg-primary', 'bg-info');
                        this.classList.replace('text-white', 'text-dark');
                        console.log('Label deselected, total selected:', selectedTriples.size);
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
            console.log('Setting up show more/less toggle for description');
            setupShowMoreLessToggle();
        } else {
            console.log('Description container or content element not found');
        }
        
        // Clear selection button
        if (clearSelectionBtn) {
            clearSelectionBtn.addEventListener('click', function() {
                console.log('Clearing all selections');
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
            console.log('Initializing triple color coding...');
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
            
            console.log('Triple color coding initialized');
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
                console.log('Skipping show more/less toggle for extraction style case');
                return;
            }
            
            try {
                // Need to make sure the element has been rendered to get accurate height
                // Use setTimeout with a longer delay to ensure proper rendering
                setTimeout(() => {
                    try {
                        const contentHeight = descriptionContent.scrollHeight;
                        const maxHeight = 300; // Default max height
                        
                        console.log('Content height:', contentHeight, 'Max height:', maxHeight);
                        
                        // Only add show more/less toggle if the content is tall enough
                        if (contentHeight > maxHeight) {
                            console.log('Adding show more/less toggle for description');
                            
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
                                safeAddEventListener(toggleBtn, 'click', function() {
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
                        } else {
                            console.log('Content height is not tall enough for show more/less toggle');
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
                console.log('Cannot fetch related cases: required DOM elements missing');
                return;
            }
            
            console.log('Fetching related cases for selected triples...');
            
            // Show loading state
            if (relatedCasesContent) {
                relatedCasesContent.innerHTML = '<p class="text-muted">Loading related cases...</p>';
            }
            if (relatedCasesList) {
                relatedCasesList.innerHTML = '';
            }
            
            // Convert selected triples to array of objects
            const triples = Array.from(selectedTriples).map(key => JSON.parse(key));
            console.log('Selected triples for API request:', triples);
            
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
            .then(response => {
                console.log('API response status:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('API response data:', data);
                
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
                        console.log('Updated related cases list with ' + cases.length + ' cases');
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
        // Initialize term highlighting functionality
        initTermHighlighting();
        
    } catch (error) {
        console.error('Error initializing case detail page:', error);
    }
    
    /**
     * Initialize term highlighting and hover functionality for ontology terms
     */
    function initTermHighlighting() {
        console.log('Initializing term highlighting...');
        
        // Get term links data from the page (passed from Flask)
        const termLinksData = window.termLinksData || {};
        
        if (Object.keys(termLinksData).length === 0) {
            console.log('No term links data available for this case');
            return;
        }
        
        console.log('Found term links for sections:', Object.keys(termLinksData));
        console.log('Total term links:', Object.values(termLinksData).reduce((sum, links) => sum + links.length, 0));
        
        // Process each section that has term links
        Object.keys(termLinksData).forEach(sectionName => {
            const sectionLinks = termLinksData[sectionName];
            if (!sectionLinks || sectionLinks.length === 0) return;
            
            console.log(`Processing ${sectionLinks.length} term links for section: ${sectionName}`);
            
            // Find the section content in the DOM
            const sectionElement = findSectionElement(sectionName);
            if (!sectionElement) {
                console.log(`Could not find DOM element for section: ${sectionName}`);
                return;
            }
            
            // Apply term highlighting to this section
            highlightTermsInSection(sectionElement, sectionLinks);
        });
        
        // Add global styles for term highlighting
        addTermHighlightingStyles();
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
            element = document.querySelector('[data-section="facts"], .card:has(h4:contains("Facts")), h4:contains("Facts") + div');
            if (element) return element;
        }
        
        if (sectionName === 'discussion') {
            element = document.querySelector('[data-section="discussion"], .card:has(h4:contains("Discussion")), h4:contains("Discussion") + div');
            if (element) return element;
        }
        
        // Strategy 3: Look in sections_dual metadata structure
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
        
        // Get the text content of the section
        const originalHTML = sectionElement.innerHTML;
        
        // Sort term links by start position (descending) to avoid position shifting
        const sortedLinks = [...termLinks].sort((a, b) => b.term_start - a.term_start);
        
        // Track the current HTML content as we modify it
        let currentHTML = originalHTML;
        
        // Apply highlighting for each term (in reverse order)
        sortedLinks.forEach(link => {
            const termText = link.term_text;
            const startPos = link.term_start;
            const endPos = link.term_end;
            
            // Create the tooltip content with RDF triple information
            const tooltipContent = createTooltipContent(link);
            
            // Create the highlighted span
            const highlightedSpan = `<span class="ontology-term-highlight" 
                data-term="${escapeHtml(termText)}"
                data-uri="${escapeHtml(link.ontology_uri)}"
                data-label="${escapeHtml(link.ontology_label)}"
                data-definition="${escapeHtml(link.definition)}"
                title="${escapeHtml(tooltipContent)}">${termText}</span>`;
            
            // Try to find and replace the term in the HTML
            // We'll use a simple approach first - look for the exact text
            const regex = new RegExp(`\\b${escapeRegex(termText)}\\b`, 'gi');
            
            // Count existing highlights to avoid re-highlighting
            const existingHighlights = (currentHTML.match(/ontology-term-highlight/g) || []).length;
            let replacementCount = 0;
            
            currentHTML = currentHTML.replace(regex, (match) => {
                replacementCount++;
                // Only highlight the first few instances to avoid over-highlighting
                if (replacementCount <= 3 && !match.includes('ontology-term-highlight')) {
                    return highlightedSpan.replace(termText, match);
                }
                return match;
            });
        });
        
        // Update the section with highlighted terms
        if (currentHTML !== originalHTML) {
            sectionElement.innerHTML = currentHTML;
            
            // Add event listeners to the highlighted terms
            const highlightedTerms = sectionElement.querySelectorAll('.ontology-term-highlight');
            highlightedTerms.forEach(term => {
                addTermHoverEvents(term);
            });
            
            console.log(`Applied highlighting to ${highlightedTerms.length} terms in section`);
        }
    }
    
    /**
     * Create tooltip content with RDF triple information
     */
    function createTooltipContent(link) {
        let content = `Term: ${link.term_text}\n`;
        content += `Label: ${link.ontology_label}\n`;
        content += `URI: ${link.ontology_uri}\n`;
        if (link.definition) {
            content += `Definition: ${link.definition}`;
        }
        return content;
    }
    
    /**
     * Add hover events to a highlighted term
     */
    function addTermHoverEvents(termElement) {
        let tooltip = null;
        
        termElement.addEventListener('mouseenter', function(e) {
            // Create and show tooltip
            tooltip = createFloatingTooltip(this);
            document.body.appendChild(tooltip);
            positionTooltip(tooltip, e);
        });
        
        termElement.addEventListener('mouseleave', function() {
            // Remove tooltip
            if (tooltip && tooltip.parentNode) {
                tooltip.parentNode.removeChild(tooltip);
                tooltip = null;
            }
        });
        
        termElement.addEventListener('mousemove', function(e) {
            // Update tooltip position
            if (tooltip) {
                positionTooltip(tooltip, e);
            }
        });
    }
    
    /**
     * Create a floating tooltip with RDF triple information
     */
    function createFloatingTooltip(termElement) {
        const tooltip = document.createElement('div');
        tooltip.className = 'ontology-term-tooltip';
        
        const termText = termElement.getAttribute('data-term');
        const uri = termElement.getAttribute('data-uri');
        const label = termElement.getAttribute('data-label');
        const definition = termElement.getAttribute('data-definition');
        
        // Create RDF triple format
        const subject = `<case_${documentId || 'unknown'}>`;
        const predicate = '<http://proethica.org/ontology#hasOntologyTerm>';
        const object = `<${uri}>`;
        
        tooltip.innerHTML = `
            <div class="tooltip-header">
                <strong>Ontology Term</strong>
            </div>
            <div class="tooltip-content">
                <div class="term-info">
                    <div><strong>Term:</strong> ${escapeHtml(termText)}</div>
                    <div><strong>Label:</strong> ${escapeHtml(label)}</div>
                    ${definition ? `<div><strong>Definition:</strong> ${escapeHtml(definition)}</div>` : ''}
                </div>
                <div class="rdf-triple">
                    <div class="rdf-header"><strong>RDF Triple:</strong></div>
                    <div class="rdf-content">
                        <div class="triple-line"><span class="subject">${subject}</span></div>
                        <div class="triple-line"><span class="predicate">${predicate}</span></div>
                        <div class="triple-line"><span class="object">${object}</span> .</div>
                    </div>
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
                margin-bottom: 4px;
            }
            
            .ontology-term-tooltip .rdf-triple {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
            }
            
            .ontology-term-tooltip .rdf-header {
                margin-bottom: 8px;
                color: #495057;
            }
            
            .ontology-term-tooltip .rdf-content {
                font-family: 'Courier New', monospace;
                font-size: 0.8rem;
                line-height: 1.3;
            }
            
            .ontology-term-tooltip .triple-line {
                margin-bottom: 2px;
            }
            
            .ontology-term-tooltip .subject { color: #d63384; }
            .ontology-term-tooltip .predicate { color: #198754; }
            .ontology-term-tooltip .object { color: #0d6efd; }
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
