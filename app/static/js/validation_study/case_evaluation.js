    // Time tracking
    let stepStartTime = Date.now();
    let currentStepName = window.CASE_EVALUATION.currentStepName;

    // Inline-layout: each view tab carries its three Likert items inline,
    // collapsed by default and revealed on click. A three-state star
    // indicator (empty / half / full) reflects rating progress on the tab
    // strip, on the Likert card header, and on the recap step. The
    // Continue button enables when all 18 items (5 views x 3 + 3 overall)
    // are rated.
    const VIEW_TAB_IDS = ['narrative-tab', 'timeline-tab', 'qc-tab', 'decisions-tab', 'provisions-tab'];
    const VIEW_KEYS = ['narrative', 'timeline', 'qc', 'decisions', 'provisions'];
    const PANE_IDS = {
        narrative: 'narrative-pane',
        timeline: 'timeline-pane',
        qc: 'qc-pane',
        decisions: 'decisions-pane',
        provisions: 'provisions-pane',
        overall: 'overall-panel'
    };

    function activateViewTab(tabId) {
        const trigger = document.getElementById(tabId);
        if (trigger && window.bootstrap) {
            bootstrap.Tab.getOrCreateInstance(trigger).show();
        }
        // Scroll to the top of the page so the new view's segue caption
        // ("View N of 5: ...") is visible and the participant must scroll
        // down through the view content to reach the rating panel + Next
        // button. Without this the participant lands at the bottom of the
        // new view (where the Next button is) and is tempted to click
        // through without reading.
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function paneRatedCount(paneId) {
        const pane = document.getElementById(paneId);
        if (!pane) return 0;
        const radios = pane.querySelectorAll('input[type="radio"][name]');
        const groups = new Set();
        radios.forEach(r => groups.add(r.name));
        let rated = 0;
        groups.forEach(name => {
            if (pane.querySelector(`input[name="${name}"]:checked`)) rated += 1;
        });
        return rated;
    }

    // Three-state star indicator: empty (no items rated), half (1-2 of 3),
    // full (3 of 3). Same icon used on tab strip, Likert card header, and
    // recap step so the rating-completion signal is consistent across the
    // page. Tab strip iterates view keys only (Overall has no tab); Likert
    // header and recap include Overall.
    const STAR_STATES = {
        empty: { icon: 'bi-star', color: 'text-muted' },
        full:  { icon: 'bi-star-fill', color: 'text-success' }
    };
    const STAR_CLASSES = ['bi-star', 'bi-star-half', 'bi-star-fill',
                          'text-muted', 'text-warning', 'text-success'];

    // Binary star state: empty until all 3 utility items for a view are
    // rated, then full. The earlier three-state (empty / half / full)
    // showed in-progress rating but added visual ambiguity; the binary
    // signal "this view is done" or "not done" is what participants
    // actually need.
    function starStateForCount(rated) {
        return rated >= 3 ? STAR_STATES.full : STAR_STATES.empty;
    }

    function applyStarState(el, state) {
        if (!el) return;
        el.classList.remove(...STAR_CLASSES);
        // Active-tab fill flag is independent of rating progress; once
        // any rating exists the rating-progress logic owns the icon.
        el.classList.remove('tab-active-empty-fill');
        el.classList.add(state.icon, state.color);
    }

    // (Active-tab star fill removed 2026-05-08. View tab stars are now
    // pure rating-progress indicators: outline when 0/3 rated, filled
    // when 3/3 rated. The active tab is signaled by the colored pill
    // background and border, not by overloading the rating star.)
    function setTabActiveFill(tabBtn) { /* no-op; kept for hook compatibility */ }
    function clearTabActiveFill(tabBtn) { /* no-op; kept for hook compatibility */ }

    function refreshStarIndicators() {
        const views = VIEW_KEYS.concat(['overall']);
        views.forEach(view => {
            const paneId = PANE_IDS[view];
            const rated = paneRatedCount(paneId);
            const state = starStateForCount(rated);

            // Tab strip star (skip 'overall' which has no tab)
            const tabStar = document.querySelector(`[data-tab-star="${view}"]`);
            applyStarState(tabStar, state);

            // Likert card header star (one per view-likert group, including Overall)
            const slugMap = {narrative:'narrative', timeline:'timeline', qc:'qc', decisions:'decisions', provisions:'provisions', overall:'overall'};
            const likertStar = document.querySelector(`[data-likert-star="${slugMap[view]}"]`);
            applyStarState(likertStar, state);

            // Likert card header count text
            const likertCount = document.querySelector(`[data-likert-count="${slugMap[view]}"]`);
            if (likertCount) {
                likertCount.textContent = `(${rated} of 3 rated)`;
            }

            // Recap row star + text
            const recapStar = document.querySelector(`[data-recap-star="${view}"]`);
            applyStarState(recapStar, state);
            const recapRow = document.querySelector(`[data-view-summary="${view}"]`);
            if (recapRow) {
                const recapText = recapRow.querySelector('.rating-text');
                if (recapText) {
                    recapText.textContent = `${rated} of 3 rated`;
                    recapText.classList.remove('text-muted', 'text-warning', 'text-success');
                    recapText.classList.add(state.color);
                }
            }
        });
        updateUtilityGate();
    }

    // Likert collapse handling. The card header is the toggle (whole row is
    // clickable). When the participant expands a Likert, swap the toggle
    // label and rotate the chevron. On resume, auto-expand any panel with
    // pre-filled ratings so the participant returns to their last visible
    // state.
    function syncLikertToggleLabel(group, expanded) {
        const label = group.querySelector('.likert-toggle-label');
        const icon = group.querySelector('.likert-toggle-icon');
        if (label) label.textContent = expanded ? 'Hide rating' : 'Begin rating';
        if (icon) {
            icon.classList.toggle('bi-chevron-down', !expanded);
            icon.classList.toggle('bi-chevron-up', expanded);
        }
        const toggle = group.querySelector('.likert-toggle');
        if (toggle) toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    }

    function initLikertCollapses() {
        document.querySelectorAll('.likert-group').forEach(group => {
            const collapse = group.querySelector('.collapse');
            if (!collapse) return;
            // Wire show/hide events to keep label and chevron in sync.
            collapse.addEventListener('show.bs.collapse', () => syncLikertToggleLabel(group, true));
            collapse.addEventListener('hide.bs.collapse', () => syncLikertToggleLabel(group, false));
            // Auto-expand if already rated (resume case).
            if (group.querySelector('input[type="radio"]:checked') && window.bootstrap) {
                bootstrap.Collapse.getOrCreateInstance(collapse, { toggle: false }).show();
            }
        });
    }

    function toggleUnratedTensions() {
        const rows = document.querySelectorAll('#tensionList .tension-unrated');
        const btn = document.getElementById('toggleUnratedTensionsBtn');
        if (!rows.length || !btn) return;
        const isHidden = rows[0].classList.contains('d-none');
        rows.forEach(r => r.classList.toggle('d-none', !isHidden));
        btn.textContent = isHidden
            ? 'Hide ' + rows.length + ' additional tensions without moral-intensity ratings'
            : 'Show ' + rows.length + ' additional tensions without moral-intensity ratings';
    }

    function updateUtilityGate() {
        // Two gates:
        //   - viewsDone (15 of 15): unlocks pill 3 (Reflection) and the
        //     Continue-to-Reflection button on the Provisions footer.
        //   - allDone (18 of 18): unlocks pill 4 (Wrap-up) and the
        //     Continue-to-Wrap-up button on the Reflection footer.
        // Server-side gates in study.py mirror these so URL navigation
        // cannot bypass the rating sequence.
        const viewsRated = VIEW_KEYS.reduce((sum, k) => sum + paneRatedCount(PANE_IDS[k]), 0);
        const overallRated = paneRatedCount(PANE_IDS.overall);
        const viewsDone = viewsRated >= 15;
        const allDone = viewsDone && overallRated >= 3;

        // Provisions footer: Continue-to-Reflection
        const reflBtn = document.getElementById('continue-to-comprehension-btn');
        const viewsHint = document.getElementById('views-gate-hint');
        if (reflBtn) {
            reflBtn.disabled = !viewsDone;
            if (viewsDone) {
                reflBtn.removeAttribute('title');
                if (viewsHint) viewsHint.classList.add('d-none');
            } else {
                reflBtn.title = `${viewsRated} of 15 view ratings; complete all five views to continue`;
                if (viewsHint) viewsHint.classList.remove('d-none');
            }
        }

        // Reflection footer: Continue-to-Wrap-up
        const wrapBtn = document.getElementById('continue-to-wrapup-btn');
        const reflHint = document.getElementById('reflection-gate-hint');
        if (wrapBtn) {
            wrapBtn.disabled = !allDone;
            if (allDone) {
                wrapBtn.removeAttribute('title');
                if (reflHint) reflHint.classList.add('d-none');
            } else {
                wrapBtn.title = `${overallRated} of 3 Overall items rated; complete all three to continue`;
                if (reflHint) reflHint.classList.remove('d-none');
            }
        }

        // Pill 3 (Reflection): locked until all five views rated.
        const pill3 = document.querySelector('.step-indicator .step[data-step="comprehension"]');
        if (pill3) {
            pill3.classList.toggle('step-locked', !viewsDone);
            if (viewsDone) {
                pill3.removeAttribute('aria-disabled');
                pill3.removeAttribute('title');
            } else {
                pill3.setAttribute('aria-disabled', 'true');
                pill3.setAttribute('title', `${viewsRated} of 15 view ratings; complete all five views to advance`);
            }
        }

        // Pill 4 (Wrap-up): locked until all 18 items rated.
        const pill4 = document.querySelector('.step-indicator .step[data-step="reveal"]');
        if (pill4) {
            pill4.classList.toggle('step-locked', !allDone);
            if (allDone) {
                pill4.removeAttribute('aria-disabled');
                pill4.removeAttribute('title');
            } else {
                pill4.setAttribute('aria-disabled', 'true');
                pill4.setAttribute('title', `Complete the per-view ratings and the Overall view rating to advance`);
            }
        }
    }

    // Block clicks on locked pills (CSS pointer-events handles mouse,
    // but anchors can still be activated via keyboard Enter).
    document.addEventListener('click', function(e) {
        const pill = e.target.closest('.step-indicator .step.step-locked');
        if (pill) {
            e.preventDefault();
            e.stopPropagation();
        }
    }, true);

    function updateTimeTracking(fromStep) {
        const elapsed = Date.now() - stepStartTime;
        const fieldMap = {
            'facts': 'time_facts_review',
            'views': 'time_views_review',
            'utility': 'time_utility_rating',
            'comprehension': 'time_comprehension',  // now the Reflection step
            'reveal': 'time_alignment'              // wrap-up; reuses time_alignment column
        };
        const field = document.getElementById(fieldMap[fromStep]);
        if (field) {
            const current = parseInt(field.value) || 0;
            field.value = current + elapsed;
        }
        stepStartTime = Date.now();
    }

    function goToStep(stepName) {
        // Update time tracking
        updateTimeTracking(currentStepName);

        // Hide all steps
        document.querySelectorAll('.step-content').forEach(el => {
            el.classList.add('hidden-step');
        });

        // Show target step
        document.getElementById('step-' + stepName).classList.remove('hidden-step');

        // Update step indicators
        const steps = ['facts', 'views', 'comprehension', 'reveal'];
        const targetIndex = steps.indexOf(stepName);

        document.querySelectorAll('.step-indicator .step').forEach((el, idx) => {
            el.classList.remove('active', 'completed');
            if (idx < targetIndex) {
                el.classList.add('completed');
            } else if (idx === targetIndex) {
                el.classList.add('active');
            }
        });

        currentStepName = stepName;

        // Sync URL ?step= so a participant who copies the URL to resume
        // later lands back at the step they were on, not at step=facts.
        // Uses replaceState to avoid polluting browser history with one
        // entry per intra-case step (Back should still cross page
        // boundaries, not walk every tab click).
        if (window.history && typeof window.history.replaceState === 'function') {
            const url = new URL(window.location.href);
            url.searchParams.set('step', stepName);
            window.history.replaceState({}, '', url.toString());
        }

        // Load board conclusions when reaching reveal step
        if (stepName === 'reveal') {
            loadBoardConclusions();
        }

        // Scroll to top
        window.scrollTo(0, 0);
    }

    function loadBoardConclusions() {
        const container = document.getElementById('board-conclusions-container');
        fetch(window.CASE_EVALUATION.revealConclusionsUrl)
            .then(response => response.json())
            .then(data => {
                let html = '';
                // Use pre-wrap only if content is not HTML
                const contentStyle = data.is_html ? '' : 'style="white-space: pre-wrap;"';

                if (data.discussion) {
                    html += '<h6>Discussion</h6>';
                    html += '<div class="mb-3 p-3 bg-white rounded board-content" ' + contentStyle + '>' + data.discussion + '</div>';
                }

                if (data.conclusion) {
                    html += '<h6>Conclusion</h6>';
                    html += '<div class="mb-3 p-3 bg-white rounded board-content" ' + contentStyle + '>' + data.conclusion + '</div>';
                }

                if (data.cited_provisions && data.cited_provisions.length > 0) {
                    html += '<h6>Cited Provisions</h6>';
                    // Earlier code truncated each provision text at 100 chars,
                    // producing visible mismatches with the Provisions tab where
                    // the same provisions render in full. Provision text is
                    // short enough to render in full here.
                    html += '<ul class="mb-0">';
                    data.cited_provisions.forEach(p => {
                        html += '<li><strong>' + p.code_section + '</strong>: ' + p.text + '</li>';
                    });
                    html += '</ul>';
                }

                if (!html) {
                    html = '<p class="text-muted">Board conclusions not available for this case.</p>';
                }

                container.innerHTML = html;
            })
            .catch(err => {
                container.innerHTML = '<p class="text-danger">Error loading conclusions: ' + err.message + '</p>';
            });
    }

    // Format long facts paragraphs into readable chunks with expand/collapse
    function setupFactsChunking() {
        document.querySelectorAll('.facts-section .case-text-content').forEach(function(container) {
            // Check if content is long enough to chunk (more than 800 chars)
            const textContent = container.textContent || container.innerText;
            if (textContent.length < 800) return;

            // For HTML content, look for long paragraphs
            const paragraphs = container.querySelectorAll('p');
            if (paragraphs.length > 0) {
                // If there are multiple paragraphs, show first few
                if (paragraphs.length > 3) {
                    const expandId = 'factsExpand_' + Math.random().toString(36).substr(2, 9);

                    // Wrap paragraphs after the third in a collapse div
                    const collapseDiv = document.createElement('div');
                    collapseDiv.className = 'collapse';
                    collapseDiv.id = expandId;

                    for (let i = 3; i < paragraphs.length; i++) {
                        collapseDiv.appendChild(paragraphs[i].cloneNode(true));
                        paragraphs[i].remove();
                    }

                    container.appendChild(collapseDiv);

                    // Add expand button
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'btn btn-sm btn-link facts-expand-btn p-0 mt-2';
                    btn.setAttribute('data-bs-toggle', 'collapse');
                    btn.setAttribute('data-bs-target', '#' + expandId);
                    btn.innerHTML = '<i class="bi bi-chevron-down"></i> Show more (' + (paragraphs.length - 3) + ' more paragraphs)';
                    container.appendChild(btn);

                    // Toggle button text
                    collapseDiv.addEventListener('show.bs.collapse', function() {
                        btn.innerHTML = '<i class="bi bi-chevron-up"></i> Show less';
                    });
                    collapseDiv.addEventListener('hide.bs.collapse', function() {
                        btn.innerHTML = '<i class="bi bi-chevron-down"></i> Show more (' + (paragraphs.length - 3) + ' more paragraphs)';
                    });
                }
            } else {
                // For plain text without paragraphs, split on sentences
                const html = container.innerHTML;
                const sentences = html.split(/\.(?=\s+[A-Z])/);
                if (sentences.length > 5) {
                    const expandId = 'factsExpand_' + Math.random().toString(36).substr(2, 9);
                    const previewSentences = sentences.slice(0, 4).join('. ') + '.';
                    const remainingSentences = sentences.slice(4);

                    // Group remaining sentences into paragraphs
                    const remainingParagraphs = [];
                    for (let i = 0; i < remainingSentences.length; i += 3) {
                        const chunk = remainingSentences.slice(i, i + 3).join('. ');
                        remainingParagraphs.push(chunk + (chunk.endsWith('.') ? '' : '.'));
                    }

                    container.innerHTML = `
                        <p class="mb-2">${previewSentences.trim()}</p>
                        <div class="collapse" id="${expandId}">
                            ${remainingParagraphs.map(p => '<p class="mb-3">' + p.trim() + '</p>').join('')}
                        </div>
                        <button class="btn btn-sm btn-link facts-expand-btn p-0" type="button"
                                data-bs-toggle="collapse" data-bs-target="#${expandId}">
                            <i class="bi bi-chevron-down"></i> Show more (${remainingSentences.length} more sentences)
                        </button>
                    `;

                    const collapseEl = document.getElementById(expandId);
                    if (collapseEl) {
                        const btn = container.querySelector('button');
                        collapseEl.addEventListener('show.bs.collapse', function() {
                            btn.innerHTML = '<i class="bi bi-chevron-up"></i> Show less';
                        });
                        collapseEl.addEventListener('hide.bs.collapse', function() {
                            btn.innerHTML = '<i class="bi bi-chevron-down"></i> Show more (' + remainingSentences.length + ' more sentences)';
                        });
                    }
                }
            }
        });
    }

    // Initialize on page load
    document.addEventListener('DOMContentLoaded', function() {
        // Set initial step
        goToStep(window.CASE_EVALUATION.currentStepName);

        // Set up facts chunking for readability
        setupFactsChunking();

        // Initialize Bootstrap popovers for character-mention links
        // in the Opening Context and the Main characters list. Click
        // is stopped from propagating so a mention nested inside a
        // collapse-toggle row (Timeline Action entries) doesn't also
        // toggle the row.
        document.querySelectorAll('.char-mention[data-bs-toggle="popover"]').forEach(function(el) {
            new bootstrap.Popover(el);
        });
        // Provision-code badges in the Conclusions view: hover reveals the
        // NSPE provision text via popover (provision_text_lookup in qc view).
        document.querySelectorAll('.provision-badge[data-bs-toggle="popover"]').forEach(function(el) {
            new bootstrap.Popover(el);
        });
        // Role badges in the Main characters cards: hover reveals the
        // per-role professional position (role_suffix_details in narrative).
        document.querySelectorAll('.role-badge[data-bs-toggle="popover"]').forEach(function(el) {
            new bootstrap.Popover(el);
        });
        // Type chips on the Provisions view (Obligation, Action, etc.):
        // hover reveals the proeth-core class definition. Both the
        // per-mapping-row chip and the "Show all mappings" group-header
        // chip share the .provision-type-chip class.
        document.querySelectorAll('.provision-type-chip[data-bs-toggle="popover"]').forEach(function(el) {
            new bootstrap.Popover(el);
        });
        // When a popover-anchored link is nested inside a collapse-toggle row
        // (Timeline Action entries), a click on the link must not also fire
        // Bootstrap's collapse handler on the parent. Bootstrap binds the
        // collapse data-API at document level in a way that runs before any
        // listener on the row or document; the only earlier hook is a
        // capture-phase listener on `window`. Trigger is `focus hover`, so
        // suppressing click does not affect popover visibility.
        window.addEventListener('click', function(e) {
            if (e.target && e.target.closest && e.target.closest('.char-mention')) {
                e.stopPropagation();
                e.stopImmediatePropagation();
            }
        }, true);

        // Per-character "Show N more tensions" toggle on the main
        // characters' cards. Each toggle reveals (or hides) the
        // tension-self-only-row entries scoped to its character anchor.
        document.querySelectorAll('.tension-self-only-toggle').forEach(function(btn) {
            btn.addEventListener('click', function() {
                const anchor = this.dataset.charAnchor;
                const selfOnlyRows = document.querySelectorAll(
                    '.tension-self-only-row[data-char-anchor="' + anchor + '"]'
                );
                const currentlyHidden = selfOnlyRows[0] && selfOnlyRows[0].classList.contains('d-none');
                selfOnlyRows.forEach(function(row) {
                    row.classList.toggle('d-none');
                });
                const count = this.dataset.selfCount;
                const plural = count === '1' ? '' : 's';
                this.textContent = currentlyHidden
                    ? 'Hide tensions involving only this role'
                    : 'Show ' + count + ' more tension' + plural + ' involving only this role';
            });
        });

        // Rotate the chevron on each timeline entry that has nested decision points.
        document.querySelectorAll('#study-timeline .tl-has-dps').forEach(function(node) {
            const targetSel = node.dataset.bsTarget;
            if (!targetSel) return;
            const target = document.querySelector(targetSel);
            if (!target) return;
            const chevron = node.querySelector('.tl-entry-chevron');
            target.addEventListener('show.bs.collapse', function() {
                if (chevron) chevron.classList.replace('bi-chevron-right', 'bi-chevron-down');
                node.classList.add('tl-compact-expanded');
            });
            target.addEventListener('hide.bs.collapse', function() {
                if (chevron) chevron.classList.replace('bi-chevron-down', 'bi-chevron-right');
                node.classList.remove('tl-compact-expanded');
            });
        });

        // Inline-layout: drive star indicators and the Continue gate from
        // radio completion in each tab pane. Wire change events on every
        // Likert radio inside step-views; refresh star icons on tabs,
        // Likert headers, and the recap step on each change. Initialize
        // Likert collapses (auto-expand for resume) before the first
        // refresh so star state is consistent with what is visible.
        initLikertCollapses();
        // Listen for rating changes on Step 2 (per-view Likerts) and
        // Step 3 (Overall view rating, since 2026-05-10 reorg).
        ['step-views', 'step-comprehension'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', function(e) {
                    if (e.target && e.target.matches('input[type="radio"]')) {
                        refreshStarIndicators();
                    }
                });
            }
        });
        refreshStarIndicators();

        // Per-view tab dwell timing. shown.bs.tab fires when a tab becomes
        // active; hidden.bs.tab fires when it deactivates. We accumulate
        // ms per tab in the matching hidden form input. The initially
        // active tab (Narrative) starts its timer here.
        const TAB_TIMER_FIELDS = {
            'narrative-tab': 'time_view_narrative',
            'timeline-tab':  'time_view_timeline',
            'qc-tab':        'time_view_qc',
            'decisions-tab': 'time_view_decisions',
            'provisions-tab':'time_view_provisions'
        };
        let tabStartMs = {};
        function startTabTimer(tabId) { tabStartMs[tabId] = Date.now(); }
        function stopTabTimer(tabId) {
            if (!tabStartMs[tabId]) return;
            const elapsed = Date.now() - tabStartMs[tabId];
            const fieldName = TAB_TIMER_FIELDS[tabId];
            if (!fieldName) return;
            const field = document.getElementById(fieldName);
            if (field) {
                const current = parseInt(field.value) || 0;
                field.value = current + elapsed;
            }
            delete tabStartMs[tabId];
        }
        // Tab dwell-timing only. The Overall-panel reveal logic that lived
        // here previously (gating the panel on "all five tabs visited" and
        // on "Provisions tab active") was removed when the Overall view
        // rating moved off Step 2 onto Step 3 (Reflection) on 2026-05-10.
        // The panel is now always-visible inside Step 3 and gated by the
        // server-side `view_ratings_complete` check on the route.
        VIEW_TAB_IDS.forEach(function(tabId) {
            const trigger = document.getElementById(tabId);
            if (!trigger) return;
            trigger.addEventListener('shown.bs.tab', function(e) {
                startTabTimer(e.target.id);
                setTabActiveFill(e.target);
            });
            trigger.addEventListener('hidden.bs.tab', function(e) {
                stopTabTimer(e.target.id);
                clearTabActiveFill(e.target);
            });
            if (trigger.classList.contains('active')) {
                startTabTimer(tabId);
                setTabActiveFill(trigger);
            }
        });

        // Stop the active tab's timer when the user leaves step-views.
        // goToStep is the only path off this step in normal flow.
        const _origGoToStep = goToStep;
        window.goToStep = function(stepName) {
            if (currentStepName === 'views') {
                Object.keys(tabStartMs).forEach(stopTabTimer);
            }
            return _origGoToStep(stepName);
        };
    });
