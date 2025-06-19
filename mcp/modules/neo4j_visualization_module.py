#!/usr/bin/env python3
"""
Neo4j Visualization Module for MCP Server

This module provides Neo4j-based ontology visualization with full import support
for BFO-compatible ontologies with proper relationship handling.
"""

import os
import sys
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from aiohttp import web

# Import base module
from .base_module import MCPBaseModule

# Set up logging
logger = logging.getLogger(__name__)

class Neo4jVisualizationModule(MCPBaseModule):
    """
    Module for Neo4j-based ontology visualization with Neosemantics (n10s) support.
    """
    
    def __init__(self):
        """Initialize the Neo4j visualization module."""
        super().__init__("neo4j_visualization")
        self.neo4j_driver = None
        self.initialized = False
        self.connection_attempted = False
        
    def initialize(self, neo4j_uri: str = None, 
                   neo4j_user: str = None, neo4j_password: str = None):
        """
        Initialize the module with Neo4j connection.
        
        Args:
            neo4j_uri: Neo4j connection URI (optional, reads from env if not provided)
            neo4j_user: Neo4j username (optional, reads from env if not provided)
            neo4j_password: Neo4j password (optional, reads from env if not provided)
        """
        try:
            from neo4j import GraphDatabase
            
            # Use environment variables if not provided
            if neo4j_uri is None:
                neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
            if neo4j_user is None:
                neo4j_user = os.environ.get("NEO4J_USERNAME", "neo4j")
            if neo4j_password is None:
                neo4j_password = os.environ.get("NEO4J_PASSWORD", "neo4j")
            
            self.neo4j_driver = GraphDatabase.driver(
                neo4j_uri, 
                auth=(neo4j_user, neo4j_password)
            )
            
            # Test connection
            with self.neo4j_driver.session() as session:
                result = session.run("RETURN 'Hello Neo4j' as message")
                message = result.single()["message"]
                
            self.initialized = True
            logger.info(f"Neo4j visualization module initialized: {message}")
            
        except ImportError:
            logger.error("Neo4j driver not available. Install with: pip install neo4j")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            logger.info("Make sure Neo4j is running and credentials are correct")
    
    async def setup_neosemantics(self):
        """Set up Neosemantics (n10s) plugin for RDF support."""
        if not self.initialized:
            return False
            
        try:
            with self.neo4j_driver.session() as session:
                # Install neosemantics if not already present
                session.run("""
                    CALL apoc.cypher.doIt(
                        'CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS FOR (r:Resource) REQUIRE r.uri IS UNIQUE', 
                        {}
                    )
                """)
                
                # Initialize graph config for RDF
                session.run("""
                    CALL n10s.graphconfig.init({
                        handleVocabUris: "IGNORE",
                        handleMultival: "ARRAY",
                        multivalPropList: ["http://www.w3.org/2000/01/rdf-schema#label"],
                        keepLangTag: true,
                        handleRDFTypes: "LABELS"
                    })
                """)
                
                logger.info("Neosemantics plugin configured successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to setup Neosemantics: {e}")
            return False
    
    async def load_ontology_stack(self, ontology_name: str = "engineering-ethics"):
        """
        Load the complete ontology stack (BFO + ProEthica + Engineering) into Neo4j.
        
        Args:
            ontology_name: Name of the target ontology
        """
        if not self.initialized:
            return False
            
        try:
            # Setup Neosemantics if not already configured
            await self.setup_neosemantics()
            
            # Get ontology content with imports
            ontology_content = await self._get_ontology_with_imports(ontology_name)
            
            if not ontology_content:
                logger.error(f"Could not load ontology: {ontology_name}")
                return False
            
            # Clear existing ontology data
            with self.neo4j_driver.session() as session:
                session.run("MATCH (n:Resource) DETACH DELETE n")
                
            # Load TTL content into Neo4j
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as ttl_file:
                ttl_file.write(ontology_content)
                ttl_path = ttl_file.name
            
            with self.neo4j_driver.session() as session:
                session.run(f"""
                    CALL n10s.rdf.import.fetch('file://{ttl_path}', 'Turtle')
                """)
                
            os.unlink(ttl_path)
            logger.info(f"Loaded ontology stack for {ontology_name} into Neo4j")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load ontology stack: {e}")
            return False
    
    async def _get_ontology_with_imports(self, ontology_name: str) -> Optional[str]:
        """
        Get ontology content with all imports merged.
        
        Args:
            ontology_name: Name of the ontology
            
        Returns:
            Complete TTL content with imports
        """
        try:
            # Load the main ontology
            main_content = await self._get_ontology_content(ontology_name)
            if not main_content:
                return None
            
            # Load BFO content (simplified - you'd want the full BFO)
            bfo_content = await self._get_ontology_content("bfo")
            
            # Load ProEthica intermediate content
            intermediate_content = await self._get_ontology_content("proethica-intermediate")
            
            # Combine all ontologies
            combined_content = []
            
            # Add all prefixes and imports
            prefixes = set()
            imports = set()
            
            for content in [bfo_content, intermediate_content, main_content]:
                if content:
                    lines = content.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line.startswith('@prefix'):
                            prefixes.add(line)
                        elif line.startswith('owl:imports'):
                            imports.add(line)
            
            # Build combined ontology
            result = '\n'.join(sorted(prefixes)) + '\n\n'
            
            # Add the actual content (without redundant prefixes)
            for content in [bfo_content, intermediate_content, main_content]:
                if content:
                    content_lines = []
                    skip_prefixes = True
                    
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('@prefix') and not line.startswith('owl:imports'):
                            skip_prefixes = False
                        
                        if not skip_prefixes and line:
                            content_lines.append(line)
                    
                    result += '\n'.join(content_lines) + '\n\n'
            
            return result
            
        except Exception as e:
            logger.error(f"Error combining ontology imports: {e}")
            return None
    
    async def _get_ontology_content(self, ontology_name: str) -> Optional[str]:
        """Get ontology content from database or file system."""
        try:
            # Try database first
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                from app import create_app
                from app.models.ontology import Ontology
                
                app = create_app('config')
                with app.app_context():
                    ontology = Ontology.query.filter_by(domain_id=ontology_name).first()
                    if ontology and ontology.content:
                        return ontology.content
                        
            except Exception as e:
                logger.debug(f"Database access failed: {e}")
            
            # Try file system
            project_root = Path(__file__).parent.parent.parent
            ontology_files = [
                project_root / "ontologies" / f"{ontology_name}.ttl",
                project_root / "ontologies" / f"{ontology_name}-annotated.ttl",
            ]
            
            for file_path in ontology_files:
                if file_path.exists():
                    return file_path.read_text()
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting ontology content: {e}")
            return None
    
    def get_neo4j_cypher_queries(self) -> Dict[str, str]:
        """Get useful Cypher queries for ontology exploration."""
        return {
            "class_hierarchy": """
                MATCH path = (child:Resource)-[:SCO*]->(parent:Resource)
                WHERE child.uri CONTAINS 'engineering-ethics'
                RETURN path
                LIMIT 100
            """,
            "engineering_concepts": """
                MATCH (n:Resource)
                WHERE n.uri CONTAINS 'engineering-ethics'
                RETURN n.uri, n.rdfs__label, n.rdfs__comment
                LIMIT 50
            """,
            "source_attribution": """
                MATCH (n:Resource)
                WHERE exists(n.dc__source) OR exists(n.rdfs__seeAlso)
                RETURN n.uri, n.rdfs__label, n.dc__source, n.rdfs__seeAlso
                LIMIT 50
            """,
            "bfo_foundation": """
                MATCH (n:Resource)
                WHERE n.uri CONTAINS 'obolibrary.org/obo/BFO'
                RETURN n.uri, n.rdfs__label
                LIMIT 20
            """,
            "property_relationships": """
                MATCH (domain:Resource)-[r:DOMAIN]->(prop:Resource)-[r2:RANGE]->(range:Resource)
                WHERE prop.uri CONTAINS 'engineering-ethics'
                RETURN domain.rdfs__label, prop.rdfs__label, range.rdfs__label
                LIMIT 50
            """
        }
    
    def get_neo4j_browser_html(self, queries: Dict[str, str]) -> str:
        """Generate HTML page with Neo4j Browser integration."""
        
        query_buttons = ""
        for name, query in queries.items():
            query_buttons += f"""
            <button class="query-btn" onclick="runQuery('{name}', `{query}`)">
                {name.replace('_', ' ').title()}
            </button>
            """
        
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Neo4j Ontology Browser - ProEthica</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 3em;
        }}
        .header p {{
            margin: 15px 0 0 0;
            opacity: 0.9;
            font-size: 1.2em;
        }}
        .browser-section {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .query-buttons {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }}
        .query-btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            transition: background 0.2s;
        }}
        .query-btn:hover {{
            background: #5a6fd8;
        }}
        .neo4j-frame {{
            width: 100%;
            height: 800px;
            border: 1px solid #ddd;
            border-radius: 8px;
            background: white;
        }}
        .info-box {{
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }}
        .info-box h3 {{
            margin-top: 0;
            color: #1976d2;
        }}
        .connection-status {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            margin-bottom: 20px;
        }}
        .status-connected {{
            background: #c8e6c9;
            color: #2e7d32;
        }}
        .status-disconnected {{
            background: #ffcdd2;
            color: #c62828;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Neo4j Ontology Browser</h1>
        <p>BFO-Compatible Engineering Ethics Ontology Visualization</p>
    </div>
    
    <div class="browser-section">
        <div class="info-box">
            <h3>📊 Connected Graph Database</h3>
            <p>This visualization shows your complete ontology stack with proper import relationships:</p>
            <ul>
                <li><strong>BFO (Basic Formal Ontology)</strong> - Foundational classes (Entity, Continuant, Occurrent)</li>
                <li><strong>ProEthica Intermediate</strong> - Bridge concepts (Role, EthicalIssue, Standard)</li>
                <li><strong>Engineering Ethics</strong> - Domain-specific classes with source attribution</li>
            </ul>
        </div>
        
        <div id="connection-status" class="connection-status status-disconnected">
            ⚠️ Connect to Neo4j Browser to explore the graph
        </div>
        
        <div id="credential-form" style="display: none; margin: 20px 0; padding: 15px; background: #f0f0f0; border-radius: 8px;">
            <h4>Configure Neo4j Connection</h4>
            <p>Enter your Neo4j credentials (default is usually neo4j/neo4j):</p>
            <input type="text" id="neo4j-user" placeholder="Username" value="neo4j" style="margin: 5px; padding: 8px;">
            <input type="password" id="neo4j-password" placeholder="Password" style="margin: 5px; padding: 8px;">
            <button onclick="testConnection()" class="query-btn" style="margin: 5px;">Test Connection</button>
        </div>
        
        <h3>🔍 Predefined Queries</h3>
        <div class="query-buttons">
            {query_buttons}
        </div>
        
        <h3>🌐 Neo4j Browser</h3>
        <p>Open <a href="http://localhost:7474" target="_blank">Neo4j Browser</a> to run these queries and explore your ontology interactively.</p>
        
        <div class="info-box">
            <h3>🚀 Getting Started</h3>
            <ol>
                <li><strong>Start Neo4j:</strong> Make sure Neo4j is running on localhost:7687</li>
                <li><strong>Install Neosemantics:</strong> Install the n10s plugin for RDF support</li>
                <li><strong>Load Data:</strong> Click "Load Ontology Stack" to import your ontologies</li>
                <li><strong>Explore:</strong> Use the predefined queries or write your own Cypher queries</li>
            </ol>
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <button class="query-btn" onclick="loadOntologyStack()" style="font-size: 1.2em; padding: 20px 40px;">
                🔄 Load Ontology Stack into Neo4j
            </button>
        </div>
    </div>
    
    <script>
        function runQuery(name, query) {{
            // Copy query to clipboard
            navigator.clipboard.writeText(query).then(function() {{
                alert(`Query "${{name}}" copied to clipboard!\\n\\nPaste it in Neo4j Browser to run.`);
            }});
        }}
        
        async function loadOntologyStack() {{
            try {{
                const response = await fetch('/neo4j/load-ontology-stack', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ ontology: 'engineering-ethics' }})
                }});
                
                const result = await response.json();
                
                if (result.success) {{
                    alert('✅ Ontology stack loaded successfully into Neo4j!\\n\\nOpen Neo4j Browser to explore the graph.');
                    document.getElementById('connection-status').className = 'connection-status status-connected';
                    document.getElementById('connection-status').innerHTML = '✅ Ontology loaded in Neo4j';
                }} else {{
                    alert('❌ Failed to load ontology: ' + result.error);
                }}
            }} catch (error) {{
                alert('❌ Error loading ontology: ' + error.message);
            }}
        }}
        
        // Check Neo4j connection status
        async function checkConnection() {{
            try {{
                const response = await fetch('/neo4j/status');
                const status = await response.json();
                
                if (status.connected) {{
                    document.getElementById('connection-status').className = 'connection-status status-connected';
                    document.getElementById('connection-status').innerHTML = '✅ Neo4j connected';
                    document.getElementById('credential-form').style.display = 'none';
                }} else {{
                    document.getElementById('connection-status').className = 'connection-status status-disconnected';
                    if (status.hint) {{
                        document.getElementById('connection-status').innerHTML = '⚠️ ' + status.hint + ' - <a href="#" onclick="showCredentialForm(); return false;">Configure Connection</a>';
                    }} else {{
                        document.getElementById('connection-status').innerHTML = '⚠️ Neo4j not connected - <a href="#" onclick="showCredentialForm(); return false;">Configure Connection</a>';
                    }}
                }}
            }} catch (error) {{
                console.log('Could not check Neo4j status:', error);
            }}
        }}
        
        function showCredentialForm() {{
            document.getElementById('credential-form').style.display = 'block';
        }}
        
        async function testConnection() {{
            const user = document.getElementById('neo4j-user').value;
            const password = document.getElementById('neo4j-password').value;
            
            try {{
                const response = await fetch('/neo4j/configure', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ username: user, password: password }})
                }});
                
                const result = await response.json();
                
                if (result.success) {{
                    alert('✅ Successfully connected to Neo4j!');
                    checkConnection();
                }} else {{
                    alert('❌ Connection failed: ' + result.error);
                }}
            }} catch (error) {{
                alert('❌ Error testing connection: ' + error.message);
            }}
        }}
        
        // Check connection on page load
        document.addEventListener('DOMContentLoaded', checkConnection);
    </script>
</body>
</html>
        """
        
        return html_template
    
    def _generate_graph_html(self, nodes, links, query):
        """Generate HTML page with D3.js graph visualization of query results."""
        
        nodes_json = json.dumps(nodes, indent=2)
        links_json = json.dumps(links, indent=2)
        
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Neo4j Graph Results - ProEthica</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .graph-container {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .query-info {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #667eea;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: #e3f2fd;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #1976d2;
        }}
        .stat-label {{
            color: #666;
            font-size: 0.9em;
        }}
        .node {{
            cursor: pointer;
            stroke: #333;
            stroke-width: 1.5px;
        }}
        .link {{
            fill: none;
            stroke: #999;
            stroke-opacity: 0.6;
            stroke-width: 2px;
        }}
        .node-label {{
            font-family: sans-serif;
            font-size: 12px;
            pointer-events: none;
            text-anchor: middle;
        }}
        .link-label {{
            font-family: sans-serif;
            font-size: 10px;
            pointer-events: none;
            text-anchor: middle;
            fill: #666;
        }}
        .tooltip {{
            position: absolute;
            text-align: left;
            padding: 10px;
            font: 12px sans-serif;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            border-radius: 8px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s;
        }}
        #graph-svg {{
            width: 100%;
            height: 600px;
            border: 1px solid #ddd;
            border-radius: 8px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Neo4j Graph Results</h1>
        <p>Direct visualization of your ontology graph query</p>
    </div>
    
    <div class="graph-container">
        <div class="query-info">
            <h3>Query Executed:</h3>
            <code>{query.strip()}</code>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{len(nodes)}</div>
                <div class="stat-label">Nodes</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(links)}</div>
                <div class="stat-label">Relationships</div>
            </div>
        </div>
        
        <svg id="graph-svg"></svg>
    </div>
    
    <div class="tooltip" id="tooltip"></div>
    
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script>
        const nodes = {nodes_json};
        const links = {links_json};
        
        // Set up SVG
        const svg = d3.select("#graph-svg");
        const width = 800;
        const height = 600;
        
        svg.attr("viewBox", `0 0 ${{width}} ${{height}}`);
        
        const tooltip = d3.select("#tooltip");
        
        // Create force simulation
        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(30));
        
        // Create links
        const link = svg.append("g")
            .selectAll("line")
            .data(links)
            .enter().append("line")
            .attr("class", "link")
            .attr("stroke-width", 2);
        
        // Create link labels
        const linkLabel = svg.append("g")
            .selectAll("text")
            .data(links)
            .enter().append("text")
            .attr("class", "link-label")
            .text(d => d.type);
        
        // Create nodes
        const node = svg.append("g")
            .selectAll("circle")
            .data(nodes)
            .enter().append("circle")
            .attr("class", "node")
            .attr("r", 20)
            .attr("fill", d => {{
                if (d.uri && d.uri.includes('engineering-ethics')) return '#4CAF50';
                if (d.uri && d.uri.includes('proethica')) return '#2196F3';
                if (d.uri && d.uri.includes('BFO')) return '#FF9800';
                return '#9C27B0';
            }})
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended))
            .on("mouseover", function(event, d) {{
                tooltip.transition().duration(200).style("opacity", .9);
                
                let tooltipContent = `<strong>${{d.label}}</strong><br/>`;
                tooltipContent += `Type: ${{d.type}}<br/>`;
                
                if (d.uri) {{
                    tooltipContent += `URI: ${{d.uri}}<br/>`;
                }}
                
                // Show some properties
                if (d.properties) {{
                    const props = Object.keys(d.properties).slice(0, 3);
                    props.forEach(prop => {{
                        if (prop !== 'uri' && prop !== 'rdfs__label') {{
                            tooltipContent += `${{prop}}: ${{String(d.properties[prop]).substring(0, 50)}}<br/>`;
                        }}
                    }});
                }}
                
                tooltip.html(tooltipContent)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            }})
            .on("mouseout", function(d) {{
                tooltip.transition().duration(500).style("opacity", 0);
            }});
        
        // Create node labels
        const nodeLabel = svg.append("g")
            .selectAll("text")
            .data(nodes)
            .enter().append("text")
            .attr("class", "node-label")
            .attr("dy", ".35em")
            .text(d => d.label.length > 15 ? d.label.substring(0, 15) + '...' : d.label);
        
        // Update positions on simulation tick
        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            linkLabel
                .attr("x", d => (d.source.x + d.target.x) / 2)
                .attr("y", d => (d.source.y + d.target.y) / 2);
            
            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
            
            nodeLabel
                .attr("x", d => d.x)
                .attr("y", d => d.y);
        }});
        
        // Drag functions
        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}
        
        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}
        
        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }}
        
        // Add zoom behavior
        svg.call(d3.zoom()
            .extent([[0, 0], [width, height]])
            .scaleExtent([0.1, 8])
            .on("zoom", function(event) {{
                svg.selectAll("g").attr("transform", event.transform);
            }}));
    </script>
</body>
</html>
        """
        
        return html_template
    
    async def create_neo4j_routes(self, app: web.Application):
        """Add Neo4j visualization routes to the web application."""
        
        async def neo4j_browser(request):
            """Neo4j browser interface."""
            queries = self.get_neo4j_cypher_queries()
            html_content = self.get_neo4j_browser_html(queries)
            
            return web.Response(
                text=html_content,
                content_type='text/html'
            )
        
        async def neo4j_status(request):
            """Check Neo4j connection status."""
            try:
                if not self.initialized and not self.connection_attempted:
                    # Try to initialize with common credentials
                    credentials_to_try = [
                        ("neo4j", "neo4j"),
                        ("neo4j", "password"),
                        ("neo4j", "neo4j123"),
                        ("neo4j", "admin")
                    ]
                    
                    for user, password in credentials_to_try:
                        try:
                            self.initialize(neo4j_user=user, neo4j_password=password)
                            if self.initialized:
                                logger.info(f"Successfully connected to Neo4j with user '{user}'")
                                break
                        except:
                            continue
                    
                    self.connection_attempted = True
                
                if not self.initialized:
                    return web.json_response({
                        "connected": False, 
                        "error": "Could not connect to Neo4j. Please check credentials.",
                        "hint": "Neo4j is running. Default credentials may have been changed during setup."
                    })
                
                with self.neo4j_driver.session() as session:
                    result = session.run("RETURN 1")
                    result.single()
                
                return web.json_response({"connected": True})
                
            except Exception as e:
                return web.json_response({"connected": False, "error": str(e)})
        
        async def load_ontology_stack(request):
            """Load ontology stack into Neo4j."""
            try:
                data = await request.json()
                ontology_name = data.get('ontology', 'engineering-ethics')
                
                # Setup Neosemantics
                await self.setup_neosemantics()
                
                # Load ontology stack
                success = await self.load_ontology_stack(ontology_name)
                
                if success:
                    return web.json_response({"success": True, "message": "Ontology stack loaded"})
                else:
                    return web.json_response({"success": False, "error": "Failed to load ontology"})
                    
            except Exception as e:
                logger.error(f"Error loading ontology stack: {e}")
                return web.json_response({"success": False, "error": str(e)})
        
        async def configure_connection(request):
            """Configure Neo4j connection with provided credentials."""
            try:
                data = await request.json()
                username = data.get('username', 'neo4j')
                password = data.get('password', 'neo4j')
                
                # Try to initialize with provided credentials
                self.initialize(neo4j_user=username, neo4j_password=password)
                
                if self.initialized:
                    return web.json_response({"success": True, "message": "Connected successfully"})
                else:
                    return web.json_response({"success": False, "error": "Failed to connect with provided credentials"})
                    
            except Exception as e:
                logger.error(f"Error configuring Neo4j connection: {e}")
                return web.json_response({"success": False, "error": str(e)})
        
        async def query_graph(request):
            """Execute a Cypher query and return graph visualization."""
            try:
                if not self.initialized:
                    return web.Response(
                        text="Neo4j not connected. Please configure connection first.",
                        status=500
                    )
                
                # Check if we should load ontology first
                ontology = request.query.get('ontology', 'engineering-ethics')
                auto_load = request.query.get('load', 'true').lower() == 'true'
                
                if auto_load:
                    # Try to load the ontology stack if not already loaded
                    await self.load_ontology_stack(ontology)
                
                # Get query from URL parameters or use default
                query = request.query.get('query', """
                    MATCH (n:Resource)
                    WHERE NOT n:_GraphConfig AND NOT n:_NsPrefDef
                    OPTIONAL MATCH (n)-[r]-(m:Resource)
                    WHERE NOT m:_GraphConfig AND NOT m:_NsPrefDef
                    RETURN n, r, m
                    LIMIT 50
                """)
                
                # Execute query
                with self.neo4j_driver.session() as session:
                    result = session.run(query)
                    records = list(result)
                
                # Debug: log number of records
                logger.info(f"Query returned {len(records)} records")
                
                # Convert results to D3.js format
                nodes = {}
                links = []
                
                for i, record in enumerate(records[:3]):  # Log first 3 records
                    logger.info(f"Record {i} keys: {list(record.keys())}")
                
                for record in records:
                    # Handle single node queries
                    if 'node' in record:
                        node = record['node']
                        node_id = node.element_id
                        if node_id not in nodes:
                            nodes[node_id] = {
                                'id': node_id,
                                'label': str(node.get('rdfs__label', node.get('uri', node.get('ns0__title', str(node_id)))))[:50],
                                'uri': node.get('uri', ''),
                                'properties': dict(node),
                                'type': 'Resource'
                            }
                    # Handle node-relationship queries
                    else:
                        for key in ['n', 'm']:
                            if key in record:
                                node = record[key]
                                node_id = node.element_id
                                if node_id not in nodes:
                                    nodes[node_id] = {
                                        'id': node_id,
                                        'label': node.get('rdfs__label', node.get('uri', str(node_id)))[:50],
                                        'uri': node.get('uri', ''),
                                        'properties': dict(node),
                                        'type': 'Resource'
                                    }
                        
                        # Add relationships
                        if 'r' in record:
                            rel = record['r']
                            links.append({
                                'source': record['n'].element_id,
                                'target': record['m'].element_id,
                                'type': rel.type,
                                'properties': dict(rel)
                            })
                
                # Generate HTML visualization
                html_content = self._generate_graph_html(list(nodes.values()), links, query)
                
                return web.Response(
                    text=html_content,
                    content_type='text/html'
                )
                
            except Exception as e:
                logger.error(f"Error executing graph query: {e}")
                return web.Response(
                    text=f"Error executing query: {str(e)}",
                    status=500
                )
        
        async def debug_neo4j(request):
            """Debug endpoint to see what's in Neo4j."""
            try:
                if not self.initialized:
                    return web.json_response({"error": "Neo4j not connected"})
                
                with self.neo4j_driver.session() as session:
                    # Count all nodes
                    result = session.run("MATCH (n) RETURN count(n) as total")
                    total_nodes = result.single()["total"]
                    
                    # Count Resource nodes
                    result = session.run("MATCH (n:Resource) RETURN count(n) as resources")
                    resource_nodes = result.single()["resources"]
                    
                    # Get some sample nodes
                    result = session.run("MATCH (n) RETURN n LIMIT 10")
                    sample_nodes = [dict(record["n"]) for record in result]
                    
                    # Get labels
                    result = session.run("CALL db.labels() YIELD label RETURN collect(label) as labels")
                    labels = result.single()["labels"]
                    
                    return web.json_response({
                        "total_nodes": total_nodes,
                        "resource_nodes": resource_nodes,
                        "labels": labels,
                        "sample_nodes": sample_nodes[:3]  # Just first 3
                    })
                    
            except Exception as e:
                return web.json_response({"error": str(e)})
        
        async def test_query(request):
            """Test query execution directly."""
            try:
                if not self.initialized:
                    return web.json_response({"error": "Neo4j not connected"})
                
                with self.neo4j_driver.session() as session:
                    # Simple query to get all non-config nodes
                    result = session.run("""
                        MATCH (n)
                        WHERE NOT n:_GraphConfig AND NOT n:_NsPrefDef
                        RETURN n.uri as uri, labels(n) as labels
                        LIMIT 10
                    """)
                    
                    data = []
                    for record in result:
                        data.append({
                            "uri": record["uri"],
                            "labels": record["labels"]
                        })
                    
                    return web.json_response({
                        "count": len(data),
                        "nodes": data
                    })
                    
            except Exception as e:
                return web.json_response({"error": str(e)})
        
        # Add routes
        app.router.add_get('/neo4j', neo4j_browser)
        app.router.add_get('/neo4j/browser', neo4j_browser)
        app.router.add_get('/neo4j/graph', query_graph)
        app.router.add_get('/neo4j/test', test_query)
        app.router.add_get('/neo4j/debug', debug_neo4j)
        app.router.add_get('/neo4j/status', neo4j_status)
        app.router.add_post('/neo4j/configure', configure_connection)
        app.router.add_post('/neo4j/load-ontology-stack', load_ontology_stack)
        
        logger.info("Neo4j visualization routes added to MCP server")