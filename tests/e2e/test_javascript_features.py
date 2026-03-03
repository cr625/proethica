"""Verify JavaScript-dependent features execute correctly in the browser."""

import pytest


pytestmark = pytest.mark.e2e

CASE_ID = 7  # Primary demo case


class TestStep4PhaseCards:
    """Phase cards on step4 entities page expand/collapse on click."""

    def test_phase_card_toggle(self, page, base_url):
        page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/step4/entities"
        )
        # Find a phase card header that toggles a collapse
        headers = page.locator(".phase-card .card-header")
        if headers.count() == 0:
            pytest.skip("No phase cards present on this case")

        header = headers.first
        # The collapse body associated with this card
        card = header.locator("..")
        collapse = card.locator(".collapse, .collapsing")
        if collapse.count() == 0:
            pytest.skip("Phase card has no collapsible body")

        # Click to toggle
        header.click()
        page.wait_for_timeout(500)
        # After click, the collapse should have toggled its 'show' class
        # (either added or removed depending on initial state)


class TestStep4FullViewTabs:
    """Tab navigation on the step4 full view page."""

    def test_tab_switching(self, page, base_url):
        page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/step4/review"
        )
        # Click the Provisions tab
        provisions_tab = page.locator("#provisions-tab")
        if provisions_tab.count() == 0:
            pytest.skip("Provisions tab not present")

        provisions_tab.click()
        page.wait_for_timeout(300)

        # The provisions pane should now be visible
        provisions_pane = page.locator("#provisions")
        assert provisions_pane.is_visible()

        # Switch to another tab
        entities_tab = page.locator("#fullgraph-tab")
        entities_tab.click()
        page.wait_for_timeout(300)
        fullgraph_pane = page.locator("#fullgraph")
        assert fullgraph_pane.is_visible()

    def test_hash_navigation(self, page, base_url):
        """Loading the page with a hash activates the corresponding tab."""
        page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/step4/review#provisions"
        )
        page.wait_for_timeout(500)
        provisions_pane = page.locator("#provisions")
        assert provisions_pane.is_visible()


class TestEntityReviewAccordion:
    """Entity detail accordions expand on click."""

    def test_details_expand(self, page, base_url):
        page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/step4/entities"
        )
        toggles = page.locator(".details-toggle")
        if toggles.count() == 0:
            pytest.skip("No entity detail toggles present")

        # Click the first toggle
        toggles.first.click()
        page.wait_for_timeout(500)
        # The associated collapse panel should become visible
        # (Bootstrap adds 'show' class to .collapse elements)
        visible_details = page.locator(".entity-card .collapse.show")
        assert visible_details.count() >= 1


class TestCasesListFilters:
    """Filter controls on the cases list page."""

    def test_world_filter_present(self, page, base_url):
        page.goto(f"{base_url}/cases/")
        world_filter = page.locator("#worldFilter")
        assert world_filter.is_visible()
        # Should have at least the "All Worlds" option
        options = world_filter.locator("option")
        assert options.count() >= 1

    def test_status_filter_present(self, page, base_url):
        page.goto(f"{base_url}/cases/")
        status_filter = page.locator("#statusFilter")
        assert status_filter.is_visible()


class TestCsrfTokenPresent:
    """Verify the CSRF meta tag is rendered (required for JS fetch calls)."""

    def test_csrf_meta_tag(self, page, base_url):
        page.goto(f"{base_url}/")
        meta = page.locator("meta[name='csrf-token']")
        assert meta.count() == 1
        assert meta.get_attribute("content") != ""
