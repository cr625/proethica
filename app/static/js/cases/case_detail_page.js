    document.addEventListener('DOMContentLoaded', function () {
        // Add document ID to page for JS to use
        const docIdEl = document.createElement('input');
        docIdEl.type = 'hidden';
        docIdEl.id = 'document-id';
        docIdEl.value = window.CASE_DETAIL.caseId;
        document.body.appendChild(docIdEl);

        // Format dense facts paragraph into readable chunks with expand/collapse
        const factsCard = document.querySelector('[data-extraction-style="true"] .card-body > p.mb-0');
        if (factsCard && factsCard.textContent.length > 500) {
            const text = factsCard.innerHTML;
            // Split on sentence boundaries (period followed by capital letter)
            const sentences = text.split(/\.(?=\s*[A-Z])/);
            if (sentences.length > 5) {
                // Create preview (first 4 sentences) and remaining content
                const previewSentences = sentences.slice(0, 4).join('. ') + '.';
                const remainingSentences = sentences.slice(4);

                // Group remaining sentences into paragraphs (3 sentences each)
                const remainingParagraphs = [];
                for (let i = 0; i < remainingSentences.length; i += 3) {
                    const chunk = remainingSentences.slice(i, i + 3).join('. ');
                    remainingParagraphs.push(chunk + (chunk.endsWith('.') ? '' : '.'));
                }

                // Build expandable structure
                const expandId = 'factsExpand';
                factsCard.innerHTML = `
                    <span class="d-block mb-2">${previewSentences.trim()}</span>
                    <div class="collapse" id="${expandId}">
                        ${remainingParagraphs.map(p => '<span class="d-block mb-3">' + p.trim() + '</span>').join('')}
                    </div>
                    <button class="btn btn-sm btn-link text-muted p-0" type="button"
                            data-bs-toggle="collapse" data-bs-target="#${expandId}"
                            aria-expanded="false" aria-controls="${expandId}">
                        <span class="expand-text"><i class="bi bi-chevron-down"></i> Show more (${remainingSentences.length} more sentences)</span>
                        <span class="collapse-text d-none"><i class="bi bi-chevron-up"></i> Show less</span>
                    </button>
                `;

                // Toggle button text on expand/collapse
                const collapseEl = document.getElementById(expandId);
                if (collapseEl) {
                    collapseEl.addEventListener('show.bs.collapse', function() {
                        const btn = factsCard.querySelector('button');
                        btn.querySelector('.expand-text').classList.add('d-none');
                        btn.querySelector('.collapse-text').classList.remove('d-none');
                    });
                    collapseEl.addEventListener('hide.bs.collapse', function() {
                        const btn = factsCard.querySelector('button');
                        btn.querySelector('.expand-text').classList.remove('d-none');
                        btn.querySelector('.collapse-text').classList.add('d-none');
                    });
                }
            }
        }

        // Add synthesis deep links to extraction_style card headers (only if Step 4 complete)
        if (window.CASE_DETAIL.step4Complete) {
        const extractionContainer = document.querySelector('[data-extraction-style="true"]');
        if (extractionContainer) {
            const caseId = window.CASE_DETAIL.caseId;
            const synthesisUrl = window.CASE_DETAIL.synthesisUrl;

            // Create link element helper
            function createSynthesisLink(tab, tooltip) {
                const link = document.createElement('a');
                link.href = synthesisUrl + '#' + tab;
                link.className = 'synthesis-link text-primary ms-2';
                link.title = tooltip;
                link.style.cssText = 'text-decoration: none; font-size: 0.85em;';
                link.innerHTML = '<i class="bi bi-box-arrow-up-right"></i>';
                return link;
            }

            // Find card headers and add synthesis links
            extractionContainer.querySelectorAll('.card-header h5').forEach(function(header) {
                const text = header.textContent.trim().toLowerCase();
                if (text.includes('facts')) {
                    header.appendChild(createSynthesisLink('narrative', 'View Initial Fluents in Synthesis'));
                } else if (text.includes('question')) {
                    header.appendChild(createSynthesisLink('questions', 'View Questions & Conclusions analysis'));
                } else if (text.includes('conclusion')) {
                    header.appendChild(createSynthesisLink('questions', 'View Questions & Conclusions analysis'));
                }
            });
        }
        }

        // Collapse NSPE Code References to section numbers
        const extractionStyleContainer = document.querySelector('[data-extraction-style="true"]');
        if (extractionStyleContainer) {
            extractionStyleContainer.querySelectorAll('.card').forEach(function(card) {
                const header = card.querySelector('.card-header h5');
                if (header && header.textContent.toLowerCase().includes('nspe')) {
                    const cardBody = card.querySelector('.card-body');
                    if (cardBody) {
                        const fullText = cardBody.innerHTML;
                        // Extract section numbers in multiple formats:
                        // - "Section II.1.a" style
                        // - "I.1." bare style (from NSPE website)
                        // - "II.3.a" with letter suffixes
                        const sectionMatches = fullText.match(/(?:Section\s+)?([IVX]+\.\d+(?:\.[a-z])?\.?)/gi) || [];
                        const sectionNumbers = sectionMatches.map(m => m.replace(/Section\s+/i, '').replace(/\.$/, ''));

                        if (sectionNumbers.length > 0) {
                            const expandId = 'nspeExpand';
                            const uniqueSections = [...new Set(sectionNumbers)];
                            cardBody.innerHTML = `
                                <div class="mb-2">
                                    <strong class="text-muted">Referenced Sections:</strong>
                                    ${uniqueSections.map(s => '<span class="badge bg-secondary me-1">' + s + '</span>').join('')}
                                </div>
                                <div class="collapse" id="${expandId}">
                                    ${fullText}
                                </div>
                                <button class="btn btn-sm btn-link text-muted p-0" type="button"
                                        data-bs-toggle="collapse" data-bs-target="#${expandId}"
                                        aria-expanded="false" aria-controls="${expandId}">
                                    <span class="expand-text"><i class="bi bi-chevron-down"></i> Show full text</span>
                                    <span class="collapse-text d-none"><i class="bi bi-chevron-up"></i> Show less</span>
                                </button>
                            `;

                            // Toggle button text on expand/collapse
                            const collapseEl = document.getElementById(expandId);
                            if (collapseEl) {
                                collapseEl.addEventListener('show.bs.collapse', function() {
                                    const btn = cardBody.querySelector('button');
                                    btn.querySelector('.expand-text').classList.add('d-none');
                                    btn.querySelector('.collapse-text').classList.remove('d-none');
                                });
                                collapseEl.addEventListener('hide.bs.collapse', function() {
                                    const btn = cardBody.querySelector('button');
                                    btn.querySelector('.expand-text').classList.remove('d-none');
                                    btn.querySelector('.collapse-text').classList.add('d-none');
                                });
                            }
                        }
                    }
                }
            });
        }
    });

    // Disable old term links highlighting (will be replaced with annotation-based highlighting)
    window.termLinksData = {};

    // Entity lookup data for popovers
    if (window.CASE_DETAIL.entityLookup) {
    var ENTITY_LOOKUP_BY_LABEL = window.CASE_DETAIL.entityLookup;

    // Apply entity popovers to case text after page load
    document.addEventListener('DOMContentLoaded', function() {
        const caseDetailsCard = document.getElementById('case-details');
        if (!caseDetailsCard) return;

        const ontserveBaseUrl = window.CASE_DETAIL.ontserveWebUrl;

        // Scan text for entity labels and wrap in .onto-label spans
        scanTextForEntities(caseDetailsCard, ENTITY_LOOKUP_BY_LABEL, {
            skipSectionTest: function(cardBody) {
                var parentCard = cardBody.closest('.card');
                if (parentCard) {
                    var cardHeader = parentCard.querySelector('.card-header h5');
                    if (cardHeader && cardHeader.textContent.toLowerCase().includes('nspe')) {
                        return true;
                    }
                }
                return false;
            }
        });

        // Initialize popovers with OntServe links on the newly created spans
        initializePopovers(caseDetailsCard, ontserveBaseUrl);
    });
    }

    // Annotation generation functions
    window.generateAnnotations = function (caseId) {
        const btn = event.target;
        const originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Generating...';

        fetch(`/api/document-annotations/case/${caseId}/annotate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.CASE_DETAIL.csrfToken
            },
            body: JSON.stringify({
                ontologies: [],
                world_id: null
            })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Failed to generate annotations: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error generating annotations: ' + error.message);
            })
            .finally(() => {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            });
    };

    window.regenerateAnnotations = function (caseId) {
        if (!confirm('This will replace existing annotations. Continue?')) {
            return;
        }

        const btn = event.target;
        const originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Regenerating...';

        // First clear existing annotations, then generate new ones
        fetch(`/api/document-annotations/case/${caseId}/annotations/clear`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': window.CASE_DETAIL.csrfToken
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Now generate new annotations
                    return fetch(`/api/document-annotations/case/${caseId}/annotate`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': window.CASE_DETAIL.csrfToken
                        },
                        body: JSON.stringify({
                            ontologies: [],
                            world_id: null
                        })
                    });
                } else {
                    throw new Error('Failed to clear existing annotations');
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Failed to regenerate annotations: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error regenerating annotations: ' + error.message);
            })
            .finally(() => {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            });
    };
