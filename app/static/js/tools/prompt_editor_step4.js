const phase = window.PROMPT_EDITOR_STEP4.phase;

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
    });
});

// Toggle prompt card expansion and load code
function togglePrompt(header) {
    const card = header.closest('.prompt-card');
    const wasExpanded = card.classList.contains('expanded');
    card.classList.toggle('expanded');

    if (!wasExpanded) {
        const method = card.dataset.method;
        const codeEl = card.querySelector('.code-view');
        if (codeEl.textContent === 'Loading...') {
            loadPromptCode(method, codeEl);
        }
    }
}

async function loadPromptCode(method, element) {
    try {
        const response = await fetch(`/api/prompts/step4/prompt/${phase}/${method}`);
        const data = await response.json();
        if (data.success) {
            element.textContent = data.code;
        } else {
            element.textContent = `# Error: ${data.error}`;
        }
    } catch (error) {
        element.textContent = `# Error loading code: ${error.message}`;
    }
}

// Update settings
async function updateSetting(key, value) {
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');

    statusDot.className = 'status-dot status-modified';
    statusText.textContent = 'Saving...';

    try {
        const response = await fetch('/api/prompts/step4/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [key]: value })
        });
        const data = await response.json();

        if (data.success) {
            statusDot.className = 'status-dot status-saved';
            statusText.textContent = 'Saved';
            setTimeout(() => {
                statusText.textContent = 'Ready';
                statusDot.className = 'status-dot';
            }, 2000);
        } else {
            throw new Error(data.error);
        }
    } catch (error) {
        statusDot.className = 'status-dot';
        statusText.textContent = 'Error: ' + error.message;
    }
}

// Case selection for testing
document.getElementById('testCaseSelect').addEventListener('change', function() {
    const caseId = this.value;
    const testBtn = document.getElementById('testBtn');
    const testLink = document.getElementById('testLink');

    if (caseId) {
        testBtn.disabled = false;
        testLink.style.pointerEvents = 'auto';
        testLink.style.opacity = '1';
        testLink.href = `/scenario_pipeline/case/${caseId}/step4`;
        testLink.querySelector('div').textContent = 'Run full synthesis';
    } else {
        testBtn.disabled = true;
        testLink.style.pointerEvents = 'none';
        testLink.style.opacity = '0.5';
        testLink.querySelector('div').textContent = 'Select a case above first';
    }
});

function goToStep4() {
    const caseId = document.getElementById('testCaseSelect').value;
    if (caseId) {
        window.location.href = `/scenario_pipeline/case/${caseId}/step4`;
    }
}

// LocalStorage for remembering template location
const TEMPLATE_STORAGE_KEY = 'proethica_prompt_editor_template';
localStorage.setItem(TEMPLATE_STORAGE_KEY, JSON.stringify({
    url: window.location.pathname
}));
