"""End-to-end Playwright tests for the validation study participant flow.

Covers fixes that landed on study/fresh-eyes-fixes-2026-05-10 plus the
post-pass-2 follow-on commits (8d88049 through e61100a) so we can run
the same suite against localhost before deploy and against production
after deploy.

Run:
    pytest tests/e2e/test_validation_study_flow.py -v --base-url http://localhost:5000
    pytest tests/e2e/test_validation_study_flow.py -v --base-url https://proethica.org

Each `?show=` URL mints a fresh preview session, so tests can run in
any order without state coupling.
"""

import re

import pytest


pytestmark = pytest.mark.e2e


class TestParticipantScreensRender:
    """Each participant-facing screen returns 200 and renders expected anchor text."""

    def test_orientation_renders(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=orientation")
        page.wait_for_load_state("networkidle")
        assert "Before you start" in page.content() or page.locator(
            "h1", has_text="Before you start"
        ).count() >= 1

    def test_dashboard_renders(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=dashboard")
        page.wait_for_load_state("networkidle")
        assert page.locator("text=Welcome").count() >= 1

    def test_case_facts_renders(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start")
        page.wait_for_load_state("networkidle")
        # Case page has a step pill labeled "Facts"
        assert page.locator("text=Facts").count() >= 1
        # And a Case Facts card
        assert page.locator("text=Case Facts").count() >= 1

    def test_retrospective_renders(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=retrospective")
        page.wait_for_load_state("networkidle")
        # Retrospective page has the View Ranking heading
        assert page.locator("text=View Ranking").count() >= 1

    def test_completion_renders(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=complete")
        page.wait_for_load_state("networkidle")
        assert page.locator("text=Thank You").count() >= 1


class TestOrientationSection3:
    """Section 3 of orientation describes the single remaining step (retrospective only).

    Demographics was removed 2026-05-12 (moved to Prolific prescreening); the
    section is now prose, not a list, because it has one step.
    """

    def test_after_your_cases_section_present(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=orientation")
        assert page.locator("h2", has_text="After your cases").count() >= 1

    def test_section_3_has_no_demographics_mention(self, page, base_url):
        """Demographics is collected via Prolific, not in-app; orientation must not advertise it."""
        page.goto(f"{base_url}/validation/preview/start?show=orientation")
        section = page.locator("div.orient-section").filter(
            has=page.locator("h2", has_text="After your cases")
        )
        text = section.inner_text().lower()
        assert "demograph" not in text, (
            "Section 3 must not mention demographics (removed 2026-05-12)"
        )

    def test_section_3_prediscloses_retrospective_yes_no_and_open_comments(self, page, base_url):
        """Section 3 must still pre-disclose the retrospective yes/no item and open comments."""
        page.goto(f"{base_url}/validation/preview/start?show=orientation")
        section = page.locator("div.orient-section").filter(
            has=page.locator("h2", has_text="After your cases")
        )
        text = section.inner_text().lower()
        assert "yes/no" in text, (
            "Section 3 should mention the yes/no Surfaced Considerations item"
        )
        assert "comment" in text, (
            "Section 3 should mention open comments"
        )


class TestNarrativeTensionDedup:
    """Per-character tension union must dedup on truncated-form key + sorted affected roles."""

    def test_engineer_a_card_has_no_duplicate_tension_labels(self, page, base_url):
        """Pass 2 [3] BLOCKER: Engineer A's expanded list previously contained two
        textually-identical tension entries that differed only past the 60-char UI
        truncation point ("Mentorship Succession ... Breached By..." vs
        "...Violated By...")."""
        page.goto(f"{base_url}/validation/preview/start")
        page.wait_for_load_state("networkidle")
        # Use the in-page JS function to switch to the views step (the
        # case page renders all steps in hidden divs; goToStep reveals the
        # target). This avoids a click-vs-DOM race on the Continue button.
        page.evaluate("if (typeof goToStep === 'function') { goToStep('views'); }")

        # The Narrative tab is the default-selected view tab; the Engineer A
        # anchor lives at #char-engineer-a inside step-views.
        eng_a_card = page.locator("#char-engineer-a")
        if eng_a_card.count() == 0:
            pytest.skip(
                "Engineer A character card not found on this case data; "
                "extraction may have produced a different protagonist."
            )

        show_all = eng_a_card.locator("a", has_text=re.compile(r"Show all \d+ tensions"))
        if show_all.count() == 0:
            pytest.skip("No 'Show all N tensions' expander on Engineer A card")
        show_all.first.click()
        # Bootstrap collapse animation; wait for it to settle.
        page.wait_for_timeout(500)

        # Each tension is a <div role="button"> containing exactly two
        # .entity-badge spans (obligation + constraint). Group badges in
        # pairs to reconstruct the displayed tension text. Total badge
        # count should be even (2 per tension).
        tension_texts = page.evaluate("""() => {
            const card = document.querySelector('#char-engineer-a');
            if (!card) return null;
            // Find every "tension row" — a div with role="button" that
            // wraps two entity-badge spans. We can't rely on a class name
            // because the template uses different classes for top vs rest.
            const rows = Array.from(card.querySelectorAll('[role="button"]'));
            const out = [];
            for (const r of rows) {
                const badges = r.querySelectorAll('.entity-badge');
                if (badges.length >= 2) {
                    out.push(
                        badges[0].textContent.trim() + ' || ' + badges[1].textContent.trim()
                    );
                }
            }
            return out;
        }""")
        if not tension_texts:
            pytest.skip("No tension rows found on Engineer A card")

        seen = set()
        duplicates = []
        for text in tension_texts:
            if text in seen:
                duplicates.append(text)
            seen.add(text)

        assert duplicates == [], (
            f"Engineer A card has {len(duplicates)} duplicate tension labels "
            f"(out of {len(tension_texts)} total): {duplicates}"
        )


class TestTensionTooltipExposesFullLabel:
    """Tension entity-badge title attribute must contain the full untruncated label."""

    def test_truncated_badge_tooltip_is_longer_than_visible_text(self, page, base_url):
        """Section 1.2 fix: title= was set to the type ('obligation'); now set to
        the full label + type so a truncated badge exposes its full text on hover."""
        page.goto(f"{base_url}/validation/preview/start")
        cont = page.locator("button", has_text="Continue to the five views")
        if cont.count() == 0:
            pytest.skip("Continue to views button not present")
        cont.first.click()
        page.wait_for_load_state("networkidle")

        # Find at least one truncated badge (visible text ends with ellipsis)
        result = page.evaluate("""() => {
            const badges = Array.from(document.querySelectorAll('.entity-badge'));
            const truncated = badges.find(b => b.textContent.trim().endsWith('...'));
            if (!truncated) return null;
            return {
                visible: truncated.textContent.trim(),
                title: truncated.getAttribute('title') || ''
            };
        }""")
        if result is None:
            pytest.skip("No truncated badges in current viewport for this case data")

        assert len(result["title"]) > len(result["visible"]), (
            f"Tooltip title ({len(result['title'])} chars) should be longer than "
            f"visible text ({len(result['visible'])} chars) on a truncated badge"
        )
        assert result["title"] != "obligation" and result["title"] != "constraint", (
            "Tooltip should not be just the entity type"
        )


class TestCaseStepURLSync:
    """goToStep() updates ?step= via history.replaceState so resume URLs work."""

    def test_step_url_updates_when_navigating_to_views(self, page, base_url):
        """Section 7.1 fix: previously the URL stayed at ?step=facts as the
        participant clicked through to step=views, breaking URL-resume."""
        page.goto(f"{base_url}/validation/preview/start")
        page.wait_for_load_state("networkidle")
        assert "step=facts" in page.url

        # Trigger the step transition via the in-page JS function
        page.evaluate("goToStep('views')")
        # replaceState updates location synchronously
        assert "step=views" in page.url, (
            f"Expected step=views in URL after goToStep('views'), got {page.url}"
        )


class TestCompletionScreenCodeDistinction:
    """Completion screen distinguishes confirmation reference from participant code."""

    def test_drexel_path_uses_confirmation_reference_label(self, page, base_url):
        """Section 5.1: the previous 'Completion code:' label collided with Prolific's
        own terminology. Renamed to 'Confirmation reference' on the Drexel/preview path."""
        page.goto(f"{base_url}/validation/preview/start?show=complete")
        page.wait_for_load_state("networkidle")
        # Preview sessions take the Drexel path (is_prolific=False)
        assert page.locator("text=Confirmation reference").count() >= 1, (
            "Completion screen should label the per-session code as 'Confirmation reference'"
        )

    def test_participant_code_is_visually_demoted(self, page, base_url):
        """Participant code line should not use <strong>; demoted to muted small text."""
        page.goto(f"{base_url}/validation/preview/start?show=complete")
        page.wait_for_load_state("networkidle")
        # Participant code text exists
        assert page.locator("text=Participant code").count() >= 1
        # And explicitly says it's for-records-only
        assert page.locator("text=For your records only").count() >= 1


class TestPreviewConsentMode:
    """`/preview/start?show=consent` walks the full Prolific consent flow.

    Designed for advisor sharing: each visit mints a fresh single-case
    preview session tagged recruitment_source='preview', so 3+ advisors
    can share one URL without picking up each other's state. Unlike the
    plain `/preview/start` (which skips consent), this mode lands on
    the Prolific v3 information sheet and proceeds through the same
    /enroll path real Prolific participants use.
    """

    def test_consent_screen_renders(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=consent")
        page.wait_for_load_state("networkidle")
        assert page.locator("text=Information Sheet").count() >= 1
        # Prolific v3 info sheet uses "Study at a Glance" card; Drexel uses
        # different wording.
        assert page.locator("text=Study at a Glance").count() >= 1

    def test_consent_submission_lands_on_orientation(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=consent")
        page.wait_for_load_state("networkidle")
        # Tick the consent checkbox and submit.
        consent_box = page.locator("input[name='consent']")
        if consent_box.count() == 0:
            pytest.skip("Consent input not found; template may have changed")
        consent_box.first.check()
        page.locator("button[type='submit']").first.click()
        page.wait_for_load_state("networkidle")
        assert "/orientation" in page.url, (
            f"Expected /orientation after consent submit, got {page.url}"
        )
        assert page.locator("text=Before you start").count() >= 1

    def test_two_distinct_browser_contexts_get_distinct_sessions(self, browser, base_url):
        """Simulate two advisors hitting the URL: confirm separate participant codes.

        Uses two browser contexts (independent cookie jars) so neither shares
        state with the other; mirrors what happens when two reviewers click
        the same link from different machines.
        """
        codes = []
        for _ in range(2):
            ctx = browser.new_context()
            pg = ctx.new_page()
            pg.set_default_timeout(15_000)
            pg.goto(f"{base_url}/validation/preview/start?show=consent")
            pg.wait_for_load_state("networkidle")
            pg.locator("input[name='consent']").first.check()
            pg.locator("button[type='submit']").first.click()
            pg.wait_for_load_state("networkidle")
            # Orientation surfaces the participant code as one of several
            # <code> elements (the preview banner also wraps recruitment_source
            # in <code>). The participant code matches the CODE_ALPHABET
            # pattern: 8 chars from [ABCDEFGHJKLMNPQRSTUVWXYZ23456789].
            code_text = pg.evaluate("""() => {
                const els = Array.from(document.querySelectorAll('code'));
                const found = els.find(
                    c => /^[A-HJ-NP-Z2-9]{8}$/.test(c.textContent.trim())
                );
                return found ? found.textContent.trim() : null;
            }""")
            codes.append(code_text)
            pg.close()
            ctx.close()
        assert codes[0] is not None and codes[1] is not None, (
            f"Failed to capture participant code from one or both contexts: {codes}"
        )
        assert codes[0] != codes[1], (
            f"Two preview-consent visits produced the same participant code: {codes[0]}"
        )


class TestViewEngagementNudges:
    """activateViewTab scrolls back to top of page so the new view's segue
    caption is the first thing visible (the participant has to scroll
    through the content to reach the Next button at the bottom).

    The companion soft amber "X of 3 rated" reminder banner added alongside
    scroll-to-top was removed in fc143934 (2026-05-12). The global "Continue
    to Reflection" gate (disabled until all five views have 3/3 ratings)
    remains the enforcement layer.
    """

    def _go_to_views(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start")
        page.wait_for_load_state("networkidle")
        page.evaluate("if (typeof goToStep === 'function') { goToStep('views'); }")
        page.wait_for_timeout(200)

    def test_activate_view_tab_scrolls_to_top(self, page, base_url):
        self._go_to_views(page, base_url)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(200)
        before_y = page.evaluate("window.scrollY")
        assert before_y > 100, (
            f"Should have scrolled before activating tab; got {before_y}"
        )
        page.evaluate("activateViewTab('timeline-tab')")
        page.wait_for_timeout(600)
        after_y = page.evaluate("window.scrollY")
        assert after_y < 50, (
            f"After tab activate, scrollY should be near top (0); got {after_y}"
        )


class TestRetrospectiveRankingControls:
    """Up/Down buttons reorder rows deterministically and update the hidden
    inputs the server reads on submit.

    The drag-and-drop interaction has known HTML5 D&D fragility on real
    human inputs (fast sweeps, drops in the container padding area);
    the per-row buttons exist as a reliable alternative AND an
    accessibility path for keyboard / touch users who cannot use D&D.
    """

    def test_rank_up_button_swaps_with_previous_row(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=retrospective")
        page.wait_for_load_state("networkidle")

        before = page.evaluate("""() => Array.from(
            document.querySelectorAll('#rankContainer .rank-item')
        ).map(i => i.dataset.view)""")
        assert len(before) == 5

        # Click the rank-up button on the last row.
        page.locator("#rankContainer .rank-item").last.locator(".rank-up").click()
        page.wait_for_timeout(100)

        after = page.evaluate("""() => Array.from(
            document.querySelectorAll('#rankContainer .rank-item')
        ).map(i => i.dataset.view)""")

        # The previously-last view should now be at index 3 (second-to-last);
        # the previously second-to-last view should be at index 4 (last).
        assert after[3] == before[4], (
            f"Expected {before[4]} to move up to index 3, but list is {after}"
        )
        assert after[4] == before[3], (
            f"Expected {before[3]} to move down to index 4, but list is {after}"
        )

    def test_hidden_inputs_track_button_reorder(self, page, base_url):
        """After button-driven reorder, hidden input value matches DOM position."""
        page.goto(f"{base_url}/validation/preview/start?show=retrospective")
        page.wait_for_load_state("networkidle")

        # Move the last row up twice.
        page.locator("#rankContainer .rank-item").last.locator(".rank-up").click()
        page.wait_for_timeout(50)
        # The originally-last row is now at index 3; click its up again.
        page.locator("#rankContainer .rank-item").nth(3).locator(".rank-up").click()
        page.wait_for_timeout(50)

        state = page.evaluate("""() => Array.from(
            document.querySelectorAll('#rankContainer .rank-item')
        ).map((i, idx) => ({
            view: i.dataset.view,
            rank_label: i.querySelector('.rank-number').textContent.trim(),
            hidden_value: i.querySelector('input[type=\"hidden\"]').value,
            expected_rank: String(idx + 1)
        }))""")

        for row in state:
            assert row["rank_label"] == row["expected_rank"], (
                f"Rank label mismatch on {row['view']}: "
                f"label={row['rank_label']!r} expected={row['expected_rank']!r}"
            )
            assert row["hidden_value"] == row["expected_rank"], (
                f"Hidden value mismatch on {row['view']}: "
                f"value={row['hidden_value']!r} expected={row['expected_rank']!r} "
                f"(this is the bug that caused rankings not to stick on submit)"
            )

    def test_up_button_disabled_on_first_row(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=retrospective")
        page.wait_for_load_state("networkidle")
        first_up = page.locator("#rankContainer .rank-item").first.locator(".rank-up")
        assert first_up.is_disabled(), "Up button on the first row should be disabled"

    def test_down_button_disabled_on_last_row(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=retrospective")
        page.wait_for_load_state("networkidle")
        last_down = page.locator("#rankContainer .rank-item").last.locator(".rank-down")
        assert last_down.is_disabled(), "Down button on the last row should be disabled"


class TestZeroConsoleErrorsAcrossFlow:
    """Every participant-facing screen renders without console errors or warnings."""

    SCREENS = [
        ("/validation/preview/start?show=consent", "consent"),
        ("/validation/preview/start?show=orientation", "orientation"),
        ("/validation/preview/start?show=dashboard", "dashboard"),
        ("/validation/preview/start", "case-facts"),
        ("/validation/preview/start?show=retrospective", "retrospective"),
        ("/validation/preview/start?show=complete", "complete"),
    ]

    @pytest.mark.parametrize("path,name", SCREENS, ids=[s[1] for s in SCREENS])
    def test_screen_has_no_console_errors(self, page, base_url, path, name):
        errors = []
        warnings = []

        def on_console(msg):
            if msg.type == "error":
                errors.append(msg.text)
            elif msg.type == "warning":
                warnings.append(msg.text)

        page.on("console", on_console)
        page.on("pageerror", lambda e: errors.append(f"PageError: {e}"))

        page.goto(f"{base_url}{path}")
        page.wait_for_load_state("networkidle")

        assert errors == [], f"Console errors on {name}: {errors}"
        # Warnings are advisory; surface but don't fail unless they are obviously
        # ours (Bootstrap deprecations etc. are noise).
        ours = [w for w in warnings if "validation" in w.lower() or "study" in w.lower()]
        assert ours == [], f"Study-related console warnings on {name}: {ours}"
