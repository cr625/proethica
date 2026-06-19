document.addEventListener('DOMContentLoaded', function() {
    // Highlight the referenced section when navigating via hash
    function highlightSection() {
        const hash = window.location.hash;
        if (hash) {
            const targetId = hash.substring(1);
            const target = document.getElementById(targetId);

            if (target) {
                // Remove any existing highlights
                document.querySelectorAll('.ref-highlight').forEach(el => {
                    el.classList.remove('ref-highlight');
                });

                // Add highlight to target
                target.classList.add('ref-highlight');

                // Scroll into view with offset for fixed header
                setTimeout(() => {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);
            }
        }
    }

    // Run on page load
    highlightSection();

    // Run on hash change (for in-page navigation)
    window.addEventListener('hashchange', highlightSection);
});
