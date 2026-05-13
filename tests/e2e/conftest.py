"""Shared fixtures for Playwright E2E tests.

Launches headless Chromium, provides fresh pages per test, and handles
authentication via the login form.

Usage:
    pytest tests/e2e/ -v --base-url http://localhost:5000
    pytest tests/e2e/ -v --base-url https://proethica.org
"""

import pytest
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# CLI options
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    # --base-url and --headed are provided by pytest-base-url / pytest-playwright;
    # only register options the plugins do not already define.
    parser.addoption(
        "--e2e-username",
        action="store",
        default="testuser",
        help="Username for authenticated tests",
    )
    parser.addoption(
        "--e2e-password",
        action="store",
        default="password",
        help="Password for authenticated tests",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url(request):
    return request.config.getoption("--base-url").rstrip("/")


@pytest.fixture(scope="session")
def browser(request):
    headed = request.config.getoption("--headed")
    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=not headed)
    yield br
    br.close()
    pw.stop()


@pytest.fixture
def page(browser, base_url):
    """Fresh browser page per test, with a 15-second default timeout."""
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.set_default_timeout(15_000)
    yield pg
    pg.close()
    ctx.close()


@pytest.fixture
def authenticated_page(browser, base_url, request):
    """Page with an active login session.

    Logs in via the login form once, then yields the page.
    """
    username = request.config.getoption("--e2e-username")
    password = request.config.getoption("--e2e-password")

    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.set_default_timeout(15_000)

    pg.goto(f"{base_url}/auth/login")
    pg.fill("#username", username)
    pg.fill("#password", password)
    pg.click("input[type='submit']")
    # Wait for redirect after login (should land on homepage or 'next' page)
    pg.wait_for_load_state("networkidle")

    yield pg
    pg.close()
    ctx.close()


