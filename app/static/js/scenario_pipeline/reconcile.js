var CONCEPT_COLORS = {
    'roles': '#4e73df',
    'states': '#6f42c1',
    'resources': '#20c9a6',
    'principles': '#fd7e14',
    'obligations': '#e74a3b',
    'capabilities': '#36b9cc',
    'constraints': '#858796'
};

// State tracking
var currentRunId = null;
var candidateData = {};   // keyed by candidate index, stores full candidate for row rebuild
var mergeSnapshots = {};   // keyed by candidate index, stores merge snapshots for undo
var totalCandidates = 0;

function runReconciliation() {
    var initial = document.getElementById('reconcileInitial');
    var progress = document.getElementById('reconcileProgress');
    var results = document.getElementById('reconcileResults');

    initial.style.display = 'none';
    progress.style.display = 'block';
    results.style.display = 'none';

    fetch((window.RECONCILE || {}).reconcileRunUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        progress.style.display = 'none';
        results.style.display = 'block';

        if (!data.success) {
            results.innerHTML = '<div class="alert alert-danger"><i class="bi bi-exclamation-triangle me-1"></i> Reconciliation failed: ' + (data.error || 'Unknown error') + '</div>';
            initial.style.display = 'block';
            return;
        }

        currentRunId = data.run_id;

        // Update summary counts if merges happened
        if (data.auto_merged > 0 && data.updated_counts) {
            updateCountDisplays(data.updated_counts);
        }

        renderReconciliationResults(data.candidates, data.auto_merged, data.errors, {});
    })
    .catch(function(err) {
        progress.style.display = 'none';
        results.style.display = 'block';
        results.innerHTML = '<div class="alert alert-danger"><i class="bi bi-exclamation-triangle me-1"></i> Error: ' + err + '</div>';
        initial.style.display = 'block';
    });
}

function renderReconciliationResults(candidates, autoMerged, errors, decisions) {
    var results = document.getElementById('reconcileResults');
    results.style.display = 'block';

    var html = '';

    // Auto-merge summary
    if (autoMerged > 0) {
        html += '<div class="alert alert-info mb-3">'
            + '<i class="bi bi-info-circle me-1"></i> '
            + '<strong>' + autoMerged + '</strong> exact-duplicate entities were auto-merged (identical labels within same concept type).'
            + '</div>';
    }

    // Errors
    if (errors && errors.length > 0) {
        html += '<div class="alert alert-warning mb-3">'
            + '<i class="bi bi-exclamation-triangle me-1"></i> '
            + errors.length + ' error(s) during reconciliation:<ul class="mb-0 mt-1">';
        for (var i = 0; i < errors.length; i++) {
            html += '<li>' + escapeHtml(errors[i]) + '</li>';
        }
        html += '</ul></div>';
    }

    // Candidates -- show LLM merge/review recommendations; keep_separate hidden behind toggle
    if (candidates && candidates.length > 0) {
        // Separate candidates by LLM recommendation
        var mergeReviewCandidates = [];
        var autoKeptSeparateCandidates = [];
        for (var i = 0; i < candidates.length; i++) {
            var rec = candidates[i].recommendation || 'review';
            var key = candidates[i].entity_a_id + '_' + candidates[i].entity_b_id;
            var storedDecision = decisions[key];
            var hasExplicitDecision = storedDecision && (storedDecision.decision === 'merge' || storedDecision.decision === 'keep_separate');
            if (rec !== 'keep_separate' || hasExplicitDecision) {
                mergeReviewCandidates.push(candidates[i]);
            } else {
                autoKeptSeparateCandidates.push(candidates[i]);
            }
        }

        // Render merge/review candidates (LLM thinks these might be duplicates)
        var idx = 1;
        totalCandidates = mergeReviewCandidates.length;

        if (mergeReviewCandidates.length > 0) {
            html += '<div class="mb-2"><strong>' + mergeReviewCandidates.length + '</strong> potential duplicate' + (mergeReviewCandidates.length !== 1 ? 's' : '') + ' for review:</div>';
            for (var j = 0; j < mergeReviewCandidates.length; j++) {
                var c = mergeReviewCandidates[j];
                candidateData[idx] = c;
                html += renderCandidateWithState(c, idx, decisions);
                idx++;
            }
        } else {
            html += '<div class="text-center text-muted py-3">'
                + '<i class="bi bi-check-circle fs-3 d-block mb-2"></i>'
                + 'No merge candidates found. Ready for Step 4.'
                + '</div>';
        }

        // Auto-kept-separate toggle (full interactive rows when expanded)
        if (autoKeptSeparateCandidates.length > 0) {
            html += '<div class="alert alert-light border mb-3 mt-3">'
                + '<i class="bi bi-dash-circle me-1 text-muted"></i> '
                + '<strong>' + autoKeptSeparateCandidates.length + '</strong> pair' + (autoKeptSeparateCandidates.length !== 1 ? 's' : '')
                + ' auto-kept separate (LLM confident they are distinct entities).'
                + ' <button class="btn btn-sm btn-outline-secondary ms-2" onclick="toggleAutoKeptSeparate()" id="toggleAutoKeptBtn">'
                + '<i class="bi bi-eye me-1"></i>Show</button>'
                + '</div>';
            html += '<div id="autoKeptSeparateList" style="display: none;">';
            for (var k = 0; k < autoKeptSeparateCandidates.length; k++) {
                var c = autoKeptSeparateCandidates[k];
                candidateData[idx] = c;
                html += buildCandidateRow(c, idx);
                idx++;
            }
            html += '</div>';
        }
    } else if (autoMerged === 0) {
        html += '<div class="text-center text-muted py-3">'
            + '<i class="bi bi-check-circle fs-3 d-block mb-2"></i>'
            + 'No duplicate entities found. Ready for Step 4.'
            + '</div>';
    } else {
        html += '<div class="text-center text-muted py-3">'
            + '<i class="bi bi-check-circle fs-3 d-block mb-2"></i>'
            + 'Only exact matches found (already merged above). Ready for Step 4.'
            + '</div>';
    }

    // Re-run button
    html += '<div class="mt-3 text-end">'
        + '<button class="btn btn-sm btn-outline-primary" onclick="runReconciliation()">'
        + '<i class="bi bi-arrow-repeat me-1"></i>Re-run Reconciliation</button>'
        + '</div>';

    results.innerHTML = html;
    checkAllResolved();
}

function updateCountDisplays(uc) {
    var el;
    el = document.getElementById('totalCount'); if (el) el.textContent = uc.unpublished;
    el = document.getElementById('classCount'); if (el) el.textContent = uc.classes;
    el = document.getElementById('individualCount'); if (el) el.textContent = uc.individuals;
}

function renderCandidateWithState(c, idx, decisions) {
    var key = c.entity_a_id + '_' + c.entity_b_id;
    var storedDecision = decisions[key];

    if (storedDecision && storedDecision.decision === 'merge') {
        mergeSnapshots[idx] = storedDecision.snapshots;
        return '<div class="candidate-row resolved" id="candidate-' + idx + '">'
            + '<div class="d-flex align-items-center justify-content-center py-2 gap-3">'
            + '<span class="text-success"><i class="bi bi-check-circle me-1"></i> Merged</span>'
            + '<span class="text-muted small">' + escapeHtml(c.entity_a_label) + ' / ' + escapeHtml(c.entity_b_label) + '</span>'
            + '<button class="btn btn-sm btn-outline-warning" onclick="unmergeEntities(' + idx + ')">'
            + '<i class="bi bi-arrow-counterclockwise me-1"></i>Undo</button>'
            + '</div></div>';
    } else if (storedDecision && storedDecision.decision === 'keep_separate') {
        return '<div class="candidate-row resolved" id="candidate-' + idx + '">'
            + '<div class="d-flex align-items-center justify-content-center py-2 gap-3">'
            + '<span class="text-muted"><i class="bi bi-dash-circle me-1"></i> Kept separate</span>'
            + '<span class="text-muted small">' + escapeHtml(c.entity_a_label) + ' / ' + escapeHtml(c.entity_b_label) + '</span>'
            + '<button class="btn btn-sm btn-outline-secondary" onclick="undoKeepSeparate(' + c.entity_a_id + ', ' + c.entity_b_id + ', ' + idx + ')">'
            + '<i class="bi bi-arrow-counterclockwise me-1"></i>Undo</button>'
            + '</div></div>';
    } else {
        return buildCandidateRow(c, idx);
    }
}

function buildCandidateRow(c, index) {
    var colorA = CONCEPT_COLORS[(c.entity_a_context || {}).extraction_type] || '#858796';
    var colorB = CONCEPT_COLORS[(c.entity_b_context || {}).extraction_type] || '#858796';
    var ctxA = c.entity_a_context || {};
    var ctxB = c.entity_b_context || {};
    var rec = c.recommendation || 'review';

    var mergeClass = (rec === 'merge') ? 'btn btn-sm btn-primary' : 'btn btn-sm btn-outline-secondary';
    var separateClass = (rec === 'keep_separate') ? 'btn btn-sm btn-secondary' : 'btn btn-sm btn-outline-secondary';
    if (rec === 'review') {
        mergeClass = 'btn btn-sm btn-outline-primary';
        separateClass = 'btn btn-sm btn-outline-secondary';
    }

    var html = '<div class="candidate-row" id="candidate-' + index + '">'
        + '<div class="row">'
        + '<div class="col-md-5">'
        + '<div class="d-flex align-items-center gap-2">'
        + '<div class="entity-label">' + escapeHtml(c.entity_a_label) + '</div>'
        + '<span class="badge bg-primary-subtle text-primary-emphasis" style="font-size: 0.65rem;">keep</span>'
        + '</div>'
        + '<div class="d-flex align-items-center gap-1 mt-1">';
    if (ctxA.extraction_type) {
        html += '<span class="badge concept-badge" style="background-color: ' + colorA + ';">'
            + titleCase(ctxA.extraction_type) + '</span>';
    }
    if (ctxA.storage_type) {
        html += '<span class="badge concept-badge bg-light text-dark border">' + escapeHtml(ctxA.storage_type) + '</span>';
    }
    if (ctxA.source_section) {
        html += '<span class="badge concept-badge bg-light text-dark border"><i class="bi bi-file-text"></i> ' + escapeHtml(ctxA.source_section) + '</span>';
    }
    html += '</div>';
    if (ctxA.definition) {
        html += '<div class="entity-def">' + escapeHtml(ctxA.definition) + '</div>';
    }
    html += '</div>'
        + '<div class="col-md-1 text-center d-flex align-items-center justify-content-center">'
        + '<button class="btn btn-sm btn-outline-secondary border-0" onclick="swapCandidate(' + index + ')" '
        + 'title="Swap primary entity (left = keep, right = merge into)">'
        + '<i class="bi bi-arrow-left-right"></i></button>'
        + '</div>'
        + '<div class="col-md-5">'
        + '<div class="entity-label">' + escapeHtml(c.entity_b_label) + '</div>'
        + '<div class="d-flex align-items-center gap-1 mt-1">';
    if (ctxB.extraction_type) {
        html += '<span class="badge concept-badge" style="background-color: ' + colorB + ';">'
            + titleCase(ctxB.extraction_type) + '</span>';
    }
    if (ctxB.storage_type) {
        html += '<span class="badge concept-badge bg-light text-dark border">' + escapeHtml(ctxB.storage_type) + '</span>';
    }
    if (ctxB.source_section) {
        html += '<span class="badge concept-badge bg-light text-dark border"><i class="bi bi-file-text"></i> ' + escapeHtml(ctxB.source_section) + '</span>';
    }
    html += '</div>';
    if (ctxB.definition) {
        html += '<div class="entity-def">' + escapeHtml(ctxB.definition) + '</div>';
    }
    html += '</div>'
        + '</div>';

    if (c.llm_reason) {
        html += '<div class="llm-reason"><i class="bi bi-robot me-1"></i> ' + escapeHtml(c.llm_reason) + '</div>';
    }

    html += '<div class="d-flex justify-content-end gap-2 mt-2">'
        + '<button class="' + mergeClass + '" data-action="merge" '
        + 'onclick="mergeEntities(candidateData[' + index + '].entity_a_id, candidateData[' + index + '].entity_b_id, ' + index + ')" '
        + 'title="Merge: keep left entity, merge right into it">'
        + '<i class="bi bi-union me-1"></i>Merge</button>'
        + '<button class="' + separateClass + '" data-action="keep_separate" '
        + 'onclick="keepSeparate(candidateData[' + index + '].entity_a_id, candidateData[' + index + '].entity_b_id, ' + index + ')" '
        + 'title="Keep both entities separate">'
        + '<i class="bi bi-arrows-expand me-1"></i>Keep Separate</button>'
        + '</div>';

    html += '</div>';
    return html;
}

function titleCase(str) {
    if (!str) return '';
    return str.replace(/_/g, ' ').replace(/\b\w/g, function(l) { return l.toUpperCase(); });
}

function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function swapCandidate(index) {
    var c = candidateData[index];
    if (!c) return;
    // Swap A and B fields
    var tmp;
    tmp = c.entity_a_id; c.entity_a_id = c.entity_b_id; c.entity_b_id = tmp;
    tmp = c.entity_a_label; c.entity_a_label = c.entity_b_label; c.entity_b_label = tmp;
    tmp = c.entity_a_context; c.entity_a_context = c.entity_b_context; c.entity_b_context = tmp;
    // Re-render the row in place
    var row = document.getElementById('candidate-' + index);
    if (row) {
        var newRow = document.createElement('div');
        newRow.innerHTML = buildCandidateRow(c, index);
        row.parentNode.replaceChild(newRow.firstChild, row);
    }
}

function toggleAutoKeptSeparate() {
    var list = document.getElementById('autoKeptSeparateList');
    var btn = document.getElementById('toggleAutoKeptBtn');
    if (list.style.display === 'none') {
        list.style.display = 'block';
        btn.innerHTML = '<i class="bi bi-eye-slash me-1"></i>Hide';
    } else {
        list.style.display = 'none';
        btn.innerHTML = '<i class="bi bi-eye me-1"></i>Show';
    }
}

function mergeEntities(entityAId, entityBId, candidateIndex) {
    var row = document.getElementById('candidate-' + candidateIndex);
    var btn = row.querySelector('[data-action="merge"]');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    }

    fetch((window.RECONCILE || {}).reconcileMergeUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({keep_id: entityAId, merge_id: entityBId, run_id: currentRunId})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            mergeSnapshots[candidateIndex] = data.snapshots;
            row.classList.add('resolved');
            row.innerHTML = '<div class="d-flex align-items-center justify-content-center py-2 gap-3">'
                + '<span class="text-success"><i class="bi bi-check-circle me-1"></i> Merged (both definitions preserved)</span>'
                + '<button class="btn btn-sm btn-outline-warning" onclick="unmergeEntities(' + candidateIndex + ')">'
                + '<i class="bi bi-arrow-counterclockwise me-1"></i>Undo</button>'
                + '</div>';
            checkAllResolved();
        } else {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-union me-1"></i>Merge'; }
            alert('Merge failed: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(function(err) {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-union me-1"></i>Merge'; }
        alert('Error: ' + err);
    });
}

function unmergeEntities(candidateIndex) {
    var row = document.getElementById('candidate-' + candidateIndex);
    var snapshots = mergeSnapshots[candidateIndex];
    var c = candidateData[candidateIndex];
    if (!snapshots) {
        alert('No undo data available for this merge.');
        return;
    }

    var btn = row.querySelector('.btn-outline-warning');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    }

    var body = {snapshots: snapshots, run_id: currentRunId};
    if (c) {
        body.entity_a_id = c.entity_a_id;
        body.entity_b_id = c.entity_b_id;
    }

    fetch((window.RECONCILE || {}).reconcileUnmergeUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            delete mergeSnapshots[candidateIndex];
            // Rebuild candidate row from stored data or server response
            var rebuildData = data.candidate || candidateData[candidateIndex];
            if (rebuildData) {
                candidateData[candidateIndex] = rebuildData;
                row.outerHTML = buildCandidateRow(rebuildData, candidateIndex);
            } else {
                row.classList.remove('resolved');
                row.innerHTML = '<div class="text-center text-info py-2">'
                    + '<i class="bi bi-arrow-counterclockwise me-1"></i> Unmerged -- both entities restored. '
                    + '<button class="btn btn-sm btn-outline-secondary" onclick="location.reload()">Refresh page</button>'
                    + '</div>';
            }
            checkAllResolved();
        } else {
            alert('Unmerge failed: ' + (data.error || 'Unknown error'));
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-arrow-counterclockwise me-1"></i>Undo';
            }
        }
    })
    .catch(function(err) {
        alert('Error: ' + err);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-arrow-counterclockwise me-1"></i>Undo';
        }
    });
}

function keepSeparate(entityAId, entityBId, candidateIndex) {
    var row = document.getElementById('candidate-' + candidateIndex);
    var btn = row.querySelector('[data-action="keep_separate"]');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    }

    fetch((window.RECONCILE || {}).reconcileKeepSeparateUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({entity_a_id: entityAId, entity_b_id: entityBId, run_id: currentRunId})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            row.classList.add('resolved');
            row.innerHTML = '<div class="d-flex align-items-center justify-content-center py-2 gap-3">'
                + '<span class="text-muted"><i class="bi bi-dash-circle me-1"></i> Kept separate</span>'
                + '<button class="btn btn-sm btn-outline-secondary" onclick="undoKeepSeparate(' + entityAId + ', ' + entityBId + ', ' + candidateIndex + ')">'
                + '<i class="bi bi-arrow-counterclockwise me-1"></i>Undo</button>'
                + '</div>';
            checkAllResolved();
        } else {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-arrows-expand me-1"></i>Keep Separate'; }
            alert('Failed: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(function(err) {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-arrows-expand me-1"></i>Keep Separate'; }
        alert('Error: ' + err);
    });
}

function undoKeepSeparate(entityAId, entityBId, candidateIndex) {
    var row = document.getElementById('candidate-' + candidateIndex);
    var btn = row.querySelector('.btn-outline-secondary');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    }

    fetch((window.RECONCILE || {}).reconcileUndoKeepSeparateUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({entity_a_id: entityAId, entity_b_id: entityBId, run_id: currentRunId})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            var rebuildData = data.candidate || candidateData[candidateIndex];
            if (rebuildData) {
                candidateData[candidateIndex] = rebuildData;
                row.outerHTML = buildCandidateRow(rebuildData, candidateIndex);
            } else {
                row.classList.remove('resolved');
                row.innerHTML = '<div class="text-center text-info py-2">Restored. <button class="btn btn-sm btn-outline-secondary" onclick="location.reload()">Refresh page</button></div>';
            }
            checkAllResolved();
        } else {
            alert('Undo failed: ' + (data.error || 'Unknown error'));
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-arrow-counterclockwise me-1"></i>Undo';
            }
        }
    })
    .catch(function(err) {
        alert('Error: ' + err);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-arrow-counterclockwise me-1"></i>Undo';
        }
    });
}

function checkAllResolved() {
    if (totalCandidates === 0) return;

    var total = document.querySelectorAll('.candidate-row').length;
    var resolved = document.querySelectorAll('.candidate-row.resolved').length;
    var pending = total - resolved;
    var statusEl = document.getElementById('reconcileStatus');

    if (statusEl) {
        if (pending > 0) {
            statusEl.textContent = resolved + '/' + total + ' resolved';
        } else {
            statusEl.textContent = 'All resolved';
        }
    }
}

// On page load: render stored reconciliation results if they exist (and not already committed)
document.addEventListener('DOMContentLoaded', function() {
    if (window.STORED_RUN && !window.IS_COMMITTED) {
        var stored = window.STORED_RUN;
        currentRunId = stored.id;

        // Hide the "Run Reconciliation" button/description
        var initial = document.getElementById('reconcileInitial');
        if (initial) initial.style.display = 'none';

        renderReconciliationResults(
            stored.candidates,
            stored.auto_merged,
            stored.errors,
            stored.decisions || {}
        );
    }
});
