# MCP Development Reference Prompt

This document serves as a reference for developers working with the Model Context Protocol (MCP) in the Proethica project. It provides key information and context that can be included in prompts when working with Claude or other LLMs on MCP-related tasks.

## MCP Server Architecture

The Proethica MCP server is structured as follows:

```
mcp/
├── __init__.py
├── add_temporal_functionality.py    # Adds temporal reasoning to ontology data
├── http_ontology_mcp_server.py      # Main MCP server implementation
├── load_from_db.py                  # Database loading utilities
└── ontology/                        # Directory for fallback ontology files
```

## Key Components

1. **OntologyMCPServer Class**: Core server implementation that:
   - Loads ontologies from database (with file fallback)
   - Exposes entity data through MCP tools and resources
   - Handles proper namespacing and entity type detection
   - Implements both JSON-RPC and REST interfaces

2. **Entity Types**: The server handles these primary entity types:
   - Roles (e.g., Engineer, Doctor)
   - Conditions (e.g., ConflictOfInterest)
   - Resources (e.g., Document, Equipment)
   - Events (e.g., Meeting, Accident)
   - Actions (e.g., Approve, Review)
   - Capabilities (e.g., StructuralAnalysis)

3. **MCP Server Tools**: The server exposes these tools:
   - `get_world_entities`: Retrieve entities of a specific type from an ontology
   - `query_ontology`: Execute custom queries against an ontology

## Integration Points

The MCP server integrates with:

1. **Database**: Loads ontologies from database tables
2. **File System**: Falls back to file-based ontologies when database access fails
3. **Web Server**: Exposes HTTP endpoints for JSON-RPC and REST
4. **Claude API**: Connects through the adapter pattern
5. **Client Applications**: Supports Claude Desktop, Cline, Continue, etc.

## Common Development Tasks

### Adding a New Tool

To add a new tool to the MCP server:

```python
@mcp.tool("new_tool_name")
def new_tool(parameter1: str, parameter2: int = 0) -> dict:
    """
    Description of what the tool does.
    
    Args:
        parameter1: Description of parameter1
        parameter2: Description of parameter2
    
    Returns:
        Dictionary containing results
    """
    # Implementation
    return {"result": "some result"}
```

### Adding a New Resource

To add a new resource to the MCP server:

```python
@mcp.resource("resource_name/{parameter}")
def some_resource(parameter: str) -> dict:
    """
    Description of what the resource provides.
    
    Args:
        parameter: Description of parameter
        
    Returns:
        Dictionary containing resource data
    """
    # Implementation
    return {"data": "some data"}
```

## Testing

For testing MCP functionality:

1. **Start the server**:
   ```bash
   ./scripts/restart_http_mcp_server.sh
   ```

2. **Test REST endpoint**:
   ```bash
   curl http://localhost:5001/api/ontology/engineering-ethics/entities
   ```

3. **Test JSON-RPC endpoint**:
   ```bash
   curl -X POST http://localhost:5001/jsonrpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "method": "call_tool", "params": {"name": "get_world_entities", "arguments": {"ontology_source": "engineering-ethics", "entity_type": "roles"}}, "id": 1}'
   ```

## Best Practices

1. **Error Handling**:
   - Always include comprehensive error handling
   - Provide fallbacks when possible
   - Return meaningful error messages

2. **Performance**:
   - Implement caching for frequently accessed data
   - Use entity type filtering to limit results
   - Consider pagination for large result sets

3. **Documentation**:
   - Document all tools and resources with clear descriptions
   - Include examples in docstrings
   - Update this reference when adding features

## Debugging Tips

1. **Missing Entities**: Check both database and file fallbacks
2. **Connection Errors**: Verify server is running on correct port
3. **Authentication Issues**: Check environment variables and API keys
4. **Unexpected Data**: Use the inspector to examine tool/resource responses

## Future Enhancements

Planned enhancements include:

1. **Temporal Ontology Support**: Enhanced support for time-bound entity relationships
2. **Advanced Query Capability**: SPARQL query support for complex ontology queries
3. **Inference Engine**: Ability to derive implicit relationships between entities
4. **Full Client Support**: Expanded support for all MCP features across clients
