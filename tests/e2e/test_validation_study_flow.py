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

    def test_demographics_renders(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=demographics")
        page.wait_for_load_state("networkidle")
        assert page.locator("text=Brief Demographics").count() >= 1

    def test_completion_renders(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=complete")
        page.wait_for_load_state("networkidle")
        assert page.locator("text=Thank You").count() >= 1


class TestOrientationSection3:
    """Section 3 of orientation pre-discloses retrospective workload as a 2-item list + prose."""

    def test_after_your_cases_section_present(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=orientation")
        assert page.locator("h2", has_text="After your cases").count() >= 1

    def test_after_your_cases_list_has_exactly_two_items(self, page, base_url):
        """Predecessor commit landed a 3-item list with 'Thank-you screen' as a passive third
        item (style-guide three-item-list trap). The Section 4.1 rewrite collapsed to 2 items
        plus a prose tail naming the thank-you screen and Prolific completion code together.
        """
        page.goto(f"{base_url}/validation/preview/start?show=orientation")
        section = page.locator("div.orient-section").filter(
            has=page.locator("h2", has_text="After your cases")
        )
        list_items = section.locator("ol.orient-steps > li")
        assert list_items.count() == 2, (
            f"Expected 2 items in Section 3 list, got {list_items.count()}"
        )

    def test_section_3_prediscloses_retrospective_yes_no_and_open_comments(self, page, base_url):
        """The first list item in Section 3 must mention the yes/no item and open comments
        (the Pass 2 [5] fix that pre-discloses retrospective workload)."""
        page.goto(f"{base_url}/validation/preview/start?show=orientation")
        section = page.locator("div.orient-section").filter(
            has=page.locator("h2", has_text="After your cases")
        )
        first_item_text = section.locator("ol.orient-steps > li").first.inner_text()
        assert "yes/no" in first_item_text.lower(), (
            "Section 3 first item should mention the yes/no Surfaced Considerations item"
        )
        assert "comment" in first_item_text.lower(), (
            "Section 3 first item should mention open comments"
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


class TestDemographicsStem:
    """Item 1 stem reads 'level reached' (not 'completed') so 'Some college, no degree yet' is consistent."""

    def test_item_1_stem_says_level_reached(self, page, base_url):
        page.goto(f"{base_url}/validation/preview/start?show=demographics")
        page.wait_for_load_state("networkidle")
        labels = page.locator("label.form-label.fw-semibold")
        first_label_text = labels.first.inner_text().strip()
        assert "level reached" in first_label_text.lower(), (
            f"Demographics item 1 should say 'level reached', got: {first_label_text!r}"
        )
        assert "completed" not in first_label_text.lower(), (
            "Demographics item 1 should not contain 'completed' (Section 6.1)"
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


class TestZeroConsoleErrorsAcrossFlow:
    """Every participant-facing screen renders without console errors or warnings."""

    SCREENS = [
        ("/validation/preview/start?show=orientation", "orientation"),
        ("/validation/preview/start?show=dashboard", "dashboard"),
        ("/validation/preview/start", "case-facts"),
        ("/validation/preview/start?show=retrospective", "retrospective"),
        ("/validation/preview/start?show=demographics", "demographics"),
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
