/**
 * CaseCard -- the standard case-details fragment (UI normalization, 2026-07-19).
 *
 * One renderer for every surface that shows "details of a case" (network
 * detail panels, popovers, future modals), so the same information appears
 * in the same order everywhere:
 *
 *   heading (case label, outcome-colored border)
 *   badges  (outcome, optional transformation)
 *   full title (prominent, not muted -- it is the primary identifier)
 *   meta line (year, outcome)
 *   "View case detail" link to /cases/<id>
 *   provisions (interactive tags: keep-open popover with the NSPE provision
 *               text + a link to the provision's OntServe entity page)
 *   optional entity count
 *   optional list sections (connections / cites / cited-by), items
 *            clickable when the caller supplies onItemClick
 *
 * Provision popovers resolve code -> text/URL through
 * GET /api/provisions/info (case-independent NSPE lookup), cached per page
 * load, and attach through window.attachKeepOpenPopover
 * (ontology-popovers.js) so in-popover links are clickable. When that
 * plumbing is absent the tag degrades to a plain link to OntServe.
 *
 * Data contract (all optional except id/label):
 *   { id, label, full_title, year, outcome, transformation,
 *     provisions: [code], entity_count }
 * Options:
 *   { outcomeColors: {outcome: cssColor}, caseUrl: (id) => url,
 *     sections: [{ title, emptyText,
 *                  items: [{id, label, year, outcome, extra}] }],
 *     onItemClick: (item) => void }
 */
(function () {
    'use strict';

    var provisionCache = {};   // code -> info (resolved)
    var provisionPending = null;

    function esc(s) {
        var d = document.createElement('div');
        d.textContent = (s === null || s === undefined) ? '' : String(s);
        return d.innerHTML;
    }

    function render(container, data, opts) {
        opts = opts || {};
        var colors = opts.outcomeColors || {};
        var color = colors[data.outcome] || '#666';
        var caseUrl = (opts.caseUrl || function (id) { return '/cases/' + id; })(data.id);

        var html = '';
        html += '<h6 class="case-card-heading" style="border-color:' + esc(color) + '">'
             + esc(data.label) + '</h6>';

        var badges = '';
        if (data.outcome) {
            badges += '<span class="badge" style="background-color:' + esc(color) + '">'
                   + esc(data.outcome) + '</span> ';
        }
        if (data.transformation) {
            badges += '<span class="badge bg-secondary">' + esc(data.transformation) + '</span>';
        }
        if (badges) html += '<p class="mb-2">' + badges + '</p>';

        if (data.full_title) {
            html += '<div class="case-card-title mb-1"><strong>' + esc(data.full_title) + '</strong></div>';
        }
        if (data.year) {
            html += '<div class="small text-muted mb-2">Year: ' + esc(data.year) + '</div>';
        }
        html += '<div class="mb-2"><a href="' + esc(caseUrl) + '" class="small" target="_blank" rel="noopener">'
             + 'View case detail <i class="bi bi-box-arrow-up-right"></i></a></div>';

        if (data.provisions && data.provisions.length > 0) {
            html += '<div class="mb-2"><strong class="small">Provisions:</strong> <div class="case-card-provisions">'
                 + data.provisions.map(function (p) {
                       return '<span class="provision-tag" data-provision-code="' + esc(p)
                            + '" tabindex="0">' + esc(p) + '</span>';
                   }).join('')
                 + '</div></div>';
        }
        if (data.entity_count !== undefined && data.entity_count !== null) {
            html += '<p class="small mb-1"><strong>Entities:</strong> ' + esc(data.entity_count) + '</p>';
        }

        (opts.sections || []).forEach(function (sec) {
            html += '<hr class="my-2">';
            html += '<div class="small text-muted mb-1"><strong>' + esc(sec.title) + '</strong></div>';
            if (!sec.items || sec.items.length === 0) {
                html += '<div class="small text-muted mb-1">' + esc(sec.emptyText || 'None') + '</div>';
                return;
            }
            html += '<div class="case-card-list">';
            sec.items.forEach(function (item, i) {
                var dot = '<span style="color:' + esc(colors[item.outcome] || '#999') + '">&#9679;</span> ';
                var line = esc(item.label);
                if (item.year) line += ' (' + esc(item.year) + ')';
                if (item.extra) line += ' <span class="text-muted">' + esc(item.extra) + '</span>';
                html += '<div class="case-card-list-item" data-sec="' + esc(sec.title)
                     + '" data-idx="' + i + '">' + dot + line + '</div>';
            });
            html += '</div>';
        });

        container.innerHTML = html;

        if (opts.onItemClick) {
            var secByTitle = {};
            (opts.sections || []).forEach(function (s) { secByTitle[s.title] = s; });
            container.querySelectorAll('.case-card-list-item').forEach(function (el) {
                el.classList.add('case-card-list-item-clickable');
                el.addEventListener('click', function () {
                    var sec = secByTitle[el.getAttribute('data-sec')];
                    var item = sec && sec.items[parseInt(el.getAttribute('data-idx'), 10)];
                    if (item) opts.onItemClick(item);
                });
            });
        }

        attachProvisionPopovers(container);
    }

    function fetchProvisionInfo(codes) {
        var missing = codes.filter(function (c) { return !(c in provisionCache); });
        if (missing.length === 0) return Promise.resolve(provisionCache);
        var url = '/api/provisions/info?codes=' + encodeURIComponent(missing.join(','));
        provisionPending = (provisionPending || Promise.resolve()).then(function () {
            return fetch(url).then(function (r) { return r.ok ? r.json() : {}; })
                .then(function (info) {
                    Object.keys(info).forEach(function (k) { provisionCache[k] = info[k]; });
                    return provisionCache;
                }).catch(function () { return provisionCache; });
        });
        return provisionPending;
    }

    function attachProvisionPopovers(root) {
        var tags = Array.prototype.slice.call(root.querySelectorAll('[data-provision-code]'));
        if (tags.length === 0) return;
        var codes = tags.map(function (t) { return t.getAttribute('data-provision-code'); });
        fetchProvisionInfo(codes).then(function (cache) {
            tags.forEach(function (tag) {
                var info = cache[tag.getAttribute('data-provision-code')];
                if (!info) return;
                if (info.display_code) tag.textContent = info.display_code;
                if (!info.text) return;   // not a modern NSPE code: plain tag
                var body = '<div class="small">' + esc(info.text) + '</div>';
                if (info.url) {
                    body += '<div class="mt-1"><a href="' + esc(info.url)
                         + '" target="_blank" rel="noopener" class="small">'
                         + 'View in NSPE Code of Ethics <i class="bi bi-box-arrow-up-right"></i></a></div>';
                }
                if (window.attachKeepOpenPopover) {
                    tag.classList.add('provision-tag-interactive');
                    window.attachKeepOpenPopover(tag, {
                        title: info.label || info.display_code,
                        content: body,
                        html: true,
                        sanitize: false,
                        customClass: 'onto-popover-wide'
                    });
                } else if (info.url) {
                    // Degraded mode: no popover plumbing on this page.
                    var a = document.createElement('a');
                    a.href = info.url;
                    a.target = '_blank';
                    a.rel = 'noopener';
                    a.className = tag.className;
                    a.textContent = tag.textContent;
                    tag.replaceWith(a);
                }
            });
        });
    }

    window.CaseCard = {
        render: render,
        attachProvisionPopovers: attachProvisionPopovers
    };
})();
