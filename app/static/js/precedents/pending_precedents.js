document.addEventListener('DOMContentLoaded', function() {
    // Single URL ingest buttons
    document.querySelectorAll('.ingest-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const url = this.dataset.url;
            const button = this;
            button.disabled = true;
            button.textContent = 'Ingesting...';

            fetch((window.PENDING_PRECEDENTS || {}).ingestUrl, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url: url, world_id: 1})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    button.textContent = 'Done';
                    button.classList.remove('btn-outline-primary');
                    button.classList.add('btn-success');
                    // Refresh after short delay
                    setTimeout(() => location.reload(), 1000);
                } else {
                    button.textContent = 'Failed';
                    button.classList.remove('btn-outline-primary');
                    button.classList.add('btn-danger');
                }
            })
            .catch(error => {
                button.textContent = 'Error';
                button.classList.add('btn-danger');
            });
        });
    });

    // Batch ingest button
    const batchBtn = document.getElementById('ingestBatchBtn');
    if (batchBtn) {
        batchBtn.addEventListener('click', function() {
            batchBtn.disabled = true;
            batchBtn.textContent = 'Ingesting...';

            fetch((window.PENDING_PRECEDENTS || {}).ingestUrl, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({max_cases: 10, world_id: 1})
            })
            .then(response => response.json())
            .then(data => {
                const ingested = data.ingested ? data.ingested.length : 0;
                batchBtn.textContent = `Ingested ${ingested} cases`;
                // Refresh after short delay
                setTimeout(() => location.reload(), 1500);
            })
            .catch(error => {
                batchBtn.textContent = 'Error';
                batchBtn.classList.add('btn-danger');
            });
        });
    }
});
