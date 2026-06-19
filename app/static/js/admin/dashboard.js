// Fetch service status on page load
document.addEventListener('DOMContentLoaded', function() {
    fetchServiceStatus();

    // Test alert button
    document.getElementById('testAlertBtn').addEventListener('click', function() {
        this.disabled = true;
        this.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Sending...';

        fetch('/health/test-alert', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.innerHTML = '<i class="fas fa-check me-2"></i>Sent!';
                    this.classList.remove('btn-outline-warning');
                    this.classList.add('btn-success');
                } else {
                    this.innerHTML = '<i class="fas fa-times me-2"></i>' + (data.message || 'Failed');
                    this.classList.remove('btn-outline-warning');
                    this.classList.add('btn-danger');
                }
                setTimeout(() => {
                    this.innerHTML = '<i class="fas fa-bell me-2"></i>Test Alert';
                    this.classList.remove('btn-success', 'btn-danger');
                    this.classList.add('btn-outline-warning');
                    this.disabled = false;
                }, 3000);
            })
            .catch(err => {
                this.innerHTML = '<i class="fas fa-times me-2"></i>Error';
                this.classList.add('btn-danger');
                this.disabled = false;
            });
    });
});

function fetchServiceStatus() {
    fetch('/health/ready')
        .then(response => response.json())
        .then(data => {
            updateServiceBadge('postgresql', data.checks?.database);
            updateServiceBadge('redis', data.checks?.redis);
            updateServiceBadge('celery', data.checks?.celery);
            updateServiceBadge('mcp', data.checks?.mcp);

            // Update overall health badge
            const overallBadge = document.getElementById('overallHealth');
            if (data.status === 'healthy') {
                overallBadge.className = 'badge bg-success';
                overallBadge.innerHTML = '<i class="fas fa-check-circle me-1"></i>All Systems Operational';
            } else if (data.status === 'degraded') {
                overallBadge.className = 'badge bg-warning';
                overallBadge.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>Degraded';
            } else {
                overallBadge.className = 'badge bg-danger';
                overallBadge.innerHTML = '<i class="fas fa-times-circle me-1"></i>Issues Detected';
            }
        })
        .catch(err => {
            console.error('Failed to fetch health status:', err);
            document.getElementById('overallHealth').className = 'badge bg-danger';
            document.getElementById('overallHealth').innerHTML = '<i class="fas fa-times-circle me-1"></i>Connection Error';
        });
}

function updateServiceBadge(service, check) {
    const badge = document.getElementById(service + 'Status');
    if (!badge) return;

    if (!check) {
        badge.className = 'badge bg-secondary ms-2';
        badge.textContent = '?';
        return;
    }

    if (check.status === 'up') {
        badge.className = 'badge bg-success ms-2';
        badge.textContent = 'OK';
    } else {
        badge.className = 'badge bg-danger ms-2';
        badge.textContent = 'DOWN';
    }
}
