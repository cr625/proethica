let selectedConcepts = new Set();

function applyFilter() {
    const filter = document.getElementById('filter-select').value;
    const sort = document.getElementById('sort-select').value;
    
    const params = new URLSearchParams();
    if (filter !== 'all') params.set('filter', filter);
    if (sort !== 'recent') params.set('sort', sort);
    
    const url = ((window.CONCEPT_LIST || {}).conceptListUrl || '') + 
                (params.toString() ? '?' + params.toString() : '');
    window.location.href = url;
}

function selectAll() {
    const checkboxes = document.querySelectorAll('.batch-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = true;
        selectedConcepts.add(parseInt(cb.value));
    });
    updateBatchButtons();
}

function clearSelection() {
    const checkboxes = document.querySelectorAll('.batch-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = false;
    });
    selectedConcepts.clear();
    updateBatchButtons();
}

function updateBatchButtons() {
    const checkboxes = document.querySelectorAll('.batch-checkbox:checked');
    selectedConcepts = new Set(Array.from(checkboxes).map(cb => parseInt(cb.value)));
    
    const count = selectedConcepts.size;
    document.getElementById('selected-count').textContent = `${count} selected`;
    
    const approveBtn = document.getElementById('batch-approve-btn');
    const reviewBtn = document.getElementById('batch-review-btn');
    
    if (count > 0) {
        approveBtn.disabled = false;
        reviewBtn.disabled = false;
    } else {
        approveBtn.disabled = true;
        reviewBtn.disabled = true;
    }
}

function batchApprove() {
    if (selectedConcepts.size === 0) return;
    
    if (confirm(`Approve ${selectedConcepts.size} concepts?`)) {
        fetch((window.CONCEPT_LIST || {}).batchApproveUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                concept_ids: Array.from(selectedConcepts),
                action: 'approve'
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(error => {
            alert('Network error: ' + error);
        });
    }
}

function batchReview() {
    if (selectedConcepts.size === 0) return;
    
    if (confirm(`Mark ${selectedConcepts.size} concepts as needing review?`)) {
        fetch((window.CONCEPT_LIST || {}).batchApproveUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                concept_ids: Array.from(selectedConcepts),
                action: 'needs_review'
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(error => {
            alert('Network error: ' + error);
        });
    }
}

// Add click handler for concept cards
document.addEventListener('DOMContentLoaded', function() {
    const conceptCards = document.querySelectorAll('.concept-card');
    conceptCards.forEach(card => {
        card.addEventListener('click', function(e) {
            // Don't trigger if clicking on checkbox, badge, or button
            if (e.target.type === 'checkbox' || 
                e.target.closest('.btn') || 
                e.target.closest('.badge')) {
                return;
            }
            
            const checkbox = card.querySelector('.batch-checkbox');
            checkbox.checked = !checkbox.checked;
            updateBatchButtons();
            
            // Visual feedback
            if (checkbox.checked) {
                card.classList.add('selected');
            } else {
                card.classList.remove('selected');
            }
        });
    });
});
