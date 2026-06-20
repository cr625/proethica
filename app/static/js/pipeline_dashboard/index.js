document.addEventListener('DOMContentLoaded', function() {
    // Service Status Check
    async function checkServiceStatus() {
        try {
            const response = await fetch('/pipeline/api/service-status');
            const data = await response.json();

            // Update Redis status
            const redisEl = document.getElementById('redisStatus');
            if (data.redis.status === 'connected') {
                redisEl.className = 'badge bg-success';
                redisEl.textContent = 'Connected';
            } else {
                redisEl.className = 'badge bg-danger';
                redisEl.textContent = 'Disconnected';
            }

            // Update Celery status
            const celeryEl = document.getElementById('celeryStatus');
            if (data.celery.status === 'online') {
                celeryEl.className = 'badge bg-success';
                celeryEl.textContent = 'Online';
            } else {
                celeryEl.className = 'badge bg-danger';
                celeryEl.textContent = 'Offline';
            }

            // Update worker count
            const workerEl = document.getElementById('workerCount');
            const workerCount = data.celery.worker_count || 0;
            workerEl.className = workerCount > 0 ? 'badge bg-success' : 'badge bg-warning';
            workerEl.textContent = workerCount;

            // Update active tasks
            const tasksEl = document.getElementById('activeTasks');
            const activeTasks = data.celery.active_tasks || 0;
            tasksEl.className = activeTasks > 0 ? 'badge bg-info' : 'badge bg-secondary';
            tasksEl.textContent = activeTasks;

            // Update overall status indicator
            const statusWidget = document.getElementById('serviceStatus');
            if (data.overall === 'healthy') {
                statusWidget.classList.remove('border-danger', 'border-warning');
                statusWidget.classList.add('border-success');
            } else if (data.overall === 'degraded') {
                statusWidget.classList.remove('border-danger', 'border-success');
                statusWidget.classList.add('border-warning');
            } else {
                statusWidget.classList.remove('border-success', 'border-warning');
                statusWidget.classList.add('border-danger');
            }

        } catch (e) {
            console.error('Service status check failed:', e);
            document.getElementById('redisStatus').className = 'badge bg-secondary';
            document.getElementById('redisStatus').textContent = 'Error';
            document.getElementById('celeryStatus').className = 'badge bg-secondary';
            document.getElementById('celeryStatus').textContent = 'Error';
        }
    }

    // Check status immediately and every 10 seconds
    checkServiceStatus();
    setInterval(checkServiceStatus, 10000);

    // Refresh status button
    document.getElementById('refreshStatusBtn').addEventListener('click', checkServiceStatus);

    // Cancel button handler
    document.querySelectorAll('.cancel-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const runId = this.dataset.runId;
            const caseId = this.dataset.caseId;
            const currentStep = this.dataset.currentStep || 'unknown';

            const msg = `Cancel pipeline run #${runId} for Case ${caseId}?\n\n` +
                        `Currently at: ${currentStep}\n\n` +
                        `This will stop the extraction and mark the run as cancelled.`;

            if (!confirm(msg)) return;

            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

            try {
                const response = await fetch(`/pipeline/api/runs/${runId}/cancel`, {
                    method: 'POST'
                });
                const data = await response.json();
                if (data.success) {
                    alert(`Pipeline cancelled.\n\nStopped at: ${data.previous_step}\nTasks revoked: ${data.revoked_tasks?.length || 0}`);
                    location.reload();
                } else {
                    alert('Error: ' + data.error);
                    this.disabled = false;
                    this.textContent = 'Cancel';
                }
            } catch (e) {
                alert('Error: ' + e.message);
                this.disabled = false;
                this.textContent = 'Cancel';
            }
        });
    });

    // Live timer update - calculate from start time to avoid reset on page refresh
    const timerDisplays = document.querySelectorAll('.timer-display');
    timerDisplays.forEach(timer => {
        const startTimeStr = timer.dataset.startTime;
        if (!startTimeStr) {
            // No start time, show 0
            timer.textContent = '0s';
            return;
        }

        const startTime = new Date(startTimeStr);

        function updateTimer() {
            const now = new Date();
            const elapsedSeconds = Math.floor((now - startTime) / 1000);
            const mins = Math.floor(elapsedSeconds / 60);
            const secs = elapsedSeconds % 60;
            if (mins > 0) {
                timer.textContent = `${mins}m ${secs}s`;
            } else {
                timer.textContent = `${secs}s`;
            }
        }

        // Update immediately and then every second
        updateTimer();
        setInterval(updateTimer, 1000);
    });

    // Store previous status for flash detection
    const statusBars = document.querySelectorAll('.status-bar');
    const previousStatus = sessionStorage.getItem('previousStatus');
    statusBars.forEach(bar => {
        const currentStatus = bar.dataset.currentStep;
        if (previousStatus && previousStatus !== currentStatus) {
            bar.classList.add('flash');
            setTimeout(() => bar.classList.remove('flash'), 1500);
        }
        sessionStorage.setItem('previousStatus', currentStatus);
    });

    // Retry button
    document.querySelectorAll('.retry-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const runId = this.dataset.runId;
            const failedStep = this.dataset.failedStep || 'unknown';
            const stepsCompleted = this.dataset.stepsCompleted || '0';

            const msg = `Resume pipeline from "${failedStep}"?\n\n` +
                        `${stepsCompleted} steps already completed will be skipped.\n` +
                        `The pipeline will continue from where it failed.`;

            if (!confirm(msg)) return;

            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Resuming...';

            try {
                const response = await fetch(`/pipeline/api/runs/${runId}/retry`, {
                    method: 'POST'
                });
                const data = await response.json();
                if (data.success) {
                    alert(`Resume started!\n\nResuming from: ${data.failed_step}\nSteps already done: ${(data.steps_completed || []).join(', ') || 'none'}`);
                    location.reload();
                } else {
                    alert('Error: ' + data.error);
                    this.disabled = false;
                    this.textContent = 'Resume';
                }
            } catch (e) {
                alert('Error: ' + e.message);
                this.disabled = false;
                this.textContent = 'Resume';
            }
        });
    });

    // Reprocess button
    document.querySelectorAll('.reprocess-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const caseId = this.dataset.caseId;
            const runStatus = this.dataset.runStatus;

            const msg = `Reprocess Case ${caseId} from scratch?\n\n` +
                        `This will:\n` +
                        `- Clear ALL extracted entities (including committed)\n` +
                        `- Clear all extraction prompts\n` +
                        `- Mark previous runs as superseded\n` +
                        `- Start a fresh pipeline run\n\n` +
                        `Previous status: ${runStatus}`;

            if (!confirm(msg)) return;

            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

            try {
                const response = await fetch(`/pipeline/api/reprocess/${caseId}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({clear_committed: true, clear_prompts: true})
                });
                const data = await response.json();
                if (data.success) {
                    const cleared = data.cleared || {};
                    alert(`Reprocessing started!\n\n` +
                          `Cleared:\n` +
                          `- ${cleared.rdf_entities || 0} RDF entities\n` +
                          `- ${cleared.extraction_prompts || 0} prompts\n` +
                          `- ${cleared.previous_runs || 0} previous runs marked superseded\n\n` +
                          `New task: ${data.task_id}`);
                    location.reload();
                } else {
                    alert('Error: ' + data.error);
                    this.disabled = false;
                    this.textContent = 'Reprocess';
                }
            } catch (e) {
                alert('Error: ' + e.message);
                this.disabled = false;
                this.textContent = 'Reprocess';
            }
        });
    });

    // Synthesize button (for extracted/partial runs - runs Step 4 synthesis only)
    document.querySelectorAll('.synthesize-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const caseId = this.dataset.caseId;

            const msg = `Run Step 4 synthesis for Case ${caseId}?\n\n` +
                        `This will run Case Synthesis (Step 4) only.\n` +
                        `No entities will be committed to OntServe.\n\n` +
                        `Steps 1-3 (extraction) are already complete.`;

            if (!confirm(msg)) return;

            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

            try {
                // Call api_run_step4 directly (no OntServe commit)
                const response = await fetch('/pipeline/api/run_step4', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({case_id: parseInt(caseId)})
                });
                const data = await response.json();

                if (data.success) {
                    alert(`Step 4 synthesis started for Case ${caseId}.\nRun ID: ${data.run_id}`);
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Unknown'));
                    this.disabled = false;
                    this.textContent = 'Synthesize';
                }
            } catch (e) {
                alert('Error: ' + e.message);
                this.disabled = false;
                this.textContent = 'Synthesize';
            }
        });
    });

    // Details button
    document.querySelectorAll('.details-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const runId = this.dataset.runId;
            try {
                const response = await fetch(`/pipeline/api/runs/${runId}`);
                const data = await response.json();
                document.getElementById('runDetails').textContent = JSON.stringify(data, null, 2);
                new bootstrap.Modal(document.getElementById('detailsModal')).show();
            } catch (e) {
                alert('Error: ' + e.message);
            }
        });
    });

    // Auto-refresh if there are active runs (every 5 seconds)
    if (window.PIPELINE_DASHBOARD.hasActiveRuns) {
    setTimeout(() => location.reload(), 5000);
    }
});
