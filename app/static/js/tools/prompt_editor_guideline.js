const templateId = window.PROMPT_EDITOR_GUIDELINE.templateId;
const conceptType = window.PROMPT_EDITOR_GUIDELINE.conceptType;

function switchTab(tabName) {
    document.querySelectorAll('.main-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`.main-tab:has(i.bi-${tabName === 'template' ? 'code-slash' : tabName === 'preview' ? 'eye' : 'clock-history'})`).classList.add('active');
    document.getElementById('tab-' + tabName).classList.add('active');
}

function saveTemplate() {
    if (!templateId) return;

    const templateText = document.getElementById('templateEditor').value;

    fetch(`/api/prompts/template/${templateId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            template_text: templateText,
            change_description: 'Updated via guideline editor'
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert('Template saved successfully!');
            location.reload();
        } else {
            alert('Error saving: ' + data.error);
        }
    })
    .catch(err => alert('Error: ' + err));
}

function renderPreview() {
    if (!templateId) return;

    const templateText = document.getElementById('templateEditor').value;

    fetch(`/api/prompts/template/${templateId}/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            template_text: templateText,
            variables: {
                guideline_text: '[Sample guideline text would appear here...]',
                guideline_title: 'NSPE Code of Ethics',
                existing_provisions: '- I.1: Hold paramount the safety...\n- II.1.a: Approve only work...',
                existing_principles: '- Public Safety\n- Professional Competence',
                existing_obligations: '- Maintain Confidentiality\n- Avoid Conflicts of Interest'
            }
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            document.getElementById('previewContent').innerHTML =
                '<pre style="white-space: pre-wrap; font-size: 0.85rem;">' +
                data.rendered_template.replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                '</pre>';
        } else {
            document.getElementById('previewContent').innerHTML =
                '<div class="alert alert-danger">' + data.error + '</div>';
        }
    })
    .catch(err => {
        document.getElementById('previewContent').innerHTML =
            '<div class="alert alert-danger">' + err + '</div>';
    });
}

function revertToVersion(versionNumber) {
    if (!confirm(`Revert to version ${versionNumber}?`)) return;

    fetch(`/api/prompts/template/${templateId}/revert/${versionNumber}`, {
        method: 'POST'
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            alert('Error reverting: ' + data.error);
        }
    })
    .catch(err => alert('Error: ' + err));
}

function createTemplate() {
    // For now, just show an info message
    alert('Template creation for guidelines coming soon. Please create templates manually via the API or database.');
}
