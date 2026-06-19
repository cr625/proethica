function startNewSession() {
    // Show loading modal
    const loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));
    loadingModal.show();
    
    // Navigate to first step - this will create the session automatically
    setTimeout(() => {
        window.location.href = `/scenarios/${(window.WIZARD_START || {}).scenarioId}/wizard/step/1`;
    }, 1000);
}

function resumeSession(sessionId) {
    window.location.href = `/scenarios/${(window.WIZARD_START || {}).scenarioId}/wizard/step/${(window.WIZARD_START || {}).currentStep}`;
}

function viewSession(sessionId) {
    window.location.href = `/scenarios/${(window.WIZARD_START || {}).scenarioId}/wizard/summary`;
}

function deleteSession(sessionId) {
    if (confirm('Are you sure you want to delete this session? This action cannot be undone.')) {
        fetch(`/wizard/session/${sessionId}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Error deleting session: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error deleting session. Please try again.');
        });
    }
}
