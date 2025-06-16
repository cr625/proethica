#!/usr/bin/env python3
"""
Enhanced Ontology MCP Server with Guidelines Support

This module provides the MCP server functionality with ontology operations
and guideline analysis capabilities.
"""

import os
import sys
import json
import logging
# from mcp.enhanced_debug_logging import log_debug_point, log_json_rpc_request, log_method_call
import asyncio
import aiohttp
from aiohttp import web
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import MCP server and modules
from mcp.http_ontology_mcp_server import OntologyMCPServer
from mcp.modules.guideline_analysis_module import GuidelineAnalysisModule
from mcp.modules.webvowl_visualization_module import WebVOWLVisualizationModule
from mcp.modules.neo4j_visualization_module import Neo4jVisualizationModule

class OntologyClientWrapper:
    """
    Wrapper class for the ontology client to ensure method availability.
    This provides a guaranteed interface to the ontology client methods.
    """
    
    def __init__(self, server):
        """
        Initialize the wrapper with a server instance.
        
        Args:
            server: The server instance to wrap
        """
        self.server = server
    
    async def get_ontology_sources(self):
        """
        Forward to the server's get_ontology_sources method.
        
        Returns:
            Dictionary containing ontology sources information
        """
        try:
            if hasattr(self.server, 'get_ontology_sources'):
                return await self.server.get_ontology_sources()
            else:
                logger.error("Server does not have get_ontology_sources method")
                return {"sources": [], "default": None}
        except Exception as e:
            logger.error(f"Error in get_ontology_sources wrapper: {str(e)}")
            return {"sources": [], "default": None}
    
    async def get_ontology_entities(self, ontology_source):
        """
        Forward to the server's get_ontology_entities method.
        
        Args:
            ontology_source: Identifier for the ontology source
            
        Returns:
            Dictionary containing entities grouped by type
        """
        try:
            if hasattr(self.server, 'get_ontology_entities'):
                return await self.server.get_ontology_entities(ontology_source)
            else:
                logger.error("Server does not have get_ontology_entities method")
                return {"entities": {}}
        except Exception as e:
            logger.error(f"Error in get_ontology_entities wrapper: {str(e)}")
            return {"entities": {}}

class EnhancedOntologyServerWithGuidelines(OntologyMCPServer):
    """
    Enhanced Ontology MCP Server with Guidelines Support
    
    This server extends the HTTP Ontology MCP Server with additional modules
    for guideline analysis and concept extraction. It provides tools for:
    
    1. Extracting concepts from guideline documents
    2. Matching concepts to ontology entities
    3. Generating RDF triples for guideline concepts
    4. Analyzing ethical principles in guidelines
    """
    
    def __init__(self):
        """
        Initialize the server.
        """
        # Call parent constructor
        super().__init__()
        
        # Set server info defaults
        self.server_info = {
            "name": "Enhanced Ontology MCP Server with Guidelines",
            "version": "1.1.0",
            "description": "MCP server for ontology operations and guideline analysis" 
        }
        
        # Update server info
        self.server_info["name"] = "Enhanced Ontology MCP Server with Guidelines"
        self.server_info["version"] = "1.1.0"
        self.server_info["description"] = "MCP server for ontology operations and guideline analysis"
        self.server_info["capabilities"] = [
            "Ontology entity extraction",
            "Guideline concept analysis",
            "Semantic matching",
            "RDF triple generation",
            "Engineering ethics analysis"
        ]
        
        # Check environment variable for debug mode
        self.debug_mode = os.environ.get("MCP_DEBUG", "false").lower() == "true"
        if self.debug_mode:
            logger.info("Debug mode enabled - breakpoints should be active")
            # Set higher log level for debug mode
            logging.getLogger().setLevel(logging.DEBUG)
            
        logger.info("Enhanced Ontology Server with Guidelines initialized")
        
        # Set up LLM clients
        self._init_anthropic_client()
        self._init_openai_client()
        
        # Set up embeddings client
        self._init_embeddings_client()
        
        # Create ontology client wrapper
        self.ontology_client_wrapper = OntologyClientWrapper(self)
        
        # Initialize modules dict
        self.modules = {}
        
        # Register additional modules
        self._register_guideline_analysis_module()
        self._register_webvowl_visualization_module()
        self._register_neo4j_visualization_module()
    
    def _init_anthropic_client(self):
        """Initialize the Anthropic client."""
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.anthropic_available = bool(self.anthropic_api_key)
        
        if self.anthropic_available:
            try:
                import anthropic
                self.anthropic_client = anthropic.AsyncClient(api_key=self.anthropic_api_key)
                logger.info("Anthropic client initialized successfully")
            except ImportError:
                logger.warning("Could not import anthropic package. Anthropic client not available.")
                self.anthropic_available = False
            except Exception as e:
                logger.error(f"Error initializing Anthropic client: {e}")
                self.anthropic_available = False
        else:
            logger.warning("ANTHROPIC_API_KEY not found in environment. Anthropic client not available.")
    
    def _init_openai_client(self):
        """Initialize the OpenAI client."""
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.openai_available = bool(self.openai_api_key)
        
        if self.openai_available:
            try:
                import openai
                self.openai_client = openai.AsyncClient(api_key=self.openai_api_key)
                logger.info("OpenAI client initialized successfully")
            except ImportError:
                logger.warning("Could not import openai package. OpenAI client not available.")
                self.openai_available = False
            except Exception as e:
                logger.error(f"Error initializing OpenAI client: {e}")
                self.openai_available = False
        else:
            logger.warning("OPENAI_API_KEY not found in environment. OpenAI client not available.")
    
    def _init_embeddings_client(self):
        """Initialize the embeddings client."""
        # Try to use a real embeddings client first
        self.openai_embeddings_key = os.environ.get("OPENAI_API_KEY")
        if self.openai_embeddings_key:
            try:
                import openai
                
                # Define an async embeddings client using OpenAI
                class OpenAIEmbeddingsClient:
                    def __init__(self, api_key):
                        self.client = openai.AsyncClient(api_key=api_key)
                        self.model = "text-embedding-3-small"
                    
                    async def get_embedding(self, text):
                        """Get embedding for a single text."""
                        response = await self.client.embeddings.create(
                            input=text, 
                            model=self.model
                        )
                        return response.data[0].embedding
                    
                    async def get_embeddings(self, texts):
                        """Get embeddings for multiple texts."""
                        response = await self.client.embeddings.create(
                            input=texts, 
                            model=self.model
                        )
                        return [item.embedding for item in response.data]
                    
                    async def calculate_similarities(self, texts1, texts2):
                        """Calculate cosine similarities between two sets of texts."""
                        # Get embeddings for all texts
                        embeddings1 = await self.get_embeddings(texts1)
                        embeddings2 = await self.get_embeddings(texts2)
                        
                        # Calculate cosine similarities
                        return self._cosine_similarities(embeddings1, embeddings2)
                    
                    def _cosine_similarities(self, embeddings1, embeddings2):
                        """Calculate all pairwise cosine similarities."""
                        import numpy as np
                        
                        # Normalize embeddings
                        normalized1 = [self._normalize(e) for e in embeddings1]
                        normalized2 = [self._normalize(e) for e in embeddings2]
                        
                        # Calculate similarities
                        return [[np.dot(e1, e2) for e2 in normalized2] for e1 in normalized1]
                    
                    def _normalize(self, v):
                        """Normalize a vector."""
                        import numpy as np
                        norm = np.linalg.norm(v)
                        if norm == 0:
                            return v
                        return v / norm
                
                self.embeddings_client = OpenAIEmbeddingsClient(self.openai_embeddings_key)
                logger.info("OpenAI embeddings client initialized successfully")
                return
                
            except (ImportError, Exception) as e:
                logger.warning(f"Error setting up OpenAI embeddings client: {e}")
        
        # Fall back to simple embeddings client if no real client available
        class SimpleEmbeddingsClient:
            async def calculate_similarities(self, texts1, texts2):
                """
                Calculate similarity scores between two sets of texts.
                
                This is a simplified implementation that just returns random scores.
                In a real implementation, this would calculate proper embeddings
                and cosine similarity.
                
                Args:
                    texts1: First set of texts
                    texts2: Second set of texts
                    
                Returns:
                    List of lists of similarity scores
                """
                import random
                
                # Generate random similarity scores with some smarter behavior
                def simple_similarity(t1, t2):
                    # Check for exact matches
                    if t1.lower() == t2.lower():
                        return 0.99
                    
                    # Check for substring matches
                    if t1.lower() in t2.lower() or t2.lower() in t1.lower():
                        return random.uniform(0.7, 0.9)
                    
                    # Check for word overlap
                    words1 = set(t1.lower().split())
                    words2 = set(t2.lower().split())
                    overlap = words1.intersection(words2)
                    if overlap:
                        return random.uniform(0.5, 0.8) * (len(overlap) / max(len(words1), len(words2)))
                    
                    # Default random similarity
                    return random.uniform(0.1, 0.5)
                
                return [[simple_similarity(t1, t2) for t2 in texts2] for t1 in texts1]
                
            async def get_embedding(self, text):
                """Get a mock embedding for a text."""
                import random
                return [random.random() for _ in range(384)]
        
        self.embeddings_client = SimpleEmbeddingsClient()
        logger.info("Simple embeddings client initialized (fallback mode)")
    
    def add_module(self, module):
        """
        Add a module to the server.
        
        Args:
            module: The module to add
        """
        module_name = module.name
        self.modules[module_name] = module
        logger.info(f"Added module: {module_name}")
    
    async def handle_health(self, request):
        """Simple health check endpoint for the Enhanced Ontology MCP server."""
        return web.json_response({"status": "ok", "message": "Enhanced Ontology MCP server with guidelines is running"})
    
    async def start(self):
        """Start the server."""
        # Initialize web application
        self.app = web.Application()
        
        # Register routes
        self.app.router.add_post('/jsonrpc', self.handle_jsonrpc)
        # Health check endpoint
        self.app.router.add_get('/health', self.handle_health)
        
        # Add CORS middleware
        @web.middleware
        async def cors_middleware(request, handler):
            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response
        
        self.app.middlewares.append(cors_middleware)
        
        # Start the server
        port = int(os.environ.get("MCP_SERVER_PORT", 5001))
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, 'localhost', port)
        await self.site.start()
        
        logger.info(f"Server started at http://localhost:{port}")
    
    async def stop(self):
        """Stop the server."""
        if hasattr(self, 'site'):
            await self.site.stop()
        if hasattr(self, 'runner'):
            await self.runner.cleanup()
        logger.info("Server stopped")
    
    async def _handle_call_tool(self, params):
        """
        Handle a tool call.
        
        Args:
            params: Parameters for the tool call
            
        Returns:
            Result of the tool call
        """
        log_debug_point(message="Handling tool call")
        name = params.get("name")
        arguments = params.get("arguments", {})
        
        # Look for the tool in all modules
        for module_name, module in self.modules.items():
            if name in module.tools:
                try:
                    logger.info(f"Calling tool '{name}' in module '{module_name}'")
                    result = await module.call_tool(name, arguments)
                    return result
                except Exception as e:
                    logger.error(f"Error calling tool '{name}' in module '{module_name}': {str(e)}")
                    import traceback
                    traceback.print_exc()
                    return {"error": f"Tool execution failed: {str(e)}"}
        
        # If tool not found in modules, try parent implementation
        return await super()._handle_call_tool(params)
    
    async def _handle_list_tools(self, params):
        """
        List all available tools.
        
        Args:
            params: Parameters (unused)
            
        Returns:
            List of available tools
        """
        tools = []
        
        # Get tools from each module
        for module_name, module in self.modules.items():
            module_tools = module.get_tools()
            for tool in module_tools:
                tools.append({
                    "name": tool["name"],
                    "description": tool["description"],
                    "module": module_name,
                    "input_schema": tool["input_schema"]
                })
        
        # Add parent tools if any
        parent_tools = await super()._handle_list_tools(params)
        if isinstance(parent_tools, dict) and "tools" in parent_tools:
            for tool_name in parent_tools["tools"]:
                tools.append({
                    "name": tool_name,
                    "description": f"Core tool: {tool_name}",
                    "module": "core"
                })
        
        return {"tools": tools}
    
    async def get_ontology_sources(self):
        """
        Get available ontology sources.
        
        This method returns a list of available ontology sources based on the
        namespaces defined in the parent class and the .ttl files in the 
        ontology directory.
        
        Returns:
            Dict containing list of available ontology sources
        """
        try:
            # Get the list of namespaces from the parent class
            sources = []
            
            # Only use the engineering_ethics source to avoid errors with non-existent sources
            sources = [
                {
                    "id": "engineering-ethics",
                    "uri": "http://proethica.org/ontology/engineering-ethics#",
                    "label": "Engineering Ethics",
                    "description": "Ontology source for Engineering Ethics domain"
                }
            ]
            
            return {
                "sources": sources,
                "default": sources[0]["id"] if sources else None
            }
        except Exception as e:
            import traceback
            logger.error(f"Error getting ontology sources: {str(e)}")
            logger.error(traceback.format_exc())
            return {"sources": [], "default": None}
            
    async def get_ontology_entities(self, ontology_source):
        """
        Get entities from a specific ontology source.
        
        This method is called by the guideline analysis module to retrieve
        entities from a specific ontology source for matching with
        extracted guideline concepts.
        
        Args:
            ontology_source: Identifier for the ontology source
            
        Returns:
            Dict containing entities grouped by type
        """
        try:
            # Load the ontology graph
            g = self._load_graph_from_file(ontology_source)
            
            # Extract entities using the parent class method
            entities = self._extract_entities(g, "all")
            
            return {"entities": entities}
        except Exception as e:
            import traceback
            logger.error(f"Error getting ontology entities: {str(e)}")
            logger.error(traceback.format_exc())
            return {"entities": {}, "error": str(e)}
    
    def _register_guideline_analysis_module(self):
        """Register the guideline analysis module."""
        try:
            # Create the module
            guideline_module = GuidelineAnalysisModule(
                llm_client=self.anthropic_client if self.anthropic_available else None,
                ontology_client=self.ontology_client_wrapper,
                embedding_client=self.embeddings_client
            )
            
            # Add it to our modules
            self.add_module(guideline_module)
            
            logger.info("Guideline analysis module registered successfully")
        except Exception as e:
            logger.error(f"Error registering guideline analysis module: {e}")
            raise
    
    def _register_webvowl_visualization_module(self):
        """Register the WebVOWL visualization module."""
        try:
            # Create the module
            webvowl_module = WebVOWLVisualizationModule()
            
            # Initialize with OWL2VOWL JAR path
            webvowl_module.initialize()
            
            # Store in modules dict for later web route registration
            self.modules['webvowl'] = webvowl_module
            
            logger.info("WebVOWL visualization module registered successfully")
        except Exception as e:
            logger.error(f"Error registering WebVOWL visualization module: {e}")
            # Don't raise - visualization is optional
    
    def _register_neo4j_visualization_module(self):
        """Register the Neo4j visualization module."""
        try:
            # Create the module
            neo4j_module = Neo4jVisualizationModule()
            
            # Initialize with default Neo4j settings
            neo4j_module.initialize()
            
            # Store in modules dict for later web route registration
            self.modules['neo4j'] = neo4j_module
            
            logger.info("Neo4j visualization module registered successfully")
        except Exception as e:
            logger.error(f"Error registering Neo4j visualization module: {e}")
            # Don't raise - visualization is optional

async def run_server():
    """
    Run the enhanced ontology server with guidelines support.
    
    This function creates and starts the server with WebVOWL visualization.
    """
    # Create server
    server = EnhancedOntologyServerWithGuidelines()
    
    # Create web application
    app = web.Application()
    
    # Add CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    app.middlewares.append(cors_middleware)
    
    # Register core MCP routes
    app.router.add_post('/jsonrpc', server.handle_jsonrpc)
    app.router.add_get('/api/ontology/{ontology_source}/entities', server.handle_get_entities)
    app.router.add_get('/api/guidelines/{world_name}', server.handle_get_guidelines)
    app.router.add_get('/health', server.handle_health)
    
    # Register WebVOWL visualization routes if module is available
    if 'webvowl' in server.modules:
        webvowl_module = server.modules['webvowl']
        await webvowl_module.create_visualization_routes(app)
        logger.info("WebVOWL visualization routes registered")
    
    # Register Neo4j visualization routes if module is available
    if 'neo4j' in server.modules:
        neo4j_module = server.modules['neo4j']
        await neo4j_module.create_neo4j_routes(app)
        logger.info("Neo4j visualization routes registered")
    
    # Start the web server
    PORT = int(os.environ.get("MCP_SERVER_PORT", 5001))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', PORT)
    await site.start()
    
    logger.info(f"Enhanced MCP Server with WebVOWL and Neo4j running on http://localhost:{PORT}")
    logger.info(f"WebVOWL visualizations available at: http://localhost:{PORT}/visualization")
    logger.info(f"Neo4j browser interface available at: http://localhost:{PORT}/neo4j")
    
    # Keep running until interrupted
    try:
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except asyncio.CancelledError:
        logger.info("Server cancelled")
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(run_server())
