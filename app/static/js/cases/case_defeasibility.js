  document.addEventListener('DOMContentLoaded', function () {
    if (typeof bootstrap === 'undefined') return;
    // Explanatory (i) popovers (plain Bootstrap; not entity popovers).
    document.querySelectorAll('.info-popover[data-bs-toggle="popover"]').forEach(function (el) {
      new bootstrap.Popover(el);
    });
    if (typeof initializePopovers !== 'function') return;
    var container = document.getElementById('defeasibility-content');
    if (container) initializePopovers(container, (window.CASE_DEFEASIBILITY || {}).ontserveWebUrl || '');
  });
