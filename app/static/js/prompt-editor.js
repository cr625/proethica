// Prompt Template Editor JavaScript
// All functions for the template editor

let editor = null;
let previewTimeout = null;

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeEditor();
});

async function initializeEditor() {
    try {
        // Import CodeMirror modules
        const {EditorView, basicSetup} = await import("https://cdn.jsdelivr.net/npm/codemirror@6.0.1/dist/index.min.js");
        
        const editorElement = document.getElementById('templateEditor');
        if (!editorElement) return;
        
        // Create the editor
        editor = new EditorView({
            doc: editorElement.textContent,
            extensions: [
                basicSetup,
                EditorView.updateListener.of((update) => {
                    if (update.docChanged) {
                        debouncePreview();
                    }
                })
            ],
            parent: editorElement.parentNode
        });
        
        // Hide original element
        editorElement.style.display = 'none';
        
        // Initial preview
        setTimeout(previewTemplate, 100);
        
    } catch (error) {
        console.error('Failed to initialize CodeMirror:', error);
        // Fall back to textarea if CodeMirror fails
        useTextareaFallback();
    }
}

function useTextareaFallback() {
    const editorElement = document.getElementById('templateEditor');
    if (!editorElement) return;
    
    // Convert to a regular textarea
    const textarea = document.createElement('textarea');
    textarea.className = 'form-control';
    textarea.style.minHeight = '400px';
    textarea.style.fontFamily = 'monospace';
    textarea.value = editorElement.textContent;
    textarea.id = 'fallbackEditor';
    
    editorElement.parentNode.replaceChild(textarea, editorElement);
    
    // Update editor reference for other functions
    editor = {
        state: {
            doc: {
                toString: () => textarea.value
            },
            selection: {
                main: {
                    from: textarea.selectionStart,
                    to: textarea.selectionEnd
                }
            },
            update: (transaction) => {
                const start = transaction.changes.from;
                const end = transaction.changes.to;
                const text = transaction.changes.insert;
                textarea.value = textarea.value.substring(0, start) + text + textarea.value.substring(end);
                textarea.selectionStart = start + text.length;
                textarea.selectionEnd = start + text.length;
            }
        },
        dispatch: () => {},
        focus: () => textarea.focus()
    };
    
    // Add input listener for preview
    textarea.addEventListener('input', debouncePreview);
}

function insertText(text) {
    if (!editor) {
        console.warn('Editor not initialized');
        return;
    }
    
    // Check if we're using the fallback textarea
    const textarea = document.getElementById('fallbackEditor');
    if (textarea) {
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const value = textarea.value;
        textarea.value = value.substring(0, start) + text + value.substring(end);
        textarea.selectionStart = start + text.length;
        textarea.selectionEnd = start + text.length;
        textarea.focus();
    } else if (editor.state) {
        // CodeMirror is active
        const selection = editor.state.selection.main;
        const transaction = editor.state.update({
            changes: {from: selection.from, to: selection.to, insert: text}
        });
        editor.dispatch(transaction);
        editor.focus();
    }
}

function insertVariable(varName) {
    // Use double curly braces for Jinja2 variables
    insertText(`{{ ${varName} }}`);
}

function previewTemplate() {
    const templateContent = getEditorContent();
    const previewElement = document.getElementById('templatePreview');
    if (!previewElement) return;
    
    // Sample variables for preview
    const sampleVars = {
        case_title: "Sample Engineering Ethics Case",
        case_domain: "engineering",
        section_content: "This is sample content for preview purposes.",
        case_id: "CASE_001",
        stakeholder_types: "engineers, public, clients",
        professional_codes: "NSPE Code, IEEE Standards",
        regulatory_context: "OSHA compliance",
        safety_considerations: "public safety, environmental impact"
    };
    
    // Simple template replacement for preview
    let preview = templateContent;
    Object.entries(sampleVars).forEach(([key, value]) => {
        // Replace Jinja2-style variables
        const regex = new RegExp(`{{\\s*${key}\\s*}}`, 'g');
        preview = preview.replace(regex, value);
    });
    
    previewElement.innerHTML = preview || '<em class="text-muted">Template preview will appear here...</em>';
}

function debouncePreview() {
    clearTimeout(previewTimeout);
    previewTimeout = setTimeout(previewTemplate, 500);
}

function getEditorContent() {
    const textarea = document.getElementById('fallbackEditor');
    if (textarea) {
        return textarea.value;
    } else if (editor && editor.state) {
        return editor.state.doc.toString();
    }
    return '';
}

function saveTemplate() {
    const templateData = {
        name: document.getElementById('templateName')?.value || '',
        description: document.getElementById('templateDescription')?.value || '',
        domain: document.getElementById('templateDomain')?.value || '',
        section_type: document.getElementById('templateSectionType')?.value || '',
        prompt_template: getEditorContent(),
        analysis_priority: parseInt(document.getElementById('analysisPriority')?.value || '1'),
        extraction_targets: document.getElementById('extractionTargets')?.value || '',
        variables: getVariables(),
        change_description: 'Updated via web editor'
    };
    
    const templateId = document.getElementById('templateId')?.value;
    if (templateId) {
        templateData.template_id = templateId;
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

function getVariables() {
    const variables = [];
    const variableItems = document.querySelectorAll('.variable-item');
    
    variableItems.forEach(item => {
        const nameInput = item.querySelector('input[placeholder="Variable name"]');
        const descInput = item.querySelector('input[placeholder="Description"]');
        
        if (nameInput && nameInput.value.trim()) {
            variables.push({
                name: nameInput.value.trim(),
                description: descInput ? descInput.value.trim() : ''
            });
        }
    });
    
    return variables;
}

function addVariable() {
    const container = document.getElementById('variablesList');
    if (!container) return;
    
    const div = document.createElement('div');
    div.className = 'variable-item d-flex align-items-center mb-2';
    div.innerHTML = `
        <input type="text" class="form-control form-control-sm me-2" placeholder="Variable name" style="flex: 1">
        <input type="text" class="form-control form-control-sm me-2" placeholder="Description" style="flex: 2">
        <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeVariable(this)">
            <i class="bi bi-trash"></i>
        </button>
    `;
    container.appendChild(div);
}

function removeVariable(button) {
    button.closest('.variable-item').remove();
}

function showMessage(message, type) {
    const container = document.getElementById('messageContainer');
    if (!container) return;
    
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

// Make functions globally available for onclick handlers
window.insertText = insertText;
window.insertVariable = insertVariable;
window.previewTemplate = previewTemplate;
window.saveTemplate = saveTemplate;
window.addVariable = addVariable;
window.removeVariable = removeVariable;
window.showMessage = showMessage;