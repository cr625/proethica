document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('network-container');
    const svg = d3.select('#network-svg');
    const focusCaseId = (window.SIMILARITY_NETWORK || {}).focusCaseId ?? null;

    let graphData = null;
    let simulation = null;
    let currentFilter = '';  // Current component filter
    let currentEntityFilter = '';  // Current entity type filter
    let currentTagFilter = '';  // Current subject tag filter
    let availableTags = [];  // All available tags from API
    let currentLayout = 'force';  // Layout type
    let hideUnconnected = true;  // Hide nodes with no connections
    let focusAutoSelected = false;  // Open the focus case's details once on initial load

    // Loading overlay helpers
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingText = loadingOverlay.querySelector('.loading-text');

    function showLoading(message = 'Building graph...') {
        loadingText.textContent = message;
        loadingOverlay.classList.remove('hidden');
    }

    function hideLoading() {
        loadingOverlay.classList.add('hidden');
    }

    // Color scales - matches docs/concepts/color-scheme.md
    const outcomeColors = {
        'ethical': '#198754',
        'unethical': '#dc3545',
        'mixed': '#fd7e14',
        'unclear': '#adb5bd',
        'unknown': '#adb5bd'
    };

    // Component-specific edge colors
    const componentColors = {
        'component_similarity': '#0d6efd',   // blue (D-tuple)
        'provision_overlap': '#198754',      // green
        'tag_overlap': '#fd7e14',            // orange
    };

    function getEdgeColor(edge) {
        // If entity filtering, use gray scale based on shared count
        if (currentEntityFilter || edge.components.entity_type) {
            const count = edge.components.shared_count || 1;
            if (count >= 3) return '#343a40';  // dark gray
            if (count >= 2) return '#6c757d';  // medium gray
            return '#adb5bd';  // light gray
        }
        // If filtering by component, use component color
        if (currentFilter && componentColors[currentFilter]) {
            const score = edge.components[currentFilter] || 0;
            if (score >= 0.5) return componentColors[currentFilter];
            if (score >= 0.3) return d3.color(componentColors[currentFilter]).darker(0.5);
            return d3.color(componentColors[currentFilter]).darker(1);
        }
        // Default: color by overall similarity
        if (edge.similarity >= 0.5) return '#198754';
        if (edge.similarity >= 0.3) return '#ffc107';
        return '#dc3545';
    }

    function loadNetwork() {
        showLoading('Fetching case data...');

        const minScore = document.getElementById('min-score-select').value;
        let url = `/cases/precedents/api/similarity_network?min_score=${minScore}`;
        if (focusCaseId) {
            url += `&case_id=${focusCaseId}`;
        }
        if (currentFilter) {
            url += `&component=${currentFilter}&component_min=${minScore}`;
        }
        if (currentEntityFilter) {
            url += `&entity_type=${currentEntityFilter}`;
        }
        if (currentTagFilter) {
            url += `&tag=${encodeURIComponent(currentTagFilter)}`;
        }

        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    graphData = data;
                    showLoading('Rendering ' + data.nodes.length + ' cases...');
                    // Use setTimeout to allow the loading message to render
                    setTimeout(() => {
                        renderNetwork(data);
                        updateStats(data.metadata);
                        // Populate available tags
                        if (data.all_tags) {
                            availableTags = data.all_tags;
                            populateTagList(data.all_tags);
                        }
                        // Preselect the case the practitioner arrived from, as if it were clicked.
                        // Only on the first load, so later filter/layout reloads do not reopen the panel.
                        if (focusCaseId && !focusAutoSelected) {
                            const focusNode = data.nodes.find(n => n.id === focusCaseId);
                            if (focusNode) {
                                showNodeDetails(null, focusNode);
                                focusAutoSelected = true;
                            }
                        }
                        hideLoading();
                    }, 50);
                } else {
                    hideLoading();
                    console.error('Failed to load network:', data.error);
                    alert('Failed to load network: ' + data.error);
                }
            })
            .catch(error => {
                hideLoading();
                console.error('Error fetching network:', error);
            });
    }

    function renderNetwork(data) {
        const width = container.clientWidth;
        const height = container.clientHeight;

        svg.selectAll('*').remove();

        // Filter out unconnected nodes if option is enabled
        let nodes = data.nodes;
        let edges = data.edges;

        if (hideUnconnected && edges.length > 0) {
            // Find connected node IDs
            const connectedIds = new Set();
            edges.forEach(e => {
                connectedIds.add(e.source.id || e.source);
                connectedIds.add(e.target.id || e.target);
            });
            nodes = nodes.filter(n => connectedIds.has(n.id));
        }

        // Update node/edge counts display
        document.getElementById('node-count').textContent = nodes.length;
        document.getElementById('edge-count').textContent = edges.length;

        // Create zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.2, 4])
            .on('zoom', (event) => {
                g.attr('transform', event.transform);
            });

        svg.call(zoom);

        // Create container group for zoom
        const g = svg.append('g');

        // Apply layout-specific positioning
        currentLayout = document.getElementById('layout-select').value;

        if (currentLayout === 'circular') {
            // Circular layout
            const radius = Math.min(width, height) * 0.35;
            nodes.forEach((node, i) => {
                const angle = (2 * Math.PI * i) / nodes.length;
                node.x = width / 2 + radius * Math.cos(angle);
                node.y = height / 2 + radius * Math.sin(angle);
                node.fx = node.x;
                node.fy = node.y;
            });
        } else if (currentLayout === 'grid') {
            // Grid layout
            const cols = Math.ceil(Math.sqrt(nodes.length));
            const cellWidth = width / (cols + 1);
            const cellHeight = height / (Math.ceil(nodes.length / cols) + 1);
            nodes.forEach((node, i) => {
                node.x = cellWidth * ((i % cols) + 1);
                node.y = cellHeight * (Math.floor(i / cols) + 1);
                node.fx = node.x;
                node.fy = node.y;
            });
        } else if (currentLayout === 'radial') {
            // Radial layout - group by outcome
            const outcomeGroups = {};
            nodes.forEach(n => {
                const outcome = n.outcome || 'unknown';
                if (!outcomeGroups[outcome]) outcomeGroups[outcome] = [];
                outcomeGroups[outcome].push(n);
            });

            const groupKeys = Object.keys(outcomeGroups);
            const groupAngle = (2 * Math.PI) / groupKeys.length;

            groupKeys.forEach((outcome, gi) => {
                const groupNodes = outcomeGroups[outcome];
                const baseAngle = gi * groupAngle;
                const groupRadius = Math.min(width, height) * 0.3;
                const spreadRadius = Math.min(width, height) * 0.12;

                groupNodes.forEach((node, ni) => {
                    const spreadAngle = baseAngle + (ni / groupNodes.length - 0.5) * 0.8;
                    node.x = width / 2 + groupRadius * Math.cos(baseAngle) + spreadRadius * Math.cos(spreadAngle) * (ni % 3);
                    node.y = height / 2 + groupRadius * Math.sin(baseAngle) + spreadRadius * Math.sin(spreadAngle) * (ni % 3);
                    node.fx = node.x;
                    node.fy = node.y;
                });
            });
        } else {
            // Force layout - spread nodes initially across canvas
            const spreadRadius = Math.min(width, height) * 0.4;
            nodes.forEach((node, i) => {
                // Start with a spiral pattern for even initial distribution
                const angle = (2 * Math.PI * i) / nodes.length + (i * 0.5);
                const r = spreadRadius * (0.3 + 0.7 * (i / nodes.length));
                node.x = width / 2 + r * Math.cos(angle);
                node.y = height / 2 + r * Math.sin(angle);
                node.fx = null;
                node.fy = null;
            });
        }

        // Adjust simulation parameters based on edge count
        const edgeCount = edges.length;
        const chargeStrength = edgeCount < 50 ? -800 : (edgeCount < 100 ? -600 : -400);
        const linkDistance = edgeCount < 50 ? 180 : (edgeCount < 100 ? 150 : 120);

        // Create simulation (only active for force layout)
        simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(edges)
                .id(d => d.id)
                .distance(d => linkDistance + (1 - d.similarity) * 80)
                .strength(d => currentLayout === 'force' ? 0.15 + d.similarity * 0.25 : 0))
            .force('charge', d3.forceManyBody().strength(currentLayout === 'force' ? chargeStrength : 0))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(60))
            .force('x', d3.forceX(width / 2).strength(0.02))
            .force('y', d3.forceY(height / 2).strength(0.02));

        // Create edges
        const link = g.append('g')
            .attr('class', 'links')
            .selectAll('line')
            .data(edges)
            .enter().append('line')
            .attr('class', 'link')
            .attr('stroke', d => getEdgeColor(d))
            .attr('stroke-width', d => {
                // Width based on filtered component or overall
                const score = currentFilter ? (d.components[currentFilter] || 0) : d.similarity;
                return 1 + score * 5;
            })
            .on('click', showEdgeDetails)
            .on('mouseover', function(event, d) {
                d3.select(this).classed('highlighted', true);
            })
            .on('mouseout', function(event, d) {
                d3.select(this).classed('highlighted', false);
            });

        // Create nodes
        const node = g.append('g')
            .attr('class', 'nodes')
            .selectAll('g')
            .data(nodes)
            .enter().append('g')
            .attr('class', d => 'node' + (d.is_focus ? ' focus' : ''))
            .call(d3.drag()
                .on('start', dragstarted)
                .on('drag', dragged)
                .on('end', dragended))
            .on('click', showNodeDetails)
            .on('mouseover', highlightConnections)
            .on('mouseout', unhighlightConnections);

        // Node circles
        node.append('circle')
            .attr('r', d => d.is_focus ? 20 : 14)
            .attr('fill', d => outcomeColors[d.outcome] || outcomeColors['unknown']);

        // Node labels
        node.append('text')
            .attr('dy', d => (d.is_focus ? 20 : 14) + 14)
            .text(d => d.label)
            .attr('fill', '#333');

        // Update positions on tick
        simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });

        // Update counts
        document.getElementById('node-count').textContent = data.nodes.length;
        document.getElementById('edge-count').textContent = data.edges.length;

        // Zoom controls
        document.getElementById('zoom-in').onclick = () => {
            svg.transition().call(zoom.scaleBy, 1.3);
        };
        document.getElementById('zoom-out').onclick = () => {
            svg.transition().call(zoom.scaleBy, 0.7);
        };
        document.getElementById('zoom-reset').onclick = () => {
            svg.transition().call(zoom.transform, d3.zoomIdentity);
        };
    }

    function showNodeDetails(event, d) {
        const panel = document.getElementById('details-panel');
        const nodeBox = document.getElementById('node-details');
        nodeBox.style.display = 'block';
        document.getElementById('edge-details').style.display = 'none';

        // Connections at the current threshold
        const connections = graphData.edges.filter(e =>
            e.source.id === d.id || e.target.id === d.id ||
            e.source === d.id || e.target === d.id
        );
        const items = connections.slice(0, 10).map(conn => {
            const otherId = (conn.source.id || conn.source) === d.id ?
                (conn.target.id || conn.target) : (conn.source.id || conn.source);
            const otherNode = graphData.nodes.find(n => n.id === otherId);
            return otherNode ? {
                id: otherNode.id,
                label: otherNode.label,
                outcome: otherNode.outcome,
                extra: `(${conn.similarity.toFixed(2)})`
            } : null;
        }).filter(Boolean);

        // Standard case-details fragment (shared/case_card.js): heading,
        // badges, full title, /cases/<id> link, interactive provision tags.
        CaseCard.render(nodeBox, d, {
            outcomeColors: outcomeColors,
            sections: [{
                title: 'Connected Cases:',
                emptyText: 'No connections at current threshold',
                items: items
            }],
            onItemClick: item => {
                const n = graphData.nodes.find(n => n.id === item.id);
                if (n) showNodeDetails(null, n);
            }
        });

        panel.classList.add('visible');
    }

    function showEdgeDetails(event, d) {
        const panel = document.getElementById('details-panel');
        document.getElementById('node-details').style.display = 'none';
        document.getElementById('edge-details').style.display = 'block';

        const sourceNode = graphData.nodes.find(n => n.id === (d.source.id || d.source));
        const targetNode = graphData.nodes.find(n => n.id === (d.target.id || d.target));

        document.getElementById('edge-source-label').textContent = sourceNode ? sourceNode.label : 'Unknown';
        document.getElementById('edge-target-label').textContent = targetNode ? targetNode.label : 'Unknown';
        document.getElementById('edge-overall-score').textContent = d.similarity.toFixed(3);

        // Component breakdown
        const compDiv = document.getElementById('edge-components');
        compDiv.innerHTML = '';

        // Check if this is an entity-based edge
        if (d.components.entity_type) {
            // Entity overlap edge
            const sharedCount = d.components.shared_count || 0;
            const entityType = d.components.entity_type;
            compDiv.innerHTML = `
                <div class="component-row-mini">
                    <span class="component-label-mini">Entity Type</span>
                    <span class="component-value-mini" style="width: auto;">${entityType}</span>
                </div>
                <div class="component-row-mini">
                    <span class="component-label-mini">Shared Count</span>
                    <span class="component-value-mini" style="width: auto;">${sharedCount}</span>
                </div>
                <div class="component-row-mini">
                    <span class="component-label-mini">Jaccard</span>
                    <div class="component-bar-mini">
                        <div class="score-bar-mini">
                            <div class="score-fill-mini" style="width: ${d.similarity * 100}%; background: #6c757d;"></div>
                        </div>
                    </div>
                    <span class="component-value-mini">${d.similarity.toFixed(2)}</span>
                </div>
            `;
        } else {
            // Similarity-based edge
            const componentLabels = {
                'component_similarity': 'D-tuple',
                'provision_overlap': 'Provisions',
                'tag_overlap': 'Tags',
            };

            for (const [key, label] of Object.entries(componentLabels)) {
                const score = d.components[key] || 0;
                const color = score >= 0.5 ? '#198754' : (score >= 0.3 ? '#ffc107' : '#dc3545');

                compDiv.innerHTML += `
                    <div class="component-row-mini">
                        <span class="component-label-mini">${label}</span>
                        <div class="component-bar-mini">
                            <div class="score-bar-mini">
                                <div class="score-fill-mini" style="width: ${score * 100}%; background: ${color};"></div>
                            </div>
                        </div>
                        <span class="component-value-mini">${score.toFixed(2)}</span>
                    </div>
                `;
            }
        }

        // Matching provisions
        const provDiv = document.getElementById('edge-provisions');
        if (d.matching_provisions && d.matching_provisions.length > 0) {
            provDiv.innerHTML = d.matching_provisions.map(p =>
                `<span class="provision-tag">${p}</span>`
            ).join('');
            provDiv.parentElement.style.display = 'block';
        } else {
            provDiv.innerHTML = '<span class="text-muted small">None</span>';
            if (d.components.entity_type) {
                provDiv.parentElement.style.display = 'none';
            }
        }

        // Matching entities (for entity edges)
        const entitiesSection = document.getElementById('edge-entities-section');
        const entitiesDiv = document.getElementById('edge-entities');
        if (d.matching_entities && d.matching_entities.length > 0) {
            entitiesDiv.innerHTML = d.matching_entities.map(e =>
                `<span class="badge bg-secondary me-1 mb-1" style="font-size: 0.7rem;">${e}</span>`
            ).join('');
            entitiesSection.style.display = 'block';
        } else if (!d.components.entity_type) {
            // Fetch shared entities on-demand for similarity edges
            const sourceId = d.source.id || d.source;
            const targetId = d.target.id || d.target;
            entitiesDiv.innerHTML = '<span class="text-muted small">Loading...</span>';
            entitiesSection.style.display = 'block';

            fetch(`/cases/precedents/api/shared_entities/${sourceId}/${targetId}`)
                .then(r => r.json())
                .then(data => {
                    if (data.success && Object.keys(data.shared_entities).length > 0) {
                        const compColors = {
                            'Roles': '#0d6efd', 'Principles': '#fd7e14', 'Obligations': '#dc3545',
                            'States': '#6f42c1', 'Resources': '#20c997', 'Actions': '#198754',
                            'Events': '#ffc107', 'Capabilities': '#0dcaf0', 'Constraints': '#6c757d'
                        };

                        let html = '';
                        for (const [comp, info] of Object.entries(data.shared_entities)) {
                            const color = compColors[comp] || '#6c757d';
                            html += `<div class="mb-2">`;
                            html += `<span class="badge me-1" style="background:${color};font-size:0.7rem;">${comp} (${info.shared_count})</span>`;
                            html += `<div class="mt-1">`;
                            html += info.shared.map(e =>
                                `<span class="badge bg-light text-dark border me-1 mb-1" style="font-size:0.65rem;">${e}</span>`
                            ).join('');
                            html += `</div></div>`;
                        }

                        entitiesDiv.innerHTML = html;
                    } else {
                        entitiesDiv.innerHTML = '<span class="text-muted small">No shared entities</span>';
                    }
                })
                .catch(() => {
                    entitiesDiv.innerHTML = '<span class="text-muted small">Failed to load</span>';
                });
        } else {
            entitiesSection.style.display = 'none';
        }

        panel.classList.add('visible');
    }

    function highlightConnections(event, d) {
        d3.selectAll('.link')
            .classed('highlighted', l =>
                (l.source.id || l.source) === d.id || (l.target.id || l.target) === d.id
            );
    }

    function unhighlightConnections() {
        d3.selectAll('.link').classed('highlighted', false);
    }

    function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }

    function updateStats(metadata) {
        // Could add more stats display here
        console.log('Network metadata:', metadata);
    }

    // Event listeners
    document.getElementById('close-details').addEventListener('click', function() {
        document.getElementById('details-panel').classList.remove('visible');
    });

    document.getElementById('min-score-select').addEventListener('change', loadNetwork);
    document.getElementById('refresh-btn').addEventListener('click', loadNetwork);

    // Layout and display options
    document.getElementById('layout-select').addEventListener('change', function() {
        if (graphData) {
            showLoading('Applying ' + this.value + ' layout...');
            setTimeout(() => {
                renderNetwork(graphData);
                hideLoading();
            }, 50);
        }
    });

    document.getElementById('hide-unconnected').addEventListener('change', function() {
        hideUnconnected = this.checked;
        if (graphData) {
            showLoading('Updating display...');
            setTimeout(() => {
                renderNetwork(graphData);
                hideLoading();
            }, 50);
        }
    });

    // Fullscreen toggle
    let isFullscreen = false;

    function toggleFullscreen(enter) {
        isFullscreen = enter;
        if (enter) {
            document.body.classList.add('fullscreen-mode');
        } else {
            document.body.classList.remove('fullscreen-mode');
        }
        // Re-render after a brief delay to get new dimensions
        if (graphData) {
            setTimeout(() => {
                renderNetwork(graphData);
            }, 100);
        }
    }

    document.getElementById('fullscreen-btn').addEventListener('click', function() {
        toggleFullscreen(true);
    });

    document.getElementById('exit-fullscreen-btn').addEventListener('click', function() {
        toggleFullscreen(false);
    });

    // ESC key to exit fullscreen
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && isFullscreen) {
            toggleFullscreen(false);
        }
    });

    // Helper to update clear button visibility
    function updateClearButton() {
        const clearBtn = document.getElementById('clear-filter-btn');
        if (currentFilter || currentEntityFilter || currentTagFilter) {
            clearBtn.style.display = 'inline-block';
        } else {
            clearBtn.style.display = 'none';
        }
    }

    // Helper to update filter indicator
    function updateFilterIndicator() {
        const indicator = document.getElementById('filter-indicator');
        const filterLabels = {
            'component_similarity': 'D-tuple Similarity',
            'provision_overlap': 'Provisions',
            'tag_overlap': 'Tags',
        };
        const entityLabels = {
            'Roles': 'Roles',
            'Principles': 'Principles',
            'Obligations': 'Obligations',
            'States': 'States',
            'Resources': 'Resources',
            'actions': 'Actions',
            'events': 'Events',
            'Capabilities': 'Capabilities',
            'Constraints': 'Constraints'
        };

        let parts = [];
        if (currentFilter) {
            parts.push(filterLabels[currentFilter] || currentFilter);
        }
        if (currentEntityFilter) {
            parts.push((entityLabels[currentEntityFilter] || currentEntityFilter) + ' entities');
        }
        if (currentTagFilter) {
            parts.push('Tag: ' + currentTagFilter);
        }

        if (parts.length > 0) {
            indicator.textContent = 'Filtered: ' + parts.join(' + ');
            indicator.style.display = 'inline';
        } else {
            indicator.style.display = 'none';
        }
    }

    // Populate tag list in the expandable section
    function populateTagList(tags) {
        const tagList = document.getElementById('tag-list');
        const activeDisplay = document.getElementById('active-tag-display');

        if (currentTagFilter) {
            // Show active tag filter
            tagList.style.display = 'none';
            activeDisplay.style.display = 'inline';
            document.getElementById('active-tag-name').textContent = currentTagFilter;
        } else {
            // Show available tags
            activeDisplay.style.display = 'none';
            tagList.style.display = 'inline';
            tagList.innerHTML = tags.slice(0, 15).map(tag =>
                `<span class="badge bg-light text-dark tag-badge me-1 mb-1" data-tag="${tag}" title="Filter by ${tag}">
                    <i class="bi bi-tag"></i> ${tag}
                </span>`
            ).join('');

            if (tags.length > 15) {
                tagList.innerHTML += `<span class="badge bg-secondary text-white tag-badge">+${tags.length - 15} more</span>`;
            }

            // Add click handlers to tags
            tagList.querySelectorAll('.tag-badge[data-tag]').forEach(badge => {
                badge.addEventListener('click', function() {
                    currentTagFilter = this.dataset.tag;
                    updateFilterIndicator();
                    updateClearButton();
                    loadNetwork();
                });
            });
        }
    }

    // Similarity filter button handlers
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            // Update active state
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            // Update current filter
            currentFilter = this.dataset.filter;

            // Update UI
            updateFilterIndicator();
            updateClearButton();

            // Reload network with new filter
            loadNetwork();
        });
    });

    // Entity filter button handlers
    document.querySelectorAll('.entity-filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            // Toggle active state
            if (this.classList.contains('active')) {
                this.classList.remove('active');
                currentEntityFilter = '';
            } else {
                document.querySelectorAll('.entity-filter-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                currentEntityFilter = this.dataset.entity;
            }

            // Update UI
            updateFilterIndicator();
            updateClearButton();

            // Reload network with new filter
            loadNetwork();
        });
    });

    // Clear filter button handler
    document.getElementById('clear-filter-btn').addEventListener('click', function() {
        // Reset all filters
        currentFilter = '';
        currentEntityFilter = '';
        currentTagFilter = '';

        // Reset button states
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        document.querySelector('.filter-btn[data-filter=""]').classList.add('active');
        document.querySelectorAll('.entity-filter-btn').forEach(b => b.classList.remove('active'));

        // Update UI
        updateFilterIndicator();
        updateClearButton();

        // Reload network
        loadNetwork();
    });

    // Tag expand button handler
    document.getElementById('tag-expand-btn').addEventListener('click', function() {
        const section = document.getElementById('tag-filter-section');
        const chevron = document.getElementById('tag-chevron');

        if (section.style.display === 'none') {
            section.style.display = 'block';
            this.classList.add('expanded');
            chevron.classList.remove('bi-chevron-down');
            chevron.classList.add('bi-chevron-up');
        } else {
            section.style.display = 'none';
            this.classList.remove('expanded');
            chevron.classList.remove('bi-chevron-up');
            chevron.classList.add('bi-chevron-down');
        }
    });

    // Clear tag filter handler
    document.getElementById('clear-tag-filter').addEventListener('click', function() {
        currentTagFilter = '';
        updateFilterIndicator();
        updateClearButton();
        loadNetwork();
    });

    // Initial load
    loadNetwork();
});
