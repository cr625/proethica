let originalText = document.getElementById('templateText')?.value || '';
let hasUnsavedChanges = false;

function switchMainTab(tabName) {
    // Identity-based (data-tab), not index-based: the Test tab is absent in the read-only viewer.
    document.querySelectorAll('.main-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.tab === tabName);
    });
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    const pane = document.getElementById('tab-' + tabName);
    if (pane) pane.classList.add('active');
    // Auto-render the Preview when its tab is opened so the injected values show immediately (the no-case
    // path renders the ontology slots with «placeholders» for case text; selecting a case fills them).
    if (tabName === 'preview') renderPreview();
}

function markUnsaved() {
    const text = document.getElementById('templateText').value;
    hasUnsavedChanges = text !== originalText;
    document.querySelector('#statusIndicator .status-dot').className =
        'status-dot ' + (hasUnsavedChanges ? 'status-unsaved' : 'status-saved');
    document.getElementById('statusText').textContent = hasUnsavedChanges ? 'Unsaved' : 'Saved';
    document.getElementById('saveBtn').disabled = !hasUnsavedChanges;
    document.getElementById('charCount').textContent = text.length + ' chars';
}

async function saveTemplate() {
    if (!templateId) return;
    const statusDot = document.querySelector('#statusIndicator .status-dot');
    const statusText = document.getElementById('statusText');
    statusDot.className = 'status-dot status-saving';
    statusText.textContent = 'Saving...';
    document.getElementById('saveBtn').disabled = true;

    try {
        const response = await fetch(`/api/prompts/template/${templateId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                template_text: document.getElementById('templateText').value,
                system_prompt: document.getElementById('systemText')?.value || '',
                change_description: 'Updated via web editor'
            })
        });

        // Check if response is JSON before parsing
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            throw new Error(`Server returned ${response.status}: ${text.substring(0, 100)}...`);
        }

        const data = await response.json();
        if (data.success) {
            originalText = document.getElementById('templateText').value;
            hasUnsavedChanges = false;
            statusDot.className = 'status-dot status-saved';
            statusText.textContent = `Saved (v${data.template.version})`;
        } else throw new Error(data.error);
    } catch (error) {
        statusDot.className = 'status-dot status-unsaved';
        statusText.textContent = 'Failed';
        document.getElementById('saveBtn').disabled = false;
        alert('Error: ' + error.message);
    }
}

// Helper to get global case selection
function getGlobalCase() {
    // For a pass-split prompt (e.g. roles facts/discussion) the section is the template's pass,
    // not the (now-hidden) dropdown; unsplit 'all' prompts still read the dropdown.
    const passSection = (TEMPLATE_PASS === 'facts' || TEMPLATE_PASS === 'discussion') ? TEMPLATE_PASS : null;
    const sel = document.getElementById('globalSectionSelect');
    return {
        caseId: document.getElementById('globalCaseSelect').value,
        section: passSection || (sel ? sel.value : 'facts')
    };
}

// LocalStorage key for persisting case selection across pages
const CASE_STORAGE_KEY = 'proethica_prompt_editor_case';

// Called when global case selection changes
function onGlobalCaseChange() {
    const { caseId, section } = getGlobalCase();
    const statusEl = document.getElementById('caseStatus');
    if (caseId) {
        statusEl.textContent = 'Loading preview...';
        // Clear cached variables when case changes
        resolvedVariables = {};
        // Persist selection to localStorage
        localStorage.setItem(CASE_STORAGE_KEY, JSON.stringify({ caseId, section }));
        // Auto-render preview
        renderPreview();
    } else {
        statusEl.textContent = '';
        localStorage.removeItem(CASE_STORAGE_KEY);
    }
}

// Called when section selection changes
function onSectionChange() {
    const { caseId, section } = getGlobalCase();
    if (caseId) {
        // Clear cached variables when section changes
        resolvedVariables = {};
        // Update persisted selection
        localStorage.setItem(CASE_STORAGE_KEY, JSON.stringify({ caseId, section }));
        // Auto-render preview
        renderPreview();
    }
}

// Restore case selection from localStorage on page load, or default to the
// most recent case (the dropdown is ordered latest-extraction first).
function restoreCaseSelection() {
    const caseSelect = document.getElementById('globalCaseSelect');
    // Pass-split prompts do not render the section dropdown; the section is
    // the template's pass (same rule as getGlobalCase).
    const sectionSelect = document.getElementById('globalSectionSelect');
    const passSection = (TEMPLATE_PASS === 'facts' || TEMPLATE_PASS === 'discussion') ? TEMPLATE_PASS : null;

    // No cases available
    if (!caseSelect || caseSelect.options.length === 0) return;

    // ?case=latest (the main-nav entry) forces the newest case over any saved
    // selection; ?case=<id> deep-links a specific case.
    const urlCase = new URLSearchParams(window.location.search).get('case');
    if (urlCase && urlCase !== 'latest' && caseSelect.querySelector(`option[value="${urlCase}"]`)) {
        caseSelect.value = urlCase;
        localStorage.setItem(CASE_STORAGE_KEY, JSON.stringify({
            caseId: urlCase,
            section: passSection || (sectionSelect ? sectionSelect.value : 'facts')
        }));
        renderPreview();
        return;
    }

    try {
        const saved = urlCase === 'latest' ? null : localStorage.getItem(CASE_STORAGE_KEY);
        if (saved) {
            const { caseId, section } = JSON.parse(saved);
            // Check if the saved case exists in the dropdown
            if (caseId && caseSelect.querySelector(`option[value="${caseId}"]`)) {
                caseSelect.value = caseId;
                if (section && sectionSelect && sectionSelect.querySelector(`option[value="${section}"]`)) {
                    sectionSelect.value = section;
                }
                // Trigger preview render
                renderPreview();
                return;
            }
        }
    } catch (e) {
        console.warn('Failed to restore case selection:', e);
    }

    // No saved selection or saved case not found - default to the latest case
    const firstCase = caseSelect.options[0];
    if (firstCase) {
        caseSelect.value = firstCase.value;
        localStorage.setItem(CASE_STORAGE_KEY, JSON.stringify({
            caseId: firstCase.value,
            section: passSection || (sectionSelect ? sectionSelect.value : 'facts')
        }));
        renderPreview();
    }
}

// LocalStorage key for persisting last viewed template
const TEMPLATE_STORAGE_KEY = 'proethica_prompt_editor_template';

// Save current template location for redirect from index
function saveTemplateLocation() {
    try {
        localStorage.setItem(TEMPLATE_STORAGE_KEY, JSON.stringify({
            url: window.location.pathname + window.location.search
        }));
    } catch (e) {
        console.warn('Failed to save template location:', e);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    restoreCaseSelection();
    saveTemplateLocation();
});

async function renderPreview() {
    const { caseId, section } = getGlobalCase();
    const body = document.getElementById('previewBody');
    const status = document.getElementById('previewStatus');
    const caseStatus = document.getElementById('caseStatus');

    // No hard stop on a missing case: the /render endpoint renders the case-independent ontology
    // injections with «placeholders» for the case-driven variables, so the tab is useful immediately.
    status.textContent = caseId ? 'Rendering...' : 'Rendering ontology injections...';
    body.innerHTML = '<div class="preview-placeholder"><div class="spinner-border spinner-border-sm"></div></div>';

    try {
        const response = await fetch(`/api/prompts/template/${templateId}/render`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ case_id: caseId ? parseInt(caseId) : null, section_type: section })
        });
        const data = await response.json();
        if (data.success) {
            body.innerHTML = formatPromptPreview(data.rendered_prompt);
            status.textContent = `Rendered (${section})`;
            caseStatus.textContent = data.case_title || `Preview ready (${data.character_count.toLocaleString()} chars)`;
        } else {
            body.innerHTML = `<div class="preview-placeholder text-danger">${data.error || 'Render failed'}</div>`;
            status.textContent = 'Failed';
            caseStatus.textContent = 'Preview failed';
        }
    } catch (error) {
        body.innerHTML = `<div class="preview-placeholder text-danger">Error: ${error.message}</div>`;
        status.textContent = 'Error';
        caseStatus.textContent = 'Preview error';
    }
}

async function runTest() {
    const { caseId, section } = getGlobalCase();
    const results = document.getElementById('testResults');
    const status = document.getElementById('testStatus');

    if (!caseId && !IS_SHARED_PROMPT) {
        alert('Please select a case above first');
        return;
    }

    document.getElementById('testBtn').disabled = true;
    status.textContent = 'Running...';
    results.innerHTML = '<div class="preview-placeholder"><div class="spinner-border"></div><p class="mt-2">Executing extraction...</p></div>';

    try {
        const response = await fetch(`/api/prompts/template/${templateId}/test-run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ case_id: parseInt(caseId), section_type: section })
        });
        const data = await response.json();

        if (data.success) {
            status.textContent = `Completed in ${data.duration_ms}ms`;
            results.innerHTML = `
                <div class="test-section">
                    <div class="test-section-header" onclick="this.parentElement.classList.toggle('collapsed')">
                        <span><i class="bi bi-chat-text"></i> Rendered Prompt</span>
                        <i class="bi bi-chevron-down"></i>
                    </div>
                    <div class="test-section-body">${escapeHtml(data.rendered_prompt)}</div>
                </div>
                <div class="test-section collapsed">
                    <div class="test-section-header" onclick="this.parentElement.classList.toggle('collapsed')">
                        <span><i class="bi bi-robot"></i> LLM Response</span>
                        <i class="bi bi-chevron-right"></i>
                    </div>
                    <div class="test-section-body">${escapeHtml(data.raw_response)}</div>
                </div>
                <div class="test-section">
                    <div class="test-section-header">
                        <span><i class="bi bi-diagram-3"></i> Extracted Entities</span>
                    </div>
                    <div style="padding: 0.5rem;">
                        ${data.entities ? formatEntities(data.entities) : '<p class="text-muted small">No entities extracted</p>'}
                    </div>
                </div>`;
        } else {
            status.textContent = 'Failed';
            results.innerHTML = `<div class="preview-placeholder text-danger"><i class="bi bi-exclamation-triangle"></i><p>${data.error}</p></div>`;
        }
    } catch (error) {
        status.textContent = 'Error';
        results.innerHTML = `<div class="preview-placeholder text-danger">Error: ${error.message}</div>`;
    }
    document.getElementById('testBtn').disabled = false;
}

function formatEntities(entities) {
    let html = '';
    // Handle various entity key patterns from different concept extractors
    for (const [key, value] of Object.entries(entities)) {
        if (!Array.isArray(value) || value.length === 0) continue;

        // Format key name for display
        const displayName = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        html += `<div class="mb-2 mt-2"><strong>${displayName} (${value.length})</strong></div>`;

        value.forEach(e => {
            const label = e.label || e.name || e.title || 'Unknown';
            const desc = e.definition || e.description || e.reasoning || '';
            const truncDesc = desc.length > 100 ? desc.substring(0, 100) + '...' : desc;
            const classRef = e.role_class || e.class_label || e.parent_class || e.type || '';

            if (classRef) {
                html += `<div class="entity-card"><strong>${label}</strong> → ${classRef}</div>`;
            } else if (truncDesc) {
                html += `<div class="entity-card"><strong>${label}</strong><br><small class="text-muted">${truncDesc}</small></div>`;
            } else {
                html += `<div class="entity-card"><strong>${label}</strong></div>`;
            }
        });
    }
    return html || '<p class="text-muted small">No entities in response</p>';
}


function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatPromptPreview(text) {
    // Escape HTML first
    let html = escapeHtml(text);

    // Format main header (first line, usually "DUAL X EXTRACTION - ...")
    html = html.replace(/^([A-Z][A-Z\s\-]+(?:Extraction|Analysis)[^\n]*)/m,
        '<div class="preview-header">$1</div>');

    // Format section markers (=== TASK === etc)
    html = html.replace(/^(={3,}\s*[A-Z\s]+\s*={3,})$/gm,
        '<div class="preview-task"><strong>$1</strong></div>');

    // Format "EXISTING X IN ONTOLOGY:" headers
    html = html.replace(/^(EXISTING [A-Z\s]+ IN ONTOLOGY:)$/gm,
        '<div class="preview-header" style="margin-top: 1rem;">$1</div>');

    // Format "CASE TEXT:" section
    html = html.replace(/^(CASE TEXT:)\n([\s\S]*?)(?=\n\nRespond with|$)/m, (match, header, content) => {
        return `<div class="preview-header" style="margin-top: 1rem;">${header}</div><div class="preview-case-text">${content.trim()}</div>`;
    });

    // Format "Respond with valid JSON:" header
    html = html.replace(/^(Respond with valid JSON[^\n]*:)$/gm,
        '<div class="preview-header" style="margin-top: 1rem;">$1</div>');

    // Format LEVEL headers
    html = html.replace(/^(LEVEL \d+ - [A-Z\s]+:)/gm,
        '<div class="preview-header" style="margin-top: 0.75rem; color: #0d6efd;">$1</div>');

    // Format list items starting with -
    html = html.replace(/^- (.+)$/gm, '<div style="padding-left: 1rem;">- $1</div>');

    // Wrap remaining content and preserve line breaks
    html = html.replace(/\n\n/g, '</p><p style="margin: 0.5rem 0;">');
    html = html.replace(/\n/g, '<br>');

    return `<div style="padding: 0.5rem;">${html}</div>`;
}

async function revertToVersion(versionNumber) {
    if (!confirm(`Revert to v${versionNumber}?`)) return;
    try {
        const response = await fetch(`/api/prompts/template/${templateId}/revert/${versionNumber}`, { method: 'POST' });
        const data = await response.json();
        if (data.success) location.reload();
        else throw new Error(data.error);
    } catch (error) { alert('Error: ' + error.message); }
}

// Variable preview storage
let resolvedVariables = {};

async function previewVariables() {
    const { caseId, section } = getGlobalCase();
    if (!caseId) {
        alert('Please select a case above first');
        return;
    }
    if (!templateId) {
        alert('No template loaded');
        return;
    }

    const modal = new bootstrap.Modal(document.getElementById('varPreviewModal'));
    document.getElementById('varPreviewLoading').style.display = 'block';
    document.getElementById('varPreviewError').style.display = 'none';
    document.getElementById('varPreviewResults').style.display = 'none';
    modal.show();

    try {
        const response = await fetch(`/api/prompts/template/${templateId}/resolve-variables`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ case_id: parseInt(caseId), section_type: section })
        });
        const data = await response.json();

        document.getElementById('varPreviewLoading').style.display = 'none';

        if (data.success) {
            resolvedVariables = data.variables;
            document.getElementById('varPreviewCaseTitle').textContent = data.case_title;
            document.getElementById('varPreviewMeta').textContent = `${Object.keys(data.variables).length} variables | ${data.concept_type} | ${section}`;

            let html = '';
            for (const [varName, varInfo] of Object.entries(data.variables)) {
                html += `
                    <div class="mb-3">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <strong class="text-primary">${" + varName + "}</strong>
                            <span class="badge bg-secondary">${varInfo.length} chars</span>
                        </div>
                        <div class="var-preview-content">${escapeHtml(varInfo.value)}</div>
                    </div>`;
            }
            document.getElementById('varPreviewList').innerHTML = html || '<p class="text-muted">No variables resolved</p>';
            document.getElementById('varPreviewResults').style.display = 'block';
        } else {
            document.getElementById('varPreviewError').textContent = data.error || 'Unknown error';
            document.getElementById('varPreviewError').style.display = 'block';
        }
    } catch (error) {
        document.getElementById('varPreviewLoading').style.display = 'none';
        document.getElementById('varPreviewError').textContent = error.message;
        document.getElementById('varPreviewError').style.display = 'block';
    }
}

let currentSingleVarName = '';

async function previewSingleVariable(varName) {
    const { caseId, section } = getGlobalCase();
    if (!caseId) {
        alert('Please select a case above first');
        return;
    }

    currentSingleVarName = varName;
    const modal = new bootstrap.Modal(document.getElementById('singleVarModal'));
    document.getElementById('singleVarName').textContent = ' + varName + ';
    document.getElementById('singleVarLoading').style.display = 'block';
    document.getElementById('singleVarContent').style.display = 'none';
    document.getElementById('singleVarMeta').textContent = '';
    modal.show();

    // Check if we already have this variable cached
    if (resolvedVariables && resolvedVariables[varName]) {
        showSingleVariable(varName, resolvedVariables[varName]);
        return;
    }

    // Otherwise fetch all variables
    try {
        const response = await fetch(`/api/prompts/template/${templateId}/resolve-variables`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ case_id: parseInt(caseId), section_type: section })
        });
        const data = await response.json();

        if (data.success) {
            resolvedVariables = data.variables;
            if (resolvedVariables[varName]) {
                showSingleVariable(varName, resolvedVariables[varName]);
            } else {
                document.getElementById('singleVarLoading').style.display = 'none';
                document.getElementById('singleVarContent').textContent = '[Variable not found in resolved data]';
                document.getElementById('singleVarContent').style.display = 'block';
            }
        } else {
            document.getElementById('singleVarLoading').style.display = 'none';
            document.getElementById('singleVarContent').textContent = 'Error: ' + (data.error || 'Unknown error');
            document.getElementById('singleVarContent').style.display = 'block';
        }
    } catch (error) {
        document.getElementById('singleVarLoading').style.display = 'none';
        document.getElementById('singleVarContent').textContent = 'Error: ' + error.message;
        document.getElementById('singleVarContent').style.display = 'block';
    }
}

function showSingleVariable(varName, varInfo) {
    document.getElementById('singleVarLoading').style.display = 'none';
    document.getElementById('singleVarContent').textContent = varInfo.value || varInfo;
    document.getElementById('singleVarContent').style.display = 'block';
    const length = (varInfo.value || varInfo).length;
    document.getElementById('singleVarMeta').textContent = `${length.toLocaleString()} characters`;
}

function copySingleVariable() {
    const content = document.getElementById('singleVarContent').textContent;
    navigator.clipboard.writeText(content).then(() => {
        const btn = event.target.closest('button');
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check"></i> Copied!';
        setTimeout(() => { btn.innerHTML = originalHtml; }, 1500);
    }).catch(err => {
        alert('Failed to copy: ' + err);
    });
}

function copyAllVariables() {
    if (!resolvedVariables || Object.keys(resolvedVariables).length === 0) {
        alert('No variables to copy');
        return;
    }
    let text = '';
    for (const [varName, varInfo] of Object.entries(resolvedVariables)) {
        text += `=== ${varName} ===\n${varInfo.value}\n\n`;
    }
    navigator.clipboard.writeText(text).then(() => {
        const btn = event.target.closest('button');
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check"></i> Copied!';
        setTimeout(() => { btn.innerHTML = originalHtml; }, 1500);
    }).catch(err => {
        alert('Failed to copy: ' + err);
    });
}

window.addEventListener('beforeunload', e => {
    if (hasUnsavedChanges) { e.preventDefault(); e.returnValue = ''; }
});
