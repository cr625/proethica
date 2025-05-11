"""
MSEO Model Context Protocol Server.

This module implements an MCP server for the Materials Science Engineering Ontology.
"""

import os
import sys
import logging
import json
import time
from typing import Dict, List, Any, Optional, Union
import traceback
import requests
import tempfile

# Import RDFlib for ontology processing
try:
    import rdflib
    from rdflib import Graph, URIRef, Literal, BNode
    from rdflib.namespace import RDF, RDFS, OWL, SKOS
except ImportError:
    logging.error("RDFlib is required. Install it with: pip install rdflib")
    sys.exit(1)

# Import Flask for the HTTP server
try:
    from flask import Flask, request, jsonify
except ImportError:
    logging.error("Flask is required. Install it with: pip install flask")
    sys.exit(1)

# Import MCP server base
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp.http_ontology_mcp_server import HTTPOntologyMCPServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MSEOMCPServer(HTTPOntologyMCPServer):
    """MCP Server for the Materials Science Engineering Ontology."""
    
    def __init__(self, name="mseo-mcp-server", ontology_file=None, data_dir=None):
        """Initialize the MSEO MCP server.
        
        Args:
            name: Name of the MCP server
            ontology_file: Path to the ontology file (.ttl, .owl, etc.)
            data_dir: Directory to store downloaded ontology files
        """
        super().__init__(name=name)
        
        # Set data directory
        self.data_dir = data_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Set ontology file path
        self.ontology_file = ontology_file
        
        # Initialize graph
        self.graph = None
        
        # Material, category, and property caches
        self.materials = {}
        self.categories = {}
        self.properties = {}
        
        # Define common namespaces
        self.ns = {
            "rdf": RDF,
            "rdfs": RDFS,
            "owl": OWL,
            "skos": SKOS,
            "mseo": rdflib.Namespace("https://matportal.org/ontologies/MSEO#"),
        }
        
        # Track load time
        self.load_time = None
    
    def load_ontology(self):
        """Load the MSEO ontology.
        
        Returns:
            True if successful, False otherwise
        """
        # Initialize graph
        self.graph = Graph()
        
        # Register namespaces
        for prefix, ns in self.ns.items():
            self.graph.bind(prefix, ns)
        
        # Check if ontology file is provided
        if self.ontology_file and os.path.exists(self.ontology_file):
            # Load from provided file
            try:
                logger.info(f"Loading ontology from file: {self.ontology_file}")
                start_time = time.time()
                self.graph.parse(self.ontology_file, format="ttl")
                self.load_time = time.time() - start_time
                logger.info(f"Loaded ontology in {self.load_time:.2f} seconds")
                return True
            except Exception as e:
                logger.error(f"Error loading ontology from file: {e}")
                logger.error(traceback.format_exc())
                return False
        else:
            # Download and load from MatPortal
            return self.download_and_load_ontology()
    
    def download_and_load_ontology(self):
        """Download and load the MSEO ontology from MatPortal.
        
        Returns:
            True if successful, False otherwise
        """
        # MSEO ontology URL
        mseo_url = "https://matportal.org/ontologies/MSEO.ttl"
        
        # Path to save downloaded ontology
        download_path = os.path.join(self.data_dir, "MSEO.ttl")
        
        try:
            # Check if we already have the file
            if os.path.exists(download_path):
                logger.info(f"Using existing ontology file: {download_path}")
            else:
                # Download ontology
                logger.info(f"Downloading ontology from {mseo_url}")
                response = requests.get(mseo_url)
                
                if response.status_code != 200:
                    logger.error(f"Failed to download ontology: HTTP {response.status_code}")
                    return False
                
                # Save to file
                with open(download_path, "wb") as f:
                    f.write(response.content)
                
                logger.info(f"Downloaded ontology to {download_path}")
            
            # Load ontology
            logger.info(f"Loading ontology from {download_path}")
            start_time = time.time()
            self.graph.parse(download_path, format="ttl")
            self.load_time = time.time() - start_time
            logger.info(f"Loaded ontology in {self.load_time:.2f} seconds")
            
            # Build caches
            self.build_caches()
            
            return True
            
        except Exception as e:
            logger.error(f"Error downloading or loading ontology: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def build_caches(self):
        """Build caches of materials, categories, and properties."""
        logger.info("Building caches...")
        start_time = time.time()
        
        # Find all materials
        self.materials = {}
        material_class = self.ns["mseo"]["Material"]
        
        for material in self.graph.subjects(RDF.type, material_class):
            if isinstance(material, URIRef):
                name = self.get_label(material)
                if name:
                    self.materials[str(material)] = {
                        "uri": str(material),
                        "name": name,
                        "label": name,
                        "description": self.get_description(material)
                    }
        
        # Find all categories
        self.categories = {}
        category_class = self.ns["mseo"]["MaterialCategory"]
        
        for category in self.graph.subjects(RDF.type, category_class):
            if isinstance(category, URIRef):
                name = self.get_label(category)
                if name:
                    self.categories[str(category)] = {
                        "uri": str(category),
                        "name": name,
                        "label": name,
                        "description": self.get_description(category)
                    }
        
        # Find all properties
        self.properties = {}
        property_class = self.ns["owl"]["DatatypeProperty"]
        
        for prop in self.graph.subjects(RDF.type, property_class):
            if isinstance(prop, URIRef):
                name = self.get_label(prop)
                if name:
                    self.properties[str(prop)] = {
                        "uri": str(prop),
                        "name": name,
                        "label": name,
                        "description": self.get_description(prop)
                    }
        
        logger.info(f"Built caches in {time.time() - start_time:.2f} seconds")
        logger.info(f"Found {len(self.materials)} materials, {len(self.categories)} categories, and {len(self.properties)} properties")
    
    def get_label(self, uri):
        """Get the label for a URI.
        
        Args:
            uri: URI to get label for
            
        Returns:
            Label string or None
        """
        # Try rdfs:label
        for label in self.graph.objects(uri, RDFS.label):
            return str(label)
        
        # Try skos:prefLabel
        for label in self.graph.objects(uri, SKOS.prefLabel):
            return str(label)
        
        # Use the URI fragment as fallback
        return str(uri).split("#")[-1]
    
    def get_description(self, uri):
        """Get the description for a URI.
        
        Args:
            uri: URI to get description for
            
        Returns:
            Description string or empty string
        """
        # Try rdfs:comment
        for comment in self.graph.objects(uri, RDFS.comment):
            return str(comment)
        
        # Try skos:definition
        for definition in self.graph.objects(uri, SKOS.definition):
            return str(definition)
        
        return ""
    
    def get_material_properties(self, material_uri):
        """Get properties for a material.
        
        Args:
            material_uri: URI of the material
            
        Returns:
            List of property objects
        """
        results = []
        material = URIRef(material_uri)
        
        # Get all predicates and objects for the material
        for predicate, obj in self.graph.predicate_objects(material):
            # Skip RDF, RDFS, and OWL properties
            if predicate.startswith(str(RDF)) or predicate.startswith(str(RDFS)) or predicate.startswith(str(OWL)):
                continue
            
            # Get predicate label
            predicate_label = self.get_label(predicate)
            
            # Format the value
            if isinstance(obj, Literal):
                value = str(obj)
            elif isinstance(obj, URIRef):
                value = self.get_label(obj)
            else:
                value = str(obj)
            
            results.append({
                "name": predicate_label,
                "uri": str(predicate),
                "value": value
            })
        
        return results
    
    def search_ontology(self, query, type_filter=None, limit=20):
        """Search the ontology for entities matching a query.
        
        Args:
            query: Search query
            type_filter: Type to filter by (material, category, property)
            limit: Maximum number of results
            
        Returns:
            Dict with search results
        """
        query = query.lower()
        results = {
            "materials": [],
            "categories": [],
            "properties": []
        }
        
        # Search materials
        if not type_filter or type_filter == "material":
            for uri, material in self.materials.items():
                if query in material["name"].lower() or query in material.get("description", "").lower():
                    results["materials"].append(material)
                    
                    if len(results["materials"]) >= limit and type_filter == "material":
                        break
        
        # Search categories
        if not type_filter or type_filter == "category":
            for uri, category in self.categories.items():
                if query in category["name"].lower() or query in category.get("description", "").lower():
                    results["categories"].append(category)
                    
                    if len(results["categories"]) >= limit and type_filter == "category":
                        break
        
        # Search properties
        if not type_filter or type_filter == "property":
            for uri, prop in self.properties.items():
                if query in prop["name"].lower() or query in prop.get("description", "").lower():
                    results["properties"].append(prop)
                    
                    if len(results["properties"]) >= limit and type_filter == "property":
                        break
        
        return results
    
    def register_tools(self):
        """Register tools for the MCP server."""
        # Base tools from parent class
        super().register_tools()
        
        # MSEO-specific tools
        self.register_tool(
            name="get_materials",
            description="Get a list of materials from the ontology",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of materials to return",
                        "default": 100
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset for pagination",
                        "default": 0
                    }
                },
                "additionalProperties": False
            },
            function=self.get_materials_tool
        )
        
        self.register_tool(
            name="get_material",
            description="Get details about a specific material",
            input_schema={
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": "URI of the material"
                    }
                },
                "required": ["uri"],
                "additionalProperties": False
            },
            function=self.get_material_tool
        )
        
        self.register_tool(
            name="get_categories",
            description="Get a list of material categories",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of categories to return",
                        "default": 100
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset for pagination",
                        "default": 0
                    }
                },
                "additionalProperties": False
            },
            function=self.get_categories_tool
        )
        
        self.register_tool(
            name="get_category",
            description="Get details about a specific category",
            input_schema={
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": "URI of the category"
                    }
                },
                "required": ["uri"],
                "additionalProperties": False
            },
            function=self.get_category_tool
        )
        
        self.register_tool(
            name="get_material_properties",
            description="Get properties of a specific material",
            input_schema={
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": "URI of the material"
                    }
                },
                "required": ["uri"],
                "additionalProperties": False
            },
            function=self.get_material_properties_tool
        )
        
        self.register_tool(
            name="compare_materials",
            description="Compare two materials by their properties",
            input_schema={
                "type": "object",
                "properties": {
                    "uri1": {
                        "type": "string",
                        "description": "URI of the first material"
                    },
                    "uri2": {
                        "type": "string",
                        "description": "URI of the second material"
                    }
                },
                "required": ["uri1", "uri2"],
                "additionalProperties": False
            },
            function=self.compare_materials_tool
        )
        
        self.register_tool(
            name="search_ontology",
            description="Search the ontology for materials, categories, or properties",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "type": {
                        "type": "string",
                        "description": "Type to filter by (material, category, property)",
                        "enum": ["material", "category", "property"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results per type",
                        "default": 20
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            },
            function=self.search_ontology_tool
        )
        
        self.register_tool(
            name="chat_completion",
            description="Generate a chat response with ontology context",
            input_schema={
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "array",
                        "description": "Array of message objects",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {
                                    "type": "string",
                                    "enum": ["system", "user", "assistant"]
                                },
                                "content": {
                                    "type": "string"
                                }
                            },
                            "required": ["role", "content"]
                        }
                    },
                    "include_ontology_context": {
                        "type": "boolean",
                        "description": "Whether to include ontology context in the prompt",
                        "default": True
                    }
                },
                "required": ["messages"],
                "additionalProperties": False
            },
            function=self.chat_completion_tool
        )
    
    def get_materials_tool(self, arguments):
        """Tool to get a list of materials.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Dict with materials list
        """
        limit = arguments.get("limit", 100)
        offset = arguments.get("offset", 0)
        
        materials = list(self.materials.values())[offset:offset+limit]
        
        return {
            "count": len(materials),
            "materials": materials
        }
    
    def get_material_tool(self, arguments):
        """Tool to get details about a specific material.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Material details
        """
        uri = arguments.get("uri")
        
        if not uri:
            return {"error": "URI is required"}
        
        material = self.materials.get(uri)
        
        if not material:
            return {"error": f"Material not found: {uri}"}
        
        # Get properties
        properties = self.get_material_properties(uri)
        
        # Add properties to material
        material["properties"] = properties
        
        return material
    
    def get_categories_tool(self, arguments):
        """Tool to get a list of categories.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Dict with categories list
        """
        limit = arguments.get("limit", 100)
        offset = arguments.get("offset", 0)
        
        categories = list(self.categories.values())[offset:offset+limit]
        
        return {
            "count": len(categories),
            "categories": categories
        }
    
    def get_category_tool(self, arguments):
        """Tool to get details about a specific category.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Category details
        """
        uri = arguments.get("uri")
        
        if not uri:
            return {"error": "URI is required"}
        
        category = self.categories.get(uri)
        
        if not category:
            return {"error": f"Category not found: {uri}"}
        
        return category
    
    def get_material_properties_tool(self, arguments):
        """Tool to get properties of a specific material.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Dict with properties list
        """
        uri = arguments.get("uri")
        
        if not uri:
            return {"error": "URI is required"}
        
        material = self.materials.get(uri)
        
        if not material:
            return {"error": f"Material not found: {uri}"}
        
        properties = self.get_material_properties(uri)
        
        return {
            "uri": uri,
            "material": material["name"],
            "count": len(properties),
            "properties": properties
        }
    
    def compare_materials_tool(self, arguments):
        """Tool to compare two materials by their properties.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Dict with comparison results
        """
        uri1 = arguments.get("uri1")
        uri2 = arguments.get("uri2")
        
        if not uri1 or not uri2:
            return {"error": "Both URIs are required"}
        
        material1 = self.materials.get(uri1)
        material2 = self.materials.get(uri2)
        
        if not material1:
            return {"error": f"Material not found: {uri1}"}
        
        if not material2:
            return {"error": f"Material not found: {uri2}"}
        
        # Get properties for both materials
        properties1 = self.get_material_properties(uri1)
        properties2 = self.get_material_properties(uri2)
        
        # Convert to dicts for easier comparison
        props1 = {p["name"]: p["value"] for p in properties1}
        props2 = {p["name"]: p["value"] for p in properties2}
        
        # Get all property names
        all_props = set(props1.keys()) | set(props2.keys())
        
        # Build comparison
        comparison = []
        
        for prop in sorted(all_props):
            comparison.append({
                "property": prop,
                "material1": props1.get(prop, "N/A"),
                "material2": props2.get(prop, "N/A"),
                "match": props1.get(prop) == props2.get(prop) and prop in props1 and prop in props2
            })
        
        return {
            "material1": material1,
            "material2": material2,
            "properties": comparison,
            "common_count": sum(1 for p in comparison if p["match"]),
            "different_count": sum(1 for p in comparison if not p["match"]),
            "total_count": len(comparison)
        }
    
    def search_ontology_tool(self, arguments):
        """Tool to search the ontology.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Dict with search results
        """
        query = arguments.get("query", "")
        type_filter = arguments.get("type")
        limit = arguments.get("limit", 20)
        
        if not query:
            return {"error": "Query is required"}
        
        results = self.search_ontology(query, type_filter, limit)
        
        return results
    
    def chat_completion_tool(self, arguments):
        """Tool to generate a chat response with ontology context.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Dict with response content
        """
        messages = arguments.get("messages", [])
        include_ontology_context = arguments.get("include_ontology_context", True)
        
        if not messages:
            return {"error": "Messages are required"}
        
        # Get the user's message
        user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        
        if not user_message:
            return {"error": "No user message found"}
        
        # Check if we need to add ontology context
        if include_ontology_context:
            # Search the ontology for relevant entities
            search_results = self.search_ontology(user_message)
            
            # Construct context from search results
            context = self.build_context_from_search(search_results, user_message)
            
            # Add context to messages
            if context:
                system_message = {
                    "role": "system",
                    "content": (
                        f"You are a materials science assistant with knowledge of various materials and their properties. "
                        f"When responding to the user, use the following context from the Materials Science Engineering Ontology:\n\n{context}\n\n"
                        f"Make sure to incorporate this information in your response when relevant, but do not mention explicitly that you are using this context."
                    )
                }
                
                # Add system message at the beginning
                has_system = any(m["role"] == "system" for m in messages)
                
                if has_system:
                    messages = [system_message] + [m for m in messages if m["role"] != "system"]
                else:
                    messages = [system_message] + messages
        
        try:
            # Use Anthropic API if available
            import anthropic
            
            # Initialize client
            client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY")
            )
            
            # Format messages for Claude
            message = client.messages.create(
                model=os.environ.get("ANTHROPIC_MODEL", "claude-3-opus-20240229"),
                max_tokens=2000,
                messages=messages
            )
            
            return {
                "content": message.content[0].text
            }
            
        except (ImportError, Exception) as e:
            logger.warning(f"Anthropic API error: {e}")
            
            # Fallback to basic response
            return {
                "content": "I don't have enough information to provide a detailed response about this material science topic. Please provide more specific questions about materials, their properties, or categories."
            }
    
    def build_context_from_search(self, search_results, query):
        """Build context from search results.
        
        Args:
            search_results: Search results from search_ontology
            query: The original user query
            
        Returns:
            Context string
        """
        context_parts = []
        
        # Add materials
        if search_results.get("materials"):
            context_parts.append("MATERIALS:")
            
            for material in search_results["materials"][:5]:
                # Get properties
                properties = self.get_material_properties(material["uri"])
                props_text = "; ".join(f"{p['name']}: {p['value']}" for p in properties[:10])
                
                material_text = (
                    f"- {material['name']}: {material.get('description', 'No description available')}.\n"
                    f"  Properties: {props_text}"
                )
                
                context_parts.append(material_text)
        
        # Add categories
        if search_results.get("categories"):
            context_parts.append("\nCATEGORIES:")
            
            for category in search_results["categories"][:5]:
                category_text = f"- {category['name']}: {category.get('description', 'No description available')}"
                context_parts.append(category_text)
        
        # Add properties
        if search_results.get("properties"):
            context_parts.append("\nPROPERTIES:")
            
            for prop in search_results["properties"][:5]:
                prop_text = f"- {prop['name']}: {prop.get('description', 'No description available')}"
                context_parts.append(prop_text)
        
        # Join all parts
        context = "\n".join(context_parts)
        
        if context:
            return context
        else:
            return "No relevant information found in the Materials Science Engineering Ontology for this query."
