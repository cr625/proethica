    const totalDecisions = (window.STEP5_DECISIONS || {}).totalDecisions ?? 0;
    let currentDecision = 0;

    function showDecision(index) {
        if (index < 0 || index >= totalDecisions) return;

        // Hide all panels
        document.querySelectorAll('.decision-panel').forEach(panel => {
            panel.classList.add('d-none');
        });

        // Show selected panel
        const targetPanel = document.getElementById('decision-' + index);
        if (targetPanel) {
            targetPanel.classList.remove('d-none');
        }

        // Update nav buttons
        document.querySelectorAll('.decision-nav-btn').forEach((btn, i) => {
            btn.classList.remove('active');
            if (i === index) {
                btn.classList.add('active');
            }
        });

        // Update progress text
        document.getElementById('decision-progress').textContent =
            'Decision ' + (index + 1) + ' of ' + totalDecisions;

        currentDecision = index;

        // Scroll to top of content
        document.getElementById('decision-content').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Keyboard navigation
    document.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
            showDecision(currentDecision + 1);
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
            showDecision(currentDecision - 1);
        }
    });
