/**
 * Step 4 Review -- Publish All Entities to OntServe.
 *
 * Requires: window.STEP4_CASE_ID, getCsrfToken() from base.html
 */

function publishAllEntities() {
    var caseId = window.STEP4_CASE_ID;
    var btn = document.getElementById('publishAllBtn');
    var statusDiv = document.getElementById('publishStatus');

    if (!btn) return;

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Publishing...';
    if (statusDiv) statusDiv.textContent = '';

    fetch('/scenario_pipeline/case/' + caseId + '/publish_all_entities', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        }
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        btn.disabled = false;
        if (data.success) {
            btn.innerHTML = '<i class="bi bi-check-circle"></i> Published';
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-success');
            if (statusDiv) {
                statusDiv.innerHTML = '<span class="text-success"><i class="bi bi-check-circle me-1"></i>' +
                    (data.published_count || 0) + ' entities published to OntServe</span>';
            }
            // Update counts in UI
            var unpubBadge = document.getElementById('unpublished-count');
            if (unpubBadge) unpubBadge.textContent = '0';
            var pubBadge = document.getElementById('published-count');
            if (pubBadge) pubBadge.textContent = data.published_count || 0;
        } else {
            btn.innerHTML = '<i class="bi bi-cloud-upload"></i> Publish All';
            if (statusDiv) {
                statusDiv.innerHTML = '<span class="text-danger">' + (data.error || 'Publish failed') + '</span>';
            }
        }
    })
    .catch(function(err) {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-cloud-upload"></i> Publish All';
        if (statusDiv) {
            statusDiv.innerHTML = '<span class="text-danger">Error: ' + err.message + '</span>';
        }
        console.error('Publish error:', err);
    });
}
