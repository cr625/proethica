# MCP Project Reference for Proethica

This document serves as a reference guide for the Model Context Protocol (MCP) implementation in the Proethica project. It contains key implementation details, configurations, and best practices specific to our project.

## Current MCP Server Implementation

The Proethica project currently implements an MCP server for ontology access using the HTTP communication method. This is implemented primarily in `mcp/http_ontology_mcp_server.py`.

### Key Components:

1. **OntologyMCPServer Class**: The core class that implements the MCP server for ontology access
2. **Database-first Loading**: Prioritizes loading ontologies from database with file-based fallback  
3. **Entity Type Extraction**: Support for all core entity types (roles, conditions, resources, events, actions, capabilities)
4. **HTTP Endpoints**: Both JSON-RPC endpoints and RESTful API endpoints

## Configuration

The MCP server uses the following environment variables for configuration:

| Variable | Default | Description |
|----------|---------|-------------|
| ONTOLOGY_DIR | `mcp/ontology` | Directory containing ontology files (for fallback) |
| DEFAULT_DOMAIN | `military-medical-triage` | Default domain when none is specified |
| MCP_SERVER_PORT | `5001` | Port for the HTTP server to listen on |

## Tools and Resources

Our MCP server exposes the following tools and resources:

### Tools:

- **get_world_entities**: Retrieve entities from a specified ontology by type

```json
{
  "jsonrpc": "2.0",
  "method": "call_tool",
  "params": {
    "name": "get_world_entities",
    "arguments": {
      "ontology_source": "engineering-ethics",
      "entity_type": "roles"
    }
  },
  "id": 1
}
```

### Direct API Endpoints:

- **GET /api/ontology/{ontology_source}/entities**: Get all entities for a specific ontology
- **GET /api/guidelines/{world_name}**: Get ethical guidelines for a specific world

## Integration with Main Application

The MCP server integrates with the main application through the `MCPClient` class implemented in `app/services/mcp_client.py`. This client uses a singleton pattern to prevent multiple instances from being created.

### Usage Example:

```python
from app.services.mcp_client import MCPClient

# Get the singleton instance
client = MCPClient.get_instance()

# Use the client to get world entities
entities = client.get_world_entities("engineering-ethics", entity_type="roles")
```

## Enhancements & TODO

The following enhancements are planned for the MCP implementation:

1. **Advanced Caching**: Implement more sophisticated caching mechanisms for frequently accessed entities
2. **Temporal Entity Support**: Add temporal support for time-bound entity relationships
3. **Query Capability**: Implement a SPARQL query endpoint for complex ontology queries
4. **Relationship Inference**: Add inference capabilities to derive implicit entity relationships

## Best Practices for MCP in Proethica

1. **Namespace Convention**: Use consistent namespace URIs for ontology entities:
   - `http://proethica.org/ontology/{domain}#{concept}`
   - Example: `http://proethica.org/ontology/engineering-ethics#Engineer`

2. **Entity Type Creation**:
   - Follow the core entity types: Role, ConditionType, ResourceType, EventType, ActionType, Capability
   - Ensure all entities have both a domain-specific type and the intermediate type

3. **Error Handling**:
   - Implement graceful fallbacks (e.g., database to file)
   - Log detailed error information
   - Return meaningful error messages to clients

4. **Performance Considerations**:
   - Use entity type filtering when possible (`entity_type` parameter)
   - Leverage caching for repeated ontology access
   - Consider pagination for large result sets

## Example MCP Server Implementation

```python
# Simplified example of our MCP server implementation
from mcp.server import FastMCP
import asyncio
import rdflib
from rdflib import Graph, Namespace, RDF, RDFS

# Create the MCP server
mcp = FastMCP("Proethica Ontology Server")

# Dictionary to store loaded ontologies
ontologies = {}

# Load an ontology
def load_ontology(domain_id, source):
    """Load ontology from database or file."""
    g = Graph()
    try:
        # Try loading from database first
        # Implementation details...
        
        # Fall back to file if needed
        g.parse(f"ontologies/{domain_id}.ttl", format="turtle")
        ontologies[domain_id] = g
    except Exception as e:
        print(f"Failed to load ontology: {str(e)}")
    
    return g

# Define MCP tool for entity access
@mcp.tool("get_world_entities")
def get_world_entities(ontology_source: str, entity_type: str = "all") -> dict:
    """Get entities from specified ontology."""
    # Load ontology if not already loaded
    if ontology_source not in ontologies:
        g = load_ontology(ontology_source, None)
    else:
        g = ontologies[ontology_source]
    
    # Extract and return entities
    # Implementation details...
    
    return {"entities": entities}

# Define resource for guidelines
@mcp.resource("guidelines/{domain}")
def get_guidelines(domain: str) -> dict:
    """Get ethical guidelines for a specific domain."""
    # Return domain-specific guidelines
    # Implementation details...
    
    return guidelines

# Run the server
if __name__ == "__main__":
    # Load core ontologies
    load_ontology("engineering-ethics", None)
    load_ontology("military-medical-triage", None)
    load_ontology("nj-legal-ethics", None)
    
    # Start the server
    asyncio.run(mcp.run_http(host="localhost", port=5001))
```

## Testing MCP Server Functionality

You can test the MCP server's functionality using:

1. **Direct HTTP Requests**:
   ```bash
   curl -X GET http://localhost:5001/api/ontology/engineering-ethics/entities
   ```

2. **JSON-RPC Requests**:
   ```bash
   curl -X POST http://localhost:5001/jsonrpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "method": "call_tool", "params": {"name": "get_world_entities", "arguments": {"ontology_source": "engineering-ethics", "entity_type": "roles"}}, "id": 1}'
   ```

3. **Python Test Script**:
   ```python
   import requests
   
   response = requests.post("http://localhost:5001/jsonrpc", json={
       "jsonrpc": "2.0",
       "method": "call_tool",
       "params": {
           "name": "get_world_entities",
           "arguments": {
               "ontology_source": "engineering-ethics",
               "entity_type": "roles"
           }
       },
       "id": 1
   })
   
   print(response.json())
   ```

## References

- [MCP Python SDK Repository](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Official Documentation](https://modelcontextprotocol.io)
- [RDFLib Documentation](https://rdflib.readthedocs.io/en/stable/)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
