/**
 * Triple Management JavaScript
 * Handles interactive features for filtering, selecting, and managing triples
 */

document.addEventListener('DOMContentLoaded', function() {
    // Track selected triples
    let selectedTriples = new Set();
    
    // Update selected count
    function updateSelectedCount() {
        document.getElementById('selected-count').textContent = selectedTriples.size;
        document.getElementById('delete-selected').disabled = selectedTriples.size === 0;
    }
    
    // Handle individual checkbox changes
    document.querySelectorAll('.triple-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const tripleId = this.value;
            const row = this.closest('tr');
            
            if (this.checked) {
                selectedTriples.add(tripleId);
                row.classList.add('selected');
            } else {
                selectedTriples.delete(tripleId);
                row.classList.remove('selected');
            }
            
            updateSelectedCount();
        });
    });
    
    // Handle select all in group
    document.querySelectorAll('.select-all-group').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const groupId = this.dataset.group;
            const groupElement = document.getElementById(groupId);
            const checkboxes = groupElement.querySelectorAll('.triple-checkbox');
            
            checkboxes.forEach(cb => {
                cb.checked = this.checked;
                const tripleId = cb.value;
                const row = cb.closest('tr');
                
                if (this.checked) {
                    selectedTriples.add(tripleId);
                    row.classList.add('selected');
                } else {
                    selectedTriples.delete(tripleId);
                    row.classList.remove('selected');
                }
            });
            
            updateSelectedCount();
        });
    });
    
    // Handle select all in table
    document.querySelectorAll('.select-all-in-table').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const tableId = this.dataset.table;
            const tbody = document.getElementById(tableId);
            const checkboxes = tbody.querySelectorAll('.triple-checkbox');
            
            checkboxes.forEach(cb => {
                cb.checked = this.checked;
                const tripleId = cb.value;
                const row = cb.closest('tr');
                
                if (this.checked) {
                    selectedTriples.add(tripleId);
                    row.classList.add('selected');
                } else {
                    selectedTriples.delete(tripleId);
                    row.classList.remove('selected');
                }
            });
            
            updateSelectedCount();
        });
    });
    
    // Toggle group visibility
    document.querySelectorAll('.toggle-group').forEach(button => {
        button.addEventListener('click', function() {
            const targetId = this.dataset.target;
            const targetElement = document.getElementById(targetId);
            const icon = this.querySelector('i');
            
            if (targetElement.classList.contains('show')) {
                targetElement.classList.remove('show');
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-right');
            } else {
                targetElement.classList.add('show');
                icon.classList.remove('fa-chevron-right');
                icon.classList.add('fa-chevron-down');
            }
        });
    });
    
    // Filter functionality
    document.getElementById('apply-filters').addEventListener('click', function() {
        const predicateFilter = document.getElementById('predicate-filter').value;
        const searchFilter = document.getElementById('search-filter').value.toLowerCase();
        
        document.querySelectorAll('.triple-group').forEach(group => {
            const predicate = group.dataset.predicate;
            let groupVisible = true;
            
            // Check predicate filter
            if (predicateFilter && predicate !== predicateFilter) {
                groupVisible = false;
            }
            
            // Apply visibility to group
            group.style.display = groupVisible ? 'block' : 'none';
            
            // Search within visible groups
            if (groupVisible && searchFilter) {
                const rows = group.querySelectorAll('.triple-row');
                rows.forEach(row => {
                    const text = row.textContent.toLowerCase();
                    row.style.display = text.includes(searchFilter) ? '' : 'none';
                });
            } else if (groupVisible) {
                // Show all rows if no search filter
                const rows = group.querySelectorAll('.triple-row');
                rows.forEach(row => {
                    row.style.display = '';
                });
            }
        });
    });
    
    // Clear filters
    document.getElementById('clear-filters').addEventListener('click', function() {
        document.getElementById('predicate-filter').value = '';
        document.getElementById('search-filter').value = '';
        
        // Show all groups and rows
        document.querySelectorAll('.triple-group').forEach(group => {
            group.style.display = 'block';
            group.querySelectorAll('.triple-row').forEach(row => {
                row.style.display = '';
            });
        });
    });
    
    // Delete single triple
    document.querySelectorAll('.delete-single').forEach(button => {
        button.addEventListener('click', function() {
            const tripleId = this.dataset.tripleId;
            selectedTriples.clear();
            selectedTriples.add(tripleId);
            
            document.getElementById('confirm-message').textContent = 
                'Are you sure you want to delete this triple?';
            
            const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
            modal.show();
        });
    });
    
    // Delete selected triples
    document.getElementById('delete-selected').addEventListener('click', function() {
        if (selectedTriples.size === 0) return;
        
        document.getElementById('confirm-message').textContent = 
            `Are you sure you want to delete ${selectedTriples.size} selected triple(s)?`;
        
        const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
        modal.show();
    });
    
    // Confirm deletion
    document.getElementById('confirm-delete').addEventListener('click', async function() {
        const modal = bootstrap.Modal.getInstance(document.getElementById('confirmModal'));
        modal.hide();
        
        // Get the world and guideline IDs from the URL
        const pathParts = window.location.pathname.split('/');
        const worldId = pathParts[2];
        const guidelineId = pathParts[4];
        
        try {
            const response = await fetch(`/worlds/${worldId}/guidelines/${guidelineId}/delete_triples`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    triple_ids: Array.from(selectedTriples)
                })
            });
            
            if (response.ok) {
                // Remove deleted rows from the UI
                selectedTriples.forEach(tripleId => {
                    const row = document.querySelector(`tr[data-triple-id="${tripleId}"]`);
                    if (row) {
                        row.remove();
                    }
                });
                
                // Clear selection
                selectedTriples.clear();
                updateSelectedCount();
                
                // Update group counts
                updateGroupCounts();
                
                // Show success message
                showAlert('Triples deleted successfully', 'success');
            } else {
                const error = await response.json();
                showAlert(`Error deleting triples: ${error.message || 'Unknown error'}`, 'danger');
            }
        } catch (error) {
            showAlert(`Error deleting triples: ${error.message}`, 'danger');
        }
    });
    
    // Update group counts after deletion
    function updateGroupCounts() {
        document.querySelectorAll('.triple-group').forEach(group => {
            const visibleRows = group.querySelectorAll('.triple-row:not([style*="display: none"])');
            const countBadge = group.querySelector('.badge');
            if (countBadge) {
                countBadge.textContent = `${visibleRows.length} triples`;
            }
            
            // Hide group if no triples left
            if (visibleRows.length === 0) {
                group.style.display = 'none';
            }
        });
        
        // Update total count
        const totalRows = document.querySelectorAll('.triple-row:not([style*="display: none"])').length;
        document.querySelector('.display-4').textContent = totalRows;
    }
    
    // Show alert message
    function showAlert(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
        alertDiv.style.zIndex = '9999';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }
});