const CASE_ID = window.PIPELINE.caseId;
const STATUS_URL = window.PIPELINE.statusUrl;
const RUN_URL = window.PIPELINE.runUrl;
const RUN_ALL_URL = window.PIPELINE.runAllUrl;
const CONTINUE_URL = window.PIPELINE.continueUrl;
const STOP_URL = window.PIPELINE.stopUrl;
const FORCE_CANCEL_URL = window.PIPELINE.forceCancelUrl;
const RERUN_PREVIEW_URL = window.PIPELINE.rerunPreviewUrl;
const RERUN_URL = window.PIPELINE.rerunUrl;
const PROVENANCE_URL = window.PIPELINE.provenanceUrl;
const STEP4_REVIEW_URL = window.PIPELINE.step4ReviewUrl;

let pollInterval = null;
let isRunning = window.PIPELINE.isRunning;
let pipelineMode = 'run_all';  // 'run_all' or 'interactive'

// Initialize: if there's an active run, start polling
if (isRunning) {
    startPolling();
    setRunningUI(true);
}
if (window.PIPELINE.isWaitingReview) {
// Active run is waiting for review -- show review bar
showReviewBar(window.PIPELINE.currentStep);
pipelineMode = 'interactive';
updateModeToggle();
}

function runSubstep(substep) {
    if (isRunning) return;

    setRunningUI(true);
    hideError();

    fetch(RUN_URL, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({substep: substep})
    })
    .then(r => r.json().then(data => ({ok: r.ok, data})))
    .then(({ok, data}) => {
        if (!ok) {
            showError(data.error || 'Failed to start');
            setRunningUI(false);
            return;
        }
        startPolling();
    })
    .catch(err => {
        showError('Network error: ' + err.message);
        setRunningUI(false);
    });
}

function runAll() {
    if (isRunning) return;

    setRunningUI(true);
    hideError();
    hideReviewBar();

    fetch(RUN_ALL_URL, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({mode: pipelineMode})
    })
    .then(r => r.json().then(data => ({ok: r.ok, data})))
    .then(({ok, data}) => {
        if (!ok) {
            showError(data.error || 'Failed to start');
            setRunningUI(false);
            return;
        }
        startPolling();
    })
    .catch(err => {
        showError('Network error: ' + err.message);
        setRunningUI(false);
    });
}

function startPolling() {
    if (pollInterval) return;
    isRunning = true;
    pollInterval = setInterval(pollStatus, 4000);
    // Immediate first poll
    pollStatus();
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
    isRunning = false;
}

function pollStatus() {
    fetch(STATUS_URL)
    .then(r => r.json())
    .then(data => {
        updateUI(data);

        if (!data.active_run) {
            // No active run -- stop polling
            stopPolling();
            setRunningUI(false);
            hideReviewBar();
        } else if (data.active_run.is_waiting_review) {
            // Interactive mode: step completed, awaiting review
            stopPolling();
            setRunningUI(false);
            showReviewBar(data.active_run.current_step);
        } else if (data.active_run.is_failed) {
            // Handled in updateUI, but stop polling here too
            stopPolling();
        }
    })
    .catch(err => {
        console.error('Poll error:', err);
    });
}

// Map Celery task current_step values to PSM substep names.
// Task layer uses "step1_facts", PSM uses "pass1_facts", etc.
// Step 4 substep tasks use PSM names directly (step4_provisions, step4_qc, etc.)
const STEP_NAME_MAP = {
    'step1_facts': 'pass1_facts',
    'step1_discussion': 'pass1_discussion',
    'step2_facts': 'pass2_facts',
    'step2_discussion': 'pass2_discussion',
    'step3': 'pass3',
    'step4': 'step4_provisions',  // Legacy monolithic task
};

// All known PSM substep names for direct-match lookup
const PSM_SUBSTEP_NAMES = new Set([
    'pass1_facts', 'pass1_discussion', 'pass2_facts', 'pass2_discussion',
    'pass3', 'reconcile', 'commit_extraction',
    'step4_provisions', 'step4_precedents', 'step4_qc',
    'step4_transformation', 'step4_rich_analysis', 'step4_phase3', 'step4_phase4',
    'commit_synthesis',
]);

function resolveRunningStep(currentStep) {
    if (!currentStep) return null;
    // Direct match against PSM names
    if (PSM_SUBSTEP_NAMES.has(currentStep)) return currentStep;
    // Map from task names
    if (STEP_NAME_MAP[currentStep]) return STEP_NAME_MAP[currentStep];
    // Progress messages: "step4_qc: Extracting..." -> extract substep before colon
    const colonIdx = currentStep.indexOf(':');
    if (colonIdx > 0) {
        const prefix = currentStep.substring(0, colonIdx).trim();
        if (PSM_SUBSTEP_NAMES.has(prefix)) return prefix;
    }
    // Prefix match: "step1_facts_parallel" -> "step1_facts" -> "pass1_facts"
    for (const [taskName, psmName] of Object.entries(STEP_NAME_MAP)) {
        if (currentStep.startsWith(taskName) || currentStep.includes(taskName)) {
            return psmName;
        }
    }
    // Step 4 sub-phases from legacy monolithic task: "PROVISIONS: ..." -> step4_provisions
    const legacyMap = {
        'PROVISIONS': 'step4_provisions', 'PRECEDENTS': 'step4_precedents',
        'QC': 'step4_qc', 'TRANSFORMATION': 'step4_transformation',
        'RICH_ANALYSIS': 'step4_rich_analysis', 'PHASE3': 'step4_phase3',
        'PHASE4': 'step4_phase4',
    };
    for (const [prefix, psmName] of Object.entries(legacyMap)) {
        if (currentStep.startsWith(prefix)) return psmName;
    }
    return null;
}

// Substep-to-display-row mapping (server-generated)
const SUBSTEP_TO_ROW = window.PIPELINE.substepToRow;

function resolveDisplayRow(psmStep) {
    if (!psmStep) return null;
    return SUBSTEP_TO_ROW[psmStep] || psmStep;
}

function updateUI(state) {
    const rows = state.display_rows;
    const total = rows.length;
    let completeCount = 0;

    // Resolve running step to display row
    const runningPsmStep = state.active_run
        ? resolveRunningStep(state.active_run.current_step)
        : null;
    const runningDisplayRow = resolveDisplayRow(runningPsmStep);

    // Update each display row card
    for (const row of rows) {
        const card = document.getElementById('substep-' + row.name);
        if (!card) continue;

        // Determine display status: overlay active run onto row state
        let displayStatus = row.status;
        if (runningDisplayRow === row.name) {
            displayStatus = 'running';
        }

        if (row.status === 'complete') completeCount++;

        // Update card classes
        card.className = 'substep-card status-' + displayStatus;
        card.dataset.status = displayStatus;

        // Update icon
        const icon = card.querySelector('.substep-icon');
        if (icon) {
            icon.className = 'substep-icon icon-' + displayStatus;
            const iconEl = icon.querySelector('i');
            if (iconEl) {
                if (displayStatus === 'complete') {
                    iconEl.className = 'bi bi-check';
                } else if (displayStatus === 'running') {
                    iconEl.className = 'bi bi-arrow-repeat';
                } else if (displayStatus === 'error') {
                    iconEl.className = 'bi bi-x';
                } else {
                    iconEl.className = 'bi bi-circle';
                }
            }
        }

        // Update badges
        const badgeContainer = card.querySelector('.substep-badges');
        if (badgeContainer && row.tasks) {
            badgeContainer.replaceChildren();
            for (const [tName, tInfo] of Object.entries(row.tasks)) {
                const total = Object.values(tInfo.artifact_counts).reduce((a, b) => a + b, 0);
                if (total > 0 || row.status === 'complete') {
                    const span = document.createElement('span');
                    span.className = 'artifact-badge has-data';
                    span.dataset.entityType = tName;
                    span.title = tInfo.artifact_types.join(', ');
                    span.textContent = total > 0
                        ? tInfo.display_name + ': ' + total
                        : tInfo.display_name;
                    badgeContainer.appendChild(span);
                }
            }
        }

        // Update section status line for merged rows
        const sectionLine = card.querySelector('.section-status');
        if (sectionLine && row.section_statuses) {
            if (row.status === 'complete' || row.status === 'not_started') {
                sectionLine.style.display = 'none';
            } else {
                sectionLine.style.display = '';
                const parts = [];
                for (const [sec, secStatus] of Object.entries(row.section_statuses)) {
                    const cls = secStatus === 'complete' ? 'text-success' :
                                secStatus === 'error' ? 'text-danger' : '';
                    parts.push('<span class="' + cls + '">' +
                        sec.charAt(0).toUpperCase() + sec.slice(1) + ': ' +
                        secStatus.replace('_', ' ') + '</span>');
                }
                sectionLine.innerHTML = parts.join('<span class="mx-1">|</span>');
            }
        }

        // Toggle run vs rerun buttons
        const runBtn = card.querySelector('.btn-run');
        const rerunBtn = card.querySelector('.btn-rerun');
        if (row.status === 'complete') {
            if (runBtn) runBtn.style.display = 'none';
            if (rerunBtn) {
                rerunBtn.style.display = isRunning ? 'none' : '';
                rerunBtn.disabled = isRunning;
            }
        } else {
            if (rerunBtn) rerunBtn.style.display = 'none';
            if (runBtn) {
                runBtn.style.display = '';
                runBtn.disabled = !row.can_start || isRunning;
                // Update run target for merged rows (may shift from facts to discussion)
                if (row.run_target) {
                    runBtn.dataset.substep = row.run_target;
                    runBtn.onclick = function() { runSubstep(row.run_target); };
                }
            }
        }

        // Toggle view links
        const viewProv = card.querySelector('.btn-view-provenance');
        if (viewProv) viewProv.style.display = row.status === 'complete' ? '' : 'none';
        const viewAnalysis = card.querySelector('.btn-view-analysis');
        if (viewAnalysis) viewAnalysis.style.display = row.status === 'complete' ? '' : 'none';
    }

    // Update summary stats
    const pct = total > 0 ? Math.round((completeCount / total) * 100) : 0;
    const statsEl = document.getElementById('stats-complete');
    if (statsEl) {
        statsEl.textContent = completeCount + '/' + total;
        statsEl.className = 'stat-value ' +
            (completeCount === total ? 'text-success' :
             completeCount > 0 ? 'text-primary' : 'text-muted');
    }
    const progressBar = document.getElementById('progress-complete');
    if (progressBar) progressBar.style.width = pct + '%';

    // Update active run status text
    const runStatus = document.getElementById('active-run-status');
    const runText = document.getElementById('active-run-text');
    const cancelBtn = document.getElementById('btn-force-cancel');
    if (state.active_run) {
        runStatus.style.display = 'flex';
        const step = state.active_run.current_step || 'initializing';
        const dur = Math.round(state.active_run.duration_seconds || 0);
        runText.textContent = step + ' (' + dur + 's)';
        // Show force-cancel after 5 minutes (run may be stuck)
        cancelBtn.style.display = dur > 300 ? '' : 'none';
    } else {
        runStatus.style.display = 'none';
        cancelBtn.style.display = 'none';
    }

    // Show error if run failed
    if (state.active_run && state.active_run.is_failed) {
        showError(state.active_run.error_message || 'Pipeline failed');
        stopPolling();
        setRunningUI(false);
    }
}

function setRunningUI(running) {
    isRunning = running;
    const runAllBtn = document.getElementById('btn-run-all');
    if (runAllBtn) runAllBtn.disabled = running;

    document.querySelectorAll('.btn-run').forEach(btn => {
        if (running) {
            btn.disabled = true;
        }
        // When not running, the pollStatus updateUI will re-enable based on can_start
    });

    document.querySelectorAll('.btn-rerun').forEach(btn => {
        btn.disabled = running;
        if (running) btn.style.display = 'none';
    });
}

function showError(msg) {
    const el = document.getElementById('run-error');
    const textEl = document.getElementById('run-error-text');
    if (el && textEl) {
        textEl.textContent = msg;
        el.style.display = '';
    }
}

function hideError() {
    const el = document.getElementById('run-error');
    if (el) el.style.display = 'none';
}

// --- Interactive mode functions ---

function setMode(mode) {
    pipelineMode = mode;
    updateModeToggle();
}

function updateModeToggle() {
    const autoBtn = document.getElementById('btn-mode-auto');
    const interBtn = document.getElementById('btn-mode-interactive');
    if (pipelineMode === 'interactive') {
        autoBtn.classList.remove('active');
        interBtn.classList.add('active');
    } else {
        autoBtn.classList.add('active');
        interBtn.classList.remove('active');
    }
}

function showReviewBar(currentStep) {
    const bar = document.getElementById('review-bar');
    const text = document.getElementById('review-bar-text');
    const link = document.getElementById('review-bar-link');
    if (!bar) return;

    // Resolve to PSM substep name for consistent matching
    const psmStep = resolveRunningStep(currentStep) || currentStep;
    bar.style.display = '';
    text.dataset.currentStep = psmStep || '';

    // Determine review link based on resolved PSM substep name
    if (psmStep && psmStep.startsWith('pass')) {
        link.href = PROVENANCE_URL;
        link.style.display = '';
        text.textContent = psmStep + ' complete. Review extracted entities.';
    } else if (psmStep && psmStep.startsWith('step4_')) {
        link.href = STEP4_REVIEW_URL;
        link.style.display = '';
        text.textContent = psmStep + ' complete. Review analysis results.';
    } else if (psmStep === 'reconcile') {
        text.textContent = 'Reconciliation complete. Continue to commit.';
        link.style.display = 'none';
    } else if (psmStep && psmStep.startsWith('commit')) {
        text.textContent = 'Entities committed. Continue to next phase.';
        link.style.display = 'none';
    } else {
        text.textContent = 'Step complete. Review results before continuing.';
        link.style.display = 'none';
    }

    // Highlight the display row with waiting_review style
    const displayRow = resolveDisplayRow(psmStep);
    const card = document.getElementById('substep-' + displayRow);
    if (card) {
        card.className = 'substep-card status-waiting_review';
        const icon = card.querySelector('.substep-icon');
        if (icon) {
            icon.className = 'substep-icon icon-waiting_review';
            const iconEl = icon.querySelector('i');
            if (iconEl) iconEl.className = 'bi bi-eye';
        }
    }
}

function hideReviewBar() {
    const bar = document.getElementById('review-bar');
    if (bar) bar.style.display = 'none';
}

function continueInteractive() {
    hideReviewBar();
    hideError();
    setRunningUI(true);

    fetch(CONTINUE_URL, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({})
    })
    .then(r => r.json().then(data => ({ok: r.ok, data})))
    .then(({ok, data}) => {
        if (!ok) {
            showError(data.error || 'Failed to continue');
            setRunningUI(false);
            return;
        }
        if (data.completed) {
            // All substeps done
            setRunningUI(false);
            pollStatus();
            return;
        }
        startPolling();
    })
    .catch(err => {
        showError('Network error: ' + err.message);
        setRunningUI(false);
    });
}

function stopInteractive() {
    // Capture current step before hiding, in case we need to restore
    const reviewText = document.getElementById('review-bar-text');
    const lastStep = reviewText ? reviewText.dataset.currentStep : null;
    hideReviewBar();

    fetch(STOP_URL, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({})
    })
    .then(r => r.json().then(data => ({ok: r.ok, data})))
    .then(({ok, data}) => {
        if (!ok) {
            showError(data.error || 'Failed to stop');
            if (lastStep) showReviewBar(lastStep);
            return;
        }
        setRunningUI(false);
        // Final poll to refresh state
        fetch(STATUS_URL).then(r => r.json()).then(updateUI);
    })
    .catch(err => {
        showError('Network error: ' + err.message);
        if (lastStep) showReviewBar(lastStep);
    });
}

function forceCancel() {
    if (!confirm('Force-cancel the active pipeline run? This marks it as failed.')) return;
    hideError();

    fetch(FORCE_CANCEL_URL, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({})
    })
    .then(r => r.json().then(data => ({ok: r.ok, data})))
    .then(({ok, data}) => {
        if (!ok) {
            showError(data.error || 'Failed to cancel');
            return;
        }
        stopPolling();
        setRunningUI(false);
        fetch(STATUS_URL).then(r => r.json()).then(updateUI);
    })
    .catch(err => {
        showError('Network error: ' + err.message);
    });
}

// --- Re-run functions ---

function rerunSubstep(substep) {
    if (isRunning) return;
    hideError();

    // Fetch preview to build confirmation dialog
    fetch(RERUN_PREVIEW_URL + '?substep=' + encodeURIComponent(substep))
    .then(r => r.json().then(data => ({ok: r.ok, data})))
    .then(({ok, data}) => {
        if (!ok) {
            showError(data.error || 'Failed to preview');
            return;
        }
        showRerunConfirmation(substep, data);
    })
    .catch(err => {
        showError('Network error: ' + err.message);
    });
}

function showRerunConfirmation(substep, preview) {
    let msg = 'Re-run "' + preview.target_display + '"?\n\n';
    if (preview.downstream_display.length > 0) {
        msg += 'This will clear data from ' + preview.affected_count + ' steps:\n';
        msg += '- ' + preview.target_display + ' (re-run target)\n';
        for (const name of preview.downstream_display) {
            msg += '- ' + name + '\n';
        }
    } else {
        msg += 'Only "' + preview.target_display + '" data will be cleared.\n';
    }
    if (preview.will_clear_commits) {
        msg += '\nOntServe entities will be stale until re-committed.';
    }

    if (!confirm(msg)) return;

    // Execute the re-run
    setRunningUI(true);
    fetch(RERUN_URL, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({substep: substep})
    })
    .then(r => r.json().then(data => ({ok: r.ok, data})))
    .then(({ok, data}) => {
        if (!ok) {
            showError(data.error || 'Failed to re-run');
            setRunningUI(false);
            return;
        }
        startPolling();
    })
    .catch(err => {
        showError('Network error: ' + err.message);
        setRunningUI(false);
    });
}
