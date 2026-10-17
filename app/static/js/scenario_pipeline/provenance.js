const CASE_ID = (window.PROVENANCE || {}).caseId;
let currentPipelineData = null;

// Origin display labels
const ORIGIN_LABELS = {
    'automated_pipeline': 'Automated Pipeline',
    'user_initiated': 'User Initiated',
    'individual_extraction': 'Individual Extraction',
    'algorithmic': 'Algorithmic'
};

// Activity type styling
const activityStyles = {
    'extraction': { icon: 'bi-download', color: '#3b82f6', label: 'Extraction' },
    'llm_query': { icon: 'bi-robot', color: '#8b5cf6', label: 'LLM Query' },
    'composition': { icon: 'bi-gear', color: '#14b8a6', label: 'Algorithmic' },
    'alignment': { icon: 'bi-check2-square', color: '#06b6d4', label: 'Alignment' },
    'enrichment': { icon: 'bi-link-45deg', color: '#22c55e', label: 'MCP Resolution' },
    'synthesis': { icon: 'bi-lightbulb', color: '#f59e0b', label: 'Synthesis' },
    'storage': { icon: 'bi-database', color: '#64748b', label: 'Storage' },
    'analysis': { icon: 'bi-graph-up', color: '#ec4899', label: 'Analysis' }
};

const ENTITY_COLORS = {
    'roles': '#0d6efd',
    'states': '#6f42c1',
    'resources': '#20c997',
    'principles': '#fd7e14',
    'obligations': '#dc3545',
    'constraints': '#6c757d',
    'capabilities': '#0dcaf0',
    'actions': '#198754',
    'events': '#ffc107'
};

document.addEventListener('DOMContentLoaded', function() {
    loadPipeline();

    document.getElementById('activityLogModal').addEventListener('show.bs.modal', function() {
        loadActivityLog();
    });
});

// ---- Data Loading ----

function loadPipeline() {
    const container = document.getElementById('pipeline-timeline');
    container.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div><p class="mt-2">Loading pipeline data...</p></div>';

    fetch(`/api/provenance/case/${CASE_ID}/pipeline`)
        .then(response => response.json())
        .then(data => {
            currentPipelineData = data;
            displayPipeline(data);
            applyFilters();
        })
        .catch(error => {
            console.error('Error loading pipeline:', error);
            container.innerHTML = `<div class="alert alert-danger">Failed to load pipeline data: ${error.message}</div>`;
        });
}

// ---- Pipeline Display ----

function displayPipeline(data) {
    const container = document.getElementById('pipeline-timeline');
    container.innerHTML = '';

    if (!data.pipeline || data.pipeline.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4 text-muted">
                <i class="bi bi-inbox" style="font-size: 3rem;"></i>
                <p class="mt-2">No pipeline data recorded for this case yet.</p>
                <p class="small">Run extraction steps to begin building the provenance record.</p>
            </div>`;
        return;
    }

    data.pipeline.forEach(step => {
        if (step.step <= 3) {
            container.appendChild(createStepHeader(step));
            step.passes.forEach(pass => {
                container.appendChild(createPassHeader(step, pass));
                pass.extractions.forEach(extraction => {
                    container.appendChild(createExtractionCard(step, pass, extraction));
                });
            });
        } else {
            container.appendChild(createStepHeader(step));
            if (step.phases) {
                step.phases.forEach(phase => {
                    container.appendChild(createPhaseCard(step, phase));
                });
            }
        }
    });

    // Consolidation & commit trail (reconcile, enrichment, edge
    // materialization, guards, conformance) -- the activities that turn the
    // working store into the committed record.
    if (data.consolidation && data.consolidation.length > 0) {
        container.appendChild(createConsolidationCard(data.consolidation));
    }

    // QC Verification results
    if (data.qc_verification) {
        container.appendChild(createQCCard(data.qc_verification));
    }

    // Manual Refinements (revision entries from review log)
    if (data.review_log) {
        const revisions = data.review_log.filter(e => e.entry_type === 'revision');
        container.appendChild(createRefinementsCard(revisions));
    }

    // Review Log (non-revision entries)
    if (data.review_log && data.review_log.length > 0) {
        const nonRevisions = data.review_log.filter(e => e.entry_type !== 'revision');
        if (nonRevisions.length > 0) {
            container.appendChild(createReviewLogCard(nonRevisions));
        }
    }
}

function formatQCDetails(check) {
    const d = check.details;
    if (!d) return '';
    const parts = [];
    switch (check.check_id) {
        case 'V0':
            if (d.facts_len !== undefined) parts.push(`facts: ${d.facts_len} chars`);
            if (d.discussion_len !== undefined) parts.push(`discussion: ${d.discussion_len} chars`);
            if (d.issues) parts.push(d.issues.join('; '));
            break;
        case 'V1':
            if (d.multi_session_types && d.multi_session_types.length > 0) {
                const typeNames = d.multi_session_types.map(t =>
                    typeof t === 'object' ? `${t.type} (${t.sessions} sessions)` : t
                );
                parts.push(`multi-session: ${typeNames.join(', ')}`);
            }
            if (d.actual_duplicates && d.actual_duplicates.length > 0)
                parts.push(`${d.actual_duplicates.length} actual duplicates`);
            else if (d.multi_session_types && d.multi_session_types.length > 0)
                parts.push('no actual label duplicates');
            break;
        case 'V4':
            if (d.violations && d.violations.length > 0)
                parts.push(`${d.violations.length} violations`);
            else if (d.decision_points)
                parts.push(`${d.decision_points.length} DPs checked`);
            break;
        case 'V6':
            if (d.type_count !== undefined) parts.push(`${d.type_count}/16 types`);
            if (d.missing_types && d.missing_types.length > 0)
                parts.push(`missing: ${d.missing_types.join(', ')}`);
            break;
        case 'V7':
            if (d.total !== undefined) parts.push(`${d.total} entities`);
            if (d.out_of_range && d.out_of_range.length > 0)
                parts.push(`${d.out_of_range.length} out of range`);
            break;
        case 'V8':
            if (d.prompt_models && d.prompt_models.length > 0) parts.push(d.prompt_models.join(', '));
            break;
        case 'V9':
            if (d.total !== undefined) parts.push(`${d.published || 0}/${d.total} published`);
            break;
        default:
            if (d.note) parts.push(d.note);
            break;
    }
    return parts.length > 0 ? `<div class="text-muted small">${escapeHtml(parts.join(' | '))}</div>` : '';
}

function createRefinementsCard(revisions) {
    const div = document.createElement('div');
    div.className = 'pipeline-card';
    div.dataset.step = 'refinements';
    div.dataset.type = 'refinements';

    let contentHtml = '';
    if (revisions.length > 0) {
        const rows = revisions.map(rev => {
            const dateStr = rev.created_at
                ? new Date(rev.created_at).toLocaleDateString('en-US', {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})
                : '';
            const statusBadge = rev.status === 'APPLIED'
                ? '<span class="badge bg-success" style="font-size: 0.7em;">APPLIED</span>'
                : rev.status === 'REVERTED'
                ? '<span class="badge bg-warning text-dark" style="font-size: 0.7em;">REVERTED</span>'
                : `<span class="badge bg-secondary" style="font-size: 0.7em;">${rev.status || 'LOGGED'}</span>`;
            const keyBadge = rev.entry_key
                ? `<code class="me-1" style="font-size: 0.8em;">${escapeHtml(rev.entry_key)}</code>`
                : '';
            let detailHtml = '';
            if (rev.details) {
                const detailId = `refinement-${rev.id || Math.random().toString(36).substr(2, 6)}`;
                detailHtml = `
                    <div class="mt-1" id="${detailId}" style="display: none;">
                        <pre class="bg-light p-2 rounded small mb-0" style="white-space: pre-wrap;">${escapeHtml(JSON.stringify(rev.details, null, 2))}</pre>
                    </div>`;
            }
            return `<div class="d-flex align-items-start gap-2 py-1 border-bottom" style="border-color: #f0f0f0 !important;">
                <i class="bi bi-pencil-square mt-1" style="color: #fd7e14; font-size: 0.85rem;"></i>
                <div class="flex-grow-1">
                    <div class="d-flex align-items-center gap-2 flex-wrap">
                        ${keyBadge} ${statusBadge}
                        <span class="small">${escapeHtml(rev.summary || '')}</span>
                        ${rev.details ? `<a href="#" class="small text-muted" onclick="event.preventDefault(); document.getElementById('${rev.details ? `refinement-${rev.id || ''}` : ''}').style.display = document.getElementById('${rev.details ? `refinement-${rev.id || ''}` : ''}').style.display === 'none' ? 'block' : 'none';">details</a>` : ''}
                    </div>
                    <div class="text-muted" style="font-size: 0.75rem;">
                        ${escapeHtml(rev.author || '')} &middot; ${dateStr}
                    </div>
                    ${detailHtml}
                </div>
            </div>`;
        }).join('');
        contentHtml = rows;
    } else {
        contentHtml = '<div class="text-muted small py-2">No manual refinements recorded. Post-extraction edits to entity data will appear here.</div>';
    }

    div.innerHTML = `
        <div class="card" style="border-left: 4px solid #fd7e14;">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h5 class="mb-0" style="color: #fd7e14;">
                        <i class="bi bi-pencil-square me-2"></i>Manual Refinements (${revisions.length})
                    </h5>
                    <div class="d-flex align-items-center gap-2 flex-wrap">
                        <span class="badge" style="background: #e5e7eb; color: #374151; font-size: 0.7em;"><i class="bi bi-person me-1"></i>Human-in-the-loop</span>
                        <span class="badge" style="background: #dbeafe; color: #1e40af; font-size: 0.7em;"><i class="bi bi-database me-1"></i>Direct DB edits</span>
                    </div>
                </div>
                ${contentHtml}
            </div>
        </div>`;
    return div;
}

function createReviewLogCard(entries) {
    const div = document.createElement('div');
    div.className = 'pipeline-card';
    div.dataset.step = 'review';
    div.dataset.type = 'review-log';

    const ENTRY_ICONS = {
        'agent_check': 'bi-robot',
        'qc_script': 'bi-clipboard-check',
        'manual_review': 'bi-person',
        'revision': 'bi-pencil-square'
    };
    const ENTRY_COLORS = {
        'agent_check': '#0d6efd',
        'qc_script': '#6f42c1',
        'manual_review': '#198754',
        'revision': '#fd7e14'
    };
    const STATUS_BADGES = {
        'PASS': '<span class="badge bg-success">PASS</span>',
        'FAIL': '<span class="badge bg-danger">FAIL</span>',
        'INFO': '<span class="badge bg-info">INFO</span>'
    };

    const rows = entries.map((entry, idx) => {
        const icon = ENTRY_ICONS[entry.entry_type] || 'bi-journal';
        const color = ENTRY_COLORS[entry.entry_type] || '#6c757d';
        const statusBadge = entry.status ? (STATUS_BADGES[entry.status] || `<span class="badge bg-secondary">${escapeHtml(entry.status)}</span>`) : '';
        const keyBadge = entry.entry_key ? `<code class="me-1">${escapeHtml(entry.entry_key)}</code>` : '';
        const dateStr = entry.created_at
            ? new Date(entry.created_at).toLocaleDateString('en-US', {year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})
            : '';
        const detailId = `review-detail-${idx}`;
        let detailHtml = '';
        if (entry.details) {
            detailHtml = `
                <div id="${detailId}" style="display: none;" class="mt-1 ms-4">
                    <pre class="bg-light p-2 rounded small mb-0" style="max-height: 200px; overflow: auto;">${escapeHtml(JSON.stringify(entry.details, null, 2))}</pre>
                </div>`;
        }
        const expandBtn = entry.details
            ? `<i class="bi bi-chevron-down ms-1 small" style="cursor:pointer;" onclick="document.getElementById('${detailId}').style.display = document.getElementById('${detailId}').style.display === 'none' ? 'block' : 'none';"></i>`
            : '';

        return `
            <div class="d-flex align-items-start gap-2 py-2 ${idx < entries.length - 1 ? 'border-bottom' : ''}">
                <i class="bi ${icon} mt-1" style="color: ${color}; font-size: 1.1rem;"></i>
                <div class="flex-grow-1">
                    <div class="d-flex align-items-center gap-2 flex-wrap">
                        ${keyBadge}
                        ${statusBadge}
                        <span class="small">${escapeHtml(entry.summary)}</span>
                        ${expandBtn}
                    </div>
                    <div class="text-muted" style="font-size: 0.75rem;">
                        ${escapeHtml(entry.author || '')} &middot; ${dateStr}
                    </div>
                    ${detailHtml}
                </div>
            </div>`;
    }).join('');

    div.innerHTML = `
        <div class="card" style="border-left: 4px solid #0d6efd;">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h5 class="mb-0" style="color: #0d6efd;">
                        <i class="bi bi-journal-text me-2"></i>Review Log (${entries.length})
                    </h5>
                </div>
                ${rows}
            </div>
        </div>`;
    return div;
}

const CONSOLIDATION_TYPE_STYLES = {
    reconciliation: { color: '#0d6efd', icon: 'bi-arrows-collapse' },
    enrichment: { color: '#20c997', icon: 'bi-stars' },
    materialization: { color: '#6f42c1', icon: 'bi-diagram-3' },
    guard: { color: '#dc3545', icon: 'bi-shield-check' },
    filter: { color: '#fd7e14', icon: 'bi-funnel' },
    validation: { color: '#198754', icon: 'bi-patch-check' },
    gate: { color: '#0dcaf0', icon: 'bi-door-open' },
    repair: { color: '#6610f2', icon: 'bi-wrench' }
};

// Display order of the recorded outcome keys (activity_metadata, served as
// `result`): drops first, then graph counts, merges, conformance, status.
const RESULT_KEY_ORDER = [
    'dropped', 'count', 'dropped_classes', 'dropped_individuals', 'triples_dropped',
    'total_edges', 'by_family', 'auto_merged', 'canonicalized',
    'canon_rejected_cross_category', 'skipped', 'conforms', 'residual',
    'repairs_applied', 'status', 'error', 'errors'
];

// One-line human summary of an activity's recorded outcome: scalars as key:
// value, label lists as a count plus the first labels, dicts of scalars inline,
// dicts of dicts (per-family edge counts) as family=n.
function summarizeResult(result) {
    if (!result || typeof result !== 'object' || Array.isArray(result)) return '';
    const rank = k => { const i = RESULT_KEY_ORDER.indexOf(k); return i === -1 ? RESULT_KEY_ORDER.length : i; };
    const keys = Object.keys(result).sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
    const scalar = v => (typeof v === 'number' || typeof v === 'boolean') ? String(v)
        : (typeof v === 'string' && v.length <= 60 ? v : null);
    const parts = [];
    for (const k of keys) {
        const v = result[k];
        if (v === null || v === undefined || v === '') continue;
        if (Array.isArray(v)) {
            if (!v.length) continue;
            const labels = v.map(x => (typeof x === 'object' && x !== null) ? (x.label || x.name || null) : String(x)).filter(Boolean);
            const shown = labels.slice(0, 5).join(', ') + (labels.length > 5 ? `, +${labels.length - 5} more` : '');
            parts.push(`${k}: ${v.length}${shown ? ` (${shown})` : ''}`);
        } else if (typeof v === 'object') {
            const inner = Object.entries(v).slice(0, 8).map(([ik, iv]) => {
                if (iv && typeof iv === 'object' && !Array.isArray(iv)) {
                    const n = iv.edges !== undefined ? iv.edges
                        : (iv.count !== undefined ? iv.count : Object.values(iv).find(x => typeof x === 'number'));
                    return `${ik}=${(n === undefined || n === null) ? '?' : n}`;
                }
                return `${ik}=${Array.isArray(iv) ? iv.length : (scalar(iv) ?? '…')}`;
            });
            if (inner.length) parts.push(`${k}: ${inner.join(', ')}`);
        } else {
            const s = scalar(v);
            if (s !== null) parts.push(`${k}: ${s}`);
        }
        if (parts.length >= 8) break;
    }
    return parts.join(' | ');
}

// One-line human summary from an activity's execution_plan JSON: show the
// first few short string-valued fields (the recorders store rule/what text).
function summarizeExecutionPlan(plan) {
    if (!plan || typeof plan !== 'object') return '';
    const parts = [];
    for (const [k, v] of Object.entries(plan)) {
        if (parts.length >= 3) break;
        if (typeof v === 'string' && v.length <= 160) {
            parts.push(`${k}: ${v}`);
        } else if (typeof v === 'number' || typeof v === 'boolean') {
            parts.push(`${k}: ${v}`);
        } else if (Array.isArray(v) && v.length <= 8 && v.every(x => typeof x === 'string')) {
            parts.push(`${k}: ${v.join(', ')}`);
        }
    }
    return parts.join(' | ');
}

// Consolidation activities arrive grouped by pipeline run (session id = the
// PipelineRun id, or the time window of a commit made outside a recorded run),
// newest run first, each run's activities in chronological order.
function createConsolidationCard(runs) {
    const div = document.createElement('div');
    div.className = 'pipeline-card';
    div.dataset.step = 'consolidation';
    div.dataset.type = 'consolidation';

    const fmtWhen = iso => iso
        ? new Date(iso).toLocaleDateString('en-US', {year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})
        : '';
    const total = runs.reduce((n, run) => n + run.activities.length, 0);

    const rows = runs.map(run => {
        const label = run.session_id
            ? `Pipeline run <code>${escapeHtml(String(run.session_id))}</code>`
            : 'Commit outside a recorded pipeline run';
        const start = fmtWhen(run.started_at), end = fmtWhen(run.ended_at);
        const window = start === end ? start : `${start} to ${end}`;
        const header = `<tr class="table-light">
            <td colspan="4" class="small">
                <i class="bi bi-play-circle me-1"></i><strong>${label}</strong>
                <span class="text-muted ms-2">${window} &middot; ${run.activities.length} activit${run.activities.length === 1 ? 'y' : 'ies'}</span>
            </td>
        </tr>`;
        const body = run.activities.map(a => {
            const style = CONSOLIDATION_TYPE_STYLES[a.activity_type] || { color: '#6c757d', icon: 'bi-gear' };
            const statusBadge = a.status === 'failed'
                ? '<span class="badge bg-danger">failed</span>'
                : (a.status === 'completed' ? '' : `<span class="badge bg-secondary">${escapeHtml(a.status || '')}</span>`);
            const plan = escapeHtml(summarizeExecutionPlan(a.execution_plan));
            const result = escapeHtml(summarizeResult(a.result));
            const summary = a.error_message
                ? `<span class="text-danger">${escapeHtml(a.error_message)}</span>`
                : `${plan ? `<div>${plan}</div>` : ''}${result ? `<div><span class="badge bg-light text-dark border me-1">result</span>${result}</div>` : ''}`;
            return `<tr>
                <td class="text-nowrap"><span class="badge" style="background-color: ${style.color};"><i class="bi ${style.icon} me-1"></i>${escapeHtml(a.activity_type)}</span></td>
                <td><code>${escapeHtml(a.activity_name)}</code> ${statusBadge}</td>
                <td class="small text-muted">${summary}</td>
                <td class="text-nowrap small text-muted">${fmtWhen(a.started_at)}</td>
            </tr>`;
        }).join('');
        return header + body;
    }).join('');

    div.innerHTML = `
        <div class="card" style="border-left: 4px solid #6f42c1;">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h5 class="mb-0" style="color: #6f42c1;">
                        <i class="bi bi-box-seam me-2"></i>Consolidation &amp; Commit
                    </h5>
                    <span class="text-muted small">${total} recorded activities in ${runs.length} run${runs.length === 1 ? '' : 's'}, newest run first</span>
                </div>
                <p class="text-muted small mb-2">
                    Post-extraction activities that turn the working store into the committed
                    ontology: extraction filters, deduplication and merge, enrichment, edge
                    materialization, guards, the verification gate, and conformance validation.
                    Each row shows the strategy (execution plan) and the recorded result.
                </p>
                <div class="table-responsive">
                    <table class="table table-sm mb-0">
                        <thead><tr><th>Stage</th><th>Activity</th><th>What it did</th><th>When</th></tr></thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>
        </div>`;
    return div;
}

function createQCCard(qc) {
    const div = document.createElement('div');
    div.className = 'pipeline-card';
    div.dataset.step = 'qc';
    div.dataset.type = 'qc-verification';

    const statusColor = qc.overall_status === 'PASS' ? '#198754'
        : qc.overall_status === 'FAIL' ? '#dc3545' : '#ffc107';
    const statusIcon = qc.overall_status === 'PASS' ? 'bi-check-circle-fill'
        : qc.overall_status === 'FAIL' ? 'bi-x-circle-fill' : 'bi-exclamation-circle-fill';

    let checksHtml = '';
    if (qc.check_results && qc.check_results.length > 0) {
        // Filter out deprecated checks (argument generation removed from pipeline)
        const DEPRECATED_CHECKS = ['V2', 'V3', 'V5'];
        const activeChecks = qc.check_results.filter(c => !DEPRECATED_CHECKS.includes(c.check_id));
        const rows = activeChecks.map(check => {
            const rowClass = check.status === 'FAIL' ? 'table-danger'
                : check.status === 'INFO' ? 'table-info'
                : check.status === 'PASS' ? '' : 'table-warning';
            const badge = check.status === 'PASS'
                ? '<span class="badge bg-success">PASS</span>'
                : check.status === 'FAIL'
                ? '<span class="badge bg-danger">FAIL</span>'
                : check.status === 'SKIP'
                ? '<span class="badge bg-secondary">SKIP</span>'
                : `<span class="badge bg-info">${check.status}</span>`;
            const severity = check.severity ? `<span class="text-muted small">${check.severity}</span>` : '';
            const detailText = formatQCDetails(check);
            return `<tr class="${rowClass}">
                <td><code>${check.check_id}</code></td>
                <td>${check.name} ${severity}</td>
                <td>${badge}</td>
                <td>${detailText}</td>
            </tr>`;
        }).join('');
        checksHtml = `
            <table class="table table-sm mb-0 mt-2">
                <thead><tr><th>Check</th><th>Name</th><th>Result</th><th>Details</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>`;
    }

    const dateStr = qc.verification_date
        ? new Date(qc.verification_date).toLocaleDateString('en-US', {year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})
        : '';

    div.innerHTML = `
        <div class="card" style="border-left: 4px solid ${statusColor};">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h5 class="mb-0" style="color: ${statusColor};">
                        <i class="bi ${statusIcon} me-2"></i>QC Verification (${qc.protocol_version || 'V0-V9'})
                    </h5>
                    <div>
                        <span class="badge" style="background-color: ${statusColor};">${qc.overall_status}</span>
                        <span class="text-muted small ms-2">${dateStr}</span>
                    </div>
                </div>
                <div class="d-flex gap-3 mb-2">
                    <span><strong>${qc.entity_count_total}</strong> entities</span>
                    <span><strong>${qc.extraction_types_count}</strong>/16 types</span>
                    <span class="text-danger"><strong>${qc.critical_count}</strong> critical</span>
                    <span class="text-warning"><strong>${qc.warning_count}</strong> warnings</span>
                    <span class="text-info"><strong>${qc.info_count}</strong> info</span>
                </div>
                ${checksHtml}
            </div>
        </div>`;
    return div;
}

function createStepHeader(step) {
    const div = document.createElement('div');
    div.className = 'pipeline-card';
    div.dataset.step = step.step;
    div.dataset.type = 'step-header';
    div.style.setProperty('--card-color', step.color);
    div.innerHTML = `
        <div class="card step-header-card" style="--card-color: ${step.color};">
            <div class="card-body">
                <h5 class="mb-0"><i class="bi bi-layers me-2"></i>Step ${step.step}: ${step.name}</h5>
            </div>
        </div>`;
    return div;
}

function createPassHeader(step, pass) {
    const div = document.createElement('div');
    div.className = 'pipeline-card';
    div.dataset.step = step.step;
    div.dataset.section = pass.section_type;
    div.dataset.type = 'pass-header';
    div.style.setProperty('--card-color', step.color);
    const hasData = pass.extractions.some(e => e.has_data);
    div.innerHTML = `
        <div class="card" style="border-left: 4px solid ${step.color};">
            <div class="card-body py-2">
                <h6 class="mb-0">
                    <i class="bi bi-arrow-right-circle me-2" style="color: ${step.color};"></i>
                    ${pass.name}
                    ${hasData ? '<span class="badge bg-success ms-2">Completed</span>' : '<span class="badge bg-secondary ms-2">Not processed</span>'}
                </h6>
            </div>
        </div>`;
    return div;
}

// Badge for a stored prompt or response whose length equals a round storage
// limit (helpers.truncation_limit): the text was sliced at that length when
// stored and the remainder was never kept.
function truncationBadge(limit) {
    if (!limit) return '';
    return `<span class="badge bg-warning text-dark ms-2" title="The stored text is exactly ${limit} characters long, the length of a storage slice: the original was longer and the remainder was not kept.">stored text truncated at ${limit} characters</span>`;
}

// Metadata-bar note when no provenance activity was recorded for the prompt's
// session: the card then has only the prompt's own date and model.
function durationNote(prov) {
    return prov ? '' : `<span class="mx-2">|</span><i class="bi bi-stopwatch me-1"></i>duration not recorded`;
}

function renderEntityFields(fg) {
    // Per-entity triple-vs-literal breakdown (field_classification.group_properties).
    if (!fg) return '';
    const rel = fg.relations || [], lit = fg.literals || [], der = fg.derived || [];
    const typed = fg.typed_as || {}, types = typed.types || [], parent = typed.parent;
    if (!rel.length && !lit.length && !der.length && !types.length && !parent) return '';
    const trunc = s => escapeHtml((s || '').substring(0, 80)) + ((s || '').length > 80 ? '…' : '');
    let html = `<details class="entity-fields"><summary class="small text-muted">`
        + `${rel.length} relation${rel.length != 1 ? 's' : ''} · ${lit.length} literal${lit.length != 1 ? 's' : ''}</summary>`;
    if (types.length || parent) html += `<div class="small mt-1"><span class="badge bg-info text-dark">Typed as</span> `
        + `${types.map(t => `<code>${escapeHtml(t)}</code>`).join(', ')}`
        + `${parent ? `${types.length ? ' · ' : ''}subclass of <code>${escapeHtml(parent)}</code>` : ''}</div>`;
    if (rel.length) html += `<div class="small mt-1"><span class="badge bg-primary">Relations (structural triples)</span>`
        + `<ul class="mb-1 ps-3">${rel.map(f => `<li><code>${escapeHtml(f.p)}</code>: ${trunc(f.v)}</li>`).join('')}</ul></div>`;
    if (lit.length) html += `<div class="small"><span class="badge bg-success">Literal extractions (kept for synthesis)</span>`
        + `<ul class="mb-1 ps-3">${lit.map(f => `<li><code>${escapeHtml(f.p)}</code> <span class="badge bg-light text-dark border">${escapeHtml(f.kind)}</span>: ${trunc(f.v)}</li>`).join('')}</ul></div>`;
    if (der.length) html += `<div class="small text-muted"><span class="badge bg-secondary">Derived</span> `
        + `${der.map(f => `<code>${escapeHtml(f.p)}</code>`).join(', ')}</div>`;
    html += `</details>`;
    return html;
}

function createExtractionCard(step, pass, extraction) {
    const div = document.createElement('div');
    div.className = `pipeline-card${extraction.has_data ? '' : ' empty'}`;
    div.dataset.step = step.step;
    div.dataset.section = pass.section_type;
    div.dataset.concept = extraction.concept;
    div.dataset.type = 'extraction';
    div.style.setProperty('--card-color', extraction.color);

    if (!extraction.has_data) {
        div.innerHTML = `
            <div class="card extraction-card empty" style="--card-color: ${extraction.color};">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span><span class="badge" style="background: ${extraction.color};">${extraction.concept_label}</span></span>
                    <span class="badge bg-secondary">Awaiting extraction</span>
                </div>
            </div>`;
        return div;
    }

    const prompt = extraction.prompt;
    const prov = extraction.provenance;
    const truncation = prompt.truncation || {};
    const entityHtml = extraction.entities.length > 0
        ? `<div class="entity-list">${extraction.entities.map(e => `
            <div class="entity-item" style="--entity-color: ${e.color};">
                <div class="entity-label">${escapeHtml(e.label)}</div>
                <div class="entity-definition">${escapeHtml((e.definition || '').substring(0, 150))}${e.definition && e.definition.length > 150 ? '...' : ''}</div>
                ${renderEntityFields(e.fields)}
            </div>`).join('')}</div>`
        : '<p class="text-muted mb-0">No entities extracted</p>';

    const provId = `prov-${step.step}-${pass.section_type}-${extraction.concept}`;
    const provBar = prov ? `
        <div class="provenance-bar" onclick="toggleProvDetail('${provId}')">
            <div class="d-flex align-items-center gap-3 flex-wrap">
                <span><i class="bi bi-person-gear me-1"></i>${escapeHtml(prov.agent_name || 'Unknown')}</span>
                ${prov.duration_ms ? `<span><i class="bi bi-stopwatch me-1"></i>${(prov.duration_ms / 1000).toFixed(1)}s</span>` : ''}
                <span class="origin-badge origin-${prov.origin}">${ORIGIN_LABELS[prov.origin] || prov.origin}</span>
                <span class="badge bg-${prov.status === 'completed' ? 'success' : prov.status === 'failed' ? 'danger' : 'secondary'}" style="font-size: 0.65rem;">${prov.status || 'unknown'}</span>
                ${extraction.history_count > 1 ? `<span class="text-muted"><i class="bi bi-clock-history me-1"></i>${extraction.history_count} runs</span>` : ''}
                <i class="bi bi-chevron-down ms-auto" style="font-size: 0.7rem;"></i>
            </div>
        </div>
        <div class="provenance-detail" id="${provId}" style="display: none;">
            <div class="row">
                <div class="col-sm-6">
                    <div><strong>Agent Type:</strong> ${escapeHtml(prov.agent_type || 'N/A')}</div>
                    <div><strong>Agent Version:</strong> ${escapeHtml(prov.agent_version || 'N/A')}</div>
                    <div><strong>Activity:</strong> ${escapeHtml(prov.activity_name || 'N/A')}</div>
                </div>
                <div class="col-sm-6">
                    <div><strong>Started:</strong> ${prov.started_at ? new Date(prov.started_at).toLocaleString() : 'N/A'}</div>
                    <div><strong>Ended:</strong> ${prov.ended_at ? new Date(prov.ended_at).toLocaleString() : 'N/A'}</div>
                    <div><strong>Session:</strong> <code style="font-size: 0.7rem;">${escapeHtml((prompt.session_id || '').substring(0, 8))}</code></div>
                </div>
            </div>
        </div>` : '';

    div.innerHTML = `
        <div class="card extraction-card" style="--card-color: ${extraction.color};">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span>
                    <span class="badge" style="background: ${extraction.color};">${extraction.concept_label}</span>
                    <span class="badge bg-success ms-1">${extraction.entity_count} entities</span>
                </span>
                <span class="badge bg-success">Completed</span>
            </div>
            ${provBar}
            <div class="card-body">
                <div class="prompt-section">
                    <div class="section-header" onclick="toggleSection(this)">
                        <span><i class="bi bi-cpu me-2"></i>LLM Prompt${truncationBadge(truncation.prompt)}</span>
                        <i class="bi bi-chevron-down"></i>
                    </div>
                    <div class="section-content" style="display: none;">
                        <pre class="prompt-text">${escapeHtml(prompt.text || 'No prompt text available')}</pre>
                    </div>
                </div>
                <div class="response-section">
                    <div class="section-header" onclick="toggleSection(this)">
                        <span><i class="bi bi-chat-left-text me-2"></i>LLM Response${truncationBadge(truncation.response)}</span>
                        <i class="bi bi-chevron-down"></i>
                    </div>
                    <div class="section-content" style="display: none;">
                        <pre class="response-text">${escapeHtml(prompt.response || 'No response available')}</pre>
                    </div>
                </div>
                <div class="entities-section">
                    <h6><i class="bi bi-collection me-2"></i>Extracted Entities (${extraction.entity_count})</h6>
                    ${entityHtml}
                </div>
            </div>
            <div class="metadata-bar">
                <i class="bi bi-clock me-1"></i>${prompt.created_at ? new Date(prompt.created_at).toLocaleString() : 'N/A'}
                <span class="mx-2">|</span>
                <i class="bi bi-robot me-1"></i>${prompt.model || 'Unknown model'}
                ${durationNote(prov)}
            </div>
        </div>`;
    return div;
}

function createPhaseCard(step, phase) {
    const div = document.createElement('div');
    div.className = `pipeline-card${phase.has_data ? '' : ' empty'}`;
    div.dataset.step = step.step;
    div.dataset.concept = phase.concept_type;
    div.dataset.type = 'phase';
    div.style.setProperty('--card-color', step.color);

    if (!phase.has_data) {
        div.innerHTML = `
            <div class="card extraction-card empty" style="--card-color: ${step.color};">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span>
                        <span class="badge" style="background: ${step.color};">Phase ${phase.phase}</span>
                        <span class="ms-2">${phase.name}</span>
                    </span>
                    <span class="badge bg-secondary">Awaiting processing</span>
                </div>
            </div>`;
        return div;
    }

    const prompt = phase.prompt;
    const prov = phase.provenance;
    const truncation = (prompt && prompt.truncation) || {};
    const entityHtml = phase.entities.length > 0
        ? `<div class="entity-list">${phase.entities.map(e => `
            <div class="entity-item" style="--entity-color: ${step.color};">
                <div class="entity-label">${escapeHtml(e.label)}</div>
                <div class="entity-definition">${escapeHtml((e.definition || '').substring(0, 150))}${e.definition && e.definition.length > 150 ? '...' : ''}</div>
            </div>`).join('')}</div>`
        : '';

    const provId = `prov-4-${phase.concept_type}`;
    const provBar = prov ? `
        <div class="provenance-bar" onclick="toggleProvDetail('${provId}')">
            <div class="d-flex align-items-center gap-3 flex-wrap">
                <span><i class="bi bi-person-gear me-1"></i>${escapeHtml(prov.agent_name || 'Unknown')}</span>
                ${prov.duration_ms ? `<span><i class="bi bi-stopwatch me-1"></i>${(prov.duration_ms / 1000).toFixed(1)}s</span>` : ''}
                <span class="origin-badge origin-${prov.origin}">${ORIGIN_LABELS[prov.origin] || prov.origin}</span>
                <span class="badge bg-${prov.status === 'completed' ? 'success' : prov.status === 'failed' ? 'danger' : 'secondary'}" style="font-size: 0.65rem;">${prov.status || 'unknown'}</span>
                <i class="bi bi-chevron-down ms-auto" style="font-size: 0.7rem;"></i>
            </div>
        </div>
        <div class="provenance-detail" id="${provId}" style="display: none;">
            <div class="row">
                <div class="col-sm-6">
                    <div><strong>Agent Type:</strong> ${escapeHtml(prov.agent_type || 'N/A')}</div>
                    <div><strong>Activity:</strong> ${escapeHtml(prov.activity_name || 'N/A')}</div>
                </div>
                <div class="col-sm-6">
                    <div><strong>Started:</strong> ${prov.started_at ? new Date(prov.started_at).toLocaleString() : 'N/A'}</div>
                    <div><strong>Ended:</strong> ${prov.ended_at ? new Date(prov.ended_at).toLocaleString() : 'N/A'}</div>
                </div>
            </div>
        </div>` : '';

    div.innerHTML = `
        <div class="card extraction-card" style="--card-color: ${step.color};">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span>
                    <span class="badge" style="background: ${step.color};">Phase ${phase.phase}</span>
                    <span class="ms-2">${phase.name}</span>
                    ${phase.entity_count > 0 ? `<span class="badge bg-success ms-1">${phase.entity_count} items</span>` : ''}
                </span>
                <span class="badge bg-success">Completed</span>
            </div>
            ${provBar}
            <div class="card-body">
                ${prompt ? `
                <div class="prompt-section">
                    <div class="section-header" onclick="toggleSection(this)">
                        <span><i class="bi bi-cpu me-2"></i>LLM Prompt${truncationBadge(truncation.prompt)}</span>
                        <i class="bi bi-chevron-down"></i>
                    </div>
                    <div class="section-content" style="display: none;">
                        <pre class="prompt-text">${escapeHtml(prompt.text || 'No prompt text available')}</pre>
                    </div>
                </div>
                <div class="response-section">
                    <div class="section-header" onclick="toggleSection(this)">
                        <span><i class="bi bi-chat-left-text me-2"></i>LLM Response${truncationBadge(truncation.response)}</span>
                        <i class="bi bi-chevron-down"></i>
                    </div>
                    <div class="section-content" style="display: none;">
                        <pre class="response-text">${escapeHtml(prompt.response || 'No response available')}</pre>
                    </div>
                </div>` : ''}
                ${phase.algorithmic_trace ? renderAlgorithmicTrace(phase.algorithmic_trace) : ''}
                ${phase.synthesis_trace ? renderSynthesisTrace(phase.synthesis_trace) : ''}
                ${entityHtml ? `
                <div class="entities-section">
                    <h6><i class="bi bi-collection me-2"></i>Generated Items (${phase.entity_count})</h6>
                    ${entityHtml}
                </div>` : ''}
            </div>
            <div class="metadata-bar">
                ${prompt ? `
                <i class="bi bi-clock me-1"></i>${prompt.created_at ? new Date(prompt.created_at).toLocaleString() : 'N/A'}
                <span class="mx-2">|</span>
                <i class="bi bi-robot me-1"></i>${prompt.model || 'Unknown model'}
                ${durationNote(prov)}
                ` : `<i class="bi bi-gear me-1"></i>Algorithmic`}
            </div>
        </div>`;
    return div;
}

function renderSynthesisTrace(trace) {
    let html = '<div class="synthesis-trace-section mt-3 mb-2">';
    html += '<h6><i class="bi bi-gear me-2"></i>Algorithmic Synthesis Pipeline</h6>';
    html += '<div class="row g-2 small">';

    // Timing
    if (trace.synthesis_started && trace.synthesis_completed) {
        const start = new Date(trace.synthesis_started);
        const end = new Date(trace.synthesis_completed);
        const durationSec = ((end - start) / 1000).toFixed(1);
        html += `<div class="col-12 mb-1">
            <span class="text-muted"><i class="bi bi-stopwatch me-1"></i>Duration: ${durationSec}s
            (${start.toLocaleTimeString()} - ${end.toLocaleTimeString()})</span>
        </div>`;
    }

    // Algorithmic Composition (E1-E3)
    if (trace.algorithmic_composition) {
        const ac = trace.algorithmic_composition;
        html += `<div class="col-md-4">
            <div class="card h-100">
                <div class="card-body py-2 px-3">
                    <div class="fw-bold mb-1"><i class="bi bi-gear me-1"></i>E1-E3 Composition</div>
                    <div>Method: ${escapeHtml(ac.method || 'E1-E3')}</div>
                    <div>Candidates: <span class="badge bg-primary">${ac.candidates_count || 0}</span></div>
                </div>
            </div>
        </div>`;
    }

    // Q&C Alignment
    if (trace.qc_alignment) {
        const qc = trace.qc_alignment;
        let scoresHtml = '';
        if (qc.top_scores && qc.top_scores.length > 0) {
            scoresHtml = qc.top_scores.map(s =>
                `<span class="badge bg-${s.score > 0.5 ? 'success' : 'secondary'} me-1">${escapeHtml(s.candidate_id)}: ${(s.score * 100).toFixed(0)}%</span>`
            ).join('');
        }
        html += `<div class="col-md-4">
            <div class="card h-100">
                <div class="card-body py-2 px-3">
                    <div class="fw-bold mb-1"><i class="bi bi-check2-square me-1"></i>Q&C Alignment</div>
                    <div>High alignment (&gt;50%): <span class="badge bg-info">${qc.high_alignment_count || 0}</span></div>
                    ${scoresHtml ? `<div class="mt-1">${scoresHtml}</div>` : ''}
                </div>
            </div>
        </div>`;
    }

    // LLM Refinement
    if (trace.llm_refinement) {
        const llm = trace.llm_refinement;
        html += `<div class="col-md-4">
            <div class="card h-100">
                <div class="card-body py-2 px-3">
                    <div class="fw-bold mb-1"><i class="bi bi-robot me-1"></i>LLM Refinement</div>
                    <div>Model: ${escapeHtml(llm.model || 'Unknown')}</div>
                    <div>Prompt: ${(llm.prompt_length || 0).toLocaleString()} chars</div>
                    <div>Response: ${(llm.response_length || 0).toLocaleString()} chars</div>
                </div>
            </div>
        </div>`;
    }

    html += '</div>';  // close .row

    // Entity Resolution (MCP) -- collapsible since it can be long
    if (trace.entity_resolution) {
        const er = trace.entity_resolution;
        const resolvedList = (er.entities_resolved || []);
        html += `<div class="mt-2">
            <div class="fw-bold small mb-1"><i class="bi bi-link-45deg me-1"></i>Entity Resolution (OntServe MCP)</div>
            <div class="d-flex gap-2 mb-1">
                <span class="badge bg-success">${er.mcp_resolved_count || 0} MCP</span>
                <span class="badge bg-warning text-dark">${er.local_resolved_count || 0} local</span>
                <span class="badge bg-secondary">${er.entities_not_found || 0} not found</span>
            </div>`;
        if (resolvedList.length > 0) {
            const traceId = 'synth-trace-entities-' + Date.now();
            html += `<details class="small">
                <summary class="text-muted" style="cursor: pointer;">${resolvedList.length} entities resolved</summary>
                <div class="mt-1" style="max-height: 200px; overflow-y: auto;">`;
            resolvedList.forEach(e => {
                const icon = e.found ? 'check-circle text-success' : 'x-circle text-danger';
                const srcClass = e.source === 'mcp' ? 'bg-success' : e.source === 'local' ? 'bg-warning text-dark' : 'bg-secondary';
                html += `<div class="d-flex align-items-center gap-1 mb-1">
                    <i class="bi bi-${icon}" style="font-size: 0.75rem;"></i>
                    <span class="badge ${srcClass}" style="font-size: 0.6rem;">${escapeHtml(e.source || '?')}</span>
                    <span>${escapeHtml(e.label || '')}</span>
                    <span class="text-muted">(${escapeHtml(e.entity_type || '')})</span>
                </div>`;
            });
            html += '</div></details>';
        }
        html += '</div>';
    }

    // Pipeline funnel (from results_summary)
    if (trace.pipeline_summary) {
        const ps = trace.pipeline_summary;
        html += `<div class="mt-2">
            <div class="fw-bold small mb-1"><i class="bi bi-funnel me-1"></i>Pipeline Funnel</div>
            <div class="d-flex align-items-center gap-1 small flex-wrap">
                <span class="badge bg-secondary">${ps.e1_obligations || 0} obligations</span>
                <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
                <span class="badge bg-secondary">${ps.e1_decision_relevant || 0} decision-relevant</span>
                <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
                <span class="badge bg-secondary">${ps.e2_action_sets || 0} action sets</span>
                <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
                <span class="badge bg-info">${ps.e3_candidates || 0} E3 candidates</span>
                <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
                <span class="badge bg-success">${ps.high_alignment_count || 0} high-align</span>
                <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
                <span class="badge bg-primary">${ps.canonical_count || 0} canonical</span>
            </div>
        </div>`;
    }

    // Output
    if (trace.output && !trace.pipeline_summary) {
        html += `<div class="mt-2 small text-muted">
            <i class="bi bi-box-arrow-right me-1"></i>Output: <span class="badge bg-primary">${trace.output.canonical_points_produced || 0}</span> decision points
        </div>`;
    }

    // Argument validation summary
    if (trace.argument_validation) {
        const av = trace.argument_validation;
        const total = av.validations_run || 0;
        html += `<div class="mt-2">
            <div class="fw-bold small mb-1"><i class="bi bi-shield-check me-1"></i>Argument Validation (3-Tier)</div>
            <div class="d-flex gap-3 small">
                <div>
                    <span class="text-muted">Generated:</span>
                    <span class="badge bg-primary">${av.arguments_generated || 0}</span>
                </div>
                <div>
                    <span class="text-muted">Valid:</span>
                    <span class="badge bg-${av.valid_count === total ? 'success' : 'warning text-dark'}">${av.valid_count || 0}/${total}</span>
                </div>
                <div>
                    <span class="text-muted">Avg score:</span>
                    <span class="badge bg-secondary">${((av.avg_score || 0) * 100).toFixed(0)}%</span>
                </div>
            </div>
            <div class="d-flex gap-2 small mt-1">
                <span class="text-muted">Entity refs:</span>
                <span class="badge bg-${av.entity_valid === total ? 'success' : 'secondary'}">${av.entity_valid || 0}/${total}</span>
                <span class="text-muted">Founding value:</span>
                <span class="badge bg-${av.founding_compliant === total ? 'success' : 'secondary'}">${av.founding_compliant || 0}/${total}</span>
                <span class="text-muted">Virtue:</span>
                <span class="badge bg-${av.virtue_valid === total ? 'success' : 'secondary'}">${av.virtue_valid || 0}/${total}</span>
            </div>
        </div>`;
    }

    html += '</div>';
    return html;
}

function renderAlgorithmicTrace(trace) {
    if (!trace || !trace.type) return '';

    let html = '<div class="synthesis-trace-section mt-3 mb-2">';

    switch (trace.type) {

    case 'precedent_resolution':
        html += '<h6><i class="bi bi-journal-bookmark me-2"></i>Case Resolution</h6>';
        html += '<div class="small">';
        html += `<div class="d-flex align-items-center gap-2 flex-wrap mb-2">
            <span class="badge" style="background: #fef3c7; color: #92400e;"><i class="bi bi-cpu me-1"></i>LLM citation extraction</span>
            <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
            <span class="badge" style="background: #e5e7eb; color: #374151;"><i class="bi bi-regex me-1"></i>Case number parsing</span>
            <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
            <span class="badge" style="background: #dbeafe; color: #1e40af;"><i class="bi bi-database me-1"></i>Internal DB resolution</span>
        </div>`;
        html += `<div class="mb-1">
            <span class="badge bg-primary">${trace.total}</span> precedents extracted,
            <span class="badge bg-success">${trace.resolved}</span> resolved to internal documents`;
        if (trace.unresolved > 0) {
            html += `, <span class="badge bg-warning text-dark">${trace.unresolved}</span> unresolved`;
        }
        html += '</div>';
        if (trace.cases && trace.cases.length > 0) {
            trace.cases.forEach(c => {
                const icon = c.resolved ? 'check-circle-fill text-success' : 'question-circle text-warning';
                const typeLabel = c.citation_type || 'cited';
                html += `<div class="d-flex align-items-center gap-2 mb-1">
                    <i class="bi bi-${icon}" style="font-size: 0.8rem;"></i>
                    <strong>${escapeHtml(c.label)}</strong>
                    <span class="badge bg-secondary" style="font-size: 0.65rem;">${escapeHtml(typeLabel)}</span>
                    ${c.resolved && c.internal_id ? `<span class="text-muted">doc #${c.internal_id}</span>` : ''}
                </div>`;
            });
        }
        html += '</div>';
        break;

    case 'code_provision_extraction':
        html += '<h6><i class="bi bi-book me-2"></i>Code Provision Detection</h6>';
        html += '<div class="small">';
        html += `<div class="mb-2">
            <span class="badge bg-primary">${trace.total}</span> NSPE Code provisions detected,
            <span class="badge bg-info">${trace.total_links}</span> entity linkages
        </div>`;
        html += `<div class="d-flex align-items-center gap-2 flex-wrap mb-2">
            <span class="badge" style="background: #e5e7eb; color: #374151;"><i class="bi bi-code-slash me-1"></i>HTML reference parsing</span>
            <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
            <span class="badge" style="background: #dbeafe; color: #1e40af;"><i class="bi bi-database me-1"></i>Provision code matching</span>
            <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
            <span class="badge" style="background: #fef3c7; color: #92400e;"><i class="bi bi-cpu me-1"></i>LLM entity linking</span>
        </div>`;
        if (trace.provisions && trace.provisions.length > 0) {
            trace.provisions.forEach(p => {
                html += `<div class="d-flex align-items-start gap-2 mb-1">
                    <span class="badge bg-secondary" style="font-size: 0.75em; min-width: 50px;">${escapeHtml(p.code)}</span>
                    <span>${escapeHtml(p.text)}</span>
                    <span class="badge bg-info" style="font-size: 0.65em;" title="Entity linkages">${p.link_count} links</span>
                </div>`;
            });
        }
        html += '</div>';
        break;

    case 'question_classification':
        html += '<h6><i class="bi bi-tag me-2"></i>Question Classification</h6>';
        html += `<div class="d-flex align-items-center gap-2 flex-wrap mb-2 small">
            <span class="badge" style="background: #fef3c7; color: #92400e;"><i class="bi bi-cpu me-1"></i>LLM question extraction</span>
            <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
            <span class="badge" style="background: #e5e7eb; color: #374151;"><i class="bi bi-funnel me-1"></i>Source classification</span>
        </div>`;
        html += `<div class="d-flex gap-3 small">
            <div><span class="text-muted">Total:</span> <span class="badge bg-primary">${trace.total}</span></div>
            <div><span class="text-muted">Board-explicit:</span> <span class="badge bg-success">${trace.board_explicit}</span></div>
            <div><span class="text-muted">Analytical:</span> <span class="badge bg-info">${trace.analytical}</span></div>
        </div>`;
        html += `<div class="text-muted small mt-1">Board-explicit questions are stated directly in the case text; analytical questions are inferred from the ethical tensions.</div>`;
        break;

    case 'conclusion_classification':
        html += '<h6><i class="bi bi-tag me-2"></i>Conclusion Classification</h6>';
        html += `<div class="d-flex align-items-center gap-2 flex-wrap mb-2 small">
            <span class="badge" style="background: #fef3c7; color: #92400e;"><i class="bi bi-cpu me-1"></i>LLM conclusion extraction</span>
            <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
            <span class="badge" style="background: #e5e7eb; color: #374151;"><i class="bi bi-funnel me-1"></i>Source classification</span>
            <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
            <span class="badge" style="background: #dbeafe; color: #1e40af;"><i class="bi bi-link-45deg me-1"></i>Q-C linking</span>
        </div>`;
        html += `<div class="d-flex gap-3 small">
            <div><span class="text-muted">Total:</span> <span class="badge bg-primary">${trace.total}</span></div>
            <div><span class="text-muted">Board-explicit:</span> <span class="badge bg-success">${trace.board_explicit}</span></div>
            <div><span class="text-muted">Analytical:</span> <span class="badge bg-info">${trace.analytical}</span></div>
            ${trace.qc_links ? `<div><span class="text-muted">Q-C links:</span> <span class="badge bg-warning text-dark">${trace.qc_links}</span></div>` : ''}
        </div>`;
        if (trace.qc_links) {
            html += `<div class="text-muted small mt-1">Q-C links connect each conclusion to the question(s) it addresses.</div>`;
        }
        break;

    case 'transformation_classification':
        html += '<h6><i class="bi bi-shuffle me-2"></i>Transformation Classification</h6>';
        html += `<div class="d-flex align-items-center gap-2 flex-wrap mb-2 small">
            <span class="badge" style="background: #fef3c7; color: #92400e;"><i class="bi bi-cpu me-1"></i>LLM classification</span>
        </div>`;
        if (trace.transformation_type) {
            const typeLabels = {
                'transfer': 'Transfer -- resolution transfers obligation to another party',
                'stalemate': 'Stalemate -- competing obligations remain in tension',
                'oscillation': 'Oscillation -- duties shift between parties over time',
                'phase_lag': 'Phase Lag -- delayed consequences reveal hidden obligations'
            };
            html += `<div class="small">
                <span class="badge bg-purple" style="background: #6f42c1; font-size: 0.85em;">${escapeHtml(trace.transformation_type)}</span>`;
            if (trace.confidence) {
                html += ` <span class="badge bg-secondary" style="font-size: 0.75em;">${(trace.confidence * 100).toFixed(0)}% confidence</span>`;
            }
            html += `<div class="text-muted mt-1">${typeLabels[trace.transformation_type] || ''}</div>`;
            html += '</div>';
        }
        break;

    case 'rich_analysis':
        html += '<h6><i class="bi bi-diagram-3 me-2"></i>Cross-Entity Analysis</h6>';
        html += `<div class="d-flex align-items-center gap-2 flex-wrap mb-2 small">
            <span class="badge" style="background: #fef3c7; color: #92400e;"><i class="bi bi-cpu me-1"></i>LLM batched extraction</span>
            <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
            <span class="badge" style="background: #e5e7eb; color: #374151;"><i class="bi bi-columns-gap me-1"></i>3 parallel sub-types</span>
        </div>`;
        html += '<div class="row g-2 small">';
        html += `<div class="col-md-4">
            <div class="card h-100">
                <div class="card-body py-2 px-3">
                    <div class="fw-bold mb-1"><i class="bi bi-arrow-left-right me-1"></i>Causal-Normative Links</div>
                    <div><span class="badge bg-primary">${trace.causal_links}</span> action-obligation mappings</div>
                    <div class="text-muted mt-1">Maps each Action to Obligations it fulfills or violates</div>
                </div>
            </div>
        </div>`;
        html += `<div class="col-md-4">
            <div class="card h-100">
                <div class="card-body py-2 px-3">
                    <div class="fw-bold mb-1"><i class="bi bi-question-diamond me-1"></i>Question Emergence</div>
                    <div><span class="badge bg-primary">${trace.question_emergence}</span> Toulmin decompositions</div>
                    <div class="text-muted mt-1">DATA, WARRANTS, REBUTTALS for each ethical question</div>
                </div>
            </div>
        </div>`;
        html += `<div class="col-md-4">
            <div class="card h-100">
                <div class="card-body py-2 px-3">
                    <div class="fw-bold mb-1"><i class="bi bi-signpost me-1"></i>Resolution Patterns</div>
                    <div><span class="badge bg-primary">${trace.resolution_patterns}</span> resolution analyses</div>
                    <div class="text-muted mt-1">How the board weighed and resolved each conclusion</div>
                </div>
            </div>
        </div>`;
        html += '</div>';
        break;

    case 'narrative_structure':
        html += '<h6><i class="bi bi-book me-2"></i>Narrative Structure</h6>';
        html += `<div class="d-flex align-items-center gap-2 flex-wrap mb-2 small">
            <span class="badge" style="background: #fef3c7; color: #92400e;"><i class="bi bi-cpu me-1"></i>LLM character enhancement</span>
            <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
            <span class="badge" style="background: #fef3c7; color: #92400e;"><i class="bi bi-cpu me-1"></i>LLM event synthesis</span>
            <i class="bi bi-arrow-right text-muted" style="font-size: 0.7rem;"></i>
            <span class="badge" style="background: #fef3c7; color: #92400e;"><i class="bi bi-cpu me-1"></i>LLM narrative construction</span>
        </div>`;
        html += '<div class="row g-2 small">';
        const items = [
            {label: 'Characters', count: trace.characters, icon: 'bi-people'},
            {label: 'Events', count: trace.events, icon: 'bi-calendar-event'},
            {label: 'Conflicts', count: trace.conflicts, icon: 'bi-lightning'},
            {label: 'Decision Moments', count: trace.decision_moments, icon: 'bi-signpost-split'},
        ];
        items.forEach(item => {
            html += `<div class="col-md-3 col-6">
                <div class="card h-100">
                    <div class="card-body py-2 px-3 text-center">
                        <div class="fw-bold" style="font-size: 1.25rem;">${item.count}</div>
                        <div class="text-muted"><i class="bi ${item.icon} me-1"></i>${item.label}</div>
                    </div>
                </div>
            </div>`;
        });
        html += '</div>';
        const features = [];
        if (trace.has_setting) features.push('Setting');
        if (trace.has_resolution) features.push('Resolution');
        if (trace.timeline_events > 0) features.push(`${trace.timeline_events} timeline events`);
        if (features.length > 0) {
            html += `<div class="mt-1 small text-muted">${features.join(' | ')}</div>`;
        }
        break;

    default:
        return '';
    }

    html += '</div>';
    return html;
}

// ---- Filtering ----

function applyFilters() {
    const stepFilter = document.getElementById('filter-step').value;
    const sectionFilter = document.getElementById('filter-section').value;
    const conceptFilter = document.getElementById('filter-concept').value;

    const cards = document.querySelectorAll('.pipeline-card');
    let visible = 0;
    let total = 0;

    cards.forEach(card => {
        const cardStep = card.dataset.step;
        const cardSection = card.dataset.section || '';
        const cardConcept = card.dataset.concept || '';
        const cardType = card.dataset.type;

        // Step headers: show if step matches or no step filter
        if (cardType === 'step-header') {
            card.style.display = (!stepFilter || cardStep === stepFilter) ? '' : 'none';
            return;
        }

        // Pass headers: show if step and section match
        if (cardType === 'pass-header') {
            const stepMatch = !stepFilter || cardStep === stepFilter;
            const sectionMatch = !sectionFilter || cardSection === sectionFilter;
            card.style.display = (stepMatch && sectionMatch) ? '' : 'none';
            return;
        }

        // QC, refinements, review-log cards: match by step value
        if (cardType === 'qc-verification' || cardType === 'refinements' || cardType === 'review-log') {
            card.style.display = (!stepFilter || cardStep === stepFilter) ? '' : 'none';
            return;
        }

        // Extraction and phase cards
        total++;
        const stepMatch = !stepFilter || cardStep === stepFilter;
        const sectionMatch = !sectionFilter || cardSection === sectionFilter || !cardSection;
        const conceptMatch = !conceptFilter || cardConcept === conceptFilter;

        if (stepMatch && sectionMatch && conceptMatch) {
            card.style.display = '';
            visible++;
        } else {
            card.style.display = 'none';
        }
    });

    const countEl = document.getElementById('filter-count');
    if (stepFilter || sectionFilter || conceptFilter) {
        countEl.textContent = `Showing ${visible} of ${total} extractions`;
    } else {
        countEl.textContent = '';
    }
}

function clearFilters() {
    document.getElementById('filter-step').value = '';
    document.getElementById('filter-section').value = '';
    document.getElementById('filter-concept').value = '';
    applyFilters();
}

// ---- Activity Log ----

function loadActivityLog() {
    const container = document.getElementById('activity-timeline');
    if (container.dataset.loaded === String(CASE_ID)) return;

    container.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary"></div></div>';

    fetch(`/api/provenance/case/${CASE_ID}`)
        .then(response => response.json())
        .then(data => {
            displayActivityLog(data.timeline);
            container.dataset.loaded = String(CASE_ID);
        })
        .catch(error => {
            container.innerHTML = `<div class="alert alert-danger">Failed to load activity log: ${error.message}</div>`;
        });
}

function displayActivityLog(timeline) {
    const container = document.getElementById('activity-timeline');

    if (!timeline || timeline.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4 text-muted">
                <i class="bi bi-inbox" style="font-size: 3rem;"></i>
                <p class="mt-2">No activities recorded yet.</p>
            </div>`;
        return;
    }

    container.innerHTML = '';
    timeline.forEach(activity => {
        const style = activityStyles[activity.activity_type] || activityStyles['extraction'];
        container.appendChild(createActivityCard(activity, style));
    });
}

function createActivityCard(activity, style) {
    const div = document.createElement('div');
    div.className = `activity-card activity-${activity.activity_type}`;

    const statusBadge = activity.status === 'completed'
        ? '<span class="badge status-completed">Completed</span>'
        : activity.status === 'failed'
        ? '<span class="badge status-failed">Failed</span>'
        : '<span class="badge status-running">Running</span>';

    const durationText = activity.duration_ms ? `${(activity.duration_ms / 1000).toFixed(2)}s` : 'N/A';
    const startTime = activity.started_at ? new Date(activity.started_at).toLocaleString() : 'N/A';
    const agentInfo = activity.agent ? `<span class="me-2"><i class="bi bi-robot me-1"></i>${activity.agent.name}</span>` : '';

    div.innerHTML = `
        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <div>
                    <i class="bi ${style.icon} me-1" style="color: ${style.color};"></i>
                    <strong>${formatActivityName(activity.name)}</strong>
                    <span class="badge ms-1" style="background: ${style.color}; font-size: 0.7rem;">${style.label}</span>
                </div>
                ${statusBadge}
            </div>
            <div class="card-body">
                <div class="d-flex flex-wrap gap-2 text-muted small">
                    ${agentInfo}
                    <span><i class="bi bi-clock me-1"></i>${startTime}</span>
                    <span><i class="bi bi-stopwatch me-1"></i>${durationText}</span>
                </div>
            </div>
        </div>`;
    return div;
}

function formatActivityName(name) {
    const nameMap = {
        'entities_pass_step1': 'Step 1: Entity Extraction',
        'entities_pass_step1_streaming': 'Step 1: Entity Extraction (Streaming)',
        'dual_roles_extraction': 'Roles Extraction',
        'dual_states_extraction': 'States Extraction',
        'dual_resources_extraction': 'Resources Extraction',
        'normative_pass_step2': 'Step 2: Normative Pass',
        'normative_pass_step2_streaming': 'Step 2: Normative Pass (Streaming)',
        'dual_principles_extraction': 'Principles Extraction',
        'dual_obligations_extraction': 'Obligations Extraction',
        'dual_constraints_extraction': 'Constraints Extraction',
        'dual_capabilities_extraction': 'Capabilities Extraction',
        'temporal_pass_step3': 'Step 3: Temporal Pass',
        'temporal_action_extraction': 'Actions Extraction',
        'temporal_event_extraction': 'Events Extraction',
        'temporal_section_analysis': 'Temporal Section Analysis',
        'temporal_temporal_markers': 'Temporal Markers',
        'temporal_causal_analysis': 'Causal Analysis',
        'step4_provisions': 'Phase 2A: Code Provisions',
        'step4_questions': 'Phase 2B: Ethical Questions',
        'step4_conclusions': 'Phase 2B: Ethical Conclusions',
        'step4_transformation': 'Phase 2C: Transformation',
        'step4_rich_analysis': 'Phase 2D: Rich Analysis',
        'step4_phase3_decision': 'Phase 3: Decision Points',
        'step4_phase4_narrative': 'Phase 4: Narrative'
    };
    return nameMap[name] || name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// ---- Utilities ----

function toggleSection(header) {
    const content = header.nextElementSibling;
    const icon = header.querySelector('.bi-chevron-down, .bi-chevron-up');
    if (content.style.display === 'none') {
        content.style.display = 'block';
        if (icon) icon.classList.replace('bi-chevron-down', 'bi-chevron-up');
    } else {
        content.style.display = 'none';
        if (icon) icon.classList.replace('bi-chevron-up', 'bi-chevron-down');
    }
}

function toggleProvDetail(id) {
    const el = document.getElementById(id);
    if (el) {
        el.style.display = el.style.display === 'none' ? '' : 'none';
        const bar = el.previousElementSibling;
        const icon = bar ? bar.querySelector('.bi-chevron-down, .bi-chevron-up') : null;
        if (icon) {
            icon.classList.toggle('bi-chevron-down');
            icon.classList.toggle('bi-chevron-up');
        }
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}
