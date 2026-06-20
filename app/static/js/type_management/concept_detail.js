function cancelEdit() {
    // Reset form or navigate back
    window.location.href = (window.CONCEPT_DETAIL || {}).conceptListUrl;
}

function quickApprove() {
    if (confirm('Approve this concept with its current type mapping?')) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = (window.CONCEPT_DETAIL || {}).updateConceptTypeUrl;
        
        // Keep current type
        const typeInput = document.createElement('input');
        typeInput.type = 'hidden';
        typeInput.name = 'new_type';
        typeInput.value = (window.CONCEPT_DETAIL || {}).objectLiteral;
        form.appendChild(typeInput);
        
        // Mark as approved
        const statusInput = document.createElement('input');
        statusInput.type = 'hidden';
        statusInput.name = 'review_status';
        statusInput.value = 'approved';
        form.appendChild(statusInput);
        
        // Add quick approval note
        const notesInput = document.createElement('input');
        notesInput.type = 'hidden';
        notesInput.name = 'notes';
        notesInput.value = 'Quick approved via concept detail page';
        form.appendChild(notesInput);
        
        document.body.appendChild(form);
        form.submit();
    }
}
