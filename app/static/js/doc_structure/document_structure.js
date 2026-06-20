            document.addEventListener('DOMContentLoaded', function() {
                // Initialize TOC navigation
                initTOCNavigation();
                
                // Initialize embedding generation handling
                const embeddingForm = document.getElementById('generate-embeddings-form');
                if (embeddingForm) {
                    embeddingForm.addEventListener('submit', function(e) {
                        e.preventDefault();
                        
                        const btn = document.getElementById('generate-embeddings-btn');
                        const errorDiv = document.getElementById('embedding-error-message');
                        
                        // Show loading state
                        btn.disabled = true;
                        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Generating embeddings...';
                        errorDiv.classList.add('d-none');
                        
                        fetch(embeddingForm.action, {
                            method: 'POST',
                            headers: {
                                'X-Requested-With': 'XMLHttpRequest'
                            },
                            body: new FormData(embeddingForm)
                        })
                        .then(response => {
                            if (!response.ok) {
                                // Try to parse error response
                                return response.text().then(text => {
                                    try {
                                        const errorData = JSON.parse(text);
                                        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
                                    } catch (e) {
                                        // If not JSON, it's probably an HTML error page
                                        throw new Error(`Server error (${response.status}). Please check server logs.`);
                                    }
                                });
                            }
                            return response.json();
                        })
                        .then(data => {
                            if (data.success) {
                                // Success - reload page to show updated status
                                window.location.reload();
                            } else {
                                // Show error message
                                errorDiv.textContent = data.message || 'An error occurred while generating embeddings.';
                                errorDiv.classList.remove('d-none');
                                
                                // Reset button
                                btn.disabled = false;
                                btn.innerHTML = '<i class="bi bi-cpu"></i> Generate Section Embeddings';
                            }
                        })
                        .catch(error => {
                            // Show error message
                            errorDiv.textContent = error.message || 'An unexpected error occurred';
                            errorDiv.classList.remove('d-none');
                            
                            // Reset button
                            btn.disabled = false;
                            btn.innerHTML = '<i class="bi bi-cpu"></i> Generate Section Embeddings';
                        });
                    });
                }
            });
            
            /**
             * Initialize Table of Contents Navigation
             */
            function initTOCNavigation() {
                const tocNav = document.getElementById('toc-nav');
                const tocToggle = document.getElementById('toc-toggle');
                const tocClose = document.getElementById('toc-close');
                const tocLinks = document.querySelectorAll('.toc-link');
                
                // Toggle TOC visibility
                function showTOC() {
                    tocNav.classList.add('visible');
                    tocToggle.classList.add('hidden');
                }
                
                function hideTOC() {
                    tocNav.classList.remove('visible');
                    tocToggle.classList.remove('hidden');
                }
                
                // Event listeners
                if (tocToggle) {
                    tocToggle.addEventListener('click', showTOC);
                }
                
                if (tocClose) {
                    tocClose.addEventListener('click', hideTOC);
                }
                
                // Click outside to close
                document.addEventListener('click', function(e) {
                    if (!tocNav.contains(e.target) && !tocToggle.contains(e.target)) {
                        hideTOC();
                    }
                });
                
                // Smooth scrolling for TOC links
                tocLinks.forEach(link => {
                    link.addEventListener('click', function(e) {
                        e.preventDefault();
                        
                        const targetId = this.getAttribute('href').substring(1);
                        const targetElement = document.getElementById(targetId);
                        
                        if (targetElement) {
                            // Smooth scroll to target with offset for fixed header
                            const offsetTop = targetElement.offsetTop - 20;
                            window.scrollTo({
                                top: offsetTop,
                                behavior: 'smooth'
                            });
                            
                            // Update active link
                            tocLinks.forEach(l => l.classList.remove('active'));
                            this.classList.add('active');
                            
                            // Hide TOC on mobile after clicking
                            if (window.innerWidth <= 768) {
                                setTimeout(hideTOC, 500);
                            }
                        }
                    });
                });
                
                // Update active section on scroll
                function updateActiveSection() {
                    const sections = ['document-info', 'section-embeddings', 'ontology-associations', 
                                    'term-links', 'structure-triples'];
                    
                    const scrollPos = window.scrollY + 100; // Offset for better UX
                    
                    let activeSection = sections[0]; // Default to first section
                    
                    sections.forEach(sectionId => {
                        const element = document.getElementById(sectionId);
                        if (element && element.offsetTop <= scrollPos) {
                            activeSection = sectionId;
                        }
                    });
                    
                    // Update active link
                    tocLinks.forEach(link => {
                        link.classList.remove('active');
                        if (link.getAttribute('href') === '#' + activeSection) {
                            link.classList.add('active');
                        }
                    });
                }
                
                // Throttled scroll listener
                let scrollTimeout;
                window.addEventListener('scroll', function() {
                    if (scrollTimeout) clearTimeout(scrollTimeout);
                    scrollTimeout = setTimeout(updateActiveSection, 100);
                });
                
                // Initialize active section
                updateActiveSection();
                
                // Auto-hide on mobile
                if (window.innerWidth <= 768) {
                    hideTOC();
                }
            }
            
            // Handle reasoning modal display
            document.addEventListener('click', function(e) {
                if (e.target.classList.contains('show-reasoning-modal') || e.target.closest('.show-reasoning-modal')) {
                    e.preventDefault();
                    const link = e.target.classList.contains('show-reasoning-modal') ? e.target : e.target.closest('.show-reasoning-modal');
                    
                    // Get data from the link
                    const conceptName = link.getAttribute('data-concept-name');
                    const combinedReasoning = link.getAttribute('data-reasoning-combined');
                    const embeddingReasoning = link.getAttribute('data-reasoning-embedding');
                    const llmReasoning = link.getAttribute('data-reasoning-llm');
                    
                    // Populate modal content
                    document.getElementById('modal-concept-name').textContent = conceptName;
                    document.getElementById('modal-reasoning-combined').textContent = combinedReasoning;
                    
                    // Show/hide embedding section
                    const embeddingSection = document.getElementById('modal-embedding-section');
                    if (embeddingReasoning && embeddingReasoning.trim()) {
                        document.getElementById('modal-reasoning-embedding').textContent = embeddingReasoning;
                        embeddingSection.style.display = 'block';
                    } else {
                        embeddingSection.style.display = 'none';
                    }
                    
                    // Show/hide LLM section
                    const llmSection = document.getElementById('modal-llm-section');
                    if (llmReasoning && llmReasoning.trim()) {
                        document.getElementById('modal-reasoning-llm').textContent = llmReasoning;
                        llmSection.style.display = 'block';
                    } else {
                        llmSection.style.display = 'none';
                    }
                    
                    // Show the modal
                    const modal = new bootstrap.Modal(document.getElementById('reasoningModal'));
                    modal.show();
                }
            });
            
            // Handle clear associations
            function clearAssociations(documentId) {
                if (confirm('Are you sure you want to clear all enhanced guideline associations? This will allow you to regenerate them.')) {
                    // Show loading state
                    const clearBtn = event.target.closest('button');
                    const originalContent = clearBtn.innerHTML;
                    clearBtn.disabled = true;
                    clearBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Clearing...';
                    
                    // Make request to clear associations
                    fetch(window.DOCUMENT_STRUCTURE.clearAssociationsUrl.replace('0', documentId), {
                        method: 'POST',
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            // Reload page to show cleared state
                            window.location.reload();
                        } else {
                            alert('Error clearing associations: ' + (data.message || 'Unknown error'));
                            // Reset button
                            clearBtn.disabled = false;
                            clearBtn.innerHTML = originalContent;
                        }
                    })
                    .catch(error => {
                        alert('Error clearing associations: ' + error.message);
                        // Reset button
                        clearBtn.disabled = false;
                        clearBtn.innerHTML = originalContent;
                    });
                }
            }
            
            // Association progress polling
            let progressPollInterval = null;
            
            function startProgressPolling(documentId) {
                console.log('DEBUG: startProgressPolling called for document:', documentId);
                console.trace('Call stack');
                
                // Show progress indicator and processing state
                document.getElementById('association-progress').style.display = 'block';
                document.getElementById('no-associations-message').style.display = 'none';
                
                // Hide form and show processing state
                const form = document.getElementById('association-form');
                const processingState = document.getElementById('processing-state');
                if (form) form.style.display = 'none';
                if (processingState) {
                    processingState.style.display = 'inline';
                    console.log('DEBUG: Processing state shown');
                }
                
                // Start polling
                progressPollInterval = setInterval(() => {
                    fetch(window.DOCUMENT_STRUCTURE.associationProgressUrl.replace('0', documentId))
                        .then(response => response.json())
                        .then(data => {
                            updateProgressDisplay(data);
                            
                            // Stop polling if completed or failed
                            if (data.status === 'completed' || data.status === 'failed') {
                                clearInterval(progressPollInterval);
                                progressPollInterval = null;
                                
                                if (data.status === 'completed') {
                                    // Reload page to show results
                                    setTimeout(() => window.location.reload(), 2000);
                                }
                            }
                        })
                        .catch(error => {
                            console.error('Error polling progress:', error);
                        });
                }, 2000); // Poll every 2 seconds
            }
            
            function updateProgressDisplay(data) {
                const progressBar = document.getElementById('progress-bar');
                const progressTitle = document.getElementById('progress-title');
                const progressPhase = document.getElementById('progress-phase');
                
                // Update progress bar
                progressBar.style.width = data.progress + '%';
                progressBar.setAttribute('aria-valuenow', data.progress);
                progressBar.textContent = data.progress + '%';
                
                // Update status text
                const phaseNames = {
                    'analyzing': 'Analyzing document structure...',
                    'llm_processing': 'Processing with LLM (this takes time)...',
                    'saving_results': 'Saving associations to database...'
                };
                
                if (data.status === 'completed') {
                    progressTitle.textContent = 'Association processing completed!';
                    progressPhase.textContent = `Generated ${data.results?.total_associations || 0} associations`;
                    progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
                    progressBar.classList.add('bg-success');
                } else if (data.status === 'failed') {
                    progressTitle.textContent = 'Association processing failed';
                    progressPhase.textContent = data.error || 'Unknown error occurred';
                    progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
                    progressBar.classList.add('bg-danger');
                } else {
                    progressTitle.textContent = 'Processing associations...';
                    progressPhase.textContent = phaseNames[data.phase] || `Phase: ${data.phase}`;
                }
            }
            
            // Handle form submission to show processing state immediately
            document.addEventListener('DOMContentLoaded', function() {
                const documentId = window.DOCUMENT_STRUCTURE.documentId;
                const form = document.getElementById('association-form');
                
                if (form) {
                    form.addEventListener('submit', function(e) {
                        // Show processing state immediately
                        const processingState = document.getElementById('processing-state');
                        if (processingState) {
                            form.style.display = 'none';
                            processingState.style.display = 'inline';
                        }
                        
                        // Start polling after a short delay to allow backend to start
                        setTimeout(() => {
                            startProgressPolling(documentId);
                        }, 1000);
                    });
                }
                
                // Check current status on page load  
                console.log('DEBUG: Checking initial status for document:', documentId);
                fetch(window.DOCUMENT_STRUCTURE.associationProgressUrl.replace('0', documentId))
                    .then(response => response.json())
                    .then(data => {
                        console.log('DEBUG: Initial status response:', data);
                        console.log('DEBUG: Status value:', data.status);
                        console.log('DEBUG: Is processing?', data.status === 'processing');
                        console.log('DEBUG: Is pending?', data.status === 'pending');
                        if (data.status === 'processing' || data.status === 'pending') {
                            console.log('DEBUG: Status is processing/pending, starting polling');
                            startProgressPolling(documentId);
                        } else {
                            console.log('DEBUG: Status is', data.status, '- not starting polling');
                        }
                    })
                    .catch(error => {
                        console.error('Error checking initial status:', error);
                    });
                
                // Also check if there's a flash message indicating processing started
                // Only check flash messages in the flash message container, not all info alerts
                const flashContainer = document.querySelector('.flash-messages, .flashes');
                console.log('DEBUG: Flash container found:', !!flashContainer);
                if (flashContainer) {
                    const flashMessages = flashContainer.querySelectorAll('.alert-info');
                    console.log('DEBUG: Flash messages found:', flashMessages.length);
                    for (let flash of flashMessages) {
                        console.log('DEBUG: Flash message text:', flash.textContent);
                        if (flash.textContent.includes('Association processing started')) {
                            console.log('DEBUG: Found processing started message, starting polling');
                            // Processing was just started, show the processing state
                            startProgressPolling(documentId);
                            break;
                        }
                    }
                }
            });
            
