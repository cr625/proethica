/**
 * Ontology Label Popovers -- shared infrastructure for entity label popovers.
 *
 * Requires:
 *   - Bootstrap 5 (Popover component)
 *   - ontology-labels.css (type badge classes)
 *   - window.ENTITY_LOOKUP (optional, for enrichment from URI lookup)
 *
 * Reads data-entity-* attributes from .onto-label elements:
 *   data-entity-type, data-entity-pass, data-entity-source,
 *   data-entity-definition, data-entity-uri
 */

function getPopoverPassClass(pass) {
    switch(parseInt(pass)) {
        case 1: return 'bg-primary';
        case 2: return 'bg-success';
        case 3: return 'bg-warning text-dark';
        case 4: return 'bg-danger';
        default: return 'bg-secondary';
    }
}

function getPopoverTypeClass(type) {
    if (!type) return 'bg-secondary';
    var t = type.toLowerCase();
    if (t.includes('role')) return 'onto-type-roles';
    if (t.includes('state')) return 'onto-type-states';
    if (t.includes('resource')) return 'onto-type-resources';
    if (t.includes('principle')) return 'onto-type-principles';
    if (t.includes('obligation')) return 'onto-type-obligations';
    if (t.includes('constraint')) return 'onto-type-constraints';
    if (t.includes('capability')) return 'onto-type-capabilities';
    if (t.includes('action') || t.includes('temporal')) return 'onto-type-actions';
    if (t.includes('event')) return 'onto-type-events';
    return 'bg-secondary';
}

function buildPopoverContent(el) {
    var entityType = el.dataset.entityType || '';
    var entityPass = el.dataset.entityPass || '';
    var entitySource = el.dataset.entitySource || 'case';
    var entityDef = el.dataset.entityDefinition || '';
    var entityUri = el.dataset.entityUri || '';

    // Unknown entities
    if (el.classList.contains('onto-label-unknown')) {
        var unknownContent = '<div class="onto-popover-content">';
        unknownContent += '<div class="text-muted small mb-1"><i class="bi bi-question-circle"></i> Not found in case entities</div>';
        if (entityUri) {
            unknownContent += '<div class="onto-uri"><i class="bi bi-link-45deg"></i> ' + entityUri + '</div>';
        }
        unknownContent += '</div>';
        return unknownContent;
    }

    var content = '<div class="onto-popover-content">';
    if (entityType || entityPass || entitySource === 'ontology') {
        content += '<div class="d-flex align-items-center gap-2 mb-2">';
        if (entityType) {
            content += '<span class="badge ' + getPopoverTypeClass(entityType) + '" style="font-size: 0.7rem;">' + entityType + '</span>';
        }
        if (entitySource === 'ontology') {
            content += '<span class="badge bg-dark" style="font-size: 0.65rem;">Ontology</span>';
        } else if (entityPass) {
            content += '<span class="badge ' + getPopoverPassClass(entityPass) + '" style="font-size: 0.65rem;">Pass ' + entityPass + '</span>';
        }
        content += '</div>';
    }
    if (entityDef) {
        var truncatedDef = entityDef.length > 200 ? entityDef.substring(0, 200) + '...' : entityDef;
        content += '<div class="onto-definition">' + truncatedDef + '</div>';
    }
    if (entityUri) {
        content += '<div class="onto-uri"><i class="bi bi-link-45deg"></i> ' + entityUri + '</div>';
    }
    content += '</div>';
    return content;
}

/**
 * Initialize Bootstrap popovers for .onto-label elements within a container.
 * Skips elements that already have popovers initialized.
 */
function initializePopovers(container) {
    if (typeof bootstrap === 'undefined') return;
    var labels = container.querySelectorAll('.onto-label[data-bs-toggle="popover"]:not([aria-describedby])');
    labels.forEach(function(el) {
        new bootstrap.Popover(el, {
            container: 'body',
            sanitize: false,
            content: buildPopoverContent(el),
            html: true
        });
    });
}

/**
 * Find all tab panes that contain an entity with the given URI.
 * Returns array of { paneId, element } objects.
 */
function findEntityInTabs(uri) {
    var results = [];
    if (!uri) return results;
    document.querySelectorAll('.tab-pane').forEach(function(pane) {
        var match = pane.querySelector('[data-entity-uri="' + uri + '"]');
        if (match) {
            results.push({ paneId: pane.id, element: match });
        }
    });
    return results;
}
window.findEntityInTabs = findEntityInTabs;

// Delegated click handler for cross-view entity navigation
document.addEventListener('click', function(e) {
    var label = e.target.closest('.onto-label');
    if (!label) return;
    var uri = label.dataset.entityUri;
    if (!uri) return;
    document.dispatchEvent(new CustomEvent('entity-navigate', {
        detail: { uri: uri, sourceElement: label }
    }));
});

// Auto-initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        if (typeof bootstrap === 'undefined') {
            console.warn('Bootstrap not available for ontology label popovers');
            return;
        }

        // Initialize all popovers on page
        initializePopovers(document);

        // Reinitialize popovers when switching tabs (needed for hidden tab content)
        document.querySelectorAll('button[data-bs-toggle="tab"]').forEach(function(tabEl) {
            tabEl.addEventListener('shown.bs.tab', function(event) {
                setTimeout(function() {
                    var tabPane = document.querySelector(event.target.dataset.bsTarget);
                    if (tabPane) {
                        initializePopovers(tabPane);
                    }
                }, 50);
            });
        });
    }, 100);
});
