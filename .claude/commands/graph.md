# ProEthica Graph Visualization Toolkit

This skill provides guidance for building, modifying, and maintaining graph visualizations in ProEthica.

## Current Graph Implementations

ProEthica has three graph visualizations:

| Graph | Location | Library | Purpose |
|-------|----------|---------|---------|
| Entity Graph | step4_review.html (Entities tab) | D3.js v7 | All extracted entities with relationships |
| Reasoning Flow | step4_review.html (Flow tab) | Cytoscape.js | Provisions -> Questions -> Conclusions |
| Similarity Network | similarity_network.html | D3.js v7 | Case-to-case precedent similarity |

## Entity Types (9-Component Formalism)

ProEthica uses a formal ontology with 9 core entity types extracted across 4 passes.

See [Color Scheme Reference](../../docs/reference/color-scheme.md) for the canonical color definitions.

### Pass 1 - Context (Foundation)
| Type | Code | Color | CSS Class | Description |
|------|------|-------|-----------|-------------|
| Roles | R | `#0d6efd` (blue) | `.onto-type-role` | Actors and stakeholders |
| States | S | `#6f42c1` (purple) | `.onto-type-state` | Conditions and situations |
| Resources | Rs | `#20c997` (teal) | `.onto-type-resource` | Assets and materials |

### Pass 2 - Normative (Requirements)
| Type | Code | Color | CSS Class | Description |
|------|------|-------|-----------|-------------|
| Principles | P | `#fd7e14` (orange) | `.onto-type-principle` | Ethical principles |
| Obligations | O | `#dc3545` (red) | `.onto-type-obligation` | Duties and requirements |
| Constraints | Cs | `#6c757d` (gray) | `.onto-type-constraint` | Limitations and restrictions |
| Capabilities | Ca | `#0dcaf0` (cyan) | `.onto-type-capability` | Abilities and skills |

### Pass 3 - Temporal (Dynamics)
| Type | Code | Color | CSS Class | Description |
|------|------|-------|-----------|-------------|
| Actions | A | `#198754` (green) | `.onto-type-action` | Actions taken |
| Events | E | `#ffc107` (yellow) | `.onto-type-event` | Events that occurred |

### Step 4 - Synthesis (Analysis)
| Type | Color | Description |
|------|-------|-------------|
| Code Provisions | `#6c757d` (gray) | NSPE Code references |
| Ethical Questions | `#0dcaf0` (cyan) | Board questions |
| Ethical Conclusions | `#198754` (green) | Board conclusions |

### Pass Filter Colors (Semantically Neutral)
| Pass | Name | Color | Entities |
|------|------|-------|----------|
| 1 | Context | `#3b82f6` | R, S, Rs |
| 2 | Normative | `#8b5cf6` | P, O, Cs, Ca |
| 3 | Temporal | `#14b8a6` | A, E |
| 4 | Synthesis | `#64748b` | Provisions, Q, C |

## Graph Data Schemas

### Entity Graph Node Schema
```json
{
  "id": "roles_123",
  "db_id": 123,
  "type": "roles",
  "entity_type": "Role",
  "label": "Engineer A",
  "definition": "Environmental engineer at firm",
  "pass": 1,
  "section": "facts",
  "color": "#0d6efd",
  "is_published": false,
  "is_selected": true,
  "is_hub": false
}
```

### Entity Graph Edge Schema
```json
{
  "id": "edge_0",
  "source": "roles_123",
  "target": "actions_456",
  "type": "performs",
  "weight": 1.0
}
```

### Similarity Network Node Schema
```json
{
  "id": 7,
  "label": "Case 24-02",
  "full_title": "NSPE Case 24-02: Environmental Engineer",
  "outcome": "ethical",
  "transformation": "transfer",
  "provisions": ["II.1.a", "III.2.a"],
  "subject_tags": ["environmental", "disclosure"],
  "entity_count": 107,
  "is_focus": false
}
```

### Similarity Network Edge Schema
```json
{
  "source": 7,
  "target": 8,
  "similarity": 0.452,
  "components": {
    "facts_similarity": 0.35,
    "discussion_similarity": 0.42,
    "provision_overlap": 0.65,
    "outcome_alignment": 1.0,
    "tag_overlap": 0.30,
    "principle_overlap": 0.25
  },
  "primary_component": "provision_overlap",
  "matching_provisions": ["II.1.a"]
}
```

## API Endpoints

### Entity Graph API
- **Endpoint**: `GET /scenario_pipeline/case/<id>/entity_graph`
- **Query params**: `?type_hubs=true` adds 9-component hub nodes
- **File**: [app/routes/scenario_pipeline/step4.py](app/routes/scenario_pipeline/step4.py#L367)

### Similarity Network API
- **Endpoint**: `GET /cases/precedents/api/similarity_network`
- **Query params**:
  - `min_score` - Minimum similarity threshold (default: 0.3)
  - `case_id` - Focus case for highlighting
  - `component` - Filter by similarity component
  - `entity_type` - Filter by shared entity type (R, P, O, S, Rs, A, E, Ca, Cs)
  - `tag` - Filter by subject tag
- **File**: [app/routes/precedents.py](app/routes/precedents.py#L222)

## D3.js Force Graph Pattern

Standard pattern used for both Entity Graph and Similarity Network:

```javascript
// 1. Container setup
const svg = d3.select('#graph-svg');
const container = document.getElementById('graph-container');
const width = container.clientWidth;
const height = container.clientHeight;

// 2. Zoom behavior
const zoom = d3.zoom()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => g.attr('transform', event.transform));
svg.call(zoom);
const g = svg.append('g');

// 3. Arrow markers for directed edges
svg.append('defs').append('marker')
    .attr('id', 'arrowhead')
    .attr('viewBox', '-0 -5 10 10')
    .attr('refX', 20)
    .attr('refY', 0)
    .attr('orient', 'auto')
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .append('path')
    .attr('d', 'M 0,-5 L 10,0 L 0,5')
    .attr('fill', '#666');

// 4. Force simulation
const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(80))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(25));

// 5. Edge rendering
const link = g.append('g').selectAll('line')
    .data(edges)
    .enter().append('line')
    .attr('stroke', '#666')
    .attr('stroke-width', 2)
    .attr('marker-end', 'url(#arrowhead)');

// 6. Node rendering
const node = g.append('g').selectAll('g')
    .data(nodes)
    .enter().append('g')
    .call(d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended));

node.append('circle')
    .attr('r', 10)
    .attr('fill', d => d.color);

node.append('text')
    .attr('dy', 20)
    .attr('text-anchor', 'middle')
    .text(d => d.label);

// 7. Tick handler
simulation.on('tick', () => {
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
});

// 8. Drag handlers
function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x; d.fy = d.y;
}
function dragged(event, d) { d.fx = event.x; d.fy = event.y; }
function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null; d.fy = null;
}
```

## Cytoscape.js Hierarchical Pattern

Used for Reasoning Flow (Provisions -> Questions -> Conclusions):

```javascript
const cy = cytoscape({
    container: document.getElementById('cy'),
    elements: elements,
    style: [
        {
            selector: 'node',
            style: {
                'background-color': 'data(color)',
                'label': 'data(label)',
                'shape': function(ele) {
                    const type = ele.data('type');
                    if (type === 'provision') return 'rectangle';
                    if (type === 'question') return 'diamond';
                    if (type === 'conclusion') return 'round-rectangle';
                    return 'ellipse';
                }
            }
        },
        {
            selector: 'edge',
            style: {
                'width': 3,
                'line-color': 'data(color)',
                'target-arrow-shape': 'triangle',
                'curve-style': 'straight'
            }
        }
    ],
    layout: {
        name: 'breadthfirst',
        directed: true,
        spacingFactor: 2.0,
        avoidOverlap: true
    }
});
```

## Color Schemes

### Outcome Colors (Similarity Network)
```javascript
const outcomeColors = {
    'ethical': '#198754',    // Green
    'unethical': '#dc3545',  // Red
    'mixed': '#fd7e14',      // Orange
    'unclear': '#adb5bd'     // Gray
};
```

### Edge Strength Colors
```javascript
const edgeColors = {
    strong: '#198754',  // > 0.5 similarity
    medium: '#ffc107',  // 0.3-0.5 similarity
    weak: '#dc3545'     // < 0.3 similarity
};
```

### Component Filter Colors (Similarity Network)
```javascript
const componentColors = {
    'provision_overlap': '#198754',      // Green
    'discussion_similarity': '#0dcaf0',  // Cyan
    'facts_similarity': '#0d6efd',       // Blue
    'outcome_alignment': '#6c757d',      // Gray
    'tag_overlap': '#fd7e14',            // Orange
    'principle_overlap': '#ffc107'       // Yellow
};
```

## Common UI Components

### Zoom Controls
```html
<div style="position: absolute; bottom: 10px; left: 10px;">
    <button id="zoom-in"><i class="bi bi-plus-lg"></i></button>
    <button id="zoom-out"><i class="bi bi-dash-lg"></i></button>
    <button id="zoom-reset"><i class="bi bi-arrows-fullscreen"></i></button>
</div>
```

### Details Panel
```html
<div id="details-panel" style="position: absolute; top: 10px; right: 10px;
    width: 300px; background: white; border: 1px solid #dee2e6;
    border-radius: 0.25rem; padding: 12px; display: none;">
    <button class="btn-close float-end" id="close-details"></button>
    <h6 id="detail-label"></h6>
    <p class="small" id="detail-definition"></p>
    <ul id="detail-connections"></ul>
</div>
```

### Legend
```html
<div id="legend" class="d-flex flex-wrap gap-3">
    <!-- Dynamically populated with entity type colors -->
</div>
```

## Files Reference

| File | Purpose |
|------|---------|
| [app/routes/scenario_pipeline/step4.py](app/routes/scenario_pipeline/step4.py) | Entity graph API endpoint |
| [app/routes/precedents.py](app/routes/precedents.py) | Similarity network API |
| [app/templates/scenario_pipeline/step4_review.html](app/templates/scenario_pipeline/step4_review.html) | Entity graph + Flow UI |
| [app/templates/similarity_network.html](app/templates/similarity_network.html) | Precedent network UI |
| [docs-internal/ENTITY_GRAPH_IMPLEMENTATION_PROGRESS.md](docs-internal/ENTITY_GRAPH_IMPLEMENTATION_PROGRESS.md) | Implementation history |

## Future Considerations

### Planned Graphs
1. **Entity-Grounded Timeline** - Temporal visualization of actions/events
2. **Sankey Diagram** - Question to Conclusion flow analysis
3. **Board Reasoning Reconstruction** - Parallel reasoning paths

### Standardization Opportunities
1. Extract common D3 patterns to shared module
2. Unified color scheme configuration
3. Shared zoom/pan controls component
4. Common details panel component
5. Consistent tooltip/popover behavior

## Usage

When building or modifying graphs:

1. Use the entity type color scheme from Pass 1-4 for consistency
2. Follow the D3 force graph pattern for new entity visualizations
3. Use Cytoscape for hierarchical/flow visualizations
4. Include standard zoom controls and details panel
5. Ensure API returns proper node/edge schema
6. Add loading overlay for large graphs
