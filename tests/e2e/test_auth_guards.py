"""Verify auth-gated UI elements are shown/hidden based on login state.

Tests check that destructive or expensive controls are hidden from anonymous
users, and present for authenticated users.
"""

import pytest


pytestmark = pytest.mark.e2e

CASE_ID = 7  # Primary demo case


# ---------------------------------------------------------------------------
# Anonymous user: controls should be HIDDEN
# ---------------------------------------------------------------------------

class TestAnonymousEntityReview:
    """Entity review pass1 hides Re-run Extraction for anonymous users."""

    def test_no_rerun_button_pass1(self, page, base_url):
        page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/entities/review"
        )
        assert page.locator("a", has_text="Re-run Extraction").count() == 0

    def test_no_rerun_button_pass2(self, page, base_url):
        page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/entities/review/pass2"
        )
        assert page.locator("a", has_text="Re-run Extraction").count() == 0


class TestAnonymousTemporalReview:
    """Enhanced temporal review hides Re-run Extraction for anonymous users."""

    def test_no_rerun_button(self, page, base_url):
        page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/enhanced_temporal/review"
        )
        assert page.locator("a", has_text="Re-run Extraction").count() == 0


class TestAnonymousStep4Entities:
    """Step 4 entity review hides accept/reject and shows login prompt."""

    def test_no_accept_reject_buttons(self, page, base_url):
        page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/step4/entities"
        )
        assert page.locator(".btn-accept").count() == 0
        assert page.locator(".btn-reject").count() == 0

    def test_commit_section_shows_login(self, page, base_url):
        page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/step4/entities"
        )
        commit = page.locator("#commit-section")
        assert commit.locator("a[href*='login']").is_visible()
        assert commit.locator(".bi-lock-fill").is_visible()


# ---------------------------------------------------------------------------
# Authenticated user: controls should be PRESENT
# ---------------------------------------------------------------------------

class TestAuthenticatedStep4Entities:
    """Step 4 entity review shows accept/reject/commit for logged-in users."""

    def test_accept_reject_visible(self, authenticated_page, base_url):
        authenticated_page.goto(
            f"{base_url}/scenario_pipeline/case/{CASE_ID}/step4/entities"
        )
        # At least some entity cards should have review controls
        accept_btns = authenticated_page.locator(".btn-accept")
        reject_btns = authenticated_page.locator(".btn-reject")
        # Entities may all be committed already; check that either review
        # controls exist or committed badges exist
        has_review = accept_btns.count() > 0 and reject_btns.count() > 0
        has_committed = authenticated_page.locator(
            ".badge", has_text="committed"
        ).count() > 0
        assert has_review or has_committed, (
            "Expected either review controls or committed badges"
        )


