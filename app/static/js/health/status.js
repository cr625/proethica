document.addEventListener('DOMContentLoaded', function() {
    let autoRefreshInterval;

    function updateServiceCard(cardId, statusId, detailsId, status, details) {
        const card = document.getElementById(cardId);
        const statusEl = document.getElementById(statusId);
        const detailsEl = document.getElementById(detailsId);

        const isUp = status === 'up' || status === 'connected' || status === 'online';
        statusEl.className = isUp ? 'badge bg-success' : 'badge bg-danger';
        statusEl.textContent = isUp ? 'Healthy' : 'Down';
        detailsEl.textContent = details || '--';

        card.classList.remove('border-success', 'border-danger');
        card.classList.add(isUp ? 'border-success' : 'border-danger');
    }

    async function fetchStatus() {
        try {
            // Fetch services status
            const servicesResp = await fetch('/health/services');
            const servicesData = await servicesResp.json();

            // Update core services
            const db = servicesData.services?.database || {};
            updateServiceCard('postgresqlCard', 'postgresqlStatus', 'postgresqlDetails',
                db.status, db.latency_ms ? `${db.latency_ms}ms latency` : db.error);

            const redis = servicesData.services?.redis || {};
            updateServiceCard('redisCard', 'redisStatus', 'redisDetails',
                redis.status, redis.latency_ms ? `${redis.latency_ms}ms latency` : redis.error);

            const celery = servicesData.services?.celery || {};
            updateServiceCard('celeryCard', 'celeryStatus', 'celeryDetails',
                celery.status, celery.workers ? `${celery.workers} worker(s)` : celery.error);

            const mcp = servicesData.services?.mcp || {};
            updateServiceCard('mcpCard', 'mcpStatus', 'mcpDetails',
                mcp.status, mcp.latency_ms ? `${mcp.latency_ms}ms latency` : mcp.error);

            // Update system info
            document.getElementById('sysEnvironment').textContent = servicesData.system?.environment || '--';
            document.getElementById('sysHostname').textContent = servicesData.system?.hostname || '--';
            document.getElementById('sysPid').textContent = servicesData.system?.pid || '--';

            // Update uptime info badge with environment
            const uptimeEl = document.getElementById('uptimeInfo');
            const env = servicesData.system?.environment || 'unknown';
            uptimeEl.textContent = env.charAt(0).toUpperCase() + env.slice(1);
            uptimeEl.className = env === 'production' ? 'badge bg-danger fs-6' : 'badge bg-info fs-6';

            // Update overall status
            const overall = document.getElementById('overallStatus');
            const statusIcon = document.getElementById('statusIcon');
            const statusTitle = document.getElementById('statusTitle');
            const statusMessage = document.getElementById('statusMessage');

            if (servicesData.status === 'healthy') {
                overall.className = 'alert alert-success d-flex align-items-center justify-content-between';
                statusIcon.innerHTML = '<i class="fas fa-check-circle text-success"></i>';
                statusTitle.textContent = 'All Systems Operational';
                statusMessage.textContent = 'All services are running normally';
            } else if (servicesData.status === 'degraded') {
                overall.className = 'alert alert-warning d-flex align-items-center justify-content-between';
                statusIcon.innerHTML = '<i class="fas fa-exclamation-triangle text-warning"></i>';
                statusTitle.textContent = 'Degraded Performance';
                statusMessage.textContent = 'Some services may be experiencing issues';
            } else {
                overall.className = 'alert alert-danger d-flex align-items-center justify-content-between';
                statusIcon.innerHTML = '<i class="fas fa-times-circle text-danger"></i>';
                statusTitle.textContent = 'System Issues Detected';
                statusMessage.textContent = 'Critical services are unavailable';
            }

            // Fetch demo cases status
            const demoResp = await fetch('/health/demo');
            const demoData = await demoResp.json();

            document.getElementById('demoCasesCount').textContent = `${demoData.healthy_cases}/${demoData.total_cases} healthy`;
            document.getElementById('demoCasesCount').className = demoData.status === 'healthy' ? 'badge bg-success' :
                demoData.status === 'degraded' ? 'badge bg-warning' : 'badge bg-danger';

            // Build demo cases grid
            const grid = document.getElementById('demoCasesGrid');
            grid.innerHTML = '';
            for (const [caseKey, caseData] of Object.entries(demoData.cases || {})) {
                const caseNum = caseKey.replace('case_', '');
                const isUp = caseData.status === 'up';
                const col = document.createElement('div');
                col.className = 'col-md-2 col-sm-3 col-4';
                col.innerHTML = `
                    <div class="card ${isUp ? 'border-success' : 'border-danger'} h-100">
                        <div class="card-body text-center py-2">
                            <strong>Case ${caseNum}</strong>
                            <span class="badge ${isUp ? 'bg-success' : 'bg-danger'} d-block mt-1">
                                ${isUp ? 'OK' : 'Down'}
                            </span>
                            ${isUp && caseData.title ? `<small class="text-muted d-block mt-1" style="font-size: 0.7rem;">${caseData.title}</small>` : ''}
                        </div>
                    </div>
                `;
                grid.appendChild(col);
            }

            // Update last check time
            document.getElementById('lastUpdate').textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
            document.getElementById('sysCacheStatus').textContent = 'Active (30s TTL)';

            // Update raw JSON
            document.getElementById('rawJson').textContent = JSON.stringify({services: servicesData, demo: demoData}, null, 2);

        } catch (e) {
            console.error('Status fetch error:', e);
            document.getElementById('overallStatus').className = 'alert alert-danger d-flex align-items-center justify-content-between';
            document.getElementById('statusIcon').innerHTML = '<i class="fas fa-times-circle text-danger"></i>';
            document.getElementById('statusTitle').textContent = 'Error Fetching Status';
            document.getElementById('statusMessage').textContent = e.message;
        }
    }

    // Initial fetch
    fetchStatus();

    // Auto-refresh every 30 seconds
    autoRefreshInterval = setInterval(fetchStatus, 30000);

    // Manual refresh button
    document.getElementById('refreshBtn').addEventListener('click', function() {
        this.disabled = true;
        this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Refreshing...';
        fetchStatus().finally(() => {
            this.disabled = false;
            this.innerHTML = '<i class="fas fa-sync-alt me-2"></i>Refresh';
        });
    });

    // Clear cache button
    document.getElementById('clearCacheBtn').addEventListener('click', async function() {
        try {
            const resp = await fetch('/health/clear-cache');
            const data = await resp.json();
            alert('Health check cache cleared. Refreshing...');
            fetchStatus();
        } catch (e) {
            alert('Error: ' + e.message);
        }
    });

    // Test alert button
    document.getElementById('testAlertBtn').addEventListener('click', async function() {
        if (!confirm('Send a test alert? This will attempt to send an email to the configured recipient.')) return;
        try {
            const resp = await fetch('/health/test-alert', {method: 'POST'});
            const data = await resp.json();
            if (data.success) {
                alert('Test alert sent successfully!');
            } else {
                alert('Alert not sent: ' + (data.message || 'Unknown error'));
            }
        } catch (e) {
            alert('Error: ' + e.message);
        }
    });

    // Error log functions
    async function fetchErrors() {
        try {
            const resp = await fetch('/health/errors?limit=20');
            const data = await resp.json();

            // Update stats
            const stats = data.stats || {};
            const statsEl = document.getElementById('errorStats');
            const lastHour = stats.last_hour || 0;
            if (lastHour > 0) {
                statsEl.className = 'badge bg-danger';
                statsEl.textContent = `${lastHour} errors (last hour)`;
            } else if (stats.total_captured > 0) {
                statsEl.className = 'badge bg-warning';
                statsEl.textContent = `${stats.total_captured} total`;
            } else {
                statsEl.className = 'badge bg-success';
                statsEl.textContent = 'No errors';
            }

            // Update card border based on recent errors
            const card = document.getElementById('errorLogCard');
            card.classList.remove('border-success', 'border-danger', 'border-warning');
            if (lastHour > 0) {
                card.classList.add('border-danger');
            } else if (stats.total_captured > 0) {
                card.classList.add('border-warning');
            } else {
                card.classList.add('border-success');
            }

            // Build error list
            const listEl = document.getElementById('errorList');
            const errors = data.errors || [];

            if (errors.length === 0) {
                listEl.innerHTML = '<div class="text-center text-muted py-3"><i class="fas fa-check-circle text-success me-2"></i>No errors recorded</div>';
                return;
            }

            let html = '<div class="table-responsive"><table class="table table-sm table-hover mb-0">';
            html += '<thead><tr><th>Time</th><th>Type</th><th>Path</th><th>Message</th><th></th></tr></thead><tbody>';

            for (const err of errors) {
                const time = new Date(err.timestamp).toLocaleString();
                const shortMsg = (err.error_message || '').substring(0, 60) + ((err.error_message || '').length > 60 ? '...' : '');
                html += `
                    <tr class="error-row" data-error='${JSON.stringify(err).replace(/'/g, "\\'")}'>
                        <td class="text-nowrap"><small>${time}</small></td>
                        <td><span class="badge bg-danger">${err.error_type}</span></td>
                        <td><code>${err.path || '-'}</code></td>
                        <td><small>${shortMsg}</small></td>
                        <td><button class="btn btn-sm btn-outline-info view-error-btn">Details</button></td>
                    </tr>
                `;
            }

            html += '</tbody></table></div>';
            listEl.innerHTML = html;

            // Add click handlers for detail buttons
            document.querySelectorAll('.view-error-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    const row = this.closest('.error-row');
                    const errData = JSON.parse(row.dataset.error);
                    showErrorDetails(errData);
                });
            });

        } catch (e) {
            console.error('Error fetching errors:', e);
            document.getElementById('errorList').innerHTML = '<div class="text-danger">Failed to load error log</div>';
        }
    }

    function showErrorDetails(err) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header bg-danger text-white">
                        <h5 class="modal-title">${err.error_type}</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p><strong>Time:</strong> ${new Date(err.timestamp).toLocaleString()}</p>
                        <p><strong>Path:</strong> <code>${err.path || '-'}</code> (${err.method || '-'})</p>
                        <p><strong>Message:</strong> ${err.error_message}</p>
                        ${err.user_id ? `<p><strong>User ID:</strong> ${err.user_id}</p>` : ''}
                        ${err.remote_addr ? `<p><strong>IP:</strong> ${err.remote_addr}</p>` : ''}
                        ${err.traceback ? `<h6>Traceback:</h6><pre class="bg-light p-2" style="max-height: 300px; overflow-y: auto; font-size: 0.75rem;">${err.traceback}</pre>` : ''}
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        modal.addEventListener('hidden.bs.modal', () => modal.remove());
    }

    // Activity log functions
    async function fetchActivities() {
        try {
            const resp = await fetch('/health/activities?limit=30');
            const data = await resp.json();

            // Update stats
            const stats = data.stats || {};
            const statsEl = document.getElementById('activityStats');
            const lastHour = stats.last_hour || 0;
            const uniqueUsers = stats.unique_users_last_hour || 0;
            if (lastHour > 0) {
                statsEl.className = 'badge bg-info';
                statsEl.textContent = `${lastHour} actions (${uniqueUsers} users)`;
            } else {
                statsEl.className = 'badge bg-secondary';
                statsEl.textContent = 'No recent activity';
            }

            // Build activity list
            const listEl = document.getElementById('activityList');
            const activities = data.activities || [];

            if (activities.length === 0) {
                listEl.innerHTML = '<div class="text-center text-muted py-3"><i class="fas fa-check-circle text-success me-2"></i>No activity recorded</div>';
                return;
            }

            let html = '<div class="list-group list-group-flush">';
            for (const act of activities) {
                const time = new Date(act.timestamp).toLocaleTimeString();
                const categoryBadge = {
                    'auth': 'bg-success',
                    'document': 'bg-primary',
                    'pipeline': 'bg-info',
                    'admin': 'bg-warning',
                    'page_view': 'bg-secondary'
                }[act.category] || 'bg-light text-dark';

                const botBadge = act.is_bot ? '<span class="badge bg-dark ms-1" title="Suspected bot">BOT</span>' : '';
                html += `
                    <div class="list-group-item px-0 py-2${act.is_bot ? ' opacity-50' : ''}">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <span class="badge ${categoryBadge} me-1">${act.category}</span>
                                <strong>${act.username || 'anonymous'}</strong>${botBadge}
                                <br><small class="text-muted">${act.action}</small>
                            </div>
                            <small class="text-muted text-nowrap">${time}</small>
                        </div>
                    </div>
                `;
            }
            html += '</div>';
            listEl.innerHTML = html;

        } catch (e) {
            console.error('Error fetching activities:', e);
            document.getElementById('activityList').innerHTML = '<div class="text-danger">Failed to load activity log</div>';
        }
    }

    // Fetch on load
    fetchActivities();
    fetchErrors();

    // Refresh every 30 seconds
    setInterval(fetchActivities, 30000);
    setInterval(fetchErrors, 30000);

    // Clear activities button
    document.getElementById('clearActivitiesBtn').addEventListener('click', async function() {
        if (!confirm('Clear all recorded activities?')) return;
        try {
            await fetch('/health/activities/clear', {method: 'POST'});
            fetchActivities();
        } catch (e) {
            alert('Error: ' + e.message);
        }
    });

    // Clear errors button
    document.getElementById('clearErrorsBtn').addEventListener('click', async function() {
        if (!confirm('Clear all recorded errors?')) return;
        try {
            await fetch('/health/errors/clear', {method: 'POST'});
            fetchErrors();
        } catch (e) {
            alert('Error: ' + e.message);
        }
    });

    // Test error button
    document.getElementById('testErrorBtn').addEventListener('click', async function() {
        if (!confirm('Generate a test error? This will create a 500 error to test error tracking and alerting.')) return;
        try {
            await fetch('/health/errors/test', {method: 'POST'});
        } catch (e) {
            // Expected to fail with 500
        }
        setTimeout(fetchErrors, 500);
    });
});
