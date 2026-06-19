function saveTemplate() {
    const templateData = {
        name: document.getElementById('templateName').value,
        description: document.getElementById('templateDescription').value,
        domain: document.getElementById('templateDomain').value,
        section_type: document.getElementById('templateSectionType').value,
        prompt_template: document.getElementById('promptTemplate').value,
        analysis_priority: 1,
        extraction_targets: '',
        variables: [],
        change_description: 'Updated via web editor'
    };

    const templateId = document.getElementById('templateId');
    if (templateId && templateId.value) {
        templateData.template_id = templateId.value;
    }

    fetch('/prompt-builder/api/templates', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(templateData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Template saved successfully!', 'success');
            if (!templateId && data.template_id) {
                // Redirect to edit mode for new template
                setTimeout(() => {
                    window.location.href = `/prompt-builder/editor/${data.template_id}`;
                }, 1500);
            }
        } else {
            showMessage('Error saving template: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error saving template: ' + error.message, 'error');
    });
}

function showMessage(message, type) {
    const container = document.getElementById('messageContainer');
    const alertClass = type === 'error' ? 'alert-danger' : 'alert-success';
    const icon = type === 'error' ? 'exclamation-triangle' : 'check-circle';
    
    const alert = document.createElement('div');
    alert.className = `alert ${alertClass} alert-dismissible fade show`;
    alert.innerHTML = `
        <i class="bi bi-${icon}"></i> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    container.appendChild(alert);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}
