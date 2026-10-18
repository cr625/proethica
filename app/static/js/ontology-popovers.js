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
 *   data-alias-entities, data-ontology-target, data-entity-anchor
 *
 * Lookup entries (window.CASE_DETAIL.entityLookup and the like) carry
 * label, definition, entityType, source, sourcePass, uri, aliasTypes,
 * aliasEntities, aliasActors, ontologyTarget.
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

function escapePopoverHtml(s) {
    return String(s).replace(/[&<>"']/g, function(c) {
        return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
    });
}

/**
 * Parse the contributing entities of a text-grounded alias span.
 * Returns [] for ordinary single-entity spans.
 */
function getAliasEntities(el) {
    try {
        return JSON.parse(el.dataset.aliasEntities || '[]');
    } catch (e) {
        return [];
    }
}

// Definitions longer than this are cut at a word boundary. A derived Agent
// definition (a facet list) is rendered in full instead.
var DEFINITION_LIMIT = 300;

function truncateDefinition(text, limit) {
    text = String(text || '');
    if (text.length <= limit) return text;
    var cut = text.lastIndexOf(' ', limit);
    if (cut < limit / 2) cut = limit;
    return text.substring(0, cut) + '...';
}

/**
 * Split a derived Agent definition ("Participant in this case: performs A and
 * B; bears C; ...") into its lead and one facet per clause.
 */
function splitAgentFacets(definition) {
    var facets = String(definition || '').split(/;\s+/).filter(function(f) { return f.trim(); });
    var lead = '';
    if (facets.length) {
        var colon = facets[0].indexOf(': ');
        if (colon !== -1) {
            lead = facets[0].substring(0, colon);
            facets[0] = facets[0].substring(colon + 2);
        }
    }
    return { lead: lead, facets: facets.map(function(f) { return f.trim().replace(/\.$/, ''); }) };
}

/** Agent definition rendered one facet per line, in full. */
function renderAgentDefinition(definition) {
    var parts = splitAgentFacets(definition);
    if (!parts.lead && parts.facets.length < 2) {
        return '<div class="onto-definition">' + truncateDefinition(definition, DEFINITION_LIMIT) + '</div>';
    }
    var html = '<div class="onto-definition onto-agent-definition">';
    if (parts.lead) html += '<div class="onto-agent-lead">' + parts.lead + '</div>';
    html += '<ul class="onto-facet-list">' + parts.facets.map(function(f) { return '<li>' + f + '</li>'; }).join('') + '</ul>';
    return html + '</div>';
}
window.truncateDefinition = truncateDefinition;
window.splitAgentFacets = splitAgentFacets;

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
    var aliasEntities = getAliasEntities(el);

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

    // Source badge
    var sourceBadge = '';
    if (entitySource === 'ontology') {
        sourceBadge = '<span class="badge bg-primary onto-type-badge">Ontology</span>';
    } else if (entityPass) {
        sourceBadge = '<span class="badge ' + getPopoverPassClass(entityPass) + ' onto-type-badge">Pass ' + entityPass + '</span>';
    } else {
        sourceBadge = '<span class="badge bg-secondary onto-type-badge">Case</span>';
    }

    // Text-grounded alias shared by several entities: list every contributor
    // (type badge + label linking to its own OntServe page) instead of showing
    // one entity's borrowed definition.
    if (aliasEntities.length > 1) {
        var listContent = '<div class="onto-popover-content onto-popover-alias">';
        listContent += '<div class="d-flex gap-1 flex-wrap align-items-center mb-2">' + sourceBadge
            + '<span class="text-muted small">' + aliasEntities.length + ' case entities share this phrase</span></div>';
        listContent += '<ul class="onto-alias-list">';
        aliasEntities.forEach(function(ent) {
            var url = buildOntserveEntityUrl(ontserveBaseUrl || '', ent.ontology_target || '', ent.uri || '');
            var badge = '<span class="badge onto-type-badge ' + getPopoverTypeClass(ent.extraction_type)
                + '">' + escapePopoverHtml(ent.extraction_type || 'entity') + '</span>';
            var name = escapePopoverHtml(ent.label || '');
            listContent += '<li>' + badge
                + (url ? '<a href="' + url + '" target="_blank" rel="noopener">' + name + '</a>'
                       : '<span>' + name + '</span>')
                + '</li>';
        });
        listContent += '</ul></div>';
        return listContent;
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

    // Definition: an Agent's derived definition lists its participation one
    // facet per line in full; any other definition is cut at a word boundary.
    var definitionHtml = '';
    if (entityDef) {
        definitionHtml = entityType === 'Agent'
            ? renderAgentDefinition(entityDef)
            : '<div class="onto-definition">' + truncateDefinition(entityDef, DEFINITION_LIMIT) + '</div>';
    }

    var content = '<div class="onto-popover-content">';
    if (typeBadgesHtml || sourceBadge) {
        content += '<div class="d-flex gap-1 flex-wrap mb-2">' + typeBadgesHtml + sourceBadge + '</div>';
    }
    content += definitionHtml;
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

        // Multi-entity alias spans render a linked contributor list, so the
        // popover must stay open while the pointer is inside it and there is
        // no single click-through target for the span itself.
        if (getAliasEntities(el).length > 1) {
            attachInteractivePopover(el, ontserveBaseUrl);
            return;
        }

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
        // A wrapper around a citation anchor leaves the click to the anchor's own href
        if (ontserveUrl && !el.dataset.entityAnchor) {
            el.addEventListener('click', function(e) {
                e.preventDefault();
                window.open(ontserveUrl, '_blank', 'noopener');
            });
        }
    });
}

/**
 * Wide popover that stays open while the pointer (or keyboard focus) is inside
 * it, so the in-popover links of the alias contributor list are usable.
 * Manual trigger: enter/focus on the span shows; leaving span or tip hides
 * after a grace period, cancelled when the pointer reaches the tip.
 */
// Keep-open popover mechanics, reusable for ANY popover whose tip carries
// links (popover-plumbing consolidation, 2026-07-09): manual trigger, shows on
// hover/focus, stays open while the pointer or focus is inside the tip (300ms
// grace) so in-popover links are clickable. Content/title come from the
// element's data-bs-* attributes unless overridden in options.
function attachKeepOpenPopover(el, options) {
    var popover = new bootstrap.Popover(el, Object.assign({
        container: 'body',
        trigger: 'manual'
    }, options || {}));
    _wireKeepOpen(el, popover);
    return popover;
}
window.attachKeepOpenPopover = attachKeepOpenPopover;

function attachInteractivePopover(el, ontserveBaseUrl) {
    var popover = attachKeepOpenPopover(el, {
        sanitize: false,
        content: buildPopoverContent(el, ontserveBaseUrl),
        html: true,
        customClass: 'onto-popover-wide'
    });
    return popover;
}

function _wireKeepOpen(el, popover) {
    var hideTimer = null;
    function cancelHide() {
        if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
    }
    function scheduleHide() {
        cancelHide();
        hideTimer = setTimeout(function() { popover.hide(); }, 300);
    }
    function show() { cancelHide(); popover.show(); }
    el.addEventListener('mouseenter', show);
    el.addEventListener('focus', show);
    el.addEventListener('mouseleave', scheduleHide);
    el.addEventListener('blur', scheduleHide);
    // The tip element is recreated on every show; wire its handlers each time
    el.addEventListener('inserted.bs.popover', function() {
        var tip = popover.tip;
        if (!tip) return;
        tip.addEventListener('mouseenter', cancelHide);
        tip.addEventListener('mouseleave', scheduleHide);
        tip.addEventListener('focusin', cancelHide);
        tip.addEventListener('focusout', scheduleHide);
    });
}

// Case-declared labels bypass the generic-vocabulary filters (skipWords,
// minLabelLength) down to this length, so a code provision alias such as
// "I.1" still matches.
var CASE_MIN_LABEL_LENGTH = 3;

// Block-level ancestors whose text is the sentence context of a text node.
var SENTENCE_BLOCK_SELECTOR = 'p, li, td, th, dd, dt, blockquote, h1, h2, h3, h4, h5, h6, .card-body';

/**
 * Alternation over the index keys, longest first for greedy matching. The
 * trailing boundary is a lookahead for a non-word character instead of \b:
 * a key that ends in a non-word character ("III.1.b.") can never satisfy \b
 * before a space. tests/unit/test_annotation_layer_scan.py mirrors this.
 */
function buildEntityPattern(labels) {
    var sorted = labels.slice().sort(function(a, b) { return b.length - a.length; });
    return new RegExp(
        '\\b(' + sorted.map(function(l) { return l.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).join('|') + ')(?![A-Za-z0-9_])',
        'gi'
    );
}

/**
 * Sentence of `text` around the span [index, index + length): from the
 * previous sentence terminator ([.!?] followed by whitespace) to the next
 * one ([.!?] followed by whitespace or the end of the text).
 */
function sentenceWindow(text, index, length) {
    var start = 0;
    var before = /[.!?]\s/g;
    var m;
    while ((m = before.exec(text)) !== null) {
        if (m.index + m[0].length > index) break;
        start = m.index + m[0].length;
    }
    var after = /[.!?](?=\s|$)/g;
    after.lastIndex = index + length;
    var e = after.exec(text);
    return text.substring(start, e ? e.index + 1 : text.length);
}

/** Whether a sentence names one of the alias actors (whole word, case-insensitive). */
function aliasActorPresent(sentence, actors) {
    if (!actors || actors.length === 0) return true;
    var lower = sentence.toLowerCase();
    return actors.some(function(actor) {
        var a = String(actor).toLowerCase();
        if (!a) return false;
        var at = lower.indexOf(a);
        while (at !== -1) {
            var beforeOk = at === 0 || !/[A-Za-z0-9_]/.test(lower.charAt(at - 1));
            var afterOk = at + a.length >= lower.length || !/[A-Za-z0-9_]/.test(lower.charAt(at + a.length));
            if (beforeOk && afterOk) return true;
            at = lower.indexOf(a, at + 1);
        }
        return false;
    });
}

/**
 * Text of the block that contains a text node, with the node's offset in it,
 * so a sentence split across inline elements (an anchor, an emphasis) is
 * still seen whole.
 */
function blockTextAround(textNode) {
    var parent = textNode.parentElement;
    var block = (parent && parent.closest(SENTENCE_BLOCK_SELECTOR)) || parent;
    var offset = 0;
    var walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT, null, false);
    var n;
    while ((n = walker.nextNode()) !== null && n !== textNode) offset += n.textContent.length;
    return { text: block.textContent, offset: offset };
}

/** Popover-enabled span carrying an entity's data attributes. */
function createEntitySpan(entity, matchText) {
    var span = document.createElement('span');
    span.className = 'onto-label';
    if (entity.source === 'ontology') span.className += ' onto-source-ontology';
    span.setAttribute('data-bs-toggle', 'popover');
    span.setAttribute('data-bs-trigger', 'hover focus');
    span.setAttribute('data-bs-html', 'true');
    span.setAttribute('data-bs-placement', 'top');
    span.setAttribute('data-entity-type', entity.entityType || '');
    span.setAttribute('data-entity-pass', entity.sourcePass ? String(entity.sourcePass) : '');
    span.setAttribute('data-entity-source', entity.source || 'case');
    span.setAttribute('data-entity-definition', entity.definition || '');
    span.setAttribute('data-entity-uri', entity.uri || '');
    span.setAttribute('data-alias-types', JSON.stringify(entity.aliasTypes || []));
    span.setAttribute('data-alias-entities', JSON.stringify(entity.aliasEntities || []));
    span.setAttribute('data-ontology-target', entity.ontologyTarget || '');
    span.setAttribute('title', entity.label || matchText);
    return span;
}

/** Longest index key found in a text, or null. */
function longestEntityMatch(pattern, text, entityLookup) {
    var best = null;
    var match;
    pattern.lastIndex = 0;
    while ((match = pattern.exec(text)) !== null) {
        var entity = entityLookup[match[1].toLowerCase()];
        if (entity && (!best || match[1].length > best.length)) {
            best = { index: match.index, length: match[1].length, text: match[1], entity: entity };
        }
    }
    pattern.lastIndex = 0;
    return best;
}

/**
 * Citation anchors (nspe.org links around cited Board cases) are skipped by
 * the text walk so an href is never split. An anchor whose text names an
 * indexed entity is wrapped instead: the anchor keeps its href, the wrapper
 * carries the popover.
 */
function decorateCitationAnchors(cardBody, pattern, entityLookup, excludeSelector) {
    var wrapperExclude = excludeSelector.split(',')
        .map(function(s) { return s.trim(); })
        .filter(function(s) { return s && s !== 'a'; })
        .join(', ');
    cardBody.querySelectorAll('a[href]').forEach(function(anchor) {
        if (anchor.closest('.onto-label') || anchor.querySelector('.onto-label')) return;
        var parent = anchor.parentElement;
        if (!parent || (wrapperExclude && parent.closest(wrapperExclude))) return;
        var text = anchor.textContent.replace(/\s+/g, ' ').trim();
        if (!text) return;
        var best = longestEntityMatch(pattern, text, entityLookup);
        // A citation names one thing: the entity has to account for at least
        // half of the anchor text.
        if (!best || best.length * 2 < text.length) return;
        var actors = best.entity.aliasActors || [];
        if (actors.length) {
            var firstText = document.createTreeWalker(anchor, NodeFilter.SHOW_TEXT, null, false).nextNode();
            if (!firstText) return;
            var block = blockTextAround(firstText);
            if (!aliasActorPresent(sentenceWindow(block.text, block.offset, anchor.textContent.length), actors)) return;
        }
        var span = createEntitySpan(best.entity, best.text);
        span.setAttribute('data-entity-anchor', 'true');
        parent.insertBefore(span, anchor);
        span.appendChild(anchor);
    });
}

/**
 * Scan text within a container for entity label matches and wrap them in
 * popover-enabled .onto-label spans.
 *
 * @param {Element} container - DOM element containing text to annotate
 * @param {Object} entityLookup - Map of lowercase label -> entity data
 * @param {Object} [options]
 * @param {Set} [options.skipWords] - Ontology labels to skip even if they match
 * @param {number} [options.minLabelLength] - Minimum ontology label length (default 4)
 * @param {string} [options.excludeSelector] - CSS selector for elements to skip
 * @param {boolean} [options.decorateAnchors] - Wrap citation anchors whose text names an entity
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

    var labels = Object.keys(entityLookup).filter(function(l) {
        var entry = entityLookup[l] || {};
        // skipWords and minLabelLength prune generic ontology vocabulary
        // ("state", "code of ethics"). A label the case itself declares is
        // never generic: its "NSPE Code of Ethics" and "I.1" stay matchable.
        if (entry.source === 'case') return l.length >= CASE_MIN_LABEL_LENGTH;
        return l.length >= minLen && !skipWords.has(l.toLowerCase());
    });

    if (labels.length === 0) return;

    var pattern = buildEntityPattern(labels);

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
            var block = null;

            while ((match = pattern.exec(text)) !== null) {
                var entity = entityLookup[match[1].toLowerCase()];
                if (!entity) continue;
                // A text-grounded alias stands for one actor's entities and is
                // decorated only in sentences that name that actor, so a
                // precedent recap about another engineer or a quoted code
                // canon stays unlinked.
                var actors = entity.aliasActors || [];
                if (actors.length) {
                    if (!block) block = blockTextAround(textNode);
                    var sentence = sentenceWindow(block.text, block.offset + match.index, match[1].length);
                    if (!aliasActorPresent(sentence, actors)) continue;
                }
                matches.push({
                    index: match.index,
                    length: match[1].length,
                    text: match[1],
                    entity: entity
                });
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

                var span = createEntitySpan(m.entity, m.text);
                span.textContent = m.text;
                span.tabIndex = 0;

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

        if (options.decorateAnchors) {
            decorateCitationAnchors(cardBody, pattern, entityLookup, excludeSelector);
        }
    });
}
window.buildEntityPattern = buildEntityPattern;
window.sentenceWindow = sentenceWindow;
window.aliasActorPresent = aliasActorPresent;

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
