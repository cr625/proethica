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
def live_server(request):
    """Boot the Flask app in a background thread on an ephemeral port.

    Used only when no external --base-url is supplied, so the e2e suite is
    self-contained (`pytest tests/e2e/ -m e2e`) instead of requiring a manually
    started server. Still needs the app's runtime deps (PostgreSQL, the OntServe
    MCP server); if the app cannot boot, the e2e tests are skipped rather than
    erroring.
    """
    if request.config.getoption("--base-url"):
        yield None  # external server provided; do not boot one
        return
    import threading
    from werkzeug.serving import make_server
    try:
        from app import create_app
        app = create_app()
        srv = make_server("127.0.0.1", 0, app, threaded=True)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"live_server unavailable (app could not boot): {exc}")
        return
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{srv.server_port}"
    finally:
        srv.shutdown()
        thread.join(timeout=5)


@pytest.fixture(scope="session")
def base_url(request, live_server):
    """External --base-url if given, else the in-process live_server."""
    url = request.config.getoption("--base-url") or live_server
    if not url:
        pytest.skip("no --base-url and live_server could not start")
    return url.rstrip("/")


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


