#!/usr/bin/env python3
"""
Capture JavaScript console errors from a ProEthica page using Playwright.
"""
import sys
from playwright.sync_api import sync_playwright

def capture_console(url: str, wait_time: int = 5000):
    """Capture console messages from a page."""
    messages = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Capture all console messages
        def handle_console(msg):
            messages.append({
                'type': msg.type,
                'text': msg.text,
                'location': msg.location if hasattr(msg, 'location') else None
            })

        page.on('console', handle_console)

        # Capture page errors
        def handle_error(error):
            messages.append({
                'type': 'error',
                'text': str(error),
                'location': None
            })

        page.on('pageerror', handle_error)

        print(f"Loading: {url}")
        page.goto(url, wait_until='networkidle')

        # Wait a bit for any async JS to run
        page.wait_for_timeout(wait_time)

        browser.close()

    return messages


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000/scenario_pipeline/case/8/step4/review"

    print(f"\n{'='*60}")
    print(f"Capturing console output from: {url}")
    print(f"{'='*60}\n")

    messages = capture_console(url)

    # Group by type
    errors = [m for m in messages if m['type'] in ('error', 'pageerror')]
    warnings = [m for m in messages if m['type'] == 'warning']
    logs = [m for m in messages if m['type'] not in ('error', 'pageerror', 'warning')]

    if errors:
        print(f"ERRORS ({len(errors)}):")
        print("-" * 40)
        for e in errors:
            print(f"  {e['text']}")
            if e.get('location'):
                print(f"    at {e['location']}")
        print()

    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        print("-" * 40)
        for w in warnings:
            print(f"  {w['text'][:200]}")
        print()

    if logs:
        print(f"LOGS ({len(logs)}):")
        print("-" * 40)
        for l in logs[:20]:  # Limit to first 20
            text = l['text'][:150] if len(l['text']) > 150 else l['text']
            print(f"  [{l['type']}] {text}")
        if len(logs) > 20:
            print(f"  ... and {len(logs) - 20} more")
        print()

    if not messages:
        print("No console messages captured.")

    print(f"\nTotal: {len(errors)} errors, {len(warnings)} warnings, {len(logs)} logs")


if __name__ == "__main__":
    main()
