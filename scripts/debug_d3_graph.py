#!/usr/bin/env python3
"""
Debug the D3.js Entity graph on step4 review page (Entities tab).
"""
import json
from playwright.sync_api import sync_playwright

def debug_d3_graph(url: str):
    """Capture and analyze D3 graph data from the API endpoint."""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        console_messages = []
        def handle_console(msg):
            console_messages.append({
                'type': msg.type,
                'text': msg.text
            })
        page.on('console', handle_console)

        page_errors = []
        def handle_error(error):
            page_errors.append(str(error))
        page.on('pageerror', handle_error)

        print(f"Loading: {url}")
        page.goto(url, wait_until='networkidle')

        # Wait for the D3 graph to initialize
        page.wait_for_timeout(3000)

        # Get D3 graph data by evaluating in page context
        result = page.evaluate("""() => {
            const data = {
                d3GraphLoaded: false,
                nodeCount: 0,
                edgeCount: 0,
                errors: [],
                graphData: null
            };

            // Check if d3 graph container exists
            const container = document.getElementById('d3-graph-container');
            const svg = document.getElementById('d3-graph-svg');

            if (container && svg) {
                // Count rendered elements
                const circles = svg.querySelectorAll('circle');
                const lines = svg.querySelectorAll('line');
                data.nodeCount = circles.length;
                data.edgeCount = lines.length;
                data.d3GraphLoaded = circles.length > 0;

                // Get node count from display
                const nodeCountEl = document.getElementById('d3-node-count');
                if (nodeCountEl) {
                    data.displayedCount = nodeCountEl.textContent;
                }
            }

            return data;
        }""")

        browser.close()

    return result, console_messages, page_errors


def fetch_entity_graph_api(case_id: int = 8):
    """Fetch data directly from the entity graph API."""
    import requests

    url = f"http://localhost:5000/scenario_pipeline/case/{case_id}/entity_graph"
    try:
        resp = requests.get(url, timeout=30)
        return resp.json()
    except Exception as e:
        return {'error': str(e)}


def main():
    url = "http://localhost:5000/scenario_pipeline/case/8/step4/review"

    print(f"\n{'='*60}")
    print("Debugging D3.js Entity Graph (Entities Tab)")
    print(f"{'='*60}\n")

    # First, get data from the API directly
    print("1. Fetching from API endpoint...")
    api_data = fetch_entity_graph_api(8)

    if api_data.get('success'):
        print(f"   API returned: {len(api_data.get('nodes', []))} nodes, {len(api_data.get('edges', []))} edges")

        # Analyze nodes
        nodes = api_data.get('nodes', [])
        type_counts = {}
        pass_counts = {}
        for node in nodes:
            t = node.get('type', 'unknown')
            p = node.get('pass', 0)
            type_counts[t] = type_counts.get(t, 0) + 1
            pass_counts[p] = pass_counts.get(p, 0) + 1

        print(f"\n   Node types:")
        for t, c in sorted(type_counts.items()):
            print(f"      {t}: {c}")

        print(f"\n   Pass distribution:")
        for p, c in sorted(pass_counts.items()):
            print(f"      Pass {p}: {c}")

        # Analyze edges
        edges = api_data.get('edges', [])
        edge_types = {}
        for edge in edges:
            et = edge.get('type', 'unknown')
            edge_types[et] = edge_types.get(et, 0) + 1

        print(f"\n   Edge types:")
        for et, c in sorted(edge_types.items()):
            print(f"      {et}: {c}")

        # Check for invalid edges
        node_ids = {n['id'] for n in nodes}
        invalid_edges = []
        for edge in edges:
            src = edge.get('source')
            tgt = edge.get('target')
            if src not in node_ids or tgt not in node_ids:
                invalid_edges.append(edge)

        if invalid_edges:
            print(f"\n   Invalid edges (missing endpoints): {len(invalid_edges)}")
            for e in invalid_edges[:5]:
                print(f"      {e['id']}: {e['source']} -> {e['target']}")
        else:
            print(f"\n   All edges have valid endpoints!")

    else:
        print(f"   API error: {api_data.get('error', 'Unknown error')}")

    # Now check the rendered page
    print(f"\n2. Checking rendered page...")
    result, console, errors = debug_d3_graph(url)

    print(f"   D3 graph loaded: {result.get('d3GraphLoaded')}")
    print(f"   Rendered circles (nodes): {result.get('nodeCount')}")
    print(f"   Rendered lines (edges): {result.get('edgeCount')}")
    print(f"   Display text: {result.get('displayedCount', 'N/A')}")

    if errors:
        print(f"\n   Page Errors ({len(errors)}):")
        for e in errors:
            print(f"      {e[:200]}")

    # Filter console for errors/warnings
    issues = [m for m in console if m['type'] in ('error', 'warning')]
    if issues:
        print(f"\n   Console Issues ({len(issues)}):")
        for m in issues:
            print(f"      [{m['type']}] {m['text'][:150]}")


if __name__ == "__main__":
    main()
