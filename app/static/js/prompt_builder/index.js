function showDomainAnalytics(domain) {
    // Implementation for showing domain analytics
    const modal = new bootstrap.Modal(document.getElementById('analyticsModal'));
    document.getElementById('analyticsContent').innerHTML = `
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading analytics for ${domain} domain...</p>
        </div>
    `;
    modal.show();
    
    // Here you would fetch and display analytics data
    setTimeout(() => {
        document.getElementById('analyticsContent').innerHTML = `
            <p>Analytics for <strong>${domain}</strong> domain would be displayed here.</p>
            <p>This could include template performance, usage patterns, success rates, etc.</p>
        `;
    }, 1000);
}
