var currentCaseId = (window.STEP4_ENTITIES || {}).caseId;

function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

/* ---- Review (accept/reject) ---- */
function reviewEntity(entityId, action) {
    fetch('/scenario_pipeline/case/' + currentCaseId + '/entities/' + entityId + '/review', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ action: action })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            var card = document.querySelector('[data-entity-id="' + entityId + '"]');
            var acceptBtn = card.querySelector('.btn-accept');
            var rejectBtn = card.querySelector('.btn-reject');

            if (action === 'reject') {
                card.classList.add('rejected');
                card.dataset.selected = 'false';
                if (acceptBtn) acceptBtn.classList.remove('active');
                if (rejectBtn) rejectBtn.classList.add('active');
            } else {
                card.classList.remove('rejected');
                card.dataset.selected = 'true';
                if (acceptBtn) acceptBtn.classList.add('active');
                if (rejectBtn) rejectBtn.classList.remove('active');
            }
            updateGlobalCounts();
        }
    })
    .catch(function(err) { console.error('Review failed:', err); });
}

/* ---- Inline edit ---- */
function toggleEdit(entityId) {
    var form = document.getElementById('edit-' + entityId);
    if (form) {
        form.style.display = form.style.display === 'none' ? 'block' : 'none';
    }
}

function cancelEdit(entityId) {
    var form = document.getElementById('edit-' + entityId);
    if (form) form.style.display = 'none';
}

function saveEdit(entityId) {
    var form = document.getElementById('edit-' + entityId);
    var label = form.querySelector('.edit-label').value.trim();
    var definition = form.querySelector('.edit-definition').value.trim();

    fetch('/scenario_pipeline/case/' + currentCaseId + '/entities/' + entityId + '/edit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ label: label, definition: definition })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            var card = document.querySelector('[data-entity-id="' + entityId + '"]');

            // Update label display
            var labelEl = card.querySelector('.entity-label');
            if (labelEl) labelEl.innerHTML = '<strong>' + escapeHtml(data.entity_label) + '</strong>';

            // Update definition display
            var defEl = card.querySelector('p.text-muted');
            if (defEl && data.entity_definition) {
                defEl.textContent = data.entity_definition;
            }

            // Add reviewed badge if not present
            var badgeArea = card.querySelector('.entity-label').parentElement;
            if (!badgeArea.querySelector('.badge-reviewed')) {
                var badge = document.createElement('span');
                badge.className = 'badge bg-light text-dark border ms-1 badge-reviewed';
                badge.style.fontSize = '0.65em';
                badge.textContent = 'reviewed';
                badgeArea.appendChild(badge);
            }

            form.style.display = 'none';
        } else {
            alert('Save failed: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(function(err) { alert('Error: ' + err); });
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/* ---- Count updates ---- */
function updateGlobalCounts() {
    var allCards = document.querySelectorAll('.entity-card[data-entity-id]');
    var accepted = 0, rejected = 0;
    allCards.forEach(function(card) {
        if (card.dataset.published === 'true') return;
        if (card.dataset.selected === 'false') rejected++;
        else accepted++;
    });

    // Nav badges
    var navReady = document.getElementById('nav-ready-badge');
    if (navReady) {
        navReady.innerHTML = accepted > 0
            ? '<span class="badge bg-warning text-dark">' + accepted + ' ready</span>'
            : '';
    }
    var navRej = document.getElementById('nav-rejected-badge');
    if (navRej) {
        navRej.innerHTML = rejected > 0
            ? '<span class="badge bg-light text-danger border">' + rejected + ' rejected</span>'
            : '';
    }

    // Commit section counts
    var readyCount = document.getElementById('commit-ready-count');
    if (readyCount) readyCount.textContent = accepted;
    var btnCount = document.getElementById('commit-btn-count');
    if (btnCount) btnCount.textContent = accepted;

    // Phase-level counts
    document.querySelectorAll('.phase-card').forEach(function(phaseCard) {
        var cards = phaseCard.querySelectorAll('.entity-card[data-entity-id]');
        if (cards.length === 0) return;
        var pa = 0, pr = 0;
        cards.forEach(function(c) {
            if (c.dataset.published === 'true') return;
            if (c.dataset.selected === 'false') pr++;
            else pa++;
        });
        var countBadge = phaseCard.querySelector('.phase-count');
        if (countBadge) {
            var text = pa + '';
            if (pr > 0) text += ', ' + pr + ' rejected';
            countBadge.textContent = text;
        }
    });
}

/* ---- Commit / Uncommit ---- */
function commitToOntServe() {
    var btn = document.getElementById('commitBtn');
    var resultDiv = document.getElementById('commitResult');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Committing...';

    fetch('/scenario_pipeline/case/' + currentCaseId + '/reconcile/commit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        }
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        resultDiv.style.display = 'block';
        if (data.success) {
            var r = data.result || {};
            resultDiv.innerHTML = '<div class="commit-status success">'
                + '<i class="bi bi-check-circle-fill me-2 text-success"></i>'
                + '<strong>Commit successful.</strong> '
                + 'Classes: ' + (r.classes_committed || 0) + ', '
                + 'Individuals: ' + (r.individuals_committed || 0) + ', '
                + 'OntServe synced: ' + (r.ontserve_synced ? 'Yes' : 'No')
                + '</div>';
            setTimeout(function() { location.reload(); }, 1500);
        } else {
            resultDiv.innerHTML = '<div class="commit-status error">'
                + '<i class="bi bi-x-circle-fill me-2 text-danger"></i>'
                + '<strong>Commit failed:</strong> ' + (data.error || 'Unknown error')
                + '</div>';
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-cloud-upload me-2"></i>Retry Commit';
        }
    })
    .catch(function(err) {
        resultDiv.style.display = 'block';
        resultDiv.innerHTML = '<div class="commit-status error">'
            + '<i class="bi bi-x-circle-fill me-2 text-danger"></i>'
            + '<strong>Error:</strong> ' + err
            + '</div>';
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-cloud-upload me-2"></i>Retry Commit';
    });
}

function uncommitEntities() {
    if (!confirm('This will remove all committed entities from OntServe and reset them to draft status. Proceed?')) {
        return;
    }
    var resultDiv = document.getElementById('uncommitResult');
    if (resultDiv) resultDiv.style.display = 'block';

    fetch('/scenario_pipeline/case/' + currentCaseId + '/reconcile/uncommit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        }
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            location.reload();
        } else {
            if (resultDiv) {
                resultDiv.innerHTML = '<div class="commit-status error">'
                    + '<strong>Uncommit failed:</strong> ' + (data.error || 'Unknown error')
                    + '</div>';
            } else {
                alert('Uncommit failed: ' + (data.error || 'Unknown error'));
            }
        }
    })
    .catch(function(err) {
        alert('Error: ' + err);
    });
}
