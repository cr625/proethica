(function() {
    // =====================================================================
    // Bootstrap tooltips
    // =====================================================================
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function(el) { new bootstrap.Tooltip(el); });

    // View Transition API feature detection
    if (!document.startViewTransition) {
        document.documentElement.classList.add('no-view-transitions');
    }

    // =====================================================================
    // Decision maker popover
    // =====================================================================
    var dmChip = document.querySelector('.decision-maker-chip[data-bs-toggle="popover"]');
    if (dmChip) {
        new bootstrap.Popover(dmChip, { container: 'body', sanitize: false });
    }

    var ontserveBaseUrl = window.STEP5_TRAVERSAL.ontserveWebUrl;

    // =====================================================================
    // Option selection
    // =====================================================================
    var optionCards = document.querySelectorAll('.option-card');
    var hiddenInput = document.getElementById('selected-option-index');
    var submitBtn = document.getElementById('submit-choice');

    optionCards.forEach(function(card) {
        card.addEventListener('click', function() {
            optionCards.forEach(function(c) {
                c.classList.remove('selected');
                c.querySelector('.option-unselected').classList.remove('d-none');
                c.querySelector('.option-selected').classList.add('d-none');
            });
            this.classList.add('selected');
            this.querySelector('.option-unselected').classList.add('d-none');
            this.querySelector('.option-selected').classList.remove('d-none');
            hiddenInput.value = this.getAttribute('data-option-index');
            submitBtn.disabled = false;
        });

        card.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.click();
            }
        });
    });

    // =====================================================================
    // Time tracking
    // =====================================================================
    var startTime = Date.now();
    var timeInput = document.getElementById('time-spent');
    document.getElementById('choice-form').addEventListener('submit', function() {
        var elapsed = Math.round((Date.now() - startTime) / 1000);
        timeInput.value = elapsed;
    });

    // =====================================================================
    // Scroll active decision into view in the timeline sidebar
    // =====================================================================
    var activeNode = document.querySelector('.stl-decision.stl-active');
    if (activeNode) {
        var sidebar = document.querySelector('.timeline-sidebar-body');
        if (sidebar) {
            // Delay to let layout settle
            setTimeout(function() {
                activeNode.scrollIntoView({ block: 'center', behavior: 'smooth' });
            }, 200);
        }
    }

    // =====================================================================
    // Entity annotation (inline popovers in text)
    // =====================================================================
    if (window.STEP5_TRAVERSAL.entityLookup) {
    var ENTITY_LOOKUP_BY_LABEL = window.STEP5_TRAVERSAL.entityLookup;

    document.addEventListener('DOMContentLoaded', function() {
        var decisionArea = document.getElementById('decision-area');

        if (decisionArea) {
            scanTextForEntities(decisionArea, ENTITY_LOOKUP_BY_LABEL, {
                excludeSelector: '.onto-label, a, button, .badge, .obligation-chip'
            });
            initializePopovers(decisionArea, ontserveBaseUrl);
        }

        // Initialize obligation chip popovers AFTER entity scanning
        // to avoid DOM mutations breaking popover bindings
        initObligationChipPopovers();
    });
    } else {
    document.addEventListener('DOMContentLoaded', function() {
        initObligationChipPopovers();
    });
    }

    function initObligationChipPopovers() {
        document.querySelectorAll('.obligation-chip[data-bs-toggle="popover"]').forEach(function(chip) {
            // Skip if already initialized
            if (bootstrap.Popover.getInstance(chip)) return;

            var fullLabel = chip.dataset.oblLabel || '';
            var oblType = chip.dataset.oblType || '';
            var definition = chip.dataset.oblDefinition || '';
            var uri = chip.dataset.oblUri || '';

            var defDisplay = definition;
            if (defDisplay.length > 200) {
                defDisplay = defDisplay.substring(0, 200) + '...';
            }

            var content = '<div class="obl-chip-popover">';
            content += '<div class="obl-full-label">' + fullLabel + '</div>';
            if (oblType) {
                content += '<span class="badge onto-type-' + oblType + ' mb-2" style="font-size:0.7rem;">' + oblType + '</span>';
            }
            if (defDisplay) {
                content += '<div class="obl-definition">' + defDisplay + '</div>';
            }

            if (window.STEP5_TRAVERSAL.provisions) {
            var provisions = window.STEP5_TRAVERSAL.provisions;
            for (var p = 0; p < provisions.length; p++) {
                var provWords = provisions[p].label.toLowerCase().split(/\s+/);
                var oblLower = fullLabel.toLowerCase();
                var matchCount = provWords.filter(function(w) { return w.length > 3 && oblLower.indexOf(w) !== -1; }).length;
                if (matchCount >= 2 || (provWords.length <= 3 && matchCount >= 1)) {
                    var provDef = provisions[p].definition;
                    if (provDef.length > 120) provDef = provDef.substring(0, 120) + '...';
                    content += '<div class="obl-provision"><strong>' + provisions[p].label + '</strong>';
                    if (provDef) content += '<br>' + provDef;
                    content += '</div>';
                    break;
                }
            }
            }

            if (uri && uri.indexOf('#') !== -1 && ontserveBaseUrl) {
                var fragment = uri.split('#').pop();
                var ontTarget = '';
                var uriBase = uri.split('#')[0];
                var lastSlash = uriBase.lastIndexOf('/');
                if (lastSlash !== -1) ontTarget = uriBase.substring(lastSlash + 1);
                if (ontTarget && fragment) {
                    var ontUrl = ontserveBaseUrl + '/entity/' + encodeURIComponent(ontTarget) + '/' + encodeURIComponent(fragment);
                    content += '<div class="obl-ontserve-link"><a href="' + ontUrl + '" target="_blank" rel="noopener"><i class="bi bi-box-arrow-up-right me-1"></i>View in OntServe</a></div>';
                }
            }

            content += '</div>';

            new bootstrap.Popover(chip, {
                container: 'body',
                sanitize: false,
                trigger: 'click',
                content: content,
                html: true
            });
        });
    }
})();
