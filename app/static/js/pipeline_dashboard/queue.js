document.addEventListener('DOMContentLoaded', function() {
    const checkboxes = document.querySelectorAll('.case-checkbox:not(:disabled)');
    const selectedCountEl = document.getElementById('selectedCount');

    function updateSelectedCount() {
        const count = document.querySelectorAll('.case-checkbox:checked').length;
        selectedCountEl.textContent = count;
    }

    // Check if processing is active on page load
    async function checkProcessingStatus() {
        try {
            const response = await fetch('/pipeline/api/service-status');
            const data = await response.json();

            // Check if Celery has active tasks
            const activeTasks = data.celery?.active_tasks || 0;
            if (activeTasks > 0) {
                setProcessingState(true);
                startPolling();
            }
        } catch (e) {
            console.error('Failed to check processing status:', e);
        }
    }

    function setProcessingState(isProcessing) {
        const startBtn = document.getElementById('startQueueBtn');
        const clearBtn = document.getElementById('clearQueueBtn');
        const addBtn = document.getElementById('addToQueueBtn');
        const removeButtons = document.querySelectorAll('.remove-queue-btn');

        if (isProcessing) {
            startBtn.disabled = true;
            startBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Processing...';
            startBtn.classList.remove('btn-success');
            startBtn.classList.add('btn-warning');
            clearBtn.disabled = true;
            addBtn.disabled = true;
            removeButtons.forEach(b => b.disabled = true);

            const infoCard = document.querySelector('.card.mt-3 .card-body');
            if (infoCard) {
                infoCard.innerHTML = `
                    <div class="alert alert-info mb-0">
                        <strong>Processing in progress</strong><br>
                        <small>Cases are being processed in the background.
                        <a href="/pipeline/dashboard">View progress on Dashboard</a></small>
                    </div>
                `;
            }
        }
    }

    // Check on page load and periodically while processing
    checkProcessingStatus();

    // Poll for status changes every 30 seconds if processing is active
    let pollInterval = null;
    async function startPolling() {
        if (pollInterval) return;
        pollInterval = setInterval(async () => {
            try {
                const response = await fetch('/pipeline/api/service-status');
                const data = await response.json();
                const activeTasks = data.celery?.active_tasks || 0;
                if (activeTasks === 0) {
                    // Processing complete - reload to refresh the page
                    clearInterval(pollInterval);
                    location.reload();
                }
            } catch (e) {
                console.error('Polling error:', e);
            }
        }, 30000);
    }

    // Select all/none
    document.getElementById('selectAll').addEventListener('click', () => {
        checkboxes.forEach(cb => cb.checked = true);
        updateSelectedCount();
    });

    document.getElementById('selectNone').addEventListener('click', () => {
        checkboxes.forEach(cb => cb.checked = false);
        updateSelectedCount();
    });

    document.getElementById('selectAllCheckbox').addEventListener('change', function() {
        checkboxes.forEach(cb => cb.checked = this.checked);
        updateSelectedCount();
    });

    checkboxes.forEach(cb => cb.addEventListener('change', updateSelectedCount));

    // Filter cases
    document.getElementById('caseFilter').addEventListener('input', function() {
        const filter = this.value.toLowerCase();
        document.querySelectorAll('.case-row').forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(filter) ? '' : 'none';
        });
    });

    // Group select
    document.getElementById('groupSelect').addEventListener('change', function() {
        if (this.value === '__new__') {
            new bootstrap.Modal(document.getElementById('newGroupModal')).show();
            this.value = '';
        }
    });

    document.getElementById('createGroupBtn').addEventListener('click', function() {
        const name = document.getElementById('newGroupName').value.trim();
        if (name) {
            const select = document.getElementById('groupSelect');
            const option = new Option(name, name);
            select.insertBefore(option, select.lastElementChild);
            select.value = name;
            bootstrap.Modal.getInstance(document.getElementById('newGroupModal')).hide();
        }
    });

    // Add to queue
    document.getElementById('addToQueueBtn').addEventListener('click', async function() {
        const selected = Array.from(document.querySelectorAll('.case-checkbox:checked'))
            .map(cb => parseInt(cb.value));

        if (selected.length === 0) {
            alert('Please select at least one case');
            return;
        }

        const priority = parseInt(document.getElementById('prioritySelect').value);
        const groupName = document.getElementById('groupSelect').value || null;
        const commitToOntserve = document.getElementById('commitToOntserve').checked;
        const includeStep4 = document.getElementById('includeStep4').checked;

        try {
            const response = await fetch('/pipeline/api/queue', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    case_ids: selected,
                    priority: priority,
                    group_name: groupName,
                    config: {
                        commit_to_ontserve: commitToOntserve,
                        include_step4: includeStep4
                    }
                })
            });
            const data = await response.json();
            if (data.success) {
                alert(`Added ${data.added.length} cases to queue`);
                location.reload();
            } else {
                alert('Error: ' + data.error);
            }
        } catch (e) {
            alert('Error: ' + e.message);
        }
    });

    // Remove from queue
    document.querySelectorAll('.remove-queue-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const queueId = this.dataset.queueId;
            try {
                const response = await fetch(`/pipeline/api/queue/${queueId}`, {
                    method: 'DELETE'
                });
                const data = await response.json();
                if (data.success) {
                    location.reload();  // Refresh to update case status badges
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (e) {
                alert('Error: ' + e.message);
            }
        });
    });

    // Start queue processing
    document.getElementById('startQueueBtn').addEventListener('click', async function() {
        if (!confirm('Start processing the queue? This may take several minutes per case.')) return;

        const btn = this;
        const clearBtn = document.getElementById('clearQueueBtn');
        const addBtn = document.getElementById('addToQueueBtn');
        const removeButtons = document.querySelectorAll('.remove-queue-btn');

        // Disable all queue controls
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Starting...';
        clearBtn.disabled = true;
        addBtn.disabled = true;
        removeButtons.forEach(b => b.disabled = true);

        try {
            const response = await fetch('/pipeline/api/queue/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({limit: 10})
            });
            const data = await response.json();
            if (data.success) {
                // Update button to show redirect state
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Redirecting...';
                btn.classList.remove('btn-success');
                btn.classList.add('btn-info');

                // Redirect to dashboard to monitor progress
                window.location.href = '/pipeline/dashboard';
            } else {
                alert('Error: ' + data.error);
                // Re-enable on error
                btn.disabled = false;
                btn.innerHTML = 'Start Processing';
                clearBtn.disabled = false;
                addBtn.disabled = false;
                removeButtons.forEach(b => b.disabled = false);
            }
        } catch (e) {
            alert('Error: ' + e.message);
            // Re-enable on error
            btn.disabled = false;
            btn.innerHTML = 'Start Processing';
            clearBtn.disabled = false;
            addBtn.disabled = false;
            removeButtons.forEach(b => b.disabled = false);
        }
    });

    // Clear queue
    document.getElementById('clearQueueBtn').addEventListener('click', async function() {
        if (!confirm('Clear all items from the queue?')) return;

        try {
            const response = await fetch('/pipeline/api/queue/clear', {
                method: 'POST'
            });
            const data = await response.json();
            if (data.success) {
                location.reload();
            } else {
                alert('Error: ' + data.error);
            }
        } catch (e) {
            alert('Error: ' + e.message);
        }
    });

});
