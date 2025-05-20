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
    } catch (error) {
        console.error('Error initializing case detail page:', error);
    }
});
