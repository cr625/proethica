(function() {
    var TAB_NAMES = {
        'fullgraph': 'Entities',
        'graph': 'Flow',
        'provisions': 'Provisions',
        'precedents': 'Precedents',
        'questions': 'Q&C',
        'decisionpoints': 'Decisions',
        'timeline': 'Timeline',
        'narrative': 'Narrative'
    };

    var TAB_BUTTON_IDS = {
        'fullgraph': 'fullgraph-tab',
        'graph': 'graph-tab',
        'provisions': 'provisions-tab',
        'precedents': 'precedents-tab',
        'questions': 'questions-tab',
        'decisionpoints': 'decision-points-tab',
        'timeline': 'timeline-tab',
        'narrative': 'narrative-tab'
    };

    function getActiveTabPaneId() {
        var active = document.querySelector('#reviewTabContent > .tab-pane.active');
        return active ? active.id : null;
    }

    function showEntityToast(uri, entityLabel, results) {
        var container = document.getElementById('entity-nav-toast-container');
        if (!container) return;

        // Remove any existing toast
        var existing = container.querySelector('.toast');
        if (existing) {
            var bsToast = bootstrap.Toast.getInstance(existing);
            if (bsToast) bsToast.dispose();
            existing.remove();
        }

        var linksHtml = '';
        for (var i = 0; i < results.length; i++) {
            var r = results[i];
            var tabName = TAB_NAMES[r.paneId] || r.paneId;
            linksHtml += '<button class="btn btn-sm btn-outline-primary me-1 mb-1" '
                + 'data-nav-pane="' + r.paneId + '" data-nav-uri="' + uri.replace(/"/g, '&quot;') + '">'
                + '<i class="bi bi-arrow-right-circle"></i> ' + tabName
                + '</button>';
        }

        var toastEl = document.createElement('div');
        toastEl.className = 'toast show';
        toastEl.setAttribute('role', 'alert');
        toastEl.innerHTML = '<div class="toast-header">'
            + '<strong class="me-auto">Find in other views</strong>'
            + '<small class="text-muted">' + entityLabel + '</small>'
            + '<button type="button" class="btn-close" data-bs-dismiss="toast"></button>'
            + '</div>'
            + '<div class="toast-body">' + linksHtml + '</div>';

        container.appendChild(toastEl);

        var toast = new bootstrap.Toast(toastEl, { delay: 6000 });
        toast.show();

        // Handle navigation button clicks
        toastEl.addEventListener('click', function(e) {
            var btn = e.target.closest('[data-nav-pane]');
            if (!btn) return;
            var paneId = btn.dataset.navPane;
            var navUri = btn.dataset.navUri;
            navigateToEntityInTab(paneId, navUri);
            toast.hide();
        });
    }

    function navigateToEntityInTab(paneId, uri) {
        var tabBtnId = TAB_BUTTON_IDS[paneId];
        if (!tabBtnId) return;
        var tabBtn = document.getElementById(tabBtnId);
        if (!tabBtn) return;

        // Switch to the tab
        var bsTab = bootstrap.Tab.getOrCreateInstance(tabBtn);
        bsTab.show();

        // After tab transition, find and highlight the entity
        setTimeout(function() {
            var pane = document.getElementById(paneId);
            if (!pane) return;
            var target = pane.querySelector('[data-entity-uri="' + uri + '"]');
            if (!target) return;

            // Auto-expand accordion if target is inside a collapsed one
            var accordionBody = target.closest('.accordion-collapse');
            if (accordionBody && !accordionBody.classList.contains('show')) {
                var bsCollapse = bootstrap.Collapse.getOrCreateInstance(accordionBody, {toggle: false});
                bsCollapse.show();
            }

            target.scrollIntoView({ behavior: 'smooth', block: 'center' });

            // Apply highlight pulse
            target.classList.add('entity-highlight-pulse');
            setTimeout(function() {
                target.classList.remove('entity-highlight-pulse');
            }, 1500);
        }, 200);
    }

    document.addEventListener('entity-navigate', function(e) {
        var uri = e.detail.uri;
        if (!uri) return;

        var results = window.findEntityInTabs(uri);
        var activePaneId = getActiveTabPaneId();

        // Filter out current tab
        var otherResults = results.filter(function(r) {
            return r.paneId !== activePaneId;
        });

        if (otherResults.length === 0) return;

        // Get entity label
        var entityLabel = uri;
        if (window.ENTITY_LOOKUP && window.ENTITY_LOOKUP.byUri && window.ENTITY_LOOKUP.byUri[uri]) {
            entityLabel = window.ENTITY_LOOKUP.byUri[uri].label;
        } else if (uri.indexOf('#') !== -1) {
            entityLabel = uri.split('#').pop();
        }

        showEntityToast(uri, entityLabel, otherResults);
    });
})();
