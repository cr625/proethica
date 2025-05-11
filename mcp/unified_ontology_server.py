#!/usr/bin/env python3
"""
Unified Ontology MCP Server

This module implements a unified MCP server for ontology access,
integrating multiple functionalities into a single, modular server.
"""

import os
import sys
import json
import importlib
import inspect
import logging
import traceback
from typing import Dict, List, Any, Optional, Type, Set, Union
import asyncio
from datetime import datetime

import rdflib
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL
from aiohttp import web
import aiohttp

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("UnifiedOntologyServer")

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import base module class
from mcp.modules.base_module import BaseModule


class UnifiedOntologyServer:
    """
    Unified Ontology MCP Server with modular architecture.
    
    This server provides access to ontology data through a unified interface,
    integrating various functionalities like ontology querying, temporal
    analysis, relationship navigation, and case analysis into a single
    modular server.
    """
    
    def __init__(self):
        """Initialize the unified ontology server."""
        self.modules = {}  # Module name -> module instance
        self.namespaces = {}  # Prefix -> Namespace
        self.cache = {}  # Cache for graphs and other data
        self.cache_timestamps = {}  # Timestamps for cache entries
        self.mcp_url = os.environ.get("MCP_SERVER_URL", "http://localhost:5001")
        
        # Set up Flask app context for database access if possible
        try:
            from app import create_app
            self.app = create_app()
            logger.info("Successfully initialized Flask app")
        except Exception as e:
            logger.warning(f"Failed to initialize Flask app: {str(e)}")
            self.app = None
            
        # Initialize common namespaces
        self._initialize_namespaces()
        
        # Load modules
        self._load_modules()
        
        logger.info("Unified Ontology MCP Server initialized")
    
    def _initialize_namespaces(self):
        """Initialize common RDF namespaces."""
        self.namespaces = {
            "rdf": RDF,
            "rdfs": RDFS,
            "owl": OWL,
            "bfo": Namespace("http://purl.obolibrary.org/obo/BFO_"),
            "proethica": Namespace("http://proethica.org/ontology/"),
            "proethica-intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
            "mseo": Namespace("http://matportal.org/ontology/MSEO#")
        }
    
    def _load_modules(self):
        """
        Dynamically load available modules from the modules directory.
        """
        try:
            # Get modules directory path
            modules_dir = os.path.join(os.path.dirname(__file__), 'modules')
            
            # Import known module types
            module_types = [
                "query_module",
                "temporal_module", 
                "relationship_module",
                "case_analysis_module"
            ]
            
            for module_type in module_types:
                try:
                    # Check if module file exists
                    module_path = os.path.join(modules_dir, f"{module_type}.py")
                    if not os.path.exists(module_path):
                        logger.warning(f"Module file not found: {module_path}")
                        continue
                    
                    # Import the module
                    module = importlib.import_module(f"mcp.modules.{module_type}")
                    
                    # Find module classes
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (issubclass(obj, BaseModule) and 
                            obj.__module__ == f"mcp.modules.{module_type}" and 
                            obj is not BaseModule):
                            
                            # Create instance and register
                            module_instance = obj(self)
                            module_name = module_instance.name
                            
                            if module_name in self.modules:
                                logger.warning(f"Module {module_name} already registered, overwriting")
                                
                            self.modules[module_name] = module_instance
                            logger.info(f"Registered module: {module_name}")
                except Exception as e:
                    logger.error(f"Error loading module {module_type}: {str(e)}")
                    traceback.print_exc()
                    
            # Initialize all modules
            for name, module in self.modules.items():
                try:
                    module.initialize()
                except Exception as e:
                    logger.error(f"Error initializing module {name}: {str(e)}")
                    traceback.print_exc()
            
            logger.info(f"Loaded {len(self.modules)} modules")
        except Exception as e:
            logger.error(f"Error loading modules: {str(e)}")
            traceback.print_exc()
    
    async def handle_jsonrpc(self, request):
        """
        Handle JSON-RPC requests sent to this server.
        
        Args:
            request: aiohttp request object
            
        Returns:
            aiohttp response with JSON-RPC response
        """
        try:
            # Parse request
            data = await request.json()
            
            # Extract common JSON-RPC fields
            method = data.get("method")
            params = data.get("params", {})
            id = data.get("id")
            
            # Process the request
            if method == "list_tools":
                result = await self._handle_list_tools(params)
            elif method == "call_tool":
                result = await self._handle_call_tool(params)
            else:
                result = {"error": {"code": -32601, "message": f"Method not found: {method}"}}
            
            # Send response
            response = {
                "jsonrpc": "2.0",
                "id": id,
                "result": result
            }
            
            return web.json_response(response)
        except Exception as e:
            logger.error(f"Error handling JSON-RPC request: {str(e)}")
            traceback.print_exc()
            
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id") if 'data' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            })
    
    async def _handle_list_tools(self, params):
        """
        Handle the list_tools method.
        
        Returns:
            Dictionary listing all available tools
        """
        tools = []
        
        # Collect tools from all modules
        for module_name, module in self.modules.items():
            tools.extend(module.get_tools())
        
        # Add legacy tools for backward compatibility
        legacy_tools = [
            "get_world_entities",
            "get_entity_relationships",
            "query_ontology",
            "get_ontology_guidelines"
        ]
        
        for tool in legacy_tools:
            if not any(t["name"] == tool for t in tools):
                tools.append({
                    "name": tool,
                    "description": f"Legacy tool: {tool}",
                    "module": "legacy"
                })
        
        return {
            "tools": [t["name"] for t in tools],
            "details": tools
        }
    
    async def _handle_call_tool(self, params):
        """
        Handle the call_tool method.
        
        Args:
            params: Parameters for the tool call
            
        Returns:
            Result of the tool execution
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name:
            return {"error": "Missing tool name"}
        
        try:
            # Find module that handles this tool
            for module_name, module in self.modules.items():
                if tool_name in module.tools:
                    return await module.handle_tool_call(tool_name, arguments)
            
            # If no module found, try legacy handler
            return await self._handle_legacy_tool(tool_name, arguments)
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            traceback.print_exc()
            error_msg = f"Error executing tool {tool_name}: {str(e)}"
            return {"content": [{"text": json.dumps({"error": error_msg})}]}
    
    async def _handle_legacy_tool(self, tool_name, arguments):
        """
        Handle legacy tools for backward compatibility.
        
        Args:
            tool_name: Name of the legacy tool
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        # Map legacy tool names to module and new tool names
        legacy_map = {
            "get_world_entities": ("query", "get_entities"),
            "get_entity_relationships": ("relationship", "get_relationships"),
            "query_ontology": ("query", "execute_sparql"),
            "get_ontology_guidelines": ("query", "get_guidelines")
        }
        
        if tool_name not in legacy_map:
            return {"error": f"Unknown legacy tool: {tool_name}"}
        
        module_name, new_tool = legacy_map[tool_name]
        
        if module_name not in self.modules:
            return {"error": f"Module {module_name} not available"}
        
        module = self.modules[module_name]
        
        if new_tool not in module.tools:
            return {"error": f"Tool {new_tool} not available in module {module_name}"}
        
        # Adapt arguments if necessary
        return await module.handle_tool_call(new_tool, arguments)
    
    def _load_graph_from_file(self, ontology_source):
        """
        Load an ontology graph from file or database.
        
        Args:
            ontology_source: Source identifier for ontology (domain_id or filename)
            
        Returns:
            RDFLib Graph object with loaded ontology
        """
        # Check cache first
        if ontology_source in self.cache:
            cache_time = self.cache_timestamps.get(ontology_source, 0)
            cache_ttl = 300  # 5 minutes
            
            if datetime.now().timestamp() - cache_time < cache_ttl:
                logger.debug(f"Using cached graph for {ontology_source}")
                return self.cache[ontology_source]
        
        # Try to load from database first
        if self.app:
            with self.app.app_context():
                try:
                    from app.models.ontology import Ontology
                    
                    # Try to find by domain ID
                    query = Ontology.query
                    
                    try:
                        # If ontology_source is an integer, use it as domain_id
                        domain_id = int(ontology_source)
                        ontology = query.filter_by(domain_id=domain_id).first()
                        
                        if not ontology:
                            # Try by name
                            ontology = query.filter_by(name=ontology_source).first()
                    except ValueError:
                        # If not an integer, try by name
                        ontology = query.filter_by(name=ontology_source).first()
                    
                    if ontology and ontology.content:
                        g = Graph()
                        
                        # Register common namespaces
                        for prefix, namespace in self.namespaces.items():
                            g.bind(prefix, namespace)
                        
                        # Parse content
                        try:
                            g.parse(data=ontology.content, format="turtle")
                            
                            # Cache the graph
                            self.cache[ontology_source] = g
                            self.cache_timestamps[ontology_source] = datetime.now().timestamp()
                            
                            logger.info(f"Loaded ontology from database: {ontology_source}")
                            return g
                        except Exception as e:
                            logger.error(f"Error parsing ontology content: {str(e)}")
                except ImportError:
                    logger.warning("Ontology model not available")
                except Exception as e:
                    logger.error(f"Error loading ontology from database: {str(e)}")
        
        # If not found in database or parsing failed, try as a file
        try:
            # If ontology_source doesn't have .ttl extension, add it
            if not ontology_source.endswith('.ttl'):
                file_path = f"{ontology_source}.ttl"
            else:
                file_path = ontology_source
                
            # Look in several locations
            search_paths = [
                file_path,
                os.path.join(os.path.dirname(__file__), 'ontology', file_path),
                os.path.join(os.path.dirname(__file__), '..', 'ontologies', file_path),
                os.path.join(os.path.dirname(__file__), 'mseo', file_path)
            ]
            
            g = Graph()
            
            # Register common namespaces
            for prefix, namespace in self.namespaces.items():
                g.bind(prefix, namespace)
            
            for path in search_paths:
                if os.path.exists(path):
                    g.parse(path, format="turtle")
                    
                    # Cache the graph
                    self.cache[ontology_source] = g
                    self.cache_timestamps[ontology_source] = datetime.now().timestamp()
                    
                    logger.info(f"Loaded ontology from file: {path}")
                    return g
                    
            logger.error(f"Ontology file not found: {file_path}")
            return Graph()  # Return empty graph
        except Exception as e:
            logger.error(f"Error loading ontology file: {str(e)}")
            return Graph()  # Return empty graph
    
    def clear_cache(self):
        """Clear the ontology cache."""
        self.cache = {}
        self.cache_timestamps = {}
        logger.info("Cache cleared")
    
    def shutdown(self):
        """Shutdown the server and its modules."""
        logger.info("Shutting down Unified Ontology MCP Server")
        
        # Shutdown all modules
        for name, module in self.modules.items():
            try:
                module.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down module {name}: {str(e)}")
                
        # Clear cache
        self.clear_cache()
        
        logger.info("Shutdown complete")
    
    async def handle_get_entities(self, request):
        """
        Direct web endpoint handler for getting entities from an ontology.
        
        Args:
            request: aiohttp request object
            
        Returns:
            aiohttp response with entities
        """
        try:
            ontology_source = request.match_info['ontology_source']
            entity_type = request.query.get('type', 'all')
            
            # Find the query module if available
            if 'query' in self.modules:
                query_module = self.modules['query']
                
                # Call the get_entities tool through the module
                result = await query_module.handle_tool_call('get_entities', {
                    'ontology_source': ontology_source,
                    'entity_type': entity_type
                })
                
                # Extract entities from result
                content_list = result.get('content', [])
                if content_list and isinstance(content_list[0], dict):
                    content_text = content_list[0].get('text', '{}')
                    try:
                        entities_data = json.loads(content_text)
                        return web.json_response(entities_data)
                    except json.JSONDecodeError:
                        return web.json_response({"error": "Invalid JSON in response"}, status=500)
                
                return web.json_response({"error": "Invalid response format"}, status=500)
            else:
                # Try legacy method if query module not available
                g = self._load_graph_from_file(ontology_source)
                
                # Manual entity extraction
                # This is simplified and would need to be expanded for actual use
                entities = []
                
                return web.json_response({"entities": entities})
                
        except Exception as e:
            logger.error(f"Error handling get_entities request: {str(e)}")
            traceback.print_exc()
            return web.json_response({"error": str(e)}, status=500)
    
    async def handle_get_guidelines(self, request):
        """
        Direct web endpoint handler for getting guidelines from a world.
        
        Args:
            request: aiohttp request object
            
        Returns:
            aiohttp response with guidelines
        """
        try:
            world_name = request.match_info['world_name']
            
            # Find the query module if available
            if 'query' in self.modules:
                query_module = self.modules['query']
                
                # Call the get_guidelines tool through the module
                result = await query_module.handle_tool_call('get_guidelines', {
                    'ontology_source': world_name
                })
                
                # Extract guidelines from result
                content_list = result.get('content', [])
                if content_list and isinstance(content_list[0], dict):
                    content_text = content_list[0].get('text', '{}')
                    try:
                        guidelines_data = json.loads(content_text)
                        return web.json_response(guidelines_data)
                    except json.JSONDecodeError:
                        return web.json_response({"error": "Invalid JSON in response"}, status=500)
                
                return web.json_response({"error": "Invalid response format"}, status=500)
            else:
                # Fallback to simple response
                return web.json_response({
                    "guidelines": [],
                    "message": "Query module not available"
                })
                
        except Exception as e:
            logger.error(f"Error handling get_guidelines request: {str(e)}")
            traceback.print_exc()
            return web.json_response({"error": str(e)}, status=500)
