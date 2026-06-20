document.querySelectorAll('#narrative .narrative-header, #narrative .character-toggle').forEach(function(header) {
    var target = document.querySelector(header.dataset.bsTarget);
    if (!target) return;
    var chevron = header.querySelector('.narrative-chevron');
    if (!chevron) return;
    target.addEventListener('show.bs.collapse', function() {
        chevron.classList.replace('bi-chevron-right', 'bi-chevron-down');
    });
    target.addEventListener('hide.bs.collapse', function() {
        chevron.classList.replace('bi-chevron-down', 'bi-chevron-right');
    });
});
