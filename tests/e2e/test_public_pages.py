"""Verify that public pages load for anonymous users and contain expected content."""

import pytest


pytestmark = pytest.mark.e2e

CASE_ID = 7  # Primary demo case


class TestHomepage:
    def test_homepage_loads(self, page, base_url):
        resp = page.goto(f"{base_url}/")
        assert resp.status == 200

    def test_homepage_has_title(self, page, base_url):
        page.goto(f"{base_url}/")
        assert page.locator("h1", has_text="ProEthica").is_visible()

    def test_homepage_has_quick_start_cards(self, page, base_url):
        page.goto(f"{base_url}/")
        cards = page.locator(".quick-start-card")
        assert cards.count() >= 3


class TestCasesList:
    def test_cases_list_loads(self, page, base_url):
        resp = page.goto(f"{base_url}/cases/")
        assert resp.status == 200
        assert page.locator("h1", has_text="Case Repository").is_visible()

    def test_cases_list_has_view_details_links(self, page, base_url):
        page.goto(f"{base_url}/cases/")
        links = page.locator("a", has_text="View Details")
        assert links.count() > 0


class TestCaseDetail:
    def test_case_detail_loads(self, page, base_url):
        resp = page.goto(f"{base_url}/cases/{CASE_ID}")
        assert resp.status == 200

    def test_case_detail_shows_title(self, page, base_url):
        page.goto(f"{base_url}/cases/{CASE_ID}")
        assert page.locator("h1").first.is_visible()


class TestCaseStructure:
    def test_case_structure_loads(self, page, base_url):
        resp = page.goto(f"{base_url}/cases/{CASE_ID}/structure")
        assert resp.status == 200


class TestPipelineOverview:
    def test_pipeline_overview_loads(self, page, base_url):
        resp = page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/overview"
        )
        assert resp.status == 200


class TestEntityReviewPass1:
    def test_entity_review_loads(self, page, base_url):
        resp = page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/entities/review"
        )
        assert resp.status == 200


class TestEnhancedTemporalReview:
    def test_temporal_review_loads(self, page, base_url):
        resp = page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/enhanced_temporal/review"
        )
        assert resp.status == 200

    def test_temporal_review_has_header(self, page, base_url):
        page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/enhanced_temporal/review"
        )
        assert page.locator("h2", has_text="PASS 3").is_visible()


class TestStep4Review:
    def test_step4_entities_loads(self, page, base_url):
        resp = page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/step4/entities"
        )
        assert resp.status == 200

    def test_step4_full_view_loads(self, page, base_url):
        resp = page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/step4/review"
        )
        assert resp.status == 200
