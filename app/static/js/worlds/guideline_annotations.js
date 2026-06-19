  // Global variables for the page
  const guidelineId = (window.GUIDELINE_ANNOTATIONS || {}).guidelineId;
  const worldId = (window.GUIDELINE_ANNOTATIONS || {}).worldId;
  const csrfToken = (window.GUIDELINE_ANNOTATIONS || {}).csrfToken;

  // Initialize the approval modal when the page loads
  document.addEventListener('DOMContentLoaded', function () {
    // The global modal instance is already created, just ensure it has the CSRF token
    if (window.annotationApprovalModal) {
      window.annotationApprovalModal.csrfToken = csrfToken;
    } else {
      window.annotationApprovalModal = new AnnotationApprovalModal('#annotationApprovalModal', csrfToken);
    }
  });

  // Batch LLM approval function
  async function batchLLMApproval() {
    const button = event.target;
    const originalText = button.innerHTML;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    button.disabled = true;

    try {
      const response = await fetch('/api/annotation_versions/batch/llm-approve', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          guideline_id: guidelineId
        })
      });

      const result = await response.json();
      if (response.ok) {
        alert(`Successfully processed ${result.approved_count} annotations via LLM approval.`);
        location.reload(); // Refresh the page to show updated statuses
      } else {
        alert('Error during batch LLM approval: ' + (result.error || 'Unknown error'));
      }
    } catch (error) {
      alert('Error during batch LLM approval: ' + error.message);
    } finally {
      button.innerHTML = originalText;
      button.disabled = false;
    }
  }

  // Save annotations as version function
  async function saveAnnotationsAsVersion() {
    const button = event.target;
    const originalText = button.innerHTML;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    button.disabled = true;

    try {
      const response = await fetch('/api/annotation_versions/batch/save-version', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          guideline_id: guidelineId,
          version_name: `Version ${new Date().toISOString().slice(0, 16).replace('T', ' ')}`
        })
      });

      const result = await response.json();
      if (response.ok) {
        alert(`Successfully saved ${result.saved_count} approved annotations as a new version.`);
        location.reload(); // Refresh the page to show updated statuses
      } else {
        alert('Error saving annotations as version: ' + (result.error || 'Unknown error'));
      }
    } catch (error) {
      alert('Error saving annotations as version: ' + error.message);
    } finally {
      button.innerHTML = originalText;
      button.disabled = false;
    }
  }

  // Reject annotation function
  async function rejectAnnotation(annotationId) {
    if (!confirm('Are you sure you want to reject this annotation?')) {
      return;
    }

    try {
      const response = await fetch(`/api/annotation_versions/${annotationId}/reject`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        }
      });

      const result = await response.json();
      if (response.ok) {
        alert('Annotation rejected successfully.');
        location.reload(); // Refresh the page to show updated status
      } else {
        alert('Error rejecting annotation: ' + (result.error || 'Unknown error'));
      }
    } catch (error) {
      alert('Error rejecting annotation: ' + error.message);
    }
  }

  // View version history function
  async function viewVersionHistory(annotationId) {
    try {
      const response = await fetch(`/api/annotation_versions/${annotationId}/versions`);
      const result = await response.json();

      if (response.ok) {
        let historyHtml = '<h6>Version History</h6><ul>';
        result.versions.forEach(version => {
          historyHtml += `<li>Version ${version.version_number} - ${version.approval_stage} (${version.created_at})</li>`;
        });
        historyHtml += '</ul>';

        // Show in a simple alert for now - could be enhanced with a modal
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = historyHtml;
        alert('Version History:\n' + tempDiv.textContent);
      } else {
        alert('Error loading version history: ' + (result.error || 'Unknown error'));
      }
    } catch (error) {
      alert('Error loading version history: ' + error.message);
    }
  }
