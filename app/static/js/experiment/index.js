function generateDetermination(caseId) {
  // Show loading modal
  const loadingModal = document.getElementById('loadingModal');
  if (loadingModal) {
    loadingModal.classList.add('show');
  }
  
  // Make AJAX request to predict conclusion
  fetch(`/experiment/quick_predict/${caseId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  })
  .then(response => response.json())
  .then(data => {
    // Hide loading modal
    if (loadingModal) {
      loadingModal.classList.remove('show');
    }
    
    if (data.success) {
      // Redirect to comparison view
      window.location.href = `/experiment/case_comparison/${caseId}`;
    } else {
      alert('Error generating determination: ' + data.error);
    }
  })
  .catch(error => {
    // Hide loading modal
    if (loadingModal) {
      loadingModal.classList.remove('show');
    }
    alert('Error generating determination: ' + error.message);
  });
}

function viewComparison(caseId) {
  window.location.href = `/experiment/case_comparison/${caseId}`;
}

// Auto-refresh page every 30 seconds if there are running experiments
if (window.EXPERIMENT_INDEX.hasRunningExperiments) {
setTimeout(function() {
  location.reload();
}, 30000);
}
