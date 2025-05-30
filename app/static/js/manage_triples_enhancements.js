/**
 * Enhancements for the Manage Triples UI
 * Adds visual indicators for triple origin and duplicate status
 */

document.addEventListener('DOMContentLoaded', function() {
    
    /**
     * Add origin indicators to triples based on their metadata
     */
    function addOriginIndicators() {
        const tripleRows = document.querySelectorAll('.triple-row');
        
        tripleRows.forEach(row => {
            const tripleId = row.dataset.tripleId;
            const subjectCell = row.querySelector('td:nth-child(2)');
            
            // Check if we have metadata about this triple
            const metadata = row.dataset.metadata;
            if (metadata) {
                const meta = JSON.parse(metadata);
                
                // Add origin badge
                if (meta.in_ontology) {
                    const badge = createBadge('In Ontology', 'primary', 'book');
                    subjectCell.appendChild(badge);
                } else if (meta.from_guideline) {
                    const badge = createBadge('From Guideline', 'info', 'file-alt');
                    subjectCell.appendChild(badge);
                }
                
                // Add duplicate indicator
                if (meta.has_duplicates) {
                    const dupBadge = createBadge('Has Duplicates', 'warning', 'copy');
                    dupBadge.setAttribute('title', `${meta.duplicate_count} similar triples found`);
                    subjectCell.appendChild(dupBadge);
                }
            }
        });
    }
    
    /**
     * Create a Bootstrap badge with icon
     */
    function createBadge(text, type, icon) {
        const badge = document.createElement('span');
        badge.className = `badge bg-${type} ms-2`;
        badge.innerHTML = `<i class="fas fa-${icon}"></i> ${text}`;
        return badge;
    }
    
    /**
     * Add tooltips to show triple details
     */
    function addTripleTooltips() {
        const predicateCells = document.querySelectorAll('.triple-row td:nth-child(3)');
        
        predicateCells.forEach(cell => {
            const predicateUri = cell.dataset.uri;
            if (predicateUri) {
                cell.setAttribute('title', predicateUri);
                cell.style.cursor = 'help';
            }
        });
    }
    
    /**
     * Enhance the value classification display
     */
    function enhanceValueClassification() {
        const qualityAlerts = document.querySelectorAll('.alert-info');
        
        qualityAlerts.forEach(alert => {
            const badges = alert.querySelectorAll('.badge');
            badges.forEach(badge => {
                if (badge.classList.contains('bg-success')) {
                    badge.innerHTML = '<i class="fas fa-star"></i> ' + badge.innerHTML;
                } else if (badge.classList.contains('bg-warning')) {
                    badge.innerHTML = '<i class="fas fa-exclamation-triangle"></i> ' + badge.innerHTML;
                } else if (badge.classList.contains('bg-primary')) {
                    badge.innerHTML = '<i class="fas fa-info-circle"></i> ' + badge.innerHTML;
                }
            });
        });
    }
    
    /**
     * Add bulk actions for value-based filtering
     */
    function addValueFilterButtons() {
        const filterSection = document.querySelector('.card-body');
        if (filterSection) {
            const valueFilterDiv = document.createElement('div');
            valueFilterDiv.className = 'col-md-4 mt-3';
            valueFilterDiv.innerHTML = `
                <label>Filter by Value</label>
                <div class="btn-group" role="group">
                    <button type="button" class="btn btn-sm btn-outline-success" data-filter="high">
                        <i class="fas fa-star"></i> High
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-primary" data-filter="medium">
                        <i class="fas fa-info-circle"></i> Medium
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-warning" data-filter="low">
                        <i class="fas fa-exclamation-triangle"></i> Low
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" data-filter="all">
                        All
                    </button>
                </div>
            `;
            
            filterSection.querySelector('.row').appendChild(valueFilterDiv);
            
            // Add click handlers
            valueFilterDiv.querySelectorAll('button').forEach(btn => {
                btn.addEventListener('click', function() {
                    filterByValue(this.dataset.filter);
                });
            });
        }
    }
    
    /**
     * Filter triple groups by value classification
     */
    function filterByValue(value) {
        const groups = document.querySelectorAll('.triple-group');
        
        groups.forEach(group => {
            const qualityBadge = group.querySelector('.badge');
            const shouldShow = value === 'all' || 
                (value === 'high' && qualityBadge.classList.contains('bg-success')) ||
                (value === 'medium' && qualityBadge.classList.contains('bg-primary')) ||
                (value === 'low' && qualityBadge.classList.contains('bg-warning'));
            
            group.style.display = shouldShow ? 'block' : 'none';
        });
    }
    
    /**
     * Add export functionality for high-value triples
     */
    function addExportButton() {
        const actionsCard = document.querySelector('.card-body:has(#delete-selected)');
        if (actionsCard) {
            const exportBtn = document.createElement('button');
            exportBtn.className = 'btn btn-success btn-sm ms-2';
            exportBtn.innerHTML = '<i class="fas fa-download"></i> Export High Value';
            exportBtn.addEventListener('click', exportHighValueTriples);
            
            actionsCard.appendChild(exportBtn);
        }
    }
    
    /**
     * Export high-value triples to TTL format
     */
    function exportHighValueTriples() {
        const highValueGroups = document.querySelectorAll('.triple-group:has(.bg-success)');
        let ttlContent = '@prefix proethica: <http://proethica.org/ontology/> .\n';
        ttlContent += '@prefix eng-ethics: <http://proethica.org/ontology/engineering-ethics#> .\n\n';
        
        highValueGroups.forEach(group => {
            const triples = group.querySelectorAll('.triple-row');
            triples.forEach(row => {
                const subject = row.querySelector('td:nth-child(2)').textContent.trim();
                const predicate = group.querySelector('h5').textContent.split(' ')[1];
                const object = row.querySelector('td:nth-child(3)').textContent.trim();
                
                ttlContent += `${subject} ${predicate} ${object} .\n`;
            });
        });
        
        // Download file
        const blob = new Blob([ttlContent], { type: 'text/turtle' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'high_value_triples.ttl';
        a.click();
    }
    
    // Initialize all enhancements
    addOriginIndicators();
    addTripleTooltips();
    enhanceValueClassification();
    addValueFilterButtons();
    addExportButton();
});