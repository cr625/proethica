/**
 * Step 4 Review -- Cytoscape.js Synthesis Reasoning Flow Graph.
 *
 * Requires:
 *   - Cytoscape.js library loaded
 *   - window.STEP4_FLOW_DATA = { provisions: [...], questions: [...], conclusions: [...] }
 *   - DOM elements: #cy, #reset-graph, #show-labels, #cy-details-panel,
 *     #cy-detail-label, #cy-detail-type, #cy-detail-text, #cy-detail-edges,
 *     #cy-close-details, #cy-zoom-in, #cy-zoom-out, #cy-zoom-fit,
 *     #cy-fullscreen-btn, #cy-exit-fullscreen-btn, #cy-graph-card
 */

document.addEventListener('DOMContentLoaded', function() {
    var flowData = window.STEP4_FLOW_DATA;
    if (!flowData) return;

    var provisions = flowData.provisions || [];
    var questions = flowData.questions || [];
    var conclusions = flowData.conclusions || [];

    // Build graph elements
    var elements = [];
    var nodeIds = new Set();
    var edgeIds = new Set();

    // Add Provision nodes
    provisions.forEach(function(prov) {
        var nodeId = 'prov_' + prov.id;
        var provCode = (prov.rdf_json_ld && prov.rdf_json_ld.codeProvision) || prov.entity_label;

        nodeIds.add(nodeId);
        elements.push({
            group: 'nodes',
            data: {
                id: nodeId,
                label: provCode,
                type: 'provision',
                fullText: prov.entity_definition,
                nodeType: 'NSPE Provision'
            }
        });

        // Edges from provisions to mentioned entities
        if (prov.rdf_json_ld && prov.rdf_json_ld.appliesTo) {
            prov.rdf_json_ld.appliesTo.forEach(function(entity) {
                var entityId = 'entity_' + entity.entity_label.replace(/\s+/g, '_');

                if (!nodeIds.has(entityId)) {
                    nodeIds.add(entityId);
                    elements.push({
                        group: 'nodes',
                        data: {
                            id: entityId,
                            label: entity.entity_label,
                            type: entity.entity_type,
                            reasoning: entity.reasoning,
                            nodeType: 'Entity'
                        }
                    });
                }

                var edgeId = nodeId + '_' + entityId;
                if (!edgeIds.has(edgeId) && nodeId !== entityId) {
                    edgeIds.add(edgeId);
                    elements.push({
                        group: 'edges',
                        data: {
                            id: edgeId,
                            source: nodeId,
                            target: entityId,
                            label: 'applies to',
                            edgeType: 'provision_to_entity'
                        }
                    });
                }
            });
        }
    });

    // Add Question nodes
    questions.forEach(function(q) {
        var nodeId = 'q_' + q.id;
        nodeIds.add(nodeId);

        elements.push({
            group: 'nodes',
            data: {
                id: nodeId,
                label: q.entity_label,
                type: 'question',
                fullText: q.entity_definition,
                nodeType: 'Question'
            }
        });

        // Link questions to related provisions
        if (q.rdf_json_ld && q.rdf_json_ld.relatedProvisions) {
            q.rdf_json_ld.relatedProvisions.forEach(function(provCode) {
                var provNode = provisions.find(function(p) {
                    return (p.rdf_json_ld && p.rdf_json_ld.codeProvision === provCode) ||
                           p.entity_label.includes(provCode);
                });
                if (provNode) {
                    var provId = 'prov_' + provNode.id;
                    var edgeId = provId + '_' + nodeId;
                    if (!edgeIds.has(edgeId) && nodeIds.has(provId) && provId !== nodeId) {
                        edgeIds.add(edgeId);
                        elements.push({
                            group: 'edges',
                            data: {
                                id: edgeId,
                                source: provId,
                                target: nodeId,
                                label: 'informs',
                                edgeType: 'provision_to_question'
                            }
                        });
                    }
                }
            });
        }
    });

    // Add Conclusion nodes
    conclusions.forEach(function(c) {
        var nodeId = 'c_' + c.id;
        nodeIds.add(nodeId);

        elements.push({
            group: 'nodes',
            data: {
                id: nodeId,
                label: c.entity_label,
                type: 'conclusion',
                fullText: c.entity_definition,
                nodeType: 'Conclusion'
            }
        });

        // Link conclusions to questions they answer
        if (c.rdf_json_ld && c.rdf_json_ld.answersQuestions) {
            c.rdf_json_ld.answersQuestions.forEach(function(qNum) {
                var qNode = questions.find(function(q) {
                    return q.entity_label.includes(qNum) || q.entity_label.includes('Question_' + qNum);
                });
                if (qNode) {
                    var qId = 'q_' + qNode.id;
                    var edgeId = qId + '_' + nodeId;
                    if (!edgeIds.has(edgeId) && nodeIds.has(qId) && qId !== nodeId) {
                        edgeIds.add(edgeId);
                        elements.push({
                            group: 'edges',
                            data: {
                                id: edgeId,
                                source: qId,
                                target: nodeId,
                                label: 'answered by',
                                edgeType: 'question_to_conclusion'
                            }
                        });
                    }
                }
            });
        }
    });

    // Filter out invalid edges
    var validElements = elements.filter(function(el) {
        if (el.group === 'edges') {
            if (el.data.source === el.data.target) return false;
            if (!nodeIds.has(el.data.source) || !nodeIds.has(el.data.target)) return false;
        }
        return true;
    });

    // Helpers
    function formatLabelForDisplay(label) {
        if (!label) return '';
        var formatted = label.replace(/_/g, ' ');
        formatted = formatted.replace(/\b\w/g, function(c) { return c.toUpperCase(); });
        return formatted;
    }

    function isShortCode(label) {
        if (!label) return false;
        return /^[IVX]+\.\d+(\.[a-z])?$/.test(label) ||
               /^[A-Z][a-z]?$/.test(label) ||
               /^[QC]\d+$/.test(label);
    }

    // Node color map
    var nodeColors = {
        'provision': '#495057',
        'question': '#0dcaf0',
        'conclusion': '#198754',
        'action': '#212529',
        'event': '#6c757d',
        'R': '#1e40af',
        'P': '#7c3aed',
        'O': '#dc2626',
        'S': '#0891b2',
        'Rs': '#d97706',
        'A': '#374151',
        'E': '#059669',
        'Ca': '#7c2d12',
        'Cs': '#be185d'
    };

    // Initialize Cytoscape
    var cy = cytoscape({
        container: document.getElementById('cy'),
        elements: validElements,
        style: [
            {
                selector: 'node',
                style: {
                    'background-color': function(ele) {
                        return nodeColors[ele.data('type')] || '#1d4ed8';
                    },
                    'label': function(ele) {
                        var label = ele.data('label') || '';
                        var type = ele.data('type');
                        var displayLabel = formatLabelForDisplay(label);
                        var maxLen;
                        if (type === 'provision') maxLen = 10;
                        else if (type === 'question' || type === 'conclusion') maxLen = 14;
                        else if (isShortCode(label)) maxLen = 8;
                        else maxLen = 18;
                        return displayLabel.length > maxLen ? displayLabel.substring(0, maxLen) + '...' : displayLabel;
                    },
                    'color': function(ele) {
                        return ele.data('type') === 'question' ? '#212529' : '#ffffff';
                    },
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'font-size': function(ele) {
                        var label = ele.data('label') || '';
                        var type = ele.data('type');
                        if (isShortCode(label)) return '12px';
                        if (type === 'provision') return '11px';
                        return '9px';
                    },
                    'font-weight': 'bold',
                    'width': function(ele) {
                        var label = ele.data('label') || '';
                        var type = ele.data('type');
                        if (type === 'question') return '85px';
                        if (type === 'conclusion') return '90px';
                        if (type === 'provision') return '70px';
                        if (isShortCode(label)) return '50px';
                        return '100px';
                    },
                    'height': function(ele) {
                        var label = ele.data('label') || '';
                        var type = ele.data('type');
                        if (type === 'question') return '85px';
                        if (type === 'conclusion') return '50px';
                        if (type === 'provision') return '70px';
                        if (isShortCode(label)) return '50px';
                        return '45px';
                    },
                    'text-wrap': 'wrap',
                    'text-max-width': function(ele) {
                        var label = ele.data('label') || '';
                        var type = ele.data('type');
                        if (type === 'question') return '75px';
                        if (type === 'conclusion') return '80px';
                        if (isShortCode(label)) return '45px';
                        return '90px';
                    },
                    'shape': function(ele) {
                        var label = ele.data('label') || '';
                        var type = ele.data('type');
                        if (type === 'provision') return 'rectangle';
                        if (type === 'question') return 'diamond';
                        if (type === 'conclusion') return 'round-rectangle';
                        if (isShortCode(label)) return 'ellipse';
                        return 'round-rectangle';
                    },
                    'border-width': 2,
                    'border-color': function(ele) {
                        var type = ele.data('type');
                        if (type === 'question') return '#0891b2';
                        if (type === 'conclusion') return '#166534';
                        return '#374151';
                    }
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': 3,
                    'line-color': function(ele) {
                        var edgeType = ele.data('edgeType');
                        if (edgeType === 'provision_to_question') return '#6c757d';
                        if (edgeType === 'question_to_conclusion') return '#0dcaf0';
                        if (edgeType === 'provision_to_entity') return '#0d6efd';
                        return '#ccc';
                    },
                    'target-arrow-color': function(ele) {
                        var edgeType = ele.data('edgeType');
                        if (edgeType === 'provision_to_question') return '#6c757d';
                        if (edgeType === 'question_to_conclusion') return '#0dcaf0';
                        if (edgeType === 'provision_to_entity') return '#0d6efd';
                        return '#ccc';
                    },
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'straight',
                    'label': 'data(label)',
                    'font-size': '9px',
                    'text-rotation': 'autorotate',
                    'edge-distances': 'node-position',
                    'text-background-color': '#fff',
                    'text-background-opacity': 0.8,
                    'text-background-padding': '2px'
                }
            }
        ],
        layout: {
            name: 'cose',
            idealEdgeLength: 150,
            nodeOverlap: 50,
            refresh: 20,
            fit: true,
            padding: 40,
            randomize: false,
            componentSpacing: 100,
            nodeRepulsion: 8000,
            edgeElasticity: 100,
            nestingFactor: 5,
            gravity: 80,
            numIter: 1000,
            initialTemp: 200,
            coolingFactor: 0.95,
            minTemp: 1.0,
            avoidOverlap: true,
            nodeDimensionsIncludeLabels: true,
            animate: true,
            animationDuration: 500
        }
    });

    // Reset layout
    document.getElementById('reset-graph').addEventListener('click', function() {
        cy.layout({
            name: 'cose',
            idealEdgeLength: 120,
            nodeOverlap: 40,
            avoidOverlap: true,
            nodeDimensionsIncludeLabels: true,
            fit: true
        }).run();
    });

    // Toggle labels
    document.getElementById('show-labels').addEventListener('change', function(e) {
        if (e.target.checked) {
            cy.style().selector('node').style('label', function(ele) {
                var label = ele.data('label') || '';
                var type = ele.data('type');
                var displayLabel = formatLabelForDisplay(label);
                var maxLen;
                if (type === 'provision') maxLen = 10;
                else if (type === 'question' || type === 'conclusion') maxLen = 14;
                else if (isShortCode(label)) maxLen = 8;
                else maxLen = 18;
                return displayLabel.length > maxLen ? displayLabel.substring(0, maxLen) + '...' : displayLabel;
            }).update();
        } else {
            cy.style().selector('node').style('label', '').update();
        }
    });

    // Node click -- details panel
    cy.on('tap', 'node', function(evt) {
        var node = evt.target;
        var data = node.data();

        var panel = document.getElementById('cy-details-panel');
        var labelEl = document.getElementById('cy-detail-label');
        var typeEl = document.getElementById('cy-detail-type');
        var textEl = document.getElementById('cy-detail-text');
        var edgesEl = document.getElementById('cy-detail-edges');

        labelEl.textContent = formatLabelForDisplay(data.label);
        labelEl.style.borderColor = nodeColors[data.type] || '#1d4ed8';

        typeEl.textContent = data.nodeType || data.type;
        typeEl.style.backgroundColor = nodeColors[data.type] || '#1d4ed8';
        typeEl.style.color = (data.type === 'question') ? '#212529' : '#fff';

        var fullText = data.fullText || data.definition || data.reasoning || '';
        textEl.textContent = fullText || 'No details available';

        var connectedEdges = node.connectedEdges();
        edgesEl.innerHTML = '';
        if (connectedEdges.length === 0) {
            edgesEl.innerHTML = '<li class="text-muted">None</li>';
        } else {
            connectedEdges.forEach(function(edge) {
                var isSource = edge.source().id() === node.id();
                var otherNode = isSource ? edge.target() : edge.source();
                var arrow = isSource ? '\u2192' : '\u2190';
                var otherLabel = formatLabelForDisplay(otherNode.data('label'));
                var li = document.createElement('li');
                li.innerHTML = '<span style="color:' + (nodeColors[otherNode.data('type')] || '#1d4ed8') + '">' + arrow + '</span> ' + otherLabel + ' <small class="text-muted">(' + (edge.data('label') || 'related') + ')</small>';
                edgesEl.appendChild(li);
            });
        }

        panel.style.display = 'block';
    });

    // Close details panel
    document.getElementById('cy-close-details').addEventListener('click', function() {
        document.getElementById('cy-details-panel').style.display = 'none';
    });

    cy.on('tap', function(evt) {
        if (evt.target === cy) {
            document.getElementById('cy-details-panel').style.display = 'none';
        }
    });

    // Zoom controls
    document.getElementById('cy-zoom-in').addEventListener('click', function() {
        cy.zoom(cy.zoom() * 1.3);
        cy.center();
    });

    document.getElementById('cy-zoom-out').addEventListener('click', function() {
        cy.zoom(cy.zoom() * 0.7);
        cy.center();
    });

    document.getElementById('cy-zoom-fit').addEventListener('click', function() {
        cy.fit();
    });

    // Fullscreen
    document.getElementById('cy-fullscreen-btn').addEventListener('click', function() {
        var card = document.getElementById('cy-graph-card');
        card.classList.add('fullscreen');
        this.style.display = 'none';
        document.getElementById('cy-exit-fullscreen-btn').style.display = 'inline-block';
        setTimeout(function() {
            cy.resize();
            cy.fit();
        }, 100);
    });

    document.getElementById('cy-exit-fullscreen-btn').addEventListener('click', function() {
        var card = document.getElementById('cy-graph-card');
        card.classList.remove('fullscreen');
        this.style.display = 'none';
        document.getElementById('cy-fullscreen-btn').style.display = 'inline-block';
        setTimeout(function() {
            cy.resize();
            cy.fit();
        }, 100);
    });

    // ESC to exit fullscreen
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            var card = document.getElementById('cy-graph-card');
            if (card && card.classList.contains('fullscreen')) {
                document.getElementById('cy-exit-fullscreen-btn').click();
            }
        }
    });
});
