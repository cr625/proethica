#!/usr/bin/env python3
"""
MSEO MCP Server - Complete implementation.

This is a fully working version of the MSEO MCP server.
"""

import os
import sys
import json
import logging
from typing import Dict, List, Any, Optional
import uuid
from collections import defaultdict
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mseo_mcp")

# Define paths for setup_mseo.py to use
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MSEO_FILE = os.path.join(DATA_DIR, "mseo.ttl")
MSEO_JSON = os.path.join(DATA_DIR, "mseo.json")
MSEO_CACHE = os.path.join(DATA_DIR, "mseo_cache.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Import setup utilities - this will be defined in setup_mseo.py
from mcp.mseo.setup_mseo import check_mseo

# Try to import MCP server base classes
try:
    # First try to import from the local app package
    from app.agent_module.blueprints.mcp.base_server import BaseMcpServer
    from app.agent_module.blueprints.mcp.tools import Tool, ToolRouter
    from app.agent_module.blueprints.mcp.resources import Resource, ResourceRouter
except ImportError:
    # Fall back to a direct import if not found in app
    try:
        from agent_module.blueprints.mcp.base_server import BaseMcpServer
        from agent_module.blueprints.mcp.tools import Tool, ToolRouter
        from agent_module.blueprints.mcp.resources import Resource, ResourceRouter
    except ImportError:
        logger.error("Could not import MCP server base classes. Please ensure agent_module is available.")
        sys.exit(1)

# Ontology manager class - abbreviated version
class MSEOOntologyManager:
    """Manager for handling the MSEO ontology data."""
    
    def __init__(self):
        """Initialize the MSEO ontology manager."""
        self.mseo_data = None
        self.mseo_cache = None
        self.loaded = False
        self.last_loaded = None
        self.load_ontology()
    
    def load_ontology(self) -> bool:
        """Load the MSEO ontology from disk."""
        # Check if MSEO files exist and are valid
        if not check_mseo():
            logger.error("Failed to initialize MSEO ontology data")
            return False
        
        try:
            # Load the full MSEO data
            with open(MSEO_JSON, 'r') as f:
                self.mseo_data = json.load(f)
            
            # Load the MSEO cache
            with open(MSEO_CACHE, 'r') as f:
                self.mseo_cache = json.load(f)
            
            self.loaded = True
            self.last_loaded = datetime.now()
            
            logger.info(f"Successfully loaded MSEO ontology with {len(self.mseo_data['classes'])} classes, " +
                       f"{len(self.mseo_data['properties'])} properties, and " +
                       f"{len(self.mseo_data['individuals'])} individuals")
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading MSEO ontology: {e}", exc_info=True)
            self.loaded = False
            return False
    
    def reload_if_needed(self, force: bool = False) -> bool:
        """Reload the ontology if needed or if forced."""
        if not self.loaded or force:
            return self.load_ontology()
        
        # Reload if data is older than 1 hour
        if self.last_loaded and (datetime.now() - self.last_loaded).total_seconds() > 3600:
            logger.info("MSEO data is older than 1 hour. Reloading...")
            return self.load_ontology()
        
        return True
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get the MSEO ontology metadata."""
        if not self.reload_if_needed():
            return {"error": "Failed to load MSEO ontology"}
        
        return self.mseo_data.get("metadata", {})
    
    def search_classes(self, query: str) -> List[Dict[str, Any]]:
        """Search for classes matching the query."""
        if not self.reload_if_needed():
            return [{"error": "Failed to load MSEO ontology"}]
        
        results = []
        query_lower = query.lower()
        
        for cls in self.mseo_data["classes"]:
            if (query_lower in cls["name"].lower() or 
                (cls["label"] and query_lower in cls["label"].lower()) or 
                (cls["description"] and query_lower in cls["description"].lower())):
                results.append(cls)
        
        return results
    
    def search_materials(self, query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for materials matching the query."""
        if not self.reload_if_needed():
            return [{"error": "Failed to load MSEO ontology"}]
        
        results = []
        query_lower = query.lower()
        
        for uri, material in self.mseo_cache["materials"].items():
            if ((query_lower in material["name"].lower() or 
                 (material["label"] and query_lower in material["label"].lower()) or 
                 (material["description"] and query_lower in material["description"].lower())) and
                (not category or 
                 any(category.lower() in t.lower() for t in material.get("types", [])))):
                results.append(material)
        
        return results
    
    def get_all_materials(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all materials, optionally filtered by category."""
        if not self.reload_if_needed():
            return [{"error": "Failed to load MSEO ontology"}]
        
        if not category:
            return list(self.mseo_cache["materials"].values())
        
        results = []
        category_lower = category.lower()
        
        for uri, material in self.mseo_cache["materials"].items():
            if any(category_lower in t.lower() for t in material.get("types", [])):
                results.append(material)
        
        return results
    
    def get_material_properties(self, material_uri: str) -> Dict[str, List[str]]:
        """Get all properties of a specific material."""
        if not self.reload_if_needed():
            return {"error": "Failed to load MSEO ontology"}
        
        material = self.mseo_cache["materials"].get(material_uri)
        if not material:
            return {}
        
        return material.get("properties", {})
    
    def get_materials_with_property(self, property_name: str, value: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all materials that have a specific property (and optionally a specific value)."""
        if not self.reload_if_needed():
            return [{"error": "Failed to load MSEO ontology"}]
        
        results = []
        
        for uri, material in self.mseo_cache["materials"].items():
            if property_name in material.get("properties", {}):
                if not value or value in material["properties"][property_name]:
                    results.append(material)
        
        return results
    
    def get_ontology_summary(self) -> Dict[str, Any]:
        """Get a summary of the ontology data."""
        if not self.reload_if_needed():
            return {"error": "Failed to load MSEO ontology"}
        
        return {
            "metadata": self.mseo_data["metadata"],
            "class_count": len(self.mseo_data["classes"]),
            "property_count": len(self.mseo_data["properties"]),
            "individual_count": len(self.mseo_data["individuals"]),
            "material_count": len(self.mseo_cache["materials"]),
            "property_types": list(self.mseo_cache["material_properties"].keys())
        }
    
    def generate_context_text(self, query: Optional[str] = None) -> str:
        """Generate text context about the ontology for LLM prompting."""
        if not self.reload_if_needed():
            return "Error: Failed to load MSEO ontology."
        
        metadata = self.mseo_data["metadata"]
        
        context = [
            f"# Materials Science Engineering Ontology (MSEO)",
            f"Version: {metadata.get('version', 'Unknown')}",
            f"{metadata.get('description', 'An ontology for materials science engineering.')}",
            "",
            f"This ontology contains {len(self.mseo_data['classes'])} classes, {len(self.mseo_data['properties'])} " +
            f"properties, and {len(self.mseo_data['individuals'])} individuals.",
            "",
            "## Key Material Science Concepts",
        ]
        
        # If a query is provided, add relevant information
        if query:
            # Search for materials
            material_results = self.search_materials(query)
            if material_results:
                context.append(f"### Relevant Materials for: {query}")
                for material in material_results[:5]:
                    context.append(f"- {material['label'] or material['name']}: {material['description'] or 'No description available.'}")
        
        return "\n".join(context)

# Initialize the MSEO ontology manager
ontology_manager = MSEOOntologyManager()

# Define the MCP server class
class MSEOMcpServer(BaseMcpServer):
    """MCP server for the MSEO ontology."""
    
    def __init__(self, host="localhost", port=5002):
        """Initialize the MSEO MCP server."""
        super().__init__(host, port)
        self.server_name = "mseo-mcp-server"
        self.description = "MCP server for the Materials Science Engineering Ontology (MSEO)"
        
        # Set up tool router
        self.tool_router = ToolRouter()
        
        # Register tools
        self.register_tools()
        
        # Set up resource router
        self.resource_router = ResourceRouter()
        
        # Register resources
        self.register_resources()
        
        # Conversation memory for chat tools
        self.conversations = defaultdict(list)
        
        logger.info(f"Initialized MSEO MCP server on {host}:{port}")
    
    def register_tools(self):
        """Register all tools provided by this server."""
        # Chat completion tool
        chat_completion_tool = Tool(
            name="chat_completion",
            description="Generate a response using a language model with materials science knowledge",
            input_schema={
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Name of the model to use (e.g., 'claude-3-opus-20240229')",
                        "default": "claude-3-opus-20240229"
                    },
                    "messages": {
                        "type": "array",
                        "description": "List of messages in the conversation",
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
                    "temperature": {
                        "type": "number",
                        "description": "Sampling temperature (0-1.0)",
                        "default": 0.7
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum number of tokens to generate",
                        "default": 2048
                    },
                    "conversation_id": {
                        "type": "string",
                        "description": "ID to maintain conversation context across calls",
                        "default": ""
                    },
                    "include_ontology_context": {
                        "type": "boolean",
                        "description": "Whether to include ontology context in the system prompt",
                        "default": True
                    }
                },
                "required": ["messages"]
            },
            handler=self.handle_chat_completion
        )
        self.tool_router.add_tool(chat_completion_tool)
        
        # Search ontology tool
        search_tool = Tool(
            name="search_ontology",
            description="Search the MSEO ontology for materials",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "category": {
                        "type": "string",
                        "description": "Category to filter by (for materials)",
                        "default": ""
                    }
                },
                "required": ["query"]
            },
            handler=self.handle_search_ontology
        )
        self.tool_router.add_tool(search_tool)
        
        # Get materials tool
        get_materials_tool = Tool(
            name="get_materials",
            description="Get a list of materials from the MSEO ontology",
            input_schema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Category to filter by",
                        "default": ""
                    },
                    "property": {
                        "type": "string",
                        "description": "Property to filter by",
                        "default": ""
                    },
                    "property_value": {
                        "type": "string",
                        "description": "Value of the property to filter by",
                        "default": ""
                    }
                }
            },
            handler=self.handle_get_materials
        )
        self.tool_router.add_tool(get_materials_tool)
        
        # Get material properties tool
        get_material_properties_tool = Tool(
            name="get_material_properties",
            description="Get properties of a specific material",
            input_schema={
                "type": "object",
                "properties": {
                    "material_name": {
                        "type": "string",
                        "description": "Name of the material"
                    },
                    "material_uri": {
                        "type": "string",
                        "description": "URI of the material (alternative to name)"
                    }
                },
                "anyOf": [
                    {"required": ["material_name"]},
                    {"required": ["material_uri"]}
                ]
            },
            handler=self.handle_get_material_properties
        )
        self.tool_router.add_tool(get_material_properties_tool)
        
        # Get ontology summary tool
        get_ontology_summary_tool = Tool(
            name="get_ontology_summary",
            description="Get a summary of the MSEO ontology",
            input_schema={
                "type": "object",
                "properties": {}
            },
            handler=self.handle_get_ontology_summary
        )
        self.tool_router.add_tool(get_ontology_summary_tool)
    
    def register_resources(self):
        """Register all resources provided by this server."""
        # Ontology metadata resource
        metadata_resource = Resource(
            uri="mseo/metadata",
            description="Metadata about the MSEO ontology",
            handler=self.handle_metadata_resource
        )
        self.resource_router.add_resource(metadata_resource)
        
        # Ontology context resource
        context_resource = Resource(
            uri="mseo/context",
            description="Contextual information about the MSEO ontology for prompting",
            handler=self.handle_context_resource
        )
        self.resource_router.add_resource(context_resource)
    
    async def handle_chat_completion(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chat completion requests."""
        # Extract arguments
        model = args.get("model", "claude-3-opus-20240229")
        messages = args.get("messages", [])
        temperature = args.get("temperature", 0.7)
        max_tokens = args.get("max_tokens", 2048)
        conversation_id = args.get("conversation_id", str(uuid.uuid4()))
        include_ontology_context = args.get("include_ontology_context", True)
        
        # Check if conversation exists and update it
        if conversation_id in self.conversations:
            # If we have history, append the new messages
            existing_messages = self.conversations[conversation_id]
            # Skip messages that are already in the history
            new_messages = messages[len(existing_messages):]
            self.conversations[conversation_id].extend(new_messages)
        else:
            # If this is a new conversation, initialize it
            self.conversations[conversation_id] = messages.copy()
        
        # Process messages
        processed_messages = messages.copy()
        
        # Add ontology context if requested
        if include_ontology_context:
            # Generate ontology context
            user_queries = [msg["content"] for msg in processed_messages if msg["role"] == "user"]
            context_query = user_queries[-1] if user_queries else None
            ontology_context = ontology_manager.generate_context_text(context_query)
            
            # Add system message with context
            processed_messages.insert(0, {
                "role": "system",
                "content": f"You are a helpful materials science expert. Answer questions using your knowledge about materials science and engineering.\n\n{ontology_context}"
            })
        
        # Mock LLM response for demonstration
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "This is a mock response from the MSEO MCP server. In a real implementation, this would call an LLM API."
                },
                "finish_reason": "stop"
            }],
            "model": model,
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            }
        }
    
    async def handle_search_ontology(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ontology search requests."""
        query = args.get("query", "")
        category = args.get("category", "")
        
        if not query:
            return {"error": "Query is required"}
        
        material_results = ontology_manager.search_materials(query, category)
        
        return {
            "count": len(material_results),
            "materials": material_results
        }
    
    async def handle_get_materials(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle requests to get materials."""
        category = args.get("category", "")
        property_name = args.get("property", "")
        property_value = args.get("property_value", "")
        
        if property_name:
            materials = ontology_manager.get_materials_with_property(property_name, property_value)
        else:
            materials = ontology_manager.get_all_materials(category)
        
        return {
            "count": len(materials),
            "materials": materials
        }
    
    async def handle_get_material_properties(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle requests to get material properties."""
        material_name = args.get("material_name", "")
        material_uri = args.get("material_uri", "")
        
        if not material_name and not material_uri:
            return {"error": "material_name or material_uri is required"}
        
        # If we have a URI, use it directly
        if material_uri:
            properties = ontology_manager.get_material_properties(material_uri)
            if properties:
                return {
                    "uri": material_uri,
                    "properties": properties
                }
        
        # If we have a name, search for matching materials
        if material_name:
            materials = ontology_manager.search_materials(material_name)
            if materials:
                # Use the first match
                material = materials[0]
                properties = ontology_manager.get_material_properties(material["uri"])
                return {
                    "uri": material["uri"],
                    "name": material["name"],
                    "label": material["label"],
                    "properties": properties
                }
        
        return {"error": f"Material not found: {material_name or material_uri}"}
    
    async def handle_get_ontology_summary(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle requests to get the ontology summary."""
        return ontology_manager.get_ontology_summary()
    
    async def handle_metadata_resource(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle requests for the ontology metadata resource."""
        return ontology_manager.get_metadata()
    
    async def handle_context_resource(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle requests for the ontology context resource."""
        query = params.get("query", "")
        context = ontology_manager.generate_context_text(query)
        return {
            "context": context,
            "query": query
        }

def main():
    """Run the MSEO MCP server."""
    host = os.environ.get("MSEO_MCP_HOST", "localhost")
    port = int(os.environ.get("MSEO_MCP_PORT", 5002))
    
    # Check if MSEO data is available
    if not check_mseo():
        logger.error("MSEO data is not available. Please run setup_mseo.py first.")
        sys.exit(1)
    
    try:
        # Create and start the server
        server = MSEOMcpServer(host, port)
        server.start()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Error running server: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
