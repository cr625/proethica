/**
 * Step 4 Review -- D3.js Full Entity Graph with Layout Options.
 *
 * Requires:
 *   - D3.js v7 library loaded
 *   - window.STEP4_CASE_ID (integer)
 *   - DOM elements: #d3-graph-svg, #d3-graph-container, #d3-graph-card,
 *     #d3-loading-overlay, #d3-loading-text, #d3-node-count,
 *     #d3-search, .d3-filter buttons, #d3-layout-select,
 *     #d3-toggle-hubs, #d3-hide-unconnected, #d3-refresh,
 *     #d3-zoom-in, #d3-zoom-out, #d3-zoom-reset,
 *     #d3-fullscreen-btn, #d3-exit-fullscreen-btn,
 *     #d3-entity-details, #d3-detail-label, #d3-detail-type,
 *     #d3-detail-pass, #d3-detail-definition, #d3-detail-metadata,
 *     #d3-detail-agent, #d3-detail-temporal, #d3-detail-connections,
 *     #d3-close-details, #d3-legend,
 *     #d3-pass1, #d3-pass2, #d3-pass3, #d3-pass4,
 *     #entities-tab-badge
 */
(function() {
    var caseId = window.STEP4_CASE_ID;
    if (!caseId) return;

    var svg = d3.select('#d3-graph-svg');
    if (svg.empty()) return;

    var graphData = null;
    var simulation = null;
    var currentFilter = 'all';
    var searchTerm = '';
    var showTypeHubs = true;
    var hideUnconnected = true;
    var currentLayout = 'force';
    var zoom = null;
    var g = null;

    function getContainer() { return document.getElementById('d3-graph-container'); }
    function getGraphCard() { return document.getElementById('d3-graph-card'); }
    function getLoadingOverlay() { return document.getElementById('d3-loading-overlay'); }

    function showLoading(text) {
        var textEl = document.getElementById('d3-loading-text');
        var overlay = getLoadingOverlay();
        if (textEl) textEl.textContent = text || 'Building graph...';
        if (overlay) {
            overlay.classList.remove('d-none');
            overlay.classList.add('d-flex');
        }
    }

    function hideLoading() {
        var overlay = getLoadingOverlay();
        if (overlay) {
            overlay.classList.remove('d-flex');
            overlay.classList.add('d-none');
        }
    }

    function loadGraph() {
        showLoading('Loading entity data...');
        var url = '/scenario_pipeline/case/' + caseId + '/entity_graph' + (showTypeHubs ? '?type_hubs=true' : '');
        fetch(url)
            .then(function(response) { return response.json(); })
            .then(function(data) {
                try {
                    if (data.success) {
                        graphData = data;
                        renderD3Graph(data);
                        updateD3Stats(data.metadata);
                        buildD3Legend(data.metadata.type_colors);
                    } else {
                        console.error('Failed to load graph:', data.error);
                        document.getElementById('d3-node-count').textContent = 'Error loading';
                    }
                } catch (e) {
                    console.error('Error rendering graph:', e);
                }
                hideLoading();
            })
            .catch(function(error) {
                console.error('Error fetching graph:', error);
                document.getElementById('d3-node-count').textContent = 'Error';
                hideLoading();
            });
    }

    function renderD3Graph(data) {
        var container = getContainer();
        var width = container.clientWidth;
        var height = container.clientHeight || 600;

        svg.selectAll('*').remove();

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

        zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', function(event) { g.attr('transform', event.transform); });

        svg.call(zoom);
        g = svg.append('g');

        var filteredNodes = filterD3Nodes(data.nodes);
        var filteredNodeIds = new Set(filteredNodes.map(function(n) { return n.id; }));
        var filteredEdges = data.edges.filter(function(e) {
            return (filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target)) ||
                   (filteredNodeIds.has(e.source && e.source.id) && filteredNodeIds.has(e.target && e.target.id));
        });

        if (hideUnconnected) {
            var connectedNodeIds = new Set();
            filteredEdges.forEach(function(e) {
                connectedNodeIds.add(typeof e.source === 'object' ? e.source.id : e.source);
                connectedNodeIds.add(typeof e.target === 'object' ? e.target.id : e.target);
            });
            filteredNodes = filteredNodes.filter(function(n) { return connectedNodeIds.has(n.id); });
            filteredNodeIds = new Set(filteredNodes.map(function(n) { return n.id; }));
            filteredEdges = data.edges.filter(function(e) {
                return (filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target)) ||
                       (filteredNodeIds.has(e.source && e.source.id) && filteredNodeIds.has(e.target && e.target.id));
            });
        }

        var nodesCopy = filteredNodes.map(function(n) { return Object.assign({}, n); });
        var edgesCopy = filteredEdges.map(function(e) { return Object.assign({}, e); });

        applyLayout(nodesCopy, edgesCopy, width, height);

        var link = g.append('g')
            .attr('class', 'links')
            .selectAll('line')
            .data(edgesCopy)
            .enter().append('line')
            .attr('stroke', function(d) { return d.type === 'instance_of' ? '#ccc' : '#666'; })
            .attr('stroke-opacity', function(d) { return d.type === 'instance_of' ? 0.3 : 0.7; })
            .attr('stroke-width', function(d) { return d.type === 'instance_of' ? 1 : 2; })
            .attr('marker-end', function(d) { return d.type !== 'instance_of' ? 'url(#arrowhead)' : null; });

        var edgeLabels = g.append('g')
            .attr('class', 'edge-labels')
            .selectAll('text')
            .data(edgesCopy.filter(function(e) { return e.type !== 'instance_of'; }))
            .enter().append('text')
            .attr('font-size', '8px')
            .attr('fill', '#666')
            .attr('text-anchor', 'middle')
            .text(function(d) { return d.type.replace(/_/g, ' '); });

        var node = g.append('g')
            .attr('class', 'nodes')
            .selectAll('g')
            .data(nodesCopy)
            .enter().append('g')
            .style('cursor', 'pointer')
            .call(d3.drag()
                .on('start', dragstarted)
                .on('drag', dragged)
                .on('end', dragended))
            .on('click', showD3Details)
            .on('mouseover', function(event, d) {
                d3.select(this).select('circle').attr('stroke-width', 3).attr('stroke', '#333');
                link.attr('stroke-opacity', function(e) { return (e.source.id === d.id || e.target.id === d.id) ? 1 : 0.2; });
            })
            .on('mouseout', function() {
                d3.select(this).select('circle').attr('stroke-width', 2).attr('stroke', '#fff');
                link.attr('stroke-opacity', function(d) { return d.type === 'instance_of' ? 0.3 : 0.7; });
            });

        node.append('circle')
            .attr('r', function(d) { return d.is_hub ? 18 : getD3NodeSize(d); })
            .attr('fill', function(d) { return d.color; })
            .attr('stroke', '#fff')
            .attr('stroke-width', 2);

        node.append('text')
            .attr('dy', function(d) { return (d.is_hub ? 18 : getD3NodeSize(d)) + 12; })
            .attr('text-anchor', 'middle')
            .attr('font-size', function(d) { return d.is_hub ? '10px' : '9px'; })
            .attr('font-weight', function(d) { return d.is_hub ? 'bold' : 'normal'; })
            .attr('fill', '#333')
            .text(function(d) { return truncateD3Label(d.label, d.is_hub ? 20 : 12); });

        if (currentLayout === 'force') {
            simulation.on('tick', function() {
                link.attr('x1', function(d) { return d.source.x; }).attr('y1', function(d) { return d.source.y; })
                    .attr('x2', function(d) { return d.target.x; }).attr('y2', function(d) { return d.target.y; });
                node.attr('transform', function(d) { return 'translate(' + d.x + ',' + d.y + ')'; });
                edgeLabels
                    .attr('x', function(d) { return (d.source.x + d.target.x) / 2; })
                    .attr('y', function(d) { return (d.source.y + d.target.y) / 2; });
            });
        } else {
            link.attr('x1', function(d) { return d.source.x; }).attr('y1', function(d) { return d.source.y; })
                .attr('x2', function(d) { return d.target.x; }).attr('y2', function(d) { return d.target.y; });
            node.attr('transform', function(d) { return 'translate(' + d.x + ',' + d.y + ')'; });
            edgeLabels
                .attr('x', function(d) { return (d.source.x + d.target.x) / 2; })
                .attr('y', function(d) { return (d.source.y + d.target.y) / 2; });
        }

        var hubCount = nodesCopy.filter(function(n) { return n.is_hub; }).length;
        var entityCount = nodesCopy.length - hubCount;
        var totalEntities = data.nodes.filter(function(n) { return !n.is_hub; }).length;
        var hiddenCount = totalEntities - entityCount;

        var statsText = 'Showing ' + entityCount + ' of ' + totalEntities + ' entities';
        if (hubCount > 0) statsText += ' (+ ' + hubCount + ' type hubs)';
        if (hiddenCount > 0) statsText += ' - ' + hiddenCount + ' unconnected hidden';
        document.getElementById('d3-node-count').textContent = statsText;

        var tabBadge = document.getElementById('entities-tab-badge');
        if (tabBadge) tabBadge.textContent = entityCount;
    }

    function applyLayout(nodes, edges, width, height) {
        if (currentLayout === 'force') {
            simulation = d3.forceSimulation(nodes)
                .force('link', d3.forceLink(edges).id(function(d) { return d.id; }).distance(function(d) { return d.type === 'instance_of' ? 35 : 60; }).strength(1.5))
                .force('charge', d3.forceManyBody().strength(function(d) { return d.is_hub ? -250 : -120; }))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('collision', d3.forceCollide().radius(function(d) { return d.is_hub ? 45 : 30; }))
                .force('x', d3.forceX(width / 2).strength(0.08))
                .force('y', d3.forceY(height / 2).strength(0.08));
        } else if (currentLayout === 'circular') {
            var typeGroups = {};
            nodes.forEach(function(n) {
                if (!typeGroups[n.type]) typeGroups[n.type] = [];
                typeGroups[n.type].push(n);
            });
            var angleOffset = 0;
            var radius = Math.min(width, height) / 2.5;
            Object.values(typeGroups).forEach(function(group) {
                var angleStep = (2 * Math.PI) / nodes.length;
                group.forEach(function(n, i) {
                    var angle = angleOffset + i * angleStep;
                    n.x = width / 2 + radius * Math.cos(angle);
                    n.y = height / 2 + radius * Math.sin(angle);
                });
                angleOffset += group.length * angleStep;
            });
            resolveEdgeReferences(nodes, edges);
        } else if (currentLayout === 'grid') {
            var hubs = nodes.filter(function(n) { return n.is_hub; });
            var others = nodes.filter(function(n) { return !n.is_hub; });
            var cols = Math.ceil(Math.sqrt(others.length));
            var cellWidth = width / (cols + 1);
            var cellHeight = (height - 100) / (Math.ceil(others.length / cols) + 1);
            hubs.forEach(function(n, i) {
                n.x = (i + 1) * (width / (hubs.length + 1));
                n.y = 40;
            });
            others.forEach(function(n, i) {
                var row = Math.floor(i / cols);
                var col = i % cols;
                n.x = (col + 1) * cellWidth;
                n.y = 100 + (row + 1) * cellHeight;
            });
            resolveEdgeReferences(nodes, edges);
        } else if (currentLayout === 'radial') {
            var hubs2 = nodes.filter(function(n) { return n.is_hub; });
            var others2 = nodes.filter(function(n) { return !n.is_hub; });
            var centerX = width / 2;
            var centerY = height / 2;
            var innerRadius = 60;
            hubs2.forEach(function(n, i) {
                var angle = (i / hubs2.length) * 2 * Math.PI;
                n.x = centerX + innerRadius * Math.cos(angle);
                n.y = centerY + innerRadius * Math.sin(angle);
            });
            var passGroups = {1: [], 2: [], 3: [], 4: []};
            others2.forEach(function(n) {
                if (passGroups[n.pass]) passGroups[n.pass].push(n);
                else passGroups[1].push(n);
            });
            var ringRadius = 120;
            Object.values(passGroups).forEach(function(group) {
                if (group.length === 0) return;
                group.forEach(function(n, i) {
                    var angle = (i / group.length) * 2 * Math.PI;
                    n.x = centerX + ringRadius * Math.cos(angle);
                    n.y = centerY + ringRadius * Math.sin(angle);
                });
                ringRadius += 80;
            });
            resolveEdgeReferences(nodes, edges);
        }
    }

    function resolveEdgeReferences(nodes, edges) {
        var nodeMap = new Map(nodes.map(function(n) { return [n.id, n]; }));
        edges.forEach(function(e) {
            if (typeof e.source === 'string') e.source = nodeMap.get(e.source) || e.source;
            if (typeof e.target === 'string') e.target = nodeMap.get(e.target) || e.target;
        });
    }

    function filterD3Nodes(nodes) {
        return nodes.filter(function(n) {
            if (currentFilter !== 'all' && n.pass !== parseInt(currentFilter)) return false;
            if (searchTerm && !n.label.toLowerCase().includes(searchTerm.toLowerCase())) return false;
            return true;
        });
    }

    function getD3NodeSize(node) {
        var sizes = { 'roles': 10, 'principles': 8, 'obligations': 8, 'temporal_dynamics_enhanced': 8,
                       'ethical_question': 9, 'ethical_conclusion': 9, 'code_provision_reference': 8 };
        return sizes[node.type] || 7;
    }

    function truncateD3Label(label, maxLen) {
        return label.length <= maxLen ? label : label.substring(0, maxLen) + '...';
    }

    function showD3Details(event, d) {
        var panel = document.getElementById('d3-entity-details');
        document.getElementById('d3-detail-label').textContent = d.label;
        document.getElementById('d3-detail-label').style.borderColor = d.color;

        var typeBadge = document.getElementById('d3-detail-type');
        typeBadge.textContent = d.type.replace(/_/g, ' ');
        typeBadge.style.backgroundColor = d.color;

        var passNames = {1: 'Pass 1', 2: 'Pass 2', 3: 'Pass 3', 4: 'Step 4'};
        document.getElementById('d3-detail-pass').textContent = passNames[d.pass] || 'Unknown';
        document.getElementById('d3-detail-definition').textContent = d.definition || 'No definition available';

        var metadataDiv = document.getElementById('d3-detail-metadata');
        var agentDiv = document.getElementById('d3-detail-agent');
        var temporalDiv = document.getElementById('d3-detail-temporal');
        var hasMetadata = false;

        if (d.agent) {
            agentDiv.querySelector('span').textContent = d.agent;
            agentDiv.style.display = 'block';
            hasMetadata = true;
        } else {
            agentDiv.style.display = 'none';
        }

        if (d.temporal_marker) {
            temporalDiv.querySelector('span').textContent = d.temporal_marker;
            temporalDiv.style.display = 'block';
            hasMetadata = true;
        } else {
            temporalDiv.style.display = 'none';
        }

        metadataDiv.style.display = hasMetadata ? 'block' : 'none';

        var connections = graphData.edges.filter(function(e) {
            return e.source === d.id || e.target === d.id ||
                   (e.source && e.source.id === d.id) || (e.target && e.target.id === d.id);
        });

        var connEl = document.getElementById('d3-detail-connections');
        connEl.innerHTML = connections.length === 0 ? '<li class="text-muted">None</li>' : '';
        connections.forEach(function(conn) {
            var isSource = conn.source === d.id || (conn.source && conn.source.id === d.id);
            var otherId = isSource ? (conn.target && conn.target.id || conn.target) : (conn.source && conn.source.id || conn.source);
            var otherNode = graphData.nodes.find(function(n) { return n.id === otherId; });
            if (otherNode) {
                var li = document.createElement('li');
                li.innerHTML = '<span style="color:' + otherNode.color + '">' + (isSource ? '&#8594;' : '&#8592;') + '</span> ' + otherNode.label;
                connEl.appendChild(li);
            }
        });
        panel.style.display = 'block';
    }

    function dragstarted(event, d) {
        if (!event.active && simulation) simulation.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
    }
    function dragged(event, d) { d.fx = event.x; d.fy = event.y; }
    function dragended(event, d) {
        if (!event.active && simulation) simulation.alphaTarget(0);
        d.fx = null; d.fy = null;
    }

    function updateD3Stats(metadata) {
        var pc = metadata.pass_counts;
        document.getElementById('d3-pass1').textContent = 'Context: ' + (pc[1] || 0);
        document.getElementById('d3-pass2').textContent = 'Normative: ' + (pc[2] || 0);
        document.getElementById('d3-pass3').textContent = 'Temporal: ' + (pc[3] || 0);
        document.getElementById('d3-pass4').textContent = 'Synthesis: ' + (pc[4] || 0);
    }

    function buildD3Legend(colors) {
        var container = document.getElementById('d3-legend');
        container.innerHTML = '';
        var labels = {
            'roles': 'Roles', 'states': 'States', 'resources': 'Resources',
            'principles': 'Principles', 'obligations': 'Obligations', 'constraints': 'Constraints',
            'capabilities': 'Capabilities', 'temporal_dynamics_enhanced': 'Actions/Events',
            'code_provision_reference': 'Provisions', 'ethical_question': 'Questions', 'ethical_conclusion': 'Conclusions'
        };
        Object.entries(colors).forEach(function(entry) {
            var type = entry[0], color = entry[1];
            if (labels[type]) {
                var span = document.createElement('span');
                span.innerHTML = '<span style="display:inline-block;width:12px;height:12px;background:' + color + ';border-radius:50%;margin-right:5px;"></span>' + labels[type];
                container.appendChild(span);
            }
        });
    }

    // Filter buttons
    document.querySelectorAll('.d3-filter').forEach(function(btn) {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.d3-filter').forEach(function(b) { b.classList.remove('active'); });
            this.classList.add('active');
            currentFilter = this.dataset.pass;
            if (graphData) renderD3Graph(graphData);
        });
    });

    // Search
    var searchEl = document.getElementById('d3-search');
    if (searchEl) {
        searchEl.addEventListener('input', function() {
            searchTerm = this.value;
            if (graphData) renderD3Graph(graphData);
        });
    }

    // Close details
    var closeBtn = document.getElementById('d3-close-details');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            document.getElementById('d3-entity-details').style.display = 'none';
        });
    }

    // Type hubs toggle
    var hubsBtn = document.getElementById('d3-toggle-hubs');
    if (hubsBtn) {
        hubsBtn.addEventListener('click', function() {
            showTypeHubs = !showTypeHubs;
            this.classList.toggle('active', showTypeHubs);
            this.classList.toggle('btn-info', showTypeHubs);
            this.classList.toggle('btn-outline-info', !showTypeHubs);
            loadGraph();
        });
    }

    // Hide unconnected toggle
    var hideBtn = document.getElementById('d3-hide-unconnected');
    if (hideBtn) {
        hideBtn.addEventListener('change', function() {
            hideUnconnected = this.checked;
            if (graphData) renderD3Graph(graphData);
        });
    }

    // Layout select
    var layoutSelect = document.getElementById('d3-layout-select');
    if (layoutSelect) {
        layoutSelect.addEventListener('change', function() {
            currentLayout = this.value;
            if (graphData) renderD3Graph(graphData);
        });
    }

    // Refresh
    var refreshBtn = document.getElementById('d3-refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() { loadGraph(); });
    }

    // Zoom controls
    var zoomInBtn = document.getElementById('d3-zoom-in');
    if (zoomInBtn) zoomInBtn.addEventListener('click', function() { if (zoom) svg.transition().call(zoom.scaleBy, 1.3); });
    var zoomOutBtn = document.getElementById('d3-zoom-out');
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', function() { if (zoom) svg.transition().call(zoom.scaleBy, 0.7); });
    var zoomResetBtn = document.getElementById('d3-zoom-reset');
    if (zoomResetBtn) zoomResetBtn.addEventListener('click', function() { if (zoom) svg.transition().call(zoom.transform, d3.zoomIdentity); });

    // Fullscreen
    var fsBtn = document.getElementById('d3-fullscreen-btn');
    if (fsBtn) {
        fsBtn.addEventListener('click', function() {
            var card = getGraphCard();
            if (card) card.classList.add('fullscreen');
            this.style.display = 'none';
            document.getElementById('d3-exit-fullscreen-btn').style.display = 'inline-block';
            setTimeout(function() { if (graphData) renderD3Graph(graphData); }, 100);
        });
    }

    var exitFsBtn = document.getElementById('d3-exit-fullscreen-btn');
    if (exitFsBtn) {
        exitFsBtn.addEventListener('click', function() {
            var card = getGraphCard();
            if (card) card.classList.remove('fullscreen');
            this.style.display = 'none';
            document.getElementById('d3-fullscreen-btn').style.display = 'inline-block';
            setTimeout(function() { if (graphData) renderD3Graph(graphData); }, 100);
        });
    }

    // ESC to exit fullscreen
    document.addEventListener('keydown', function(e) {
        var card = getGraphCard();
        if (e.key === 'Escape' && card && card.classList.contains('fullscreen')) {
            document.getElementById('d3-exit-fullscreen-btn').click();
        }
    });

    // Initialize
    function initGraph() {
        var btn = document.getElementById('d3-toggle-hubs');
        if (btn) {
            btn.classList.toggle('active', showTypeHubs);
            btn.classList.toggle('btn-info', showTypeHubs);
            btn.classList.toggle('btn-outline-info', !showTypeHubs);
        }
        loadGraph();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initGraph);
    } else {
        initGraph();
    }
})();
