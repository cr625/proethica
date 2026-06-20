"""Asset-integrity e2e checks: each key page must load with zero console errors
and zero failed CSS/JS asset requests.

This guards the externalized view layer end-to-end: a broken or missing static
asset (a <link>/<script src> pointing at a file that 404s after CSS/JS
externalization) leaves the page returning 200 but failing here, and any
JavaScript that throws on load surfaces as a console error. Complements the
server-free static checks in tests/integration/test_template_integrity.py.

Server-gated like the rest of tests/e2e/:
    pytest tests/e2e/test_asset_integrity.py -m e2e --base-url http://localhost:5000
"""
import re

import pytest

pytestmark = pytest.mark.e2e

CASE_ID = 7  # primary demo case

# Anonymous-accessible pages spanning the externalized templates/assets:
# base.html (global), case_detail/case_structure CSS, scenario_step.css (every
# base_step child: overview/step4/step5/step4_entities), step4/step5 page CSS,
# and the entity_review view.
PAGES = [
    ("home", "/"),
    ("cases", "/cases/"),
    ("case_detail", f"/cases/{CASE_ID}"),
    ("case_structure", f"/cases/{CASE_ID}/structure"),
    ("pipeline_overview", f"/scenario_pipeline/case/{CASE_ID}/overview"),
    ("entity_review", f"/scenario_pipeline/case/{CASE_ID}/entities/review/pass1"),
    ("step4", f"/scenario_pipeline/case/{CASE_ID}/step4"),
    ("step4_entities", f"/scenario_pipeline/case/{CASE_ID}/step4/entities"),
    ("step5", f"/scenario_pipeline/case/{CASE_ID}/step5"),
]

# Console substrings that are known-benign and not actionable. Keep this TIGHT --
# the whole point is to fail on real errors.
IGNORE_CONSOLE = (
    "favicon",
)

ASSET_RE = re.compile(r"\.(css|js)(\?|$)")


def _load(page, url):
    console_errors = []
    failed_assets = []

    def on_console(msg):
        if msg.type == "error" and not any(s in msg.text.lower() for s in IGNORE_CONSOLE):
            console_errors.append(msg.text)

    def on_pageerror(err):
        console_errors.append(f"pageerror: {err}")

    def on_response(resp):
        if resp.status >= 400 and ASSET_RE.search(resp.url):
            failed_assets.append(f"{resp.status} {resp.url}")

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("response", on_response)
    resp = page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(400)  # allow late console errors / async asset loads
    return resp, console_errors, failed_assets


@pytest.mark.parametrize("label,path", PAGES, ids=[p[0] for p in PAGES])
def test_page_assets_clean(label, path, page, base_url):
    resp, console_errors, failed_assets = _load(page, f"{base_url}{path}")
    assert resp is not None and resp.status < 400, \
        f"{label}: HTTP {resp.status if resp else 'no response'}"
    assert not failed_assets, \
        f"{label}: failed CSS/JS requests:\n" + "\n".join(failed_assets)
    assert not console_errors, \
        f"{label}: console errors:\n" + "\n".join(console_errors)
