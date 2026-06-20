// Tree node click: scroll to corresponding detail card
document.querySelectorAll('.tree-node[data-target]').forEach(function(node) {
    node.addEventListener('click', function() {
        var targetId = this.getAttribute('data-target');
        var target = document.getElementById(targetId);
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
    node.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            this.click();
        }
    });
});

// Rotate collapse chevron on rationale toggle
document.querySelectorAll('[data-bs-toggle="collapse"]').forEach(function(trigger) {
    var targetId = trigger.getAttribute('href');
    var target = document.querySelector(targetId);
    if (target) {
        target.addEventListener('show.bs.collapse', function() {
            var icon = trigger.querySelector('.bi-chevron-right');
            if (icon) { icon.classList.replace('bi-chevron-right', 'bi-chevron-down'); }
        });
        target.addEventListener('hide.bs.collapse', function() {
            var icon = trigger.querySelector('.bi-chevron-down');
            if (icon) { icon.classList.replace('bi-chevron-down', 'bi-chevron-right'); }
        });
    }
});
