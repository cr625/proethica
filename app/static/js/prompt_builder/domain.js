function viewPerformance(templateId) {
    const modal = new bootstrap.Modal(document.getElementById('performanceModal'));
    document.getElementById('performanceContent').innerHTML = `
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading performance data...</p>
        </div>
    `;
    modal.show();
    
    fetch(`/prompt-builder/api/template/${templateId}/performance`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const stats = data.statistics;
                const recentUses = data.recent_uses;
                
                document.getElementById('performanceContent').innerHTML = `
                    <div class="row mb-4">
                        <div class="col-md-3 text-center">
                            <h3>${stats.total_uses}</h3>
                            <small class="text-muted">Total Uses</small>
                        </div>
                        <div class="col-md-3 text-center">
                            <h3>${stats.avg_performance ? stats.avg_performance + '%' : '-'}</h3>
                            <small class="text-muted">Avg Performance</small>
                        </div>
                        <div class="col-md-3 text-center">
                            <h3>${stats.success_rate}%</h3>
                            <small class="text-muted">Success Rate</small>
                        </div>
                        <div class="col-md-3 text-center">
                            <h3>${stats.avg_processing_time ? stats.avg_processing_time + 'ms' : '-'}</h3>
                            <small class="text-muted">Avg Time</small>
                        </div>
                    </div>
                    
                    ${recentUses.length > 0 ? `
                    <h6>Recent Usage:</h6>
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>Case ID</th>
                                    <th>Section</th>
                                    <th>Performance</th>
                                    <th>Concepts</th>
                                    <th>Date</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${recentUses.map(use => `
                                    <tr>
                                        <td>${use.case_id || '-'}</td>
                                        <td>${use.section_title || '-'}</td>
                                        <td>${use.performance_score ? (use.performance_score * 100).toFixed(1) + '%' : '-'}</td>
                                        <td>${use.concepts_extracted || '-'}</td>
                                        <td>${use.created_at ? new Date(use.created_at).toLocaleDateString() : '-'}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                    ` : '<p class="text-muted">No usage data available yet.</p>'}
                `;
            } else {
                document.getElementById('performanceContent').innerHTML = `
                    <div class="alert alert-danger">Error loading performance data: ${data.error}</div>
                `;
            }
        })
        .catch(error => {
            document.getElementById('performanceContent').innerHTML = `
                <div class="alert alert-danger">Error: ${error.message}</div>
            `;
        });
}

function duplicateTemplate(templateId) {
    // Implementation for duplicating a template
    if (confirm('Create a copy of this template?')) {
        // Here you would implement template duplication
        alert('Template duplication would be implemented here');
    }
}

function deactivateTemplate(templateId) {
    if (confirm('Are you sure you want to deactivate this template?')) {
        // Implementation for deactivating a template
        alert('Template deactivation would be implemented here');
    }
}
