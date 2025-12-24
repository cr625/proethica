#!/usr/bin/env python3
"""
Debug the Cytoscape graph data on step4 review page.
"""
import json
from playwright.sync_api import sync_playwright

def debug_graph(url: str):
    """Capture and analyze graph data."""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Inject script to capture graph data before Cytoscape init
        page.add_init_script("""
            window.debugGraphData = {};

            // Override console.warn to capture Cytoscape warnings
            const originalWarn = console.warn;
            window.cytoscapeWarnings = [];
            console.warn = function(...args) {
                window.cytoscapeWarnings.push(args.join(' '));
                originalWarn.apply(console, args);
            };
        """)

        print(f"Loading: {url}")
        page.goto(url, wait_until='networkidle')
        page.wait_for_timeout(3000)

        # Get graph data from the page
        result = page.evaluate("""() => {
            // Try to get the provisions, questions, conclusions data
            const data = {
                warnings: window.cytoscapeWarnings || [],
                cyExists: typeof cy !== 'undefined',
                nodeCount: 0,
                edgeCount: 0,
                provisionCount: 0,
                questionCount: 0,
                conclusionCount: 0,
                invalidEdges: [],
                nodeIds: [],
                edgeDetails: []
            };

            if (typeof cy !== 'undefined') {
                data.nodeCount = cy.nodes().length;
                data.edgeCount = cy.edges().length;

                // Get node IDs by type
                data.nodeIds = cy.nodes().map(n => ({
                    id: n.id(),
                    type: n.data('type'),
                    label: n.data('label')
                }));

                // Count by type
                data.provisionCount = cy.nodes('[type="provision"]').length;
                data.questionCount = cy.nodes('[type="question"]').length;
                data.conclusionCount = cy.nodes('[type="conclusion"]').length;

                // Get edge details
                data.edgeDetails = cy.edges().map(e => ({
                    id: e.id(),
                    source: e.source().id(),
                    target: e.target().id(),
                    edgeType: e.data('edgeType'),
                    // Check if endpoints are valid
                    sourceExists: e.source().length > 0,
                    targetExists: e.target().length > 0
                }));

                // Find edges with issues
                data.invalidEdges = cy.edges().filter(e => {
                    return e.source().length === 0 || e.target().length === 0;
                }).map(e => e.id());
            }

            return data;
        }""")

        browser.close()

    return result


def main():
    url = "http://localhost:5000/scenario_pipeline/case/8/step4/review"

    print(f"\n{'='*60}")
    print("Debugging Cytoscape Graph")
    print(f"{'='*60}\n")

    data = debug_graph(url)

    print(f"Cytoscape initialized: {data['cyExists']}")
    print(f"Nodes: {data['nodeCount']} (Provisions: {data['provisionCount']}, Questions: {data['questionCount']}, Conclusions: {data['conclusionCount']})")
    print(f"Edges: {data['edgeCount']}")

    if data['warnings']:
        print(f"\nWarnings ({len(data['warnings'])}):")
        # Show unique warnings
        seen = set()
        for w in data['warnings']:
            if w not in seen:
                seen.add(w)
                # Extract edge ID from warning
                if 'Edge `' in w:
                    edge_id = w.split('`')[1]
                    print(f"  - Edge: {edge_id}")

    if data['invalidEdges']:
        print(f"\nInvalid edges in Cytoscape: {data['invalidEdges']}")

    # Analyze edge connectivity
    print(f"\nEdge Type Analysis:")
    edge_types = {}
    for edge in data['edgeDetails']:
        et = edge['edgeType']
        if et not in edge_types:
            edge_types[et] = {'count': 0, 'invalid': 0}
        edge_types[et]['count'] += 1
        if not edge['sourceExists'] or not edge['targetExists']:
            edge_types[et]['invalid'] += 1

    for et, stats in edge_types.items():
        print(f"  {et}: {stats['count']} edges ({stats['invalid']} invalid)")

    # Check if the problematic edges have valid nodes
    print(f"\nNode ID samples:")
    for node in data['nodeIds'][:10]:
        print(f"  {node['id']}: {node['type']} - {node['label'][:50] if node['label'] else 'None'}")

    # Look for the specific problematic edge
    print(f"\nEdge samples:")
    for edge in data['edgeDetails'][:5]:
        print(f"  {edge['id']}: {edge['source']} -> {edge['target']} ({edge['edgeType']})")


if __name__ == "__main__":
    main()
