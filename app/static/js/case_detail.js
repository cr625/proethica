/**
 * Case Detail Page Interactions
 * -----------------------------
 * Handle interactive elements on the case detail page:
 * 1. Triple label selection for finding related cases
 * 2. Show more/less toggle for case description
 * 3. Clear selection button for triple labels
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
            setupShowMoreLessToggle(descriptionContainer, descriptionContent);
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
         * Set up show more/less toggle for a content element
         * @param {HTMLElement} container The container element
         * @param {HTMLElement} content The content element to toggle
         */
        function setupShowMoreLessToggle(container, content) {
            // Safety check
            if (!container || !content) {
                console.warn('setupShowMoreLessToggle: Missing container or content element');
                return;
            }
            
            try {
                const contentHeight = content.scrollHeight;
                const maxHeight = 300; // Default max height
                
                console.log('Content height:', contentHeight, 'Max height:', maxHeight);
                
                // Only add show more/less toggle if the content is tall enough
                if (contentHeight > maxHeight) {
                    console.log('Adding show more/less toggle for description');
                    
                    // Set initial height
                    content.style.maxHeight = maxHeight + 'px';
                    content.style.overflow = 'hidden';
                    content.style.transition = 'max-height 0.3s ease-out';
                    
                    // Add show more button
                    const showMoreBtn = document.createElement('button');
                    showMoreBtn.classList.add('btn', 'btn-link', 'mt-2', 'p-0');
                    showMoreBtn.textContent = 'Show More';
                    container.appendChild(showMoreBtn);
                    
                    // Toggle content height on button click
                    showMoreBtn.addEventListener('click', function() {
                        if (content.style.maxHeight === maxHeight + 'px') {
                            content.style.maxHeight = contentHeight + 'px';
                            this.textContent = 'Show Less';
                        } else {
                            content.style.maxHeight = maxHeight + 'px';
                            this.textContent = 'Show More';
                        }
                    });
                } else {
                    console.log('Content height is not tall enough for show more/less toggle');
                }
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
