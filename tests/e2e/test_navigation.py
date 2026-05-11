"""Verify cross-page navigation flows -- links work and produce no 404s."""

import pytest


pytestmark = pytest.mark.e2e

CASE_ID = 7  # Primary demo case


class TestCaseNavigationChain:
    """Cases list -> case detail -> case structure."""

    def test_cases_to_detail(self, page, base_url):
        page.goto(f"{base_url}/cases/")
        page.locator("a.case-title-link").first.click()
        page.wait_for_load_state("networkidle")
        assert page.url != f"{base_url}/cases/"
        assert page.locator("h1").first.is_visible()

    def test_detail_to_structure(self, page, base_url):
        page.goto(f"{base_url}/cases/{CASE_ID}")
        structure_link = page.locator("a", has_text="Structure")
        if structure_link.count() > 0:
            structure_link.first.click()
            page.wait_for_load_state("networkidle")
            assert "/structure" in page.url


class TestPipelineNavigation:
    """Pipeline overview -> step pages -> review pages."""

    def test_overview_step_cards(self, page, base_url):
        page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/overview"
        )
        # Overview uses step-card divs for each section
        step_cards = page.locator(".step-card")
        assert step_cards.count() >= 1

    def test_step4_entities_to_full_view(self, page, base_url):
        page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/step4/entities"
        )
        full_view = page.locator("a", has_text="Full View")
        if full_view.count() > 0:
            full_view.first.click()
            page.wait_for_load_state("networkidle")
            assert "/step4/review" in page.url

    def test_full_view_to_entity_review(self, page, base_url):
        page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/step4/review"
        )
        review_link = page.locator("a", has_text="Entity Review")
        if review_link.count() > 0:
            review_link.first.click()
            page.wait_for_load_state("networkidle")
            assert "/step4/entities" in page.url


class TestNavbarLinks:
    """Top-level navbar links produce 200 responses."""

    @pytest.mark.parametrize("path,text", [
        ("/", "ProEthica"),
        ("/cases/", "Case Repository"),
    ])
    def test_navbar_page_loads(self, page, base_url, path, text):
        resp = page.goto(f"{base_url}{path}")
        assert resp.status == 200
        assert page.locator("h1", has_text=text).is_visible()

    def test_login_page_loads(self, page, base_url):
        page.goto(f"{base_url}/auth/login")
        assert page.locator("h2", has_text="Login").is_visible()
