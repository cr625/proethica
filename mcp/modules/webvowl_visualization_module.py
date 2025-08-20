#!/usr/bin/env python3
"""
WebVOWL Visualization Module for MCP Server

This module provides WebVOWL-compatible ontology visualization capabilities
integrated with the ProEthica MCP server infrastructure.
"""

import os
import sys
import json
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from aiohttp import web

# Import base module
from .base_module import MCPBaseModule

# Set up logging
logger = logging.getLogger(__name__)

class WebVOWLVisualizationModule(MCPBaseModule):
    """
    Module for generating WebVOWL-compatible visualizations of ontologies.
    """
    
    def __init__(self):
        """Initialize the WebVOWL visualization module."""
        super().__init__("webvowl_visualization")
        self.owl2vowl_jar = None
        self.initialized = False
        
    def initialize(self, owl2vowl_jar_path: Optional[str] = None):
        """
        Initialize the module with OWL2VOWL converter.
        
        Args:
            owl2vowl_jar_path: Path to OWL2VOWL JAR file
        """
        if owl2vowl_jar_path:
            self.owl2vowl_jar = owl2vowl_jar_path
        else:
            # Try to find OWL2VOWL JAR in project
            project_root = Path(__file__).parent.parent.parent
            possible_paths = [
                project_root / "WebVOWL" / "webvowl" / "OWL2VOWL-0.3.7" / "target" / "OWL2VOWL-0.3.7-shaded.jar",
                project_root / "OWL2VOWL-0.2.1.jar"
            ]
            
            for path in possible_paths:
                if path.exists():
                    self.owl2vowl_jar = str(path)
                    break
                    
        if self.owl2vowl_jar and Path(self.owl2vowl_jar).exists():
            self.initialized = True
            logger.info(f"WebVOWL module initialized with OWL2VOWL at: {self.owl2vowl_jar}")
        else:
            # Only show message if not explicitly disabled
            if os.environ.get("DISABLE_WEBVOWL_MESSAGES", "false").lower() != "true":
                logger.info("WebVOWL visualization features are optional and not currently installed")
                logger.debug("To enable WebVOWL: download OWL2VOWL JAR from https://github.com/VisualDataWeb/OWL2VOWL/releases")
    
    def convert_ttl_to_vowl_json(self, ttl_content: str, ontology_name: str = "ontology") -> Optional[Dict[str, Any]]:
        """
        Convert TTL ontology content to WebVOWL JSON format.
        
        Args:
            ttl_content: Turtle/TTL ontology content
            ontology_name: Name for the ontology
            
        Returns:
            WebVOWL JSON data or None if conversion fails
        """
        if not self.initialized:
            logger.error("WebVOWL module not initialized")
            return None
            
        try:
            # Create temporary files
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as ttl_file:
                ttl_file.write(ttl_content)
                ttl_path = ttl_file.name
            
            # Convert using OWL2VOWL
            working_dir = Path(ttl_path).parent
            result = subprocess.run([
                'java', '-jar', self.owl2vowl_jar, 
                '-file', ttl_path
            ], cwd=working_dir, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"OWL2VOWL conversion failed: {result.stderr}")
                return None
            
            # Find generated JSON file
            json_path = working_dir / f"{Path(ttl_path).stem}.json"
            if not json_path.exists():
                # Try with ontology name
                json_path = working_dir / f"{ontology_name}.json"
                if not json_path.exists():
                    logger.error("Generated JSON file not found")
                    return None
            
            # Read and parse JSON
            with open(json_path, 'r') as json_file:
                vowl_data = json.load(json_file)
            
            # Cleanup temporary files
            os.unlink(ttl_path)
            if json_path.exists():
                os.unlink(json_path)
                
            return vowl_data
            
        except Exception as e:
            logger.error(f"Error converting TTL to VOWL JSON: {e}")
            return None
    
    def get_webvowl_html_template(self, vowl_json_data: Dict[str, Any], ontology_name: str) -> str:
        """
        Generate HTML page with embedded WebVOWL visualization.
        
        Args:
            vowl_json_data: WebVOWL JSON data
            ontology_name: Name of the ontology
            
        Returns:
            Complete HTML page with WebVOWL visualization
        """
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{ontology_name} - WebVOWL Visualization</title>
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
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
        }}
        .ontology-info {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .visualization-container {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            min-height: 600px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #667eea;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            display: block;
        }}
        .stat-label {{
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        .webvowl-embed {{
            width: 100%;
            height: 800px;
            border: none;
            border-radius: 8px;
        }}
        .json-data {{
            display: none;
        }}
        .controls {{
            margin-bottom: 20px;
            text-align: center;
        }}
        .btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 0 10px;
            font-size: 1em;
        }}
        .btn:hover {{
            background: #5a6fd8;
        }}
        .json-viewer {{
            background: #2d3748;
            color: #e2e8f0;
            padding: 20px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            max-height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
            display: none;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
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
    </style>
</head>
<body>
    <div class="header">
        <h1>{ontology_name}</h1>
        <p>ProEthica BFO-Compatible Engineering Ethics Ontology Visualization</p>
    </div>
    
    <div class="ontology-info">
        <h2>Ontology Statistics</h2>
        <div class="stats" id="stats">
            <!-- Stats will be populated by JavaScript -->
        </div>
    </div>
    
    <div class="visualization-container">
        <h2>Interactive Ontology Visualization</h2>
        <div class="controls">
            <button class="btn" onclick="showVisualization()">Show Visualization</button>
            <button class="btn" onclick="showRawData()">Show Raw Data</button>
            <button class="btn" onclick="downloadJson()">Download JSON</button>
        </div>
        
        <div id="visualization">
            <div id="vowl-graph" style="width: 100%; height: 800px; border: 1px solid #ddd; border-radius: 8px; background: #f9f9f9; position: relative;">
                <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; color: #666;">
                    <h3>Interactive Ontology Graph</h3>
                    <p>Loading visualization...</p>
                    <div class="loading-spinner" style="margin: 20px auto; width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #667eea; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                </div>
            </div>
        </div>
        
        <div class="json-viewer" id="json-viewer">
            <!-- JSON data will be populated here -->
        </div>
    </div>
    
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script type="application/json" class="json-data" id="ontology-data">
{json.dumps(vowl_json_data, indent=2)}
    </script>
    
    <div class="tooltip" id="tooltip"></div>
    
    <script>
        // Load ontology data
        const ontologyData = JSON.parse(document.getElementById('ontology-data').textContent);
        
        // Calculate and display statistics
        function displayStats() {{
            const stats = calculateOntologyStats(ontologyData);
            const statsContainer = document.getElementById('stats');
            
            statsContainer.innerHTML = Object.entries(stats).map(([label, value]) => `
                <div class="stat-card">
                    <span class="stat-number">${{value}}</span>
                    <div class="stat-label">${{label}}</div>
                </div>
            `).join('');
        }}
        
        function calculateOntologyStats(data) {{
            const stats = {{}};
            
            if (data.class && Array.isArray(data.class)) {{
                stats['Classes'] = data.class.length;
            }}
            
            if (data.property && Array.isArray(data.property)) {{
                stats['Properties'] = data.property.length;
                
                // Count different property types
                const objProps = data.property.filter(p => p.type === 'owl:ObjectProperty').length;
                const dataProps = data.property.filter(p => p.type === 'owl:DatatypeProperty').length;
                
                if (objProps > 0) stats['Object Properties'] = objProps;
                if (dataProps > 0) stats['Data Properties'] = dataProps;
            }}
            
            if (data.classAttribute && Array.isArray(data.classAttribute)) {{
                // Count classes with source attribution
                const classesWithSources = data.classAttribute.filter(cls => 
                    cls.other && (cls.other['dc:source'] || cls.other['rdfs:seeAlso'])
                ).length;
                
                if (classesWithSources > 0) {{
                    stats['Classes with Sources'] = classesWithSources;
                }}
                
                // Count total instances
                const totalInstances = data.classAttribute.reduce((sum, cls) => sum + (cls.instances || 0), 0);
                if (totalInstances > 0) {{
                    stats['Total Instances'] = totalInstances;
                }}
            }}
            
            if (data.propertyAttribute && Array.isArray(data.propertyAttribute)) {{
                stats['Property Attributes'] = data.propertyAttribute.length;
            }}
            
            // Count subclass relationships
            if (data.classAttribute) {{
                const subclassCount = data.classAttribute.reduce((sum, cls) => 
                    sum + (cls.superClasses ? cls.superClasses.length : 0), 0
                );
                if (subclassCount > 0) {{
                    stats['Subclass Relations'] = subclassCount;
                }}
            }}
            
            return stats;
        }}
        
        function showVisualization() {{
            document.getElementById('visualization').style.display = 'block';
            document.getElementById('json-viewer').style.display = 'none';
            
            // Create D3.js visualization
            createD3Visualization();
        }}
        
        function createD3Visualization() {{
            // Clear any existing visualization
            d3.select('#vowl-graph').selectAll('*').remove();
            
            // Set up dimensions
            const container = d3.select('#vowl-graph');
            const width = 800;
            const height = 800;
            
            // Create SVG
            const svg = container.append('svg')
                .attr('width', '100%')
                .attr('height', '100%')
                .attr('viewBox', `0 0 ${{width}} ${{height}}`);
            
            // Create tooltip
            const tooltip = d3.select('#tooltip');
            
            // Create lookup maps for labels and metadata
            const classAttributeMap = new Map();
            const propertyAttributeMap = new Map();
            
            // Build class attribute lookup
            if (ontologyData.classAttribute) {{
                ontologyData.classAttribute.forEach(attr => {{
                    classAttributeMap.set(attr.id, attr);
                }});
            }}
            
            // Build property attribute lookup  
            if (ontologyData.propertyAttribute) {{
                ontologyData.propertyAttribute.forEach(attr => {{
                    propertyAttributeMap.set(attr.id, attr);
                }});
            }}
            
            // Process ontology data for D3
            const nodes = [];
            const links = [];
            
            // Add classes as nodes with proper labels
            if (ontologyData.class) {{
                ontologyData.class.forEach(cls => {{
                    const classAttr = classAttributeMap.get(cls.id);
                    const label = classAttr?.label?.en || classAttr?.label?.['IRI-based'] || cls.id;
                    
                    nodes.push({{
                        id: cls.id,
                        label: label,
                        type: 'class',
                        color: '#4CAF50',
                        data: cls,
                        attributes: classAttr,
                        iri: classAttr?.iri,
                        comment: classAttr?.comment?.en
                    }});
                }});
            }}
            
            // Add properties as nodes with proper labels
            if (ontologyData.property) {{
                ontologyData.property.forEach(prop => {{
                    const propAttr = propertyAttributeMap.get(prop.id);
                    const label = propAttr?.label?.en || propAttr?.label?.['IRI-based'] || prop.id;
                    const color = prop.type === 'owl:ObjectProperty' ? '#2196F3' : '#FF9800';
                    
                    nodes.push({{
                        id: prop.id,
                        label: label,
                        type: 'property',
                        color: color,
                        data: prop,
                        attributes: propAttr,
                        iri: propAttr?.iri,
                        comment: propAttr?.comment?.en
                    }});
                    
                    // Create links from domain to range
                    if (prop.domain && prop.range) {{
                        links.push({{
                            source: prop.domain,
                            target: prop.range,
                            type: 'property',
                            property: prop.id,
                            label: label
                        }});
                    }}
                }});
            }}
            
            // Add subclass relationships as links
            if (ontologyData.classAttribute) {{
                ontologyData.classAttribute.forEach(classAttr => {{
                    if (classAttr.superClasses) {{
                        classAttr.superClasses.forEach(superClassId => {{
                            links.push({{
                                source: classAttr.id,
                                target: superClassId,
                                type: 'subclass',
                                label: 'subClassOf'
                            }});
                        }});
                    }}
                }});
            }}
            
            // Set up force simulation
            const simulation = d3.forceSimulation(nodes)
                .force('link', d3.forceLink(links).id(d => d.id).distance(100))
                .force('charge', d3.forceManyBody().strength(-300))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('collision', d3.forceCollide().radius(30));
            
            // Create links
            const link = svg.append('g')
                .selectAll('line')
                .data(links)
                .enter().append('line')
                .attr('class', 'link')
                .attr('stroke-width', 2);
            
            // Create link labels
            const linkLabel = svg.append('g')
                .selectAll('text')
                .data(links)
                .enter().append('text')
                .attr('class', 'node-label')
                .attr('font-size', '10px')
                .attr('fill', '#666')
                .text(d => d.label);
            
            // Create nodes
            const node = svg.append('g')
                .selectAll('circle')
                .data(nodes)
                .enter().append('circle')
                .attr('class', 'node')
                .attr('r', d => d.type === 'class' ? 20 : 15)
                .attr('fill', d => d.color)
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended))
                .on('mouseover', function(event, d) {{
                    tooltip.transition().duration(200).style('opacity', .9);
                    
                    let tooltipContent = `<strong>${{d.label}}</strong><br/>`;
                    tooltipContent += `Type: ${{d.type}}<br/>`;
                    
                    if (d.iri) {{
                        tooltipContent += `IRI: ${{d.iri}}<br/>`;
                    }}
                    
                    if (d.comment) {{
                        tooltipContent += `<em>${{d.comment}}</em><br/>`;
                    }}
                    
                    if (d.attributes?.instances !== undefined) {{
                        tooltipContent += `Instances: ${{d.attributes.instances}}<br/>`;
                    }}
                    
                    if (d.attributes?.superClasses?.length > 0) {{
                        tooltipContent += `Super Classes: ${{d.attributes.superClasses.length}}<br/>`;
                    }}
                    
                    // Show source attribution if available
                    if (d.attributes?.other) {{
                        const sources = [];
                        if (d.attributes.other['dc:source']) {{
                            sources.push('dc:source');
                        }}
                        if (d.attributes.other['rdfs:seeAlso']) {{
                            sources.push('rdfs:seeAlso');
                        }}
                        if (sources.length > 0) {{
                            tooltipContent += `<span style="color: #4CAF50;">✓ Source Attribution</span><br/>`;
                        }}
                    }}
                    
                    tooltip.html(tooltipContent)
                        .style('left', (event.pageX + 10) + 'px')
                        .style('top', (event.pageY - 28) + 'px');
                }})
                .on('mouseout', function(d) {{
                    tooltip.transition().duration(500).style('opacity', 0);
                }});
            
            // Create node labels
            const nodeLabel = svg.append('g')
                .selectAll('text')
                .data(nodes)
                .enter().append('text')
                .attr('class', 'node-label')
                .attr('dy', '.35em')
                .text(d => d.label.length > 15 ? d.label.substring(0, 15) + '...' : d.label);
            
            // Update positions on simulation tick
            simulation.on('tick', () => {{
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
                
                linkLabel
                    .attr('x', d => (d.source.x + d.target.x) / 2)
                    .attr('y', d => (d.source.y + d.target.y) / 2);
                
                node
                    .attr('cx', d => d.x)
                    .attr('cy', d => d.y);
                
                nodeLabel
                    .attr('x', d => d.x)
                    .attr('y', d => d.y);
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
                .on('zoom', function(event) {{
                    svg.selectAll('g').attr('transform', event.transform);
                }}));
        }}
        
        function showRawData() {{
            document.getElementById('visualization').style.display = 'none';
            document.getElementById('json-viewer').style.display = 'block';
            document.getElementById('json-viewer').textContent = JSON.stringify(ontologyData, null, 2);
        }}
        
        function downloadJson() {{
            const dataStr = JSON.stringify(ontologyData, null, 2);
            const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
            
            const exportFileDefaultName = '{ontology_name.lower().replace(" ", "_")}_webvowl.json';
            
            const linkElement = document.createElement('a');
            linkElement.setAttribute('href', dataUri);
            linkElement.setAttribute('download', exportFileDefaultName);
            linkElement.click();
        }}
        
        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {{
            displayStats();
            showVisualization();
        }});
    </script>
</body>
</html>
        """
        
        return html_template
    
    async def create_visualization_routes(self, app: web.Application):
        """
        Add WebVOWL visualization routes to the web application.
        
        Args:
            app: aiohttp web application
        """
        
        async def visualize_ontology(request):
            """Handle ontology visualization requests."""
            try:
                ontology_name = request.match_info.get('name', 'unknown')
                
                # Try to get ontology from database or file
                ontology_content = await self._get_ontology_content(ontology_name)
                
                if not ontology_content:
                    return web.Response(
                        text=f"Ontology '{ontology_name}' not found",
                        status=404
                    )
                
                # Convert to WebVOWL JSON
                vowl_data = self.convert_ttl_to_vowl_json(ontology_content, ontology_name)
                
                if not vowl_data:
                    return web.Response(
                        text="Failed to convert ontology to WebVOWL format",
                        status=500
                    )
                
                # Generate HTML visualization
                html_content = self.get_webvowl_html_template(vowl_data, ontology_name)
                
                return web.Response(
                    text=html_content,
                    content_type='text/html'
                )
                
            except Exception as e:
                logger.error(f"Error creating ontology visualization: {e}")
                return web.Response(
                    text=f"Error: {str(e)}",
                    status=500
                )
        
        async def list_visualizable_ontologies(request):
            """List available ontologies for visualization."""
            try:
                ontologies = await self._get_available_ontologies()
                
                html_content = self._generate_ontology_list_html(ontologies)
                
                return web.Response(
                    text=html_content,
                    content_type='text/html'
                )
                
            except Exception as e:
                logger.error(f"Error listing ontologies: {e}")
                return web.Response(
                    text=f"Error: {str(e)}",
                    status=500
                )
        
        # Add routes
        app.router.add_get('/visualization/ontology/{name}', visualize_ontology)
        app.router.add_get('/visualization/ontologies', list_visualizable_ontologies)
        app.router.add_get('/visualization', list_visualizable_ontologies)
        
        logger.info("WebVOWL visualization routes added to MCP server")
    
    async def _get_ontology_content(self, ontology_name: str) -> Optional[str]:
        """
        Get ontology content from database or file system.
        
        Args:
            ontology_name: Name of the ontology
            
        Returns:
            Ontology content as TTL string or None
        """
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
    
    async def _get_available_ontologies(self) -> List[str]:
        """Get list of available ontologies."""
        ontologies = []
        
        try:
            # Check database
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                from app import create_app
                from app.models.ontology import Ontology
                
                app = create_app('config')
                with app.app_context():
                    db_ontologies = Ontology.query.all()
                    ontologies.extend([ont.domain_id for ont in db_ontologies if ont.domain_id])
                    
            except Exception as e:
                logger.debug(f"Database access failed: {e}")
            
            # Check file system
            project_root = Path(__file__).parent.parent.parent
            ontology_dir = project_root / "ontologies"
            
            if ontology_dir.exists():
                for ttl_file in ontology_dir.glob("*.ttl"):
                    name = ttl_file.stem
                    if name not in ontologies:
                        ontologies.append(name)
            
        except Exception as e:
            logger.error(f"Error getting available ontologies: {e}")
        
        return sorted(ontologies)
    
    def _generate_ontology_list_html(self, ontologies: List[str]) -> str:
        """Generate HTML page listing available ontologies."""
        ontology_cards = ""
        
        for ontology in ontologies:
            ontology_cards += f"""
            <div class="ontology-card">
                <h3>{ontology.replace('-', ' ').title()}</h3>
                <p>BFO-compatible ontology for engineering ethics analysis</p>
                <a href="/visualization/ontology/{ontology}" class="btn">Visualize</a>
            </div>
            """
        
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProEthica Ontology Visualizations</title>
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
        .ontologies-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .ontology-card {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .ontology-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
        }}
        .ontology-card h3 {{
            color: #333;
            margin-bottom: 15px;
            font-size: 1.5em;
        }}
        .ontology-card p {{
            color: #666;
            margin-bottom: 20px;
            line-height: 1.5;
        }}
        .btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1em;
            text-decoration: none;
            display: inline-block;
            transition: background 0.2s;
        }}
        .btn:hover {{
            background: #5a6fd8;
        }}
        .info-section {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .features {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .feature {{
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        .feature-icon {{
            font-size: 2em;
            margin-bottom: 10px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>ProEthica Ontology Visualizations</h1>
        <p>Interactive WebVOWL visualizations of BFO-compatible engineering ethics ontologies</p>
    </div>
    
    <div class="info-section">
        <h2>Visualization Features</h2>
        <div class="features">
            <div class="feature">
                <div class="feature-icon">🔗</div>
                <h3>BFO Integration</h3>
                <p>Visualize complete ontology stack from BFO foundational classes to engineering-specific concepts</p>
            </div>
            <div class="feature">
                <div class="feature-icon">📊</div>
                <h3>Interactive Exploration</h3>
                <p>Navigate class hierarchies, properties, and relationships with force-directed layouts</p>
            </div>
            <div class="feature">
                <div class="feature-icon">📋</div>
                <h3>Source Attribution</h3>
                <p>View ISO standards, NSPE codes, and professional engineering references for each concept</p>
            </div>
            <div class="feature">
                <div class="feature-icon">💾</div>
                <h3>Export & Share</h3>
                <p>Download WebVOWL JSON data for use in other visualization tools and applications</p>
            </div>
        </div>
    </div>
    
    <div class="info-section">
        <h2>Available Ontologies ({len(ontologies)})</h2>
        <div class="ontologies-grid">
            {ontology_cards if ontology_cards else '<p>No ontologies available for visualization.</p>'}
        </div>
    </div>
</body>
</html>
        """
        
        return html_template