/**
 * Ontology Label Popovers -- shared infrastructure for entity label popovers
 * and inline text annotation.
 *
 * Requires:
 *   - Bootstrap 5 (Popover component)
 *   - ontology-labels.css (type badge classes, defined in page styles)
 *   - window.ENTITY_LOOKUP (optional, for enrichment from URI lookup)
 *
 * Reads data-entity-* attributes from .onto-label elements:
 *   data-entity-type, data-entity-pass, data-entity-source,
 *   data-entity-definition, data-entity-uri, data-alias-types,
 *   data-ontology-target
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

/**
 * Build OntServe entity URL from ontology target and URI fragment.
 * @param {string} ontserveBaseUrl - Base URL of OntServe (e.g., 'http://localhost:5003')
 * @param {string} ontTarget - Ontology name (e.g., 'proethica-case-7')
 * @param {string} uri - Full entity URI containing '#' fragment
 * @returns {string} Full OntServe URL, or empty string if not constructable
 */
function buildOntserveEntityUrl(ontserveBaseUrl, ontTarget, uri) {
    if (!ontserveBaseUrl || !ontTarget || !uri || !uri.includes('#')) return '';
    var fragment = uri.split('#').pop();
    if (!fragment) return '';
    return ontserveBaseUrl + '/entity/' + encodeURIComponent(ontTarget) + '/' + encodeURIComponent(fragment);
}

function buildPopoverContent(el, ontserveBaseUrl) {
    var entityType = el.dataset.entityType || '';
    var entityPass = el.dataset.entityPass || '';
    var entitySource = el.dataset.entitySource || 'case';
    var entityDef = el.dataset.entityDefinition || '';
    var entityUri = el.dataset.entityUri || '';
    var ontTarget = el.dataset.ontologyTarget || '';
    var aliasTypesRaw = el.dataset.aliasTypes || '[]';
    var aliasTypes;
    try { aliasTypes = JSON.parse(aliasTypesRaw); } catch(e) { aliasTypes = []; }

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

    // Build type badges
    var typeBadgesHtml = '';
    if (aliasTypes.length > 1) {
        typeBadgesHtml = aliasTypes.map(function(t) {
            return '<span class="badge onto-type-badge ' + getPopoverTypeClass(t) + '">' + t + '</span>';
        }).join('');
    } else if (entityType) {
        typeBadgesHtml = '<span class="badge onto-type-badge ' + getPopoverTypeClass(entityType) + '">' + entityType + '</span>';
    }

    // Source badge
    var sourceBadge = '';
    if (entitySource === 'ontology') {
        sourceBadge = '<span class="badge bg-primary onto-type-badge">Ontology</span>';
    } else if (entityPass) {
        sourceBadge = '<span class="badge ' + getPopoverPassClass(entityPass) + ' onto-type-badge">Pass ' + entityPass + '</span>';
    } else {
        sourceBadge = '<span class="badge bg-secondary onto-type-badge">Case</span>';
    }

    // Truncate long definitions
    var displayDef = entityDef;
    if (displayDef && displayDef.length > 300) {
        displayDef = displayDef.substring(0, 300) + '...';
    }

    var content = '<div class="onto-popover-content">';
    if (typeBadgesHtml || sourceBadge) {
        content += '<div class="d-flex gap-1 flex-wrap mb-2">' + typeBadgesHtml + sourceBadge + '</div>';
    }
    if (displayDef) {
        content += '<div class="onto-definition">' + displayDef + '</div>';
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
 *
 * @param {Element} container - DOM element to search within
 * @param {string} [ontserveBaseUrl] - OntServe base URL for entity links
 */
function initializePopovers(container, ontserveBaseUrl) {
    if (typeof bootstrap === 'undefined') return;
    var labels = container.querySelectorAll('.onto-label[data-bs-toggle="popover"]');
    labels.forEach(function(el) {
        // Skip elements that already have a popover instance
        if (bootstrap.Popover.getInstance(el)) return;
        new bootstrap.Popover(el, {
            container: 'body',
            sanitize: false,
            content: buildPopoverContent(el, ontserveBaseUrl),
            html: true
        });

        // Click handler: open OntServe entity page in new tab
        var ontTarget = el.dataset.ontologyTarget || '';
        var entityUri = el.dataset.entityUri || '';
        var ontserveUrl = buildOntserveEntityUrl(ontserveBaseUrl || '', ontTarget, entityUri);
        if (ontserveUrl) {
            el.addEventListener('click', function(e) {
                e.preventDefault();
                window.open(ontserveUrl, '_blank', 'noopener');
            });
        }
    });
}

/**
 * Scan text within a container for entity label matches and wrap them in
 * popover-enabled .onto-label spans.
 *
 * @param {Element} container - DOM element containing text to annotate
 * @param {Object} entityLookup - Map of lowercase label -> entity data
 * @param {Object} [options]
 * @param {Set} [options.skipWords] - Labels to skip even if they match
 * @param {number} [options.minLabelLength] - Minimum label length (default 4)
 * @param {string} [options.excludeSelector] - CSS selector for elements to skip
 */
function scanTextForEntities(container, entityLookup, options) {
    options = options || {};
    var skipWords = options.skipWords || new Set([
        'state', 'action', 'event', 'role', 'resource', 'principle',
        'obligation', 'constraint', 'capability',
        'nspe code of ethics', 'code of ethics'
    ]);
    var minLen = options.minLabelLength || 4;
    var excludeSelector = options.excludeSelector || '.onto-label, a, button, .badge';

    // Sort labels longest-first for greedy matching
    var sortedLabels = Object.keys(entityLookup)
        .filter(function(l) { return l.length >= minLen && !skipWords.has(l.toLowerCase()); })
        .sort(function(a, b) { return b.length - a.length; });

    if (sortedLabels.length === 0) return;

    var pattern = new RegExp(
        '\\b(' + sortedLabels.map(function(l) { return l.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).join('|') + ')\\b',
        'gi'
    );

    // Walk text nodes
    var cardBodies = container.querySelectorAll('.card-body');
    cardBodies.forEach(function(cardBody) {
        // Skip excluded sections (e.g., NSPE references)
        if (options.skipSectionTest && options.skipSectionTest(cardBody)) return;

        var walker = document.createTreeWalker(cardBody, NodeFilter.SHOW_TEXT, null, false);
        var textNodes = [];
        var node;
        while (node = walker.nextNode()) {
            if (node.textContent.trim() && node.parentElement.closest(excludeSelector) === null) {
                textNodes.push(node);
            }
        }

        textNodes.forEach(function(textNode) {
            var text = textNode.textContent;
            var matches = [];
            var match;

            while ((match = pattern.exec(text)) !== null) {
                var lowerMatch = match[1].toLowerCase();
                if (entityLookup[lowerMatch]) {
                    matches.push({
                        index: match.index,
                        length: match[1].length,
                        text: match[1],
                        entity: entityLookup[lowerMatch]
                    });
                }
            }

            if (matches.length === 0) return;

            // Remove overlapping matches (keep longest)
            matches.sort(function(a, b) { return a.index - b.index; });
            var nonOverlapping = [];
            for (var i = 0; i < matches.length; i++) {
                var last = nonOverlapping[nonOverlapping.length - 1];
                if (!last || matches[i].index >= last.index + last.length) {
                    nonOverlapping.push(matches[i]);
                }
            }

            var fragment = document.createDocumentFragment();
            var lastIndex = 0;

            nonOverlapping.forEach(function(m) {
                if (m.index > lastIndex) {
                    fragment.appendChild(document.createTextNode(text.substring(lastIndex, m.index)));
                }

                var span = document.createElement('span');
                span.className = 'onto-label';
                if (m.entity.source === 'ontology') span.className += ' onto-source-ontology';
                span.textContent = m.text;
                span.tabIndex = 0;
                span.setAttribute('data-bs-toggle', 'popover');
                span.setAttribute('data-bs-trigger', 'hover focus');
                span.setAttribute('data-bs-html', 'true');
                span.setAttribute('data-bs-placement', 'top');
                span.setAttribute('data-entity-type', m.entity.entityType || '');
                span.setAttribute('data-entity-source', m.entity.source || 'case');
                span.setAttribute('data-entity-definition', m.entity.definition || '');
                span.setAttribute('data-entity-uri', m.entity.uri || '');
                span.setAttribute('data-alias-types', JSON.stringify(m.entity.aliasTypes || []));
                span.setAttribute('data-ontology-target', m.entity.ontologyTarget || '');
                span.setAttribute('title', m.entity.label || m.text);

                if (m.entity.ontologyTarget && m.entity.uri && m.entity.uri.includes('#')) {
                    span.style.cursor = 'pointer';
                }

                fragment.appendChild(span);
                lastIndex = m.index + m.length;
            });

            if (lastIndex < text.length) {
                fragment.appendChild(document.createTextNode(text.substring(lastIndex)));
            }

            textNode.parentNode.replaceChild(fragment, textNode);
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
