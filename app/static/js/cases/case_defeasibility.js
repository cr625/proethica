  document.addEventListener('DOMContentLoaded', function () {
    if (typeof bootstrap === 'undefined' || typeof initializePopovers !== 'function') return;
    var container = document.getElementById('defeasibility-content');
    if (container) initializePopovers(container, (window.CASE_DEFEASIBILITY || {}).ontserveWebUrl || '');
  });
