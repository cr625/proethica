/**
 * Ontology Hierarchy Visualization JavaScript
 * 
 * This script handles the visualization of ontology hierarchies,
 * including class hierarchies, property relationships, and individuals.
 */

// Initialize global variables
let hierarchyData;        // Raw hierarchy data
let currentEntityData;    // Currently selected entity data
let tree;                 // D3 tree layout

// Document ready function
document.addEventListener('DOMContentLoaded', function() {
    // Set up event listeners
    setupEventListeners();
    
    // Load the ontology data
    loadOntologyData();
});

/**
 * Set up event listeners for buttons and other controls
 */
function setupEventListeners() {
    // Back to editor button
    document.getElementById('backToEditorBtn').addEventListener('click', function() {
        window.location.href = '/ontology-editor/';
    });
    
    // Expand all button
    document.getElementById('expandAllBtn').addEventListener('click', expandAllNodes);
    
    // Collapse all button
    document.getElementById('collapseAllBtn').addEventListener('click', collapseAllNodes);
    
    // Apply filters button
    document.getElementById('applyFiltersBtn').addEventListener('click', applyFilters);
    
    // Search box - filter on enter key
    document.getElementById('searchBox').addEventListener('keyup', function(e) {
        if (e.key === 'Enter') {
            applyFilters();
        }
    });
}

/**
 * Load the ontology data from the API
 */
function loadOntologyData() {
    if (!ontologyId) {
        document.getElementById('loadingIndicator').innerHTML = `
            <div class="alert alert-danger">
                No ontology ID provided. Please select an ontology from the editor.
            </div>
        `;
        return;
    }
    
    // Show loading indicator
    document.getElementById('loadingIndicator').style.display = 'block';
    document.getElementById('hierarchyTree').style.display = 'none';
    
    // Fetch the ontology content
    fetch(`/ontology-editor/api/ontologies/${ontologyId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load ontology');
            }
            return response.json();
        })
        .then(data => {
            // Parse the TTL content into a hierarchy
            parseTTLToHierarchy(data.content);
            
            // Hide loading indicator
            document.getElementById('loadingIndicator').style.display = 'none';
            document.getElementById('hierarchyTree').style.display = 'block';
        })
        .catch(error => {
            console.error('Error loading ontology:', error);
            
            // Display error
            document.getElementById('loadingIndicator').innerHTML = `
                <div class="alert alert-danger">
                    Error loading ontology: ${error.message}
                </div>
            `;
        });
}

/**
 * Parse TTL content into a hierarchy structure
 * 
 * @param {string} ttlContent - The TTL content to parse
 */
function parseTTLToHierarchy(ttlContent) {
    // In a real implementation, we would use a full RDF parser
    // For simplicity in this prototype, we'll use a simplified approach
    
    // Create a mock hierarchy for demonstration
    hierarchyData = createMockHierarchy();
    
    // Visualize the hierarchy
    visualizeHierarchy(hierarchyData);
    
    // Update the visualization title
    document.getElementById('visualizationTitle').innerText = `Ontology Hierarchy: ${hierarchyData.name}`;
}

/**
 * Create a mock hierarchy for demonstration
 * 
 * @returns {Object} - Mock hierarchy data
 */
function createMockHierarchy() {
    return {
        name: "Engineering Ethics Ontology",
        type: "root",
        children: [
            {
                name: "Entity",
                type: "bfo",
                uri: "http://purl.obolibrary.org/obo/BFO_0000001",
                description: "A universal that is the most general of all universals",
                children: [
                    {
                        name: "Continuant",
                        type: "bfo",
                        uri: "http://purl.obolibrary.org/obo/BFO_0000002",
                        description: "An entity that persists through time",
                        children: [
                            {
                                name: "IndependentContinuant",
                                type: "bfo",
                                uri: "http://purl.obolibrary.org/obo/BFO_0000004",
                                description: "A continuant that doesn't inhere in other entities",
                                children: [
                                    {
                                        name: "MaterialEntity",
                                        type: "bfo",
                                        uri: "http://purl.obolibrary.org/obo/BFO_0000040",
                                        description: "An independent continuant that has material parts",
                                        children: [
                                            {
                                                name: "EngineeringSystem",
                                                type: "bfo-aligned",
                                                uri: "http://proethica.org/ontology/engineering-ethics#EngineeringSystem",
                                                description: "A complex system designed for a specific purpose",
                                                properties: {
                                                    "rdfs:subClassOf": "http://purl.obolibrary.org/obo/BFO_0000040",
                                                    "created": "2025-04-23"
                                                },
                                                children: [
                                                    {
                                                        name: "Bridge",
                                                        type: "bfo-aligned",
                                                        uri: "http://proethica.org/ontology/engineering-ethics#Bridge",
                                                        description: "A structure that spans physical obstacles",
                                                        properties: {
                                                            "rdfs:subClassOf": "http://proethica.org/ontology/engineering-ethics#EngineeringSystem"
                                                        }
                                                    },
                                                    {
                                                        name: "Building",
                                                        type: "bfo-aligned",
                                                        uri: "http://proethica.org/ontology/engineering-ethics#Building",
                                                        description: "A structure for human occupation",
                                                        properties: {
                                                            "rdfs:subClassOf": "http://proethica.org/ontology/engineering-ethics#EngineeringSystem"
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                name: "Person",
                                                type: "bfo-aligned",
                                                uri: "http://proethica.org/ontology/engineering-ethics#Person",
                                                description: "A human being",
                                                properties: {
                                                    "rdfs:subClassOf": "http://purl.obolibrary.org/obo/BFO_0000040"
                                                },
                                                children: [
                                                    {
                                                        name: "Engineer",
                                                        type: "bfo-aligned",
                                                        uri: "http://proethica.org/ontology/engineering-ethics#Engineer",
                                                        description: "A person who practices engineering",
                                                        properties: {
                                                            "rdfs:subClassOf": "http://proethica.org/ontology/engineering-ethics#Person"
                                                        }
                                                    },
                                                    {
                                                        name: "Client",
                                                        type: "bfo-aligned",
                                                        uri: "http://proethica.org/ontology/engineering-ethics#Client",
                                                        description: "A person who commissions engineering work",
                                                        properties: {
                                                            "rdfs:subClassOf": "http://proethica.org/ontology/engineering-ethics#Person"
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                name: "DependentContinuant",
                                type: "bfo",
                                uri: "http://purl.obolibrary.org/obo/BFO_0000005",
                                description: "A continuant that inheres in or is borne by other entities",
                                children: [
                                    {
                                        name: "Role",
                                        type: "bfo",
                                        uri: "http://purl.obolibrary.org/obo/BFO_0000023",
                                        description: "A realizable entity that exists due to a bearer's circumstances",
                                        children: [
                                            {
                                                name: "EngineeringRole",
                                                type: "bfo-aligned",
                                                uri: "http://proethica.org/ontology/engineering-ethics#EngineeringRole",
                                                description: "A role within the engineering profession",
                                                properties: {
                                                    "rdfs:subClassOf": "http://purl.obolibrary.org/obo/BFO_0000023"
                                                },
                                                children: [
                                                    {
                                                        name: "ConsultantRole",
                                                        type: "bfo-aligned",
                                                        uri: "http://proethica.org/ontology/engineering-ethics#ConsultantRole",
                                                        description: "A role of providing expert advice",
                                                        properties: {
                                                            "rdfs:subClassOf": "http://proethica.org/ontology/engineering-ethics#EngineeringRole"
                                                        }
                                                    },
                                                    {
                                                        name: "InspectionEngineerRole",
                                                        type: "bfo-aligned",
                                                        uri: "http://proethica.org/ontology/engineering-ethics#InspectionEngineerRole",
                                                        description: "A role of inspecting engineering works",
                                                        properties: {
                                                            "rdfs:subClassOf": "http://proethica.org/ontology/engineering-ethics#EngineeringRole"
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        name: "Occurrent",
                        type: "bfo",
                        uri: "http://purl.obolibrary.org/obo/BFO_0000003",
                        description: "An entity that unfolds itself in time",
                        children: [
                            {
                                name: "Process",
                                type: "bfo",
                                uri: "http://purl.obolibrary.org/obo/BFO_0000015",
                                description: "An occurrent that has temporal parts",
                                children: [
                                    {
                                        name: "EngineeringProcess",
                                        type: "bfo-aligned",
                                        uri: "http://proethica.org/ontology/engineering-ethics#EngineeringProcess",
                                        description: "A process carried out within engineering practice",
                                        properties: {
                                            "rdfs:subClassOf": "http://purl.obolibrary.org/obo/BFO_0000015"
                                        },
                                        children: [
                                            {
                                                name: "DesignProcess",
                                                type: "bfo-aligned",
                                                uri: "http://proethica.org/ontology/engineering-ethics#DesignProcess",
                                                description: "The process of designing an engineering system",
                                                properties: {
                                                    "rdfs:subClassOf": "http://proethica.org/ontology/engineering-ethics#EngineeringProcess"
                                                }
                                            },
                                            {
                                                name: "InspectionProcess",
                                                type: "bfo-aligned",
                                                uri: "http://proethica.org/ontology/engineering-ethics#InspectionProcess",
                                                description: "The process of inspecting an engineering system",
                                                properties: {
                                                    "rdfs:subClassOf": "http://proethica.org/ontology/engineering-ethics#EngineeringProcess"
                                                }
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    };
}

/**
 * Visualize the hierarchy using D3
 * 
 * @param {Object} data - Hierarchy data to visualize
 */
function visualizeHierarchy(data) {
    // Clear previous visualization
    document.getElementById('hierarchyTree').innerHTML = '';
    
    // Set dimensions and margins
    const width = document.getElementById('hierarchyTree').clientWidth;
    const height = 700;
    const margin = { top: 20, right: 120, bottom: 20, left: 120 };
    
    // Create the SVG container
    const svg = d3.select('#hierarchyTree')
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);
    
    // Create the tree layout
    tree = d3.tree()
        .size([height - margin.top - margin.bottom, width - margin.left - margin.right]);
    
    // Create the root node and apply the tree layout
    const root = d3.hierarchy(data);
    tree(root);
    
    // Add links between nodes
    const links = svg.selectAll('.link')
        .data(root.links())
        .enter()
        .append('path')
        .attr('class', 'link')
        .attr('d', d3.linkHorizontal()
            .x(d => d.y)
            .y(d => d.x));
    
    // Add nodes
    const nodes = svg.selectAll('.node')
        .data(root.descendants())
        .enter()
        .append('g')
        .attr('class', d => {
            let classes = 'node';
            if (d.data.type) {
                classes += ` ${d.data.type}`;
            }
            if (d.children) {
                classes += ' node--internal';
            } else {
                classes += ' node--leaf';
            }
            return classes;
        })
        .attr('transform', d => `translate(${d.y},${d.x})`)
        .on('click', toggleNode);
    
    // Add circles to nodes
    nodes.append('circle')
        .attr('r', 6);
    
    // Add text labels to nodes
    nodes.append('text')
        .attr('dy', 3)
        .attr('x', d => d.children ? -8 : 8)
        .style('text-anchor', d => d.children ? 'end' : 'start')
        .text(d => d.data.name);
    
    // Initially collapse nodes at level 3+
    root.descendants().forEach(d => {
        if (d.depth >= 3) {
            toggleChildren(d);
        }
    });
    
    // Update the visualization
    update(root);
}

/**
 * Toggle node expansion/collapse when clicked
 * 
 * @param {Object} event - Click event
 * @param {Object} d - Node data
 */
function toggleNode(event, d) {
    // If the node has children, toggle them
    if (d.children || d._children) {
        toggleChildren(d);
        update(d3.hierarchy(hierarchyData));
    }
    
    // Show entity details
    showEntityDetails(d.data);
    
    // Prevent event propagation
    event.stopPropagation();
}

/**
 * Toggle node children (expand/collapse)
 * 
 * @param {Object} d - Node data
 */
function toggleChildren(d) {
    if (d.children) {
        d._children = d.children;
        d.children = null;
    } else {
        d.children = d._children;
        d._children = null;
    }
}

/**
 * Expand all nodes
 */
function expandAllNodes() {
    expandCollapseAll(d3.hierarchy(hierarchyData), true);
    update(d3.hierarchy(hierarchyData));
}

/**
 * Collapse all nodes
 */
function collapseAllNodes() {
    expandCollapseAll(d3.hierarchy(hierarchyData), false);
    update(d3.hierarchy(hierarchyData));
}

/**
 * Recursively expand or collapse all nodes
 * 
 * @param {Object} d - Node data
 * @param {boolean} expand - Whether to expand (true) or collapse (false)
 */
function expandCollapseAll(d, expand) {
    if (d.children || d._children) {
        if (expand) {
            // Expand this node
            if (d._children) {
                d.children = d._children;
                d._children = null;
            }
            
            // Recursively expand children
            if (d.children) {
                d.children.forEach(child => expandCollapseAll(child, expand));
            }
        } else {
            // Recursively collapse children first
            if (d.children) {
                d.children.forEach(child => expandCollapseAll(child, expand));
            }
            
            // Collapse this node unless it's the root
            if (d.depth > 0) {
                d._children = d.children;
                d.children = null;
            }
        }
    }
}

/**
 * Update the tree visualization
 * 
 * @param {Object} source - Source node for the update
 */
function update(source) {
    // Apply the tree layout
    tree(source);
    
    // Select all nodes
    const nodes = d3.selectAll('.node');
    
    // Update node positions
    nodes.attr('transform', d => `translate(${d.y},${d.x})`);
    
    // Update links
    d3.selectAll('.link')
        .attr('d', d3.linkHorizontal()
            .x(d => d.y)
            .y(d => d.x));
}

/**
 * Show entity details in the details panel
 * 
 * @param {Object} entityData - Entity data to display
 */
function showEntityDetails(entityData) {
    // Store the current entity data
    currentEntityData = entityData;
    
    // Get the details element
    const detailsElement = document.getElementById('entityDetails');
    const detailsCard = document.getElementById('entityDetailsCard');
    
    // If no entity data, hide the details panel
    if (!entityData) {
        detailsCard.style.display = 'none';
        return;
    }
    
    // Build the HTML for the details
    let html = `
        <div class="entity-header">${entityData.name}</div>
    `;
    
    if (entityData.uri) {
        html += `<div class="entity-uri">${entityData.uri}</div>`;
    }
    
    if (entityData.description) {
        html += `
            <div class="entity-property">
                <span class="entity-property-name">Description:</span>
                <div class="entity-property-value">${entityData.description}</div>
            </div>
        `;
    }
    
    if (entityData.type) {
        html += `
            <div class="entity-property">
                <span class="entity-property-name">Type:</span>
                <div class="entity-property-value">${formatEntityType(entityData.type)}</div>
            </div>
        `;
    }
    
    if (entityData.properties) {
        html += `
            <div class="entity-property">
                <span class="entity-property-name">Properties:</span>
                <div class="entity-property-value">
                    <ul class="list-unstyled">
        `;
        
        for (const [key, value] of Object.entries(entityData.properties)) {
            html += `<li><strong>${key}:</strong> ${value}</li>`;
        }
        
        html += `
                    </ul>
                </div>
            </div>
        `;
    }
    
    // Update the details element
    detailsElement.innerHTML = html;
    
    // Show the details card
    detailsCard.style.display = 'block';
}

/**
 * Format entity type for display
 * 
 * @param {string} type - Entity type
 * @returns {string} - Formatted entity type
 */
function formatEntityType(type) {
    switch (type) {
        case 'bfo':
            return 'BFO Class';
        case 'bfo-aligned':
            return 'BFO-Aligned Class';
        case 'non-bfo':
            return 'Non-BFO-Aligned Class';
        case 'property':
            return 'Property';
        case 'individual':
            return 'Individual';
        default:
            return type;
    }
}

/**
 * Apply filters to the visualization
 */
function applyFilters() {
    // Get filter values
    const filterType = document.getElementById('filterType').value;
    const searchTerm = document.getElementById('searchBox').value.toLowerCase();
    const showBFO = document.getElementById('showBFOClasses').checked;
    const highlightBFOAligned = document.getElementById('highlightBFOAligned').checked;
    
    // Apply filters to nodes
    d3.selectAll('.node').style('display', function() {
        const d = d3.select(this).datum();
        
        // Filter by type
        if (filterType !== 'all') {
            if (filterType === 'class' && (d.data.type === 'property' || d.data.type === 'individual')) {
                return 'none';
            }
            if (filterType === 'property' && d.data.type !== 'property') {
                return 'none';
            }
            if (filterType === 'individual' && d.data.type !== 'individual') {
                return 'none';
            }
        }
        
        // Filter by BFO
        if (!showBFO && d.data.type === 'bfo') {
            return 'none';
        }
        
        // Filter by search term
        if (searchTerm && !d.data.name.toLowerCase().includes(searchTerm) && 
            !(d.data.description && d.data.description.toLowerCase().includes(searchTerm))) {
            return 'none';
        }
        
        return null;
    });
    
    // Apply highlight based on BFO alignment
    if (highlightBFOAligned) {
        d3.selectAll('.node circle').attr('r', function() {
            const d = d3.select(this.parentNode).datum();
            if (d.data.type === 'bfo' || d.data.type === 'bfo-aligned') {
                return 8;  // Larger radius for BFO-aligned nodes
            }
            return 6;
        });
    } else {
        d3.selectAll('.node circle').attr('r', 6);
    }
}
