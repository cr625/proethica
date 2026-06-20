    // Prototype JavaScript for reasoning inspector
    let currentStepIndex = 0;
    let allSteps = (window.REASONING_INSPECTOR || {}).steps;

    function showStepDetails(stepId) {
        const step = allSteps.find(s => s.id === stepId);
        if (!step) return;

        // Update timeline highlighting
        document.querySelectorAll('.timeline-step').forEach(el => {
            el.classList.remove('active');
        });
        document.querySelector(`[data-step-id="${stepId}"]`).classList.add('active');

        // Update step index
        currentStepIndex = allSteps.findIndex(s => s.id === stepId);
        updateNavigationButtons();

        // Render step details
        const container = document.getElementById('step-details-content');

        if (step.step_type === 'llm_call') {
            container.innerHTML = renderLLMStepDetails(step);
        } else if (step.step_type === 'ontology_query') {
            container.innerHTML = renderOntologyStepDetails(step);
        } else {
            container.innerHTML = renderGenericStepDetails(step);
        }

        // Show first tab
        showTab('input');
    }

    function renderLLMStepDetails(step) {
        const inputData = step.input_data || {};
        const outputData = step.output_data || {};

        return `
        <div class="step-details">
            <h4>${step.phase_name} ${step.model_used ? '(' + step.model_used + ')' : ''}</h4>
            <div style="margin-bottom: 1rem;">
                ${step.tokens_used ? '<span class="summary-card">Tokens: ' + step.tokens_used + '</span>' : ''}
                ${step.temperature !== null ? '<span class="summary-card">Temp: ' + step.temperature + '</span>' : ''}
                <span class="summary-card">Time: ${(step.processing_time || 0).toFixed(1)}s</span>
                ${step.confidence_score ? '<span class="summary-card">Confidence: ' + Math.round(step.confidence_score * 100) + '%</span>' : ''}
            </div>
            
            <div class="detail-tabs">
                <button class="tab-btn active" onclick="showTab('input')" data-tab="input">Input Data</button>
                ${inputData.prompt ? '<button class="tab-btn" onclick="showTab(\'prompt\')" data-tab="prompt">LLM Prompt</button>' : ''}
                <button class="tab-btn" onclick="showTab('response')" data-tab="response">Raw Response</button>
                <button class="tab-btn" onclick="showTab('parsed')" data-tab="parsed">Parsed Result</button>
            </div>
            
            <div class="tab-content active" id="tab-input">
                <h5>Input Data</h5>
                <pre class="json-viewer">${JSON.stringify(inputData, null, 2)}</pre>
            </div>
            
            ${inputData.prompt ? `
            <div class="tab-content" id="tab-prompt">
                <h5>LLM Prompt</h5>
                <pre class="json-viewer">${inputData.prompt}</pre>
            </div>
            ` : ''}
            
            <div class="tab-content" id="tab-response">
                <h5>Raw LLM Response</h5>
                <pre class="json-viewer">${outputData.response || 'No response data'}</pre>
            </div>
            
            <div class="tab-content" id="tab-parsed">
                <h5>Parsed Result</h5>
                <pre class="json-viewer">${JSON.stringify(step.processed_result || {}, null, 2)}</pre>
            </div>
        </div>
    `;
    }

    function renderOntologyStepDetails(step) {
        const inputData = step.input_data || {};
        const outputData = step.output_data || {};

        return `
        <div class="step-details">
            <h4>${step.phase_name}</h4>
            <div style="margin-bottom: 1rem;">
                ${step.entity_type ? '<span class="summary-card">' + step.entity_type + '</span>' : ''}
                ${step.query_type ? '<span class="summary-card">' + step.query_type + '</span>' : ''}
                <span class="summary-card">Time: ${(step.processing_time || 0).toFixed(1)}s</span>
            </div>
            
            <div class="detail-tabs">
                <button class="tab-btn active" onclick="showTab('query')" data-tab="query">Query</button>
                <button class="tab-btn" onclick="showTab('results')" data-tab="results">Results</button>
            </div>
            
            <div class="tab-content active" id="tab-query">
                <h5>Ontology Query</h5>
                <p><strong>Entity Type:</strong> ${step.entity_type || 'Unknown'}</p>
                <p><strong>Query Type:</strong> ${step.query_type || 'Unknown'}</p>
                <pre class="json-viewer">${JSON.stringify(inputData, null, 2)}</pre>
            </div>
            
            <div class="tab-content" id="tab-results">
                <h5>Query Results</h5>
                <p>${outputData.result_count || outputData.results?.length || 0} results found</p>
                <pre class="json-viewer">${JSON.stringify(outputData, null, 2)}</pre>
            </div>
        </div>
    `;
    }

    function renderGenericStepDetails(step) {
        return `
        <div class="step-details">
            <h4>${step.phase_name}</h4>
            <div style="margin-bottom: 1rem;">
                <span class="summary-card">${step.step_type}</span>
                <span class="summary-card">Time: ${(step.processing_time || 0).toFixed(1)}s</span>
            </div>
            
            <div class="detail-tabs">
                <button class="tab-btn active" onclick="showTab('data')" data-tab="data">Step Data</button>
            </div>
            
            <div class="tab-content active" id="tab-data">
                <h5>Step Information</h5>
                <pre class="json-viewer">${JSON.stringify({
            input_data: step.input_data,
            output_data: step.output_data,
            processed_result: step.processed_result
        }, null, 2)}</pre>
            </div>
        </div>
    `;
    }

    function showTab(tabName) {
        // Hide all tab contents
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });

        // Deactivate all tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });

        // Show selected tab
        const selectedContent = document.getElementById('tab-' + tabName);
        const selectedButton = document.querySelector(`[data-tab="${tabName}"]`);

        if (selectedContent) {
            selectedContent.classList.add('active');
        }

        if (selectedButton) {
            selectedButton.classList.add('active');
        }
    }

    function previousStep() {
        if (currentStepIndex > 0) {
            const prevStep = allSteps[currentStepIndex - 1];
            showStepDetails(prevStep.id);
        }
    }

    function nextStep() {
        if (currentStepIndex < allSteps.length - 1) {
            const nextStep = allSteps[currentStepIndex + 1];
            showStepDetails(nextStep.id);
        }
    }

    function updateNavigationButtons() {
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');

        if (prevBtn) {
            prevBtn.disabled = currentStepIndex <= 0;
        }

        if (nextBtn) {
            nextBtn.disabled = currentStepIndex >= allSteps.length - 1;
        }
    }

    function exportTrace() {
        const traceData = (window.REASONING_INSPECTOR || {}).trace;
    const exportData = {
        trace: traceData,
        steps: allSteps,
        exported_at: new Date().toISOString()
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: 'application/json'
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'reasoning_trace_' + traceData.session_id + '.json';
    a.click();
    URL.revokeObjectURL(url);
    }

    // Initialize first step on page load
    document.addEventListener('DOMContentLoaded', () => {
        if (allSteps.length > 0) {
            showStepDetails(allSteps[0].id);
        }
    });
