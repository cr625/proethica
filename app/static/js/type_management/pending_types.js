let selectedTypes = new Set();
let currentReviewTypeId = null;

function selectAll() {
    const checkboxes = document.querySelectorAll('.type-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = true;
        selectedTypes.add(parseInt(cb.value));
    });
    updateBulkButtons();
}

function clearSelection() {
    const checkboxes = document.querySelectorAll('.type-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = false;
    });
    selectedTypes.clear();
    updateBulkButtons();
}

function updateBulkButtons() {
    const checkboxes = document.querySelectorAll('.type-checkbox:checked');
    selectedTypes = new Set(Array.from(checkboxes).map(cb => parseInt(cb.value)));
    
    const count = selectedTypes.size;
    document.getElementById('selection-count').textContent = `${count} selected`;
    
    const approveBtn = document.getElementById('bulk-approve-btn');
    const rejectBtn = document.getElementById('bulk-reject-btn');
    
    if (count > 0) {
        approveBtn.disabled = false;
        rejectBtn.disabled = false;
    } else {
        approveBtn.disabled = true;
        rejectBtn.disabled = true;
    }
}

function bulkApprove() {
    if (selectedTypes.size === 0) return;
    
    if (confirm(`Approve ${selectedTypes.size} pending types?`)) {
        // Implementation would call backend API
        alert(`Would approve types: ${Array.from(selectedTypes).join(', ')}`);
        // location.reload();
    }
}

function bulkReject() {
    if (selectedTypes.size === 0) return;
    
    if (confirm(`Reject ${selectedTypes.size} pending types?`)) {
        // Implementation would call backend API
        alert(`Would reject types: ${Array.from(selectedTypes).join(', ')}`);
        // location.reload();
    }
}

function approveSingle(typeId) {
    if (confirm('Approve this pending type?')) {
        // Implementation would call backend API
        alert(`Would approve type ID: ${typeId}`);
        // location.reload();
    }
}

function rejectSingle(typeId) {
    if (confirm('Reject this pending type?')) {
        // Implementation would call backend API
        alert(`Would reject type ID: ${typeId}`);
        // location.reload();
    }
}

function reviewSingle(typeId) {
    currentReviewTypeId = typeId;
    
    // Load type details into modal
    document.getElementById('typeReviewContent').innerHTML = `
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('typeReviewModal'));
    modal.show();
    
    // Simulate loading type details
    setTimeout(() => {
        document.getElementById('typeReviewContent').innerHTML = `
            <div class="alert alert-info">
                <h6>Type ID: ${typeId}</h6>
                <p>Detailed review interface would be loaded here with:</p>
                <ul>
                    <li>Full type description and examples</li>
                    <li>Similar existing types</li>
                    <li>Usage patterns and contexts</li>
                    <li>Suggested mappings</li>
                </ul>
            </div>
        `;
    }, 500);
}

function approveFromModal() {
    if (currentReviewTypeId) {
        approveSingle(currentReviewTypeId);
        bootstrap.Modal.getInstance(document.getElementById('typeReviewModal')).hide();
    }
}

function rejectFromModal() {
    if (currentReviewTypeId) {
        rejectSingle(currentReviewTypeId);
        bootstrap.Modal.getInstance(document.getElementById('typeReviewModal')).hide();
    }
}

// Initialize tooltips and other Bootstrap components
document.addEventListener('DOMContentLoaded', function() {
    // Auto-refresh every 60 seconds
    setTimeout(function() {
        location.reload();
    }, 60000);
});
