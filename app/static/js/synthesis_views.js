/*
 * Synthesis view behaviors, shared by the validation-study case evaluation
 * interface and the Step-4 review tabs. Initializes the popovers and collapse
 * chevrons used by the shared view partials (app/templates/shared/synthviews/).
 *
 * Idempotent and scope-agnostic: it initializes any not-yet-initialized
 * popover/toggle inside an element carrying the `.synthview` class, so it works
 * whether the views are all on one page (study) or inside Bootstrap tab panes
 * (Step-4 review). Safe to call multiple times.
 */
(function () {
  function initSynthViews(root) {
    root = root || document;
    if (typeof bootstrap === 'undefined' || !bootstrap.Popover) {
      return;
    }
    // Popovers: character mentions, provision-code badges, role badges,
    // provision type chips, secondary-conclusion chips. Skip any element
    // already initialized.
    var popoverSelectors = [
      '.char-mention[data-bs-toggle="popover"]',
      '.provision-badge[data-bs-toggle="popover"]',
      '.role-badge[data-bs-toggle="popover"]',
      '.provision-type-chip[data-bs-toggle="popover"]',
      '.qc-secondary-chip[data-bs-toggle="popover"]',
      '.tl-grounding-chip[data-bs-toggle="popover"]'
    ];
    root.querySelectorAll(popoverSelectors.join(',')).forEach(function (el) {
      if (!bootstrap.Popover.getInstance(el)) {
        new bootstrap.Popover(el);
      }
    });

    // A popover-anchored link nested inside a collapse-toggle row must not also
    // fire the parent's collapse handler. Bind once at window capture phase.
    if (!window.__synthviewClickGuard) {
      window.__synthviewClickGuard = true;
      window.addEventListener('click', function (e) {
        if (e.target && e.target.closest && e.target.closest('.char-mention')) {
          e.stopPropagation();
          e.stopImmediatePropagation();
        }
      }, true);
    }
  }

  window.initSynthViews = initSynthViews;
  document.addEventListener('DOMContentLoaded', function () {
    initSynthViews(document);
  });
})();
