document.addEventListener('DOMContentLoaded', function() {
    const frame = document.getElementById('print-frame');
    const svg = d3.select('#print-svg');
    let graphData = null;
    let simulation = null;

    let currentHops = (window.LINEAGE_PRINT || {}).hops;
    const MIN_HOPS = 1, MAX_HOPS = 8;

    const outcomeColors = {
        'ethical': '#198754',
        'unethical': '#dc3545',
        'mixed': '#fd7e14',
        'unknown': '#adb5bd',
        'unclear': '#adb5bd'
    };

    function updateHopsDisplay() {
        document.getElementById('hops-value').textContent = currentHops;
        document.getElementById('hops-minus').disabled = currentHops <= MIN_HOPS;
        document.getElementById('hops-plus').disabled = currentHops >= MAX_HOPS;
    }

    function toggleHopsControl() {
        const caseId = document.getElementById('case-selector').value;
        document.getElementById('hops-control').style.display = caseId ? 'flex' : 'none';
    }

    function loadGraph() {
        const caseId = document.getElementById('case-selector').value;
        let url = '/cases/precedents/api/lineage_graph?';
        if (caseId) url += `case_id=${caseId}&hops=${currentHops}&`;

        fetch(url)
            .then(r => r.json())
            .then(data => {
                if (!data.success) return;
                graphData = data;
                document.getElementById('stats-text').textContent =
                    data.nodes.length + ' cases, ' + data.edges.length + ' citations';
                renderGraph(data);
                // Auto-open detail panel for focus case
                if (caseId && document.getElementById('show-panel').checked) {
                    const focusNode = data.nodes.find(n => n.is_focus);
                    if (focusNode) showNodeDetails(focusNode);
                }
            });
    }

    function renderGraph(data) {
        const width = frame.clientWidth;
        const height = frame.clientHeight;
        const legendHeight = 32;
        const graphHeight = height - legendHeight;
        svg.selectAll('*').remove();

        if (!data.nodes.length) return;

        const nodes = data.nodes;
        const edges = data.edges;
        const showLabels = document.getElementById('show-labels').checked;

        const years = nodes.map(n => n.year).filter(y => y > 0);
        const minYear = Math.min(...years);
        const maxYear = Math.max(...years);
        const topMargin = 40;
        const bottomMargin = 40;
        const leftMargin = 50;

        const yScale = d3.scaleLinear()
            .domain([minYear, maxYear])
            .range([topMargin, graphHeight - bottomMargin]);

        nodes.forEach(n => {
            n.fy = n.year > 0 ? yScale(n.year) : topMargin;
            if (n.x === undefined) {
                n.x = leftMargin + (width - leftMargin) / 2 + (Math.random() - 0.5) * (width * 0.4);
            }
        });

        const maxInDegree = Math.max(1, d3.max(nodes, n => n.in_degree));
        const radiusScale = d3.scaleSqrt().domain([0, maxInDegree]).range([7, 22]);

        const zoom = d3.zoom()
            .scaleExtent([0.3, 5])
            .on('zoom', (event) => g.attr('transform', event.transform));
        svg.call(zoom);
        const g = svg.append('g');

        // Markers
        svg.append('defs').append('marker')
            .attr('id', 'arrow').attr('viewBox', '0 -5 10 10')
            .attr('refX', 10).attr('refY', 0)
            .attr('markerWidth', 7).attr('markerHeight', 7)
            .attr('orient', 'auto')
            .append('path').attr('d', 'M0,-4L8,0L0,4').attr('fill', '#999');

        svg.select('defs').append('marker')
            .attr('id', 'arrow-hl').attr('viewBox', '0 -5 10 10')
            .attr('refX', 10).attr('refY', 0)
            .attr('markerWidth', 7).attr('markerHeight', 7)
            .attr('orient', 'auto')
            .append('path').attr('d', 'M0,-4L8,0L0,4').attr('fill', '#0d6efd');

        // Year gridlines
        const decades = [];
        for (let y = Math.ceil(minYear / 10) * 10; y <= maxYear; y += 10) decades.push(y);

        g.selectAll('.year-gridline').data(decades).enter().append('line')
            .attr('class', 'year-gridline')
            .attr('x1', leftMargin).attr('y1', d => yScale(d))
            .attr('x2', width).attr('y2', d => yScale(d));

        g.selectAll('.year-label').data(decades).enter().append('text')
            .attr('class', 'year-label')
            .attr('x', leftMargin - 6).attr('y', d => yScale(d) + 4)
            .attr('text-anchor', 'end').text(d => d);

        // Forces scaled by node count
        const nodeCount = nodes.length;
        const chargeStr = nodeCount < 20 ? -500 : nodeCount < 50 ? -350 : -150;
        const centerStr = nodeCount < 20 ? 0.015 : nodeCount < 50 ? 0.025 : 0.04;
        const collisionPad = nodeCount < 20 ? 20 : nodeCount < 50 ? 14 : 8;

        simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(edges).id(d => d.id).strength(0.03))
            .force('charge', d3.forceManyBody().strength(chargeStr))
            .force('x', d3.forceX((leftMargin + width) / 2).strength(centerStr))
            .force('collision', d3.forceCollide().radius(d => radiusScale(d.in_degree) + collisionPad))
            .alphaDecay(0.03)
            .on('tick', ticked);

        const link = g.append('g').selectAll('path').data(edges)
            .enter().append('path')
            .attr('class', 'citation-link')
            .attr('stroke-width', 1.5)
            .attr('marker-end', 'url(#arrow)');

        const node = g.append('g').selectAll('g').data(nodes)
            .enter().append('g')
            .attr('class', d => 'node' + (d.is_focus ? ' focus' : ''))
            .on('click', (e, d) => { e.stopPropagation(); showNodeDetails(d); })
            .on('mouseover', highlightLineage)
            .on('mouseout', resetHighlight)
            .call(d3.drag()
                .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; })
                .on('drag', (e, d) => { d.fx = e.x; })
                .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; }));

        node.append('circle')
            .attr('r', d => d.is_focus ? radiusScale(d.in_degree) + 4 : radiusScale(d.in_degree))
            .attr('fill', d => outcomeColors[d.outcome] || outcomeColors['unknown']);

        node.append('text')
            .attr('dy', d => radiusScale(d.in_degree) + 14)
            .attr('visibility', showLabels ? 'visible' : 'hidden')
            .text(d => d.label);

        function ticked() {
            nodes.forEach(n => {
                const r = radiusScale(n.in_degree);
                n.x = Math.max(leftMargin + r, Math.min(width - r, n.x));
            });
            link.attr('d', d => {
                const sx = d.source.x, sy = d.source.y;
                const tx = d.target.x, ty = d.target.y;
                const r = radiusScale(d.target.in_degree) + 4;
                const dx = tx - sx, dy = ty - sy;
                const dist = Math.sqrt(dx*dx + dy*dy) || 1;
                const ex = tx - (dx/dist)*r, ey = ty - (dy/dist)*r;
                const mx = (sx+ex)/2 + dy*0.08, my = (sy+ey)/2 - dx*0.08;
                return `M${sx},${sy} Q${mx},${my} ${ex},${ey}`;
            });
            node.attr('transform', d => `translate(${d.x},${d.y})`);
        }

        simulation.on('end', fitToView);
        setTimeout(fitToView, 2000);

        function fitToView() {
            if (!nodes.length) return;
            const pad = d3.max(nodes, n => radiusScale(n.in_degree)) + 20;
            const xExt = d3.extent(nodes, n => n.x);
            const yExt = d3.extent(nodes, n => n.fy !== undefined ? n.fy : n.y);
            const bx = xExt[0] - pad, by = yExt[0] - pad;
            const bw = (xExt[1] - xExt[0]) + pad*2;
            const bh = (yExt[1] - yExt[0]) + pad*2;
            if (bw === 0 || bh === 0) return;

            const scale = Math.min(width / bw, graphHeight / bh, 1.5);
            const tx = (width - bw*scale)/2 - bx*scale;
            const ty = (graphHeight - bh*scale)/2 - by*scale;
            svg.transition().duration(500).call(
                zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
        }
    }

    function highlightLineage(event, d) {
        const outgoing = new Set(), incoming = new Set();
        graphData.edges.forEach(e => {
            const sid = e.source.id !== undefined ? e.source.id : e.source;
            const tid = e.target.id !== undefined ? e.target.id : e.target;
            if (sid === d.id) outgoing.add(tid);
            if (tid === d.id) incoming.add(sid);
        });
        d3.selectAll('.node').attr('opacity', n =>
            n.id === d.id || outgoing.has(n.id) || incoming.has(n.id) ? 1 : 0.12);
        d3.selectAll('.citation-link').each(function(e) {
            const sid = e.source.id !== undefined ? e.source.id : e.source;
            const tid = e.target.id !== undefined ? e.target.id : e.target;
            const connected = sid === d.id || tid === d.id;
            d3.select(this)
                .attr('stroke-opacity', connected ? 0.9 : 0.04)
                .attr('stroke-width', connected ? 3 : 1.5)
                .attr('stroke', connected ? '#0d6efd' : '#999')
                .attr('marker-end', connected ? 'url(#arrow-hl)' : 'url(#arrow)');
        });
    }

    function resetHighlight() {
        d3.selectAll('.node').attr('opacity', 1);
        d3.selectAll('.citation-link')
            .attr('stroke-opacity', 0.4).attr('stroke-width', 1.5)
            .attr('stroke', '#999').attr('marker-end', 'url(#arrow)');
    }

    function showNodeDetails(d) {
        const panel = document.getElementById('details-panel');
        const title = document.getElementById('detail-title');
        const content = document.getElementById('detail-content');
        const color = outcomeColors[d.outcome] || outcomeColors['unknown'];
        title.style.borderColor = color;
        title.textContent = d.label;

        const nodeMap = {};
        graphData.nodes.forEach(n => { nodeMap[n.id] = n; });
        const cites = [], citedBy = [];
        graphData.edges.forEach(e => {
            const sid = e.source.id !== undefined ? e.source.id : e.source;
            const tid = e.target.id !== undefined ? e.target.id : e.target;
            if (sid === d.id && nodeMap[tid]) cites.push(nodeMap[tid]);
            if (tid === d.id && nodeMap[sid]) citedBy.push(nodeMap[sid]);
        });

        let html = `
            <div class="mb-2"><strong>${d.full_title}</strong></div>
            <div class="small text-muted mb-2">
                Year: ${d.year} &middot;
                Outcome: <span style="color:${color}; font-weight:600">${d.outcome}</span>
            </div>
            <hr class="my-2">`;

        if (cites.length > 0) {
            html += `<div class="small text-muted mb-1"><strong>Cites ${cites.length} precedent${cites.length > 1 ? 's' : ''}:</strong></div>`;
            cites.sort((a, b) => a.year - b.year);
            cites.forEach(c => {
                html += `<div class="citation-list-item">
                    <span style="color:${outcomeColors[c.outcome]||'#999'}">&#9679;</span>
                    ${c.label} (${c.year}) - ${c.full_title.substring(0, 45)}${c.full_title.length > 45 ? '...' : ''}
                </div>`;
            });
        } else {
            html += `<div class="small text-muted mb-1">Does not cite any precedents in the database.</div>`;
        }

        if (citedBy.length > 0) {
            html += `<hr class="my-2"><div class="small text-muted mb-1"><strong>Cited by ${citedBy.length} case${citedBy.length > 1 ? 's' : ''}:</strong></div>`;
            citedBy.sort((a, b) => a.year - b.year);
            citedBy.forEach(c => {
                html += `<div class="citation-list-item">
                    <span style="color:${outcomeColors[c.outcome]||'#999'}">&#9679;</span>
                    ${c.label} (${c.year}) - ${c.full_title.substring(0, 45)}${c.full_title.length > 45 ? '...' : ''}
                </div>`;
            });
        } else {
            html += `<hr class="my-2"><div class="small text-muted mb-1">Not cited by any case in the database.</div>`;
        }

        content.innerHTML = html;
        panel.classList.add('visible');
    }

    // ── Controls ──
    document.getElementById('close-details').addEventListener('click', () => {
        document.getElementById('details-panel').classList.remove('visible');
    });

    svg.on('click', () => {
        document.getElementById('details-panel').classList.remove('visible');
    });

    document.getElementById('case-selector').addEventListener('change', function() {
        toggleHopsControl();
        if (!this.value) {
            document.getElementById('details-panel').classList.remove('visible');
        } else {
            currentHops = 2;
            updateHopsDisplay();
        }
        loadGraph();
    });

    document.getElementById('hops-minus').addEventListener('click', () => {
        if (currentHops > MIN_HOPS) { currentHops--; updateHopsDisplay(); loadGraph(); }
    });
    document.getElementById('hops-plus').addEventListener('click', () => {
        if (currentHops < MAX_HOPS) { currentHops++; updateHopsDisplay(); loadGraph(); }
    });

    document.getElementById('preset-selector').addEventListener('change', function() {
        frame.className = 'preset-' + this.value;
        if (graphData) setTimeout(() => renderGraph(graphData), 50);
    });

    document.getElementById('show-labels').addEventListener('change', function() {
        d3.selectAll('.node text').attr('visibility', this.checked ? 'visible' : 'hidden');
    });

    document.getElementById('show-panel').addEventListener('change', function() {
        if (!this.checked) {
            document.getElementById('details-panel').classList.remove('visible');
        } else if (graphData) {
            const focusNode = graphData.nodes.find(n => n.is_focus);
            if (focusNode) showNodeDetails(focusNode);
        }
    });

    // Init
    toggleHopsControl();
    updateHopsDisplay();
    loadGraph();
});
