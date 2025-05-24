# Model Context Protocol (MCP) Server Guide

This comprehensive guide provides instructions and best practices for creating and using MCP servers in AI applications, with a particular focus on ontology and knowledge integration.

## Table of Contents

- [Model Context Protocol (MCP) Server Guide](#model-context-protocol-mcp-server-guide)
  - [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [MCP Architecture Overview](#mcp-architecture-overview)
  - [Creating an MCP Server](#creating-an-mcp-server)
    - [Installation \& Setup](#installation--setup)
  - [Server Types and Communication Methods](#server-types-and-communication-methods)
    - [1. Standard MCP Server (stdio)](#1-standard-mcp-server-stdio)
    - [2. HTTP MCP Server](#2-http-mcp-server)
  - [Exposing Tools and Resources](#exposing-tools-and-resources)
    - [1. Tools](#1-tools)
    - [2. Resources](#2-resources)
  - [Ontology Integration](#ontology-integration)
    - [Example: Ontology-based MCP Server](#example-ontology-based-mcp-server)
    - [Key Ontology Integration Features](#key-ontology-integration-features)
  - [Best Practices](#best-practices)
    - [Server Implementation](#server-implementation)
    - [Ontology Integration](#ontology-integration-1)
  - [Troubleshooting](#troubleshooting)
    - [Connection Issues](#connection-issues)
    - [Tool Execution Failures](#tool-execution-failures)
    - [Ontology Access Problems](#ontology-access-problems)
  - [Example Implementations](#example-implementations)
    - [Basic Echo Server](#basic-echo-server)
    - [Ontology Query Server](#ontology-query-server)
  - [Conclusion](#conclusion)

## Introduction

Model Context Protocol (MCP) is an open protocol that enables seamless integration between LLM applications and external data sources and tools. It allows models like Claude to access custom tools, resources, and domain-specific knowledge through a standardized communication interface.

Key benefits of MCP include:
- **Extended capabilities**: Give models access to data and functions beyond their training data
- **Up-to-date information**: Provide models with current information without retraining
- **Domain expertise**: Integrate specialized knowledge from ontologies and knowledge graphs
- **Reduced hallucination**: Ground model responses in accurate data sources
- **Controlled API access**: Enable secure, mediated access to external systems

## MCP Architecture Overview

The MCP architecture consists of three main components:

1. **Client**: The application interfacing with the LLM (e.g., a web app using Claude)
2. **MCP Server**: A middleware service that exposes tools and resources
3. **LLM**: The language model consuming the exposed capabilities (e.g., Claude)

```
+-------------+         +-----------------+         +--------------+
|   Client    |-------->|   MCP Server    |-------->|     LLM      |
| Application |<--------|  (Tools/Data)   |<--------|   (Claude)   |
+-------------+         +-----------------+         +--------------+
```

## Creating an MCP Server

### Installation & Setup

1. **Install the Python SDK**:
   ```bash
   pip install mcp
   ```

2. **Basic Server Structure**:
   ```python
   from mcp.server import FastMCP

   # Create server instance
   mcp = FastMCP("My MCP Server")
   
   # Define tools and resources
   
   # Run the server
   if __name__ == "__main__":
       mcp.run()
   ```

## Server Types and Communication Methods

MCP servers can be implemented using different communication methods:

### 1. Standard MCP Server (stdio)

Uses standard input/output for communication. Ideal for direct integration with Claude or other LLMs.

```python
from mcp.server import FastMCP

mcp = FastMCP("My Server")
# Define tools and resources
mcp.run()  # Uses stdin/stdout by default
```

### 2. HTTP MCP Server

Exposes MCP capabilities through HTTP endpoints. Better for distributed systems or web-based integrations.

```python
from mcp.server.fastmcp import FastMCP
import asyncio

async def run_server():
    mcp = FastMCP("My HTTP Server")
    # Define tools and resources
    
    # Start HTTP server on specific port
    await mcp.run_http(host="localhost", port=5001)
    
    # Keep server running
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(run_server())
```

## Exposing Tools and Resources

MCP servers can expose two types of capabilities:

### 1. Tools

Functions that perform specific tasks when called by a model.

```python
from mcp.server import FastMCP

mcp = FastMCP("Tool Server")

# Define a tool with the @mcp.tool decorator
@mcp.tool("echo")
def echo_tool(text: str) -> str:
    """Echo the input text."""
    return text

if __name__ == "__main__":
    mcp.run()
```

Tool with input schemas and rich output:

```python
from pydantic import BaseModel, Field

class WeatherInput(BaseModel):
    location: str = Field(..., description="City and state/country")
    units: str = Field("metric", description="Temperature units (metric/imperial)")

@mcp.tool("get_weather")
def get_weather(args: WeatherInput) -> dict:
    """Get current weather for a location."""
    # Implement weather API call
    return {
        "temperature": 22.5,
        "conditions": "Partly cloudy",
        "humidity": 65,
        "location": args.location
    }
```

### 2. Resources

Static or dynamic data sources that models can reference.

```python
# Static resource
@mcp.resource("company/mission")
def mission_statement() -> str:
    """Company mission statement."""
    return "Our mission is to make AI accessible and beneficial for everyone."

# Dynamic resource with parameters
@mcp.resource("products/{product_id}")
def product_info(product_id: str) -> dict:
    """Product information by ID."""
    # Could fetch from a database
    products = {
        "A123": {"name": "Widget", "price": 19.99},
        "B456": {"name": "Gadget", "price": 29.99}
    }
    return products.get(product_id, {"error": "Product not found"})
```

## Ontology Integration

Integrating ontologies with MCP servers enables LLMs to access structured knowledge about domains, entities, relationships, and guidelines.

### Example: Ontology-based MCP Server

```python
import rdflib
from rdflib import Graph, Namespace, RDF, RDFS
from mcp.server import FastMCP

class OntologyMCPServer:
    def __init__(self):
        self.mcp = FastMCP("Ontology Server")
        self.ontologies = {}
        
    def load_ontology(self, ontology_id, file_path):
        """Load an ontology from a file."""
        g = Graph()
        g.parse(file_path, format="turtle")
        self.ontologies[ontology_id] = g
        print(f"Loaded ontology {ontology_id} with {len(g)} triples")
        
    def setup_tools(self):
        """Set up tools for accessing ontology data."""
        
        @self.mcp.tool("get_entities")
        def get_entities(ontology_id: str, entity_type: str = "all") -> dict:
            """
            Get entities from specified ontology.
            
            Args:
                ontology_id: ID of the ontology to query
                entity_type: Type of entity to retrieve (roles, conditions, resources, etc.)
            """
            if ontology_id not in self.ontologies:
                return {"error": f"Ontology {ontology_id} not found"}
                
            g = self.ontologies[ontology_id]
            entities = self._extract_entities(g, entity_type)
            return {"entities": entities}
            
        @self.mcp.resource("guidelines/{domain}")
        def get_guidelines(domain: str) -> dict:
            """Get ethical guidelines for a specific domain."""
            # Implementation to extract guidelines from ontology
            # ...
            
    def _extract_entities(self, graph, entity_type):
        """Extract entities of the specified type from the graph."""
        # Implementation similar to your existing code
        # ...
        
    def run(self):
        """Run the MCP server."""
        self.setup_tools()
        self.mcp.run()
```

### Key Ontology Integration Features

1. **Entity Extraction**: Parse ontology graphs to extract structured information about domain entities
2. **Relationship Navigation**: Allow traversal of entity relationships in the ontology
3. **Guideline Access**: Extract domain-specific guidelines and principles  
4. **Hierarchy Understanding**: Provide parent-child relationships between entities
5. **Cross-Ontology Mapping**: Enable connections between related entities across different ontologies

## Best Practices

### Server Implementation

1. **Role Separation**: Clearly separate tool definitions from implementation logic
2. **Error Handling**: Implement robust error handling with informative error messages
3. **Documentation**: Thoroughly document tools and resources with descriptions and examples
4. **Input Validation**: Use schemas (e.g., Pydantic models) to validate tool inputs
5. **Caching**: Cache expensive operations and results to improve performance
6. **Logging**: Implement comprehensive logging for debugging and monitoring
7. **Testing**: Create unit and integration tests for tools and resources

### Ontology Integration

1. **Namespace Management**: Properly handle ontology namespaces to avoid conflicts
2. **Primitive Fallbacks**: Provide file-based fallback when database access fails
3. **Entity Type Detection**: Use flexible entity type detection across multiple namespaces
4. **Relationship Extraction**: Extract meaningful relationships between entities
5. **Cache Results**: Cache extraction results to improve performance

## Troubleshooting

Common issues and solutions when working with MCP servers:

### Connection Issues

- Check that the MCP server is running on the expected port
- Verify that the client is properly configured to connect to the server
- Ensure firewall rules allow communication between client and server

### Tool Execution Failures

- Verify input parameters match the expected schema
- Check for proper error handling in tool implementations
- Review server logs for detailed error information

### Ontology Access Problems

- Confirm that ontology files or database records exist and are accessible
- Check namespace definitions and URI references
- Validate that the ontology is well-formed using a validator

## Example Implementations

### Basic Echo Server

```python
from mcp.server import FastMCP

mcp = FastMCP("Echo Server")

@mcp.tool("echo")
def echo_tool(text: str) -> str:
    """Echo the input text."""
    return text

@mcp.resource("echo/static")
def echo_resource() -> str:
    """Return a static string."""
    return "Echo!"

@mcp.resource("echo/{text}")
def echo_template(text: str) -> str:
    """Echo the input text."""
    return f"Echo: {text}"

if __name__ == "__main__":
    mcp.run()
```

### Ontology Query Server

```python
from mcp.server import FastMCP
import rdflib
from rdflib import Graph, Namespace, RDF, RDFS

mcp = FastMCP("Ontology Server")

# Load ontologies
ontologies = {}

def load_ontology(ontology_id, file_path):
    g = Graph()
    g.parse(file_path, format="turtle")
    ontologies[ontology_id] = g
    print(f"Loaded ontology {ontology_id} with {len(g)} triples")

# Load example ontologies
load_ontology("engineering", "ontologies/engineering-ethics.ttl")
load_ontology("medical", "ontologies/medical-ethics.ttl")

@mcp.tool("query_ontology")
def query_ontology(ontology_id: str, query: str) -> dict:
    """
    Run a SPARQL query against an ontology.
    
    Args:
        ontology_id: ID of the ontology to query
        query: SPARQL query string
    """
    if ontology_id not in ontologies:
        return {"error": f"Ontology {ontology_id} not found"}
        
    try:
        g = ontologies[ontology_id]
        results = []
        
        for row in g.query(query):
            result = {}
            for i, var in enumerate(row.vars):
                value = row[i]
                if isinstance(value, rdflib.term.URIRef):
                    # For URI references, include label if available
                    label = g.value(value, RDFS.label)
                    result[str(var)] = {"uri": str(value), "label": str(label) if label else str(value).split("/")[-1]}
                else:
                    result[str(var)] = str(value)
            results.append(result)
            
        return {"results": results}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    mcp.run()
```

## Conclusion

MCP servers provide a powerful way to extend AI capabilities with external tools, data sources, and domain expertise. By following best practices and properly integrating with ontologies, you can create robust systems that enhance AI applications with structured knowledge and specialized capabilities.

For more information, visit the [MCP GitHub repository](https://github.com/modelcontextprotocol/python-sdk) or [Model Context Protocol website](https://modelcontextprotocol.io).
