/**
 * Structure Triples Viewer
 * Provides formatted and raw views of RDF structure triples
 */

class StructureTriplesViewer {
    constructor(containerId, structuredData) {
        this.container = document.getElementById(containerId);
        this.structuredData = structuredData;
        this.currentView = 'formatted'; // 'formatted' or 'raw'
        this.init();
    }

    init() {
        if (!this.container) {
            console.error('Container not found');
            return;
        }

        // Create the viewer structure
        this.createViewerStructure();
        
        // Show initial view
        this.showFormattedView();
    }

    createViewerStructure() {
        this.container.innerHTML = `
            <div class="structure-viewer">
                <div class="viewer-controls mb-3">
                    <div class="btn-group" role="group">
                        <button type="button" class="btn btn-sm btn-primary" id="formatted-view-btn">
                            <i class="bi bi-eye"></i> Formatted View
                        </button>
                        <button type="button" class="btn btn-sm btn-outline-primary" id="raw-view-btn">
                            <i class="bi bi-code"></i> Raw Triples
                        </button>
                    </div>
                    <span class="ms-3 text-muted">
                        <i class="bi bi-info-circle"></i>
                        <span id="triple-stats"></span>
                    </span>
                </div>
                <div id="viewer-content" class="viewer-content">
                    <!-- Content will be inserted here -->
                </div>
            </div>
        `;

        // Add event listeners
        document.getElementById('formatted-view-btn').addEventListener('click', () => {
            this.showFormattedView();
        });

        document.getElementById('raw-view-btn').addEventListener('click', () => {
            this.showRawView();
        });
    }

    showFormattedView() {
        this.currentView = 'formatted';
        this.updateButtonStates();
        
        const content = document.getElementById('viewer-content');
        
        if (this.structuredData.error) {
            content.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> Error parsing structure: ${this.structuredData.error}
                </div>
            `;
            return;
        }

        let html = '<div class="formatted-structure">';

        // Document Information
        if (this.structuredData.document_info && Object.keys(this.structuredData.document_info).length > 0) {
            html += `
                <div class="document-info card mb-3">
                    <div class="card-header">
                        <i class="bi bi-file-text"></i> Document Information
                    </div>
                    <div class="card-body">
                        ${this.formatDocumentInfo(this.structuredData.document_info)}
                    </div>
                </div>
            `;
        }

        // Combined Section Metadata and Content
        if (this.structuredData.section_items && Object.keys(this.structuredData.section_items).length > 0) {
            html += `
                <div class="section-items-container">
                    <h4 class="mb-3">Document Sections and Content</h4>
                    ${this.formatSectionItems(this.structuredData.section_items)}
                </div>
            `;
        } else if (this.structuredData.sections && Object.keys(this.structuredData.sections).length > 0) {
            // Fallback to old format if section_items not available
            html += '<div class="sections-container">';
            
            for (const [sectionType, sectionData] of Object.entries(this.structuredData.sections)) {
                html += this.formatSection(sectionData);
            }
            
            html += '</div>';
        }

        html += '</div>';
        content.innerHTML = html;

        // Update statistics
        this.updateStatistics();
    }

    formatDocumentInfo(info) {
        let html = '<dl class="row mb-0">';
        
        if (info.case_number) {
            html += `
                <dt class="col-sm-3">Case Number:</dt>
                <dd class="col-sm-9">${this.escapeHtml(info.case_number)}</dd>
            `;
        }
        
        if (info.title) {
            html += `
                <dt class="col-sm-3">Title:</dt>
                <dd class="col-sm-9">${this.escapeHtml(info.title)}</dd>
            `;
        }
        
        if (info.year) {
            html += `
                <dt class="col-sm-3">Year:</dt>
                <dd class="col-sm-9">${this.escapeHtml(info.year)}</dd>
            `;
        }
        
        html += '</dl>';
        return html;
    }

    formatSection(sectionData) {
        const hasContent = sectionData.content || (sectionData.items && sectionData.items.length > 0);
        const iconClass = this.getSectionIcon(sectionData.type);
        
        let html = `
            <div class="section-card card mb-3">
                <div class="card-header">
                    <i class="bi ${iconClass}"></i> ${this.escapeHtml(sectionData.label)}
                    ${sectionData.full_content_length ? `<span class="text-muted ms-2">(${sectionData.full_content_length} characters)</span>` : ''}
                </div>
        `;
        
        if (hasContent) {
            html += '<div class="card-body">';
            
            // Section content preview
            if (sectionData.content) {
                html += `
                    <div class="section-content mb-3">
                        <small class="text-muted">Content preview:</small>
                        <p class="mb-2">${this.escapeHtml(sectionData.content)}</p>
                    </div>
                `;
            }
            
            // Section items
            if (sectionData.items && sectionData.items.length > 0) {
                html += `
                    <div class="section-items">
                        <small class="text-muted">Contains ${sectionData.items.length} item(s):</small>
                        <ul class="list-unstyled mt-2">
                `;
                
                for (const item of sectionData.items) {
                    html += `
                        <li class="mb-2">
                            <strong>${this.escapeHtml(item.type)}:</strong>
                            <span class="text-break">${this.escapeHtml(item.content || 'No content')}</span>
                        </li>
                    `;
                }
                
                html += '</ul></div>';
            }
            
            html += '</div>';
        } else {
            html += '<div class="card-body text-muted">No content available</div>';
        }
        
        html += '</div>';
        return html;
    }

    getSectionIcon(sectionType) {
        const iconMap = {
            'FactsSection': 'bi-list-ul',
            'DiscussionSection': 'bi-chat-dots',
            'QuestionsSection': 'bi-question-circle',
            'ConclusionSection': 'bi-check-circle',
            'ReferencesSection': 'bi-book'
        };
        return iconMap[sectionType] || 'bi-file-text';
    }

    formatSectionItems(items) {
        // Group items by parent section
        const groupedItems = {};
        for (const [itemId, itemData] of Object.entries(items)) {
            const section = itemData.parent_section || 'other';
            if (!groupedItems[section]) {
                groupedItems[section] = [];
            }
            groupedItems[section].push({ id: itemId, ...itemData });
        }
        
        // Sort items within each section by sequence number if available
        for (const section in groupedItems) {
            groupedItems[section].sort((a, b) => {
                if (a.sequence_number && b.sequence_number) {
                    return a.sequence_number - b.sequence_number;
                }
                return 0;
            });
        }

        // Section display order and labels
        const sectionOrder = {
            'facts': 'Facts',
            'discussion': 'Discussion',
            'questions': 'Questions',
            'conclusion': 'Conclusion',
            'references': 'References',
            'other': 'Other Items'
        };

        let html = '<div class="section-items-table">';
        
        // Create sections
        for (const [sectionKey, sectionLabel] of Object.entries(sectionOrder)) {
            if (!groupedItems[sectionKey] || groupedItems[sectionKey].length === 0) continue;
            
            html += `
                <div class="section-group mb-4">
                    <h5 class="section-group-header mb-3">
                        <i class="bi ${this.getSectionIconByKey(sectionKey)}"></i> ${sectionLabel}
                    </h5>
                    <div class="table-responsive">
                        <table class="table table-hover">
                            <tbody>
            `;
            
            // Add items for this section
            groupedItems[sectionKey].forEach(item => {
                // Add segment type badge for discussion segments
                let segmentTypeBadge = '';
                if (item.segment_type) {
                    const badgeClass = item.segment_type === 'ethical_analysis' ? 'bg-primary' : 
                                     item.segment_type === 'reasoning' ? 'bg-info' : 
                                     item.segment_type === 'code_reference' ? 'bg-warning' : 'bg-secondary';
                    segmentTypeBadge = `<span class="badge ${badgeClass} ms-2">${this.escapeHtml(item.segment_type.replace('_', ' '))}</span>`;
                }
                
                html += `
                    <tr>
                        <td class="w-100">
                            <div class="item-header">
                                <code class="item-id">${this.escapeHtml(item.id)}</code>
                                <span class="item-type badge bg-secondary ms-2">${this.escapeHtml(item.type || 'Item')}</span>
                                ${segmentTypeBadge}
                                <span class="item-uri text-muted ms-2"><small>${this.escapeHtml(item.uri)}</small></span>
                            </div>
                            <div class="item-content mt-2">
                                ${this.escapeHtml(item.content)}
                            </div>
                        </td>
                    </tr>
                `;
            });
            
            html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }
        
        html += '</div>';
        return html;
    }

    getSectionIconByKey(sectionKey) {
        const iconMap = {
            'facts': 'bi-list-ul',
            'discussion': 'bi-chat-dots',
            'questions': 'bi-question-circle',
            'conclusion': 'bi-check-circle',
            'references': 'bi-book',
            'other': 'bi-folder'
        };
        return iconMap[sectionKey] || 'bi-file-text';
    }

    showRawView() {
        this.currentView = 'raw';
        this.updateButtonStates();
        
        const content = document.getElementById('viewer-content');
        
        if (this.structuredData.raw_triples) {
            content.innerHTML = `
                <div class="raw-triples-container">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <small class="text-muted">Raw RDF Triples (Turtle format)</small>
                        <button class="btn btn-sm btn-outline-secondary" onclick="structureTriplesViewer.copyRawTriples(event)">
                            <i class="bi bi-clipboard"></i> Copy
                        </button>
                    </div>
                    <pre class="bg-light p-3 rounded"><code>${this.escapeHtml(this.structuredData.raw_triples)}</code></pre>
                </div>
            `;
        } else {
            content.innerHTML = '<div class="alert alert-warning">No raw triples available</div>';
        }

        // Update statistics
        this.updateStatistics();
    }

    updateButtonStates() {
        const formattedBtn = document.getElementById('formatted-view-btn');
        const rawBtn = document.getElementById('raw-view-btn');
        
        if (this.currentView === 'formatted') {
            formattedBtn.classList.remove('btn-outline-primary');
            formattedBtn.classList.add('btn-primary');
            rawBtn.classList.remove('btn-primary');
            rawBtn.classList.add('btn-outline-primary');
        } else {
            formattedBtn.classList.remove('btn-primary');
            formattedBtn.classList.add('btn-outline-primary');
            rawBtn.classList.remove('btn-outline-primary');
            rawBtn.classList.add('btn-primary');
        }
    }

    updateStatistics() {
        const statsEl = document.getElementById('triple-stats');
        if (this.structuredData.statistics) {
            const stats = this.structuredData.statistics;
            statsEl.textContent = `${stats.total_triples} triples, ${stats.entities} entities, ${stats.sections} sections`;
        }
    }

    copyRawTriples(event) {
        if (this.structuredData.raw_triples) {
            navigator.clipboard.writeText(this.structuredData.raw_triples).then(() => {
                // Show success feedback
                const btn = event.target.closest('button');
                const originalContent = btn.innerHTML;
                btn.innerHTML = '<i class="bi bi-check"></i> Copied!';
                btn.classList.add('btn-success');
                btn.classList.remove('btn-outline-secondary');
                
                setTimeout(() => {
                    btn.innerHTML = originalContent;
                    btn.classList.remove('btn-success');
                    btn.classList.add('btn-outline-secondary');
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy:', err);
                alert('Failed to copy to clipboard');
            });
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Make it globally accessible for the copy function
let structureTriplesViewer;