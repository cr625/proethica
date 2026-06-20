"""On-demand front-end visual diff: confirm a view-layer change did not alter a
page's rendered pixels.

This is the lightweight, zero-maintenance alternative to committed
golden-screenshot regression (which churns badly for this data-heavy app, where
pages carry entities/timestamps/counts). It is how the STEP-5 CSS externalization
was verified -- the pilot rendered pixel-identical before and after.

Workflow (run against the same server + same case data, before and after your
change):

    # 1. baseline BEFORE your change
    python scripts/fe_visual_diff.py http://localhost:5000/cases/7 case7

    # 2. make your CSS/JS/template change, then compare
    python scripts/fe_visual_diff.py http://localhost:5000/cases/7 case7 --check

`--check` exits 0 if the full-page screenshot is byte-identical to the baseline,
1 otherwise (and reports the saved before/after PNG paths for inspection).
Baselines live under /tmp/fe_visual_diff/<label>.png.

Requires the proethica venv (Playwright) and a running server. For asserting a
page merely loads cleanly (no console errors / no failed assets) use the e2e
suite tests/e2e/test_asset_integrity.py instead; this tool answers the narrower
"did the rendered output change?" question.
"""
import hashlib
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("/tmp/fe_visual_diff")


def _shot(url, dest):
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_context(viewport={"width": 1400, "height": 1100}).new_page()
        pg.goto(url, wait_until="networkidle", timeout=30000)
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(dest), full_page=True)
        br.close()


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    url, label = argv[0], argv[1]
    check = "--check" in argv[2:]
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = OUT / f"{label}.png"
    if not check:
        _shot(url, baseline)
        print(f"baseline saved: {baseline}  ({baseline.stat().st_size} bytes)")
        return 0
    if not baseline.exists():
        print(f"no baseline at {baseline}; run without --check first")
        return 2
    after = OUT / f"{label}.after.png"
    _shot(url, after)
    b = hashlib.md5(baseline.read_bytes()).hexdigest()
    a = hashlib.md5(after.read_bytes()).hexdigest()
    if a == b:
        print(f"IDENTICAL: {url} render unchanged (md5 {a[:8]})")
        return 0
    print(f"CHANGED: {url} render differs\n  before: {baseline}\n  after:  {after}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
