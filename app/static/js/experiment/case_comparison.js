function toggleMetadata() {
  const metadata = document.getElementById('prediction-metadata');
  const button = event.target;
  
  if (metadata.style.display === 'none') {
    metadata.style.display = 'block';
    button.textContent = 'Hide Details';
  } else {
    metadata.style.display = 'none';
    button.textContent = 'View Details';
  }
}

function toggleAnonymousMode() {
  const container = document.querySelector('.comparison-container');
  const normalLabels = document.querySelectorAll('.normal-label, .normal-tag');
  const anonymousLabels = document.querySelectorAll('.anonymous-label, .anonymous-tag');
  
  container.classList.toggle('anonymous-mode');
  
  normalLabels.forEach(label => {
    label.style.display = container.classList.contains('anonymous-mode') ? 'none' : '';
  });
  
  anonymousLabels.forEach(label => {
    label.style.display = container.classList.contains('anonymous-mode') ? '' : 'none';
  });
}

function generateAnother() {
  if (confirm('This will generate a new prediction for this case. Continue?')) {
    // Trigger new prediction generation
    fetch(`/experiment/quick_predict/${(window.CASE_COMPARISON || {}).documentId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        location.reload();
      } else {
        alert('Error generating new prediction: ' + data.error);
      }
    })
    .catch(error => {
      alert('Error generating new prediction: ' + error.message);
    });
  }
}

function exportComparison() {
  // Simple export functionality
  const content = document.querySelector('.comparison-container').innerText;
  const blob = new Blob([content], { type: 'text/plain' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `case_${document.id}_comparison.txt`;
  a.click();
  window.URL.revokeObjectURL(url);
}

function exportForPaper() {
  // Export formatted data suitable for paper documentation
  const exportData = {
    case_id: (window.CASE_COMPARISON || {}).documentId,
    case_title: (window.CASE_COMPARISON || {}).documentTitle,
    metrics: {
      ethical_principles: (window.CASE_COMPARISON || {}).ethicalPrinciples,
      precedent_alignment: (window.CASE_COMPARISON || {}).precedentAlignment,
      reasoning_coherence: (window.CASE_COMPARISON || {}).reasoningCoherence,
      ontology_coverage: (window.CASE_COMPARISON || {}).ontologyCoverage,
      combined_score: (window.CASE_COMPARISON || {}).combinedScore
    },
    firac_detection: {
      facts_confidence: (window.CASE_COMPARISON || {}).factsConfidence,
      issue_confidence: (window.CASE_COMPARISON || {}).issueConfidence,
      rule_confidence: (window.CASE_COMPARISON || {}).ruleConfidence,
      analysis_confidence: (window.CASE_COMPARISON || {}).analysisConfidence,
      conclusion_confidence: (window.CASE_COMPARISON || {}).conclusionConfidence
    },
    performance: {
      total_time: (window.CASE_COMPARISON || {}).totalTime,
      ontology_time: (window.CASE_COMPARISON || {}).ontologyTime,
      analysis_time: (window.CASE_COMPARISON || {}).analysisTime,
      generation_time: (window.CASE_COMPARISON || {}).generationTime
    },
    original_conclusion: (window.CASE_COMPARISON || {}).originalConclusion,
    predicted_conclusion: (window.CASE_COMPARISON || {}).predictedConclusion
  };
  
  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `case_${(window.CASE_COMPARISON || {}).documentId}_paper_data.json`;
  a.click();
  window.URL.revokeObjectURL(url);
}
