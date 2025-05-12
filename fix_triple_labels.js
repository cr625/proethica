/**
 * Fix Triple Labels Script
 * ------------------------
 * This script adds proper null checking and error handling to the triple labels 
 * event handlers and the "Show More" functionality in case detail pages.
 * 
 * Usage:
 * 1. Open case_detail.js
 * 2. Implement improved null checking and error handling for the event handlers
 */

// Additional event listener wrapper with null check
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

// Improved show more/less toggle setup
function enhancedShowMoreLessToggle(descriptionContainer, descriptionContent) {
    // Safety check - return early if elements aren't available
    if (!descriptionContainer || !descriptionContent) {
        console.warn('setupShowMoreLessToggle: Missing container or content element');
        return;
    }
    
    try {
        // Ensure content has been rendered with a longer timeout
        setTimeout(() => {
            try {
                const contentHeight = descriptionContent.scrollHeight;
                const maxHeight = 300; // Default max height
                
                console.log('Content height:', contentHeight, 'Max height:', maxHeight);
                
                // Only add show more/less toggle if the content is tall enough
                if (contentHeight > maxHeight) {
                    console.log('Adding show more/less toggle for description');
                    
                    // Set initial height
                    descriptionContent.style.maxHeight = maxHeight + 'px';
                    descriptionContent.style.overflow = 'hidden';
                    descriptionContent.style.transition = 'max-height 0.3s ease-out';
                    
                    // Create the show more button
                    const showMoreBtn = document.createElement('button');
                    if (showMoreBtn) {
                        showMoreBtn.classList.add('btn', 'btn-link', 'mt-2', 'p-0');
                        showMoreBtn.textContent = 'Show More';
                        
                        // Append button only if container exists
                        if (descriptionContainer) {
                            descriptionContainer.appendChild(showMoreBtn);
                            
                            // Safely add click event listener
                            safeAddEventListener(showMoreBtn, 'click', function() {
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
                        console.warn('Could not create Show More button');
                    }
                } else {
                    console.log('Content height is not tall enough for show more/less toggle');
                }
            } catch (innerError) {
                console.error('Error in setTimeout callback:', innerError);
            }
        }, 50); // Slightly longer timeout to ensure complete rendering
    } catch (error) {
        console.error('Error setting up show more/less toggle:', error);
    }
}

// Safety function for triple label click handlers
function setupTripleLabelClicks(tripleLabels, selectedTriples, relatedCasesContainer, clearSelectionBtn, fetchRelatedCasesFn) {
    if (!tripleLabels || tripleLabels.length === 0) {
        console.warn('No triple labels found to set up');
        return;
    }
    
    tripleLabels.forEach(label => {
        if (label) {
            safeAddEventListener(label, 'click', function() {
                try {
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
                        if (typeof fetchRelatedCasesFn === 'function') {
                            fetchRelatedCasesFn();
                        }
                    } else {
                        if (clearSelectionBtn) clearSelectionBtn.style.display = 'none';
                        if (relatedCasesContainer) relatedCasesContainer.style.display = 'none';
                    }
                } catch (error) {
                    console.error('Error in triple label click handler:', error);
                }
            });
        }
    });
}

// Helper function to safely get triple key
function getTripleKey(label) {
    if (!label) return "{}";
    try {
        return JSON.stringify({
            predicate: label.getAttribute('data-predicate'),
            object: label.getAttribute('data-object'),
            is_literal: label.getAttribute('data-is-literal') === 'true'
        });
    } catch (error) {
        console.error('Error getting triple key:', error);
        return "{}";
    }
}
