let currentCaseId = window.PROVENANCE_VIEWER.selectedCaseId;
let currentPipelineData = null;
let sidebarCollapsed = window.PROVENANCE_VIEWER.selectedCaseId !== null;

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

// Entity colors
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
    if (window.PROVENANCE_VIEWER.selectedCaseId !== null) {
        loadCasePipeline(window.PROVENANCE_VIEWER.selectedCaseId);
    }

    // Load activity log when modal opens
    document.getElementById('activityLogModal').addEventListener('show.bs.modal', function() {
        if (currentCaseId) {
            loadActivityLog();
        }
    });
});

function toggleSidebar() {
    const sidebarContainer = document.getElementById('sidebar-container');
    const casesSidebar = document.getElementById('cases-sidebar');
    const contentContainer = document.getElementById('content-container');

    sidebarCollapsed = !sidebarCollapsed;

    if (sidebarCollapsed) {
        sidebarContainer.className = 'sidebar-collapsed';
        casesSidebar.classList.add('d-none');
        contentContainer.className = 'col-12';
    } else {
        sidebarContainer.className = 'col-md-3';
        casesSidebar.classList.remove('d-none');
        contentContainer.className = 'col-md-9';
    }
}

function loadCasePipeline(caseId) {
    currentCaseId = caseId;

    // Update URL without reload
    const newUrl = `/tools/provenance/cases?selected=${caseId}`;
    history.pushState({caseId: caseId}, '', newUrl);

    // Update active state in case list
    document.querySelectorAll('.list-group-item').forEach(el => el.classList.remove('active'));
    const caseEl = document.getElementById(`case-${caseId}`);
    if (caseEl) caseEl.classList.add('active');

    // Enable activity log button
    document.getElementById('activityLogBtn').disabled = false;

    // Show loading state
    document.getElementById('welcome-message').style.display = 'none';
    document.getElementById('pipeline-content').style.display = 'block';
    document.getElementById('pipeline-timeline').innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div><p class="mt-2">Loading pipeline data...</p></div>';

    // Fetch pipeline data
    fetch(`/api/provenance/case/${caseId}/pipeline`)
        .then(response => response.json())
        .then(data => {
            currentPipelineData = data;
            displayPipeline(data);
            updateCaseHeader(data.case);
        })
        .catch(error => {
            console.error('Error loading pipeline:', error);
            document.getElementById('pipeline-timeline').innerHTML = `<div class="alert alert-danger">Failed to load pipeline data: ${error.message}</div>`;
        });
}

function updateCaseHeader(caseData) {
    // Update case title
    document.getElementById('case-title').textContent = caseData.title;

    // Update source links
    const linksContainer = document.getElementById('case-source-links');
    let linksHtml = '';
    if (caseData.source) {
        linksHtml += `<a href="${escapeHtml(caseData.source)}" target="_blank" class="text-decoration-none" title="Original source (external)">
            <i class="bi bi-box-arrow-up-right me-1"></i>
            <span class="small text-muted">Source</span>
        </a>`;
    }
    linksHtml += `<a href="/cases/${caseData.id}/structure" class="text-decoration-none" title="Document structure and embeddings">
        <i class="bi bi-diagram-2 me-1"></i>
        <span class="small text-muted">Structure</span>
    </a>`;
    linksContainer.innerHTML = linksHtml;
}

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
            step.phases.forEach(phase => {
                container.appendChild(createPhaseCard(step, phase));
            });
        }
    });
}

function createStepHeader(step) {
    const div = document.createElement('div');
    div.className = 'pipeline-card';
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

function createExtractionCard(step, pass, extraction) {
    const div = document.createElement('div');
    div.className = `pipeline-card${extraction.has_data ? '' : ' empty'}`;
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
    const entityHtml = extraction.entities.length > 0
        ? `<div class="entity-list">${extraction.entities.map(e => `
            <div class="entity-item" style="--entity-color: ${e.color};">
                <div class="entity-label">${escapeHtml(e.label)}</div>
                <div class="entity-definition">${escapeHtml((e.definition || '').substring(0, 150))}${e.definition && e.definition.length > 150 ? '...' : ''}</div>
            </div>`).join('')}</div>`
        : '<p class="text-muted mb-0">No entities extracted</p>';

    div.innerHTML = `
        <div class="card extraction-card" style="--card-color: ${extraction.color};">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span>
                    <span class="badge" style="background: ${extraction.color};">${extraction.concept_label}</span>
                    <span class="badge bg-success ms-1">${extraction.entity_count} entities</span>
                </span>
                <span class="badge bg-success">Completed</span>
            </div>
            <div class="card-body">
                <div class="prompt-section">
                    <div class="section-header" onclick="toggleSection(this)">
                        <span><i class="bi bi-cpu me-2"></i>LLM Prompt</span>
                        <i class="bi bi-chevron-down"></i>
                    </div>
                    <div class="section-content">
                        <pre class="prompt-text">${escapeHtml(prompt.text || 'No prompt text available')}</pre>
                    </div>
                </div>
                <div class="response-section">
                    <div class="section-header" onclick="toggleSection(this)">
                        <span><i class="bi bi-chat-left-text me-2"></i>LLM Response</span>
                        <i class="bi bi-chevron-down"></i>
                    </div>
                    <div class="section-content">
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
            </div>
        </div>`;
    return div;
}

function createPhaseCard(step, phase) {
    const div = document.createElement('div');
    div.className = `pipeline-card${phase.has_data ? '' : ' empty'}`;
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
    const entityHtml = phase.entities.length > 0
        ? `<div class="entity-list">${phase.entities.map(e => `
            <div class="entity-item" style="--entity-color: ${step.color};">
                <div class="entity-label">${escapeHtml(e.label)}</div>
                <div class="entity-definition">${escapeHtml((e.definition || '').substring(0, 150))}${e.definition && e.definition.length > 150 ? '...' : ''}</div>
            </div>`).join('')}</div>`
        : '';

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
            <div class="card-body">
                <div class="prompt-section">
                    <div class="section-header" onclick="toggleSection(this)">
                        <span><i class="bi bi-cpu me-2"></i>LLM Prompt</span>
                        <i class="bi bi-chevron-down"></i>
                    </div>
                    <div class="section-content">
                        <pre class="prompt-text">${escapeHtml(prompt.text || 'No prompt text available')}</pre>
                    </div>
                </div>
                <div class="response-section">
                    <div class="section-header" onclick="toggleSection(this)">
                        <span><i class="bi bi-chat-left-text me-2"></i>LLM Response</span>
                        <i class="bi bi-chevron-down"></i>
                    </div>
                    <div class="section-content">
                        <pre class="response-text">${escapeHtml(prompt.response || 'No response available')}</pre>
                    </div>
                </div>
                ${entityHtml ? `
                <div class="entities-section">
                    <h6><i class="bi bi-collection me-2"></i>Generated Items (${phase.entity_count})</h6>
                    ${entityHtml}
                </div>` : ''}
            </div>
            <div class="metadata-bar">
                <i class="bi bi-clock me-1"></i>${prompt.created_at ? new Date(prompt.created_at).toLocaleString() : 'N/A'}
                <span class="mx-2">|</span>
                <i class="bi bi-robot me-1"></i>${prompt.model || 'Unknown model'}
            </div>
        </div>`;
    return div;
}

// Activity Log functions
function loadActivityLog() {
    const container = document.getElementById('activity-timeline');
    if (container.dataset.loaded === String(currentCaseId)) return;

    container.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary"></div></div>';

    fetch(`/api/provenance/case/${currentCaseId}`)
        .then(response => response.json())
        .then(data => {
            displayActivityLog(data.timeline);
            container.dataset.loaded = String(currentCaseId);
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
        'entities_pass_step1a': 'Step 1: Entity Extraction',
        'dual_roles_extraction': 'Roles Extraction',
        'roles_extraction': 'Roles Extraction',
        'resources_extraction': 'Resources Extraction',
        'states_extraction': 'States Extraction',
        'normative_pass_step2': 'Step 2: Normative Pass',
        'principles_extraction': 'Principles Extraction',
        'obligations_extraction': 'Obligations Extraction',
        'constraints_extraction': 'Constraints Extraction',
        'capabilities_extraction': 'Capabilities Extraction',
        'temporal_pass_step3': 'Step 3: Temporal Pass',
        'actions_extraction': 'Actions Extraction',
        'events_extraction': 'Events Extraction',
        'step4_provisions': 'Phase 2A: Code Provisions',
        'step4_questions': 'Phase 2B: Ethical Questions',
        'step4_conclusions': 'Phase 2B: Ethical Conclusions',
        'step4_transformation': 'Phase 2C: Transformation',
        'step4_rich_analysis': 'Phase 2D: Rich Analysis',
        'step4_phase3_decision': 'Phase 3: Decision Points',
        'step4_phase4_narrative': 'Phase 4: Narrative',
        'phase3_e1e3_algorithmic': 'Phase 3: E1-E3 Composition',
        'phase3_qc_alignment': 'Phase 3: Q&C Alignment',
        'phase3_mcp_entity_resolution': 'Phase 3: MCP Resolution',
        'phase3_llm_refinement': 'Phase 3: LLM Refinement',
        'phase3_decision_points_stored': 'Phase 3: Points Stored'
    };
    return nameMap[name] || name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function toggleSection(header) {
    const content = header.nextElementSibling;
    const icon = header.querySelector('.bi-chevron-down, .bi-chevron-up');
    if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.classList.replace('bi-chevron-up', 'bi-chevron-down');
    } else {
        content.style.display = 'none';
        icon.classList.replace('bi-chevron-down', 'bi-chevron-up');
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}
