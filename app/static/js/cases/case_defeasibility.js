  document.addEventListener('DOMContentLoaded', function () {
    if (typeof bootstrap === 'undefined') return;
    // Explanatory (i) popovers (plain Bootstrap; not entity popovers).
    document.querySelectorAll('.info-popover[data-bs-toggle="popover"]').forEach(function (el) {
      new bootstrap.Popover(el);
    });
    if (typeof initializePopovers !== 'function') return;
    var page = window.CASE_DEFEASIBILITY || {};
    // People and entities named in the case text get the popovers of the case page,
    // from the same label index; the scan runs before the popovers are initialized.
    if (typeof scanTextForEntities === 'function' && page.textEntityLookup) {
      document.querySelectorAll('.defeasibility-case-text').forEach(function (el) {
        scanTextForEntities(el, page.textEntityLookup);
      });
    }
    var container = document.getElementById('defeasibility-content');
    if (container) initializePopovers(container, page.ontserveWebUrl || '');
  });
