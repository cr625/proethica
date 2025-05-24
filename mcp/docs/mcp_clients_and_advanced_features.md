# MCP Clients and Advanced Features

This document provides information about MCP client applications and advanced MCP features that can be leveraged in the Proethica project.

## MCP Client Applications

The following applications support the Model Context Protocol (MCP) with varying levels of features:

| Client | Resources | Prompts | Tools | Sampling | Notes |
|--------|-----------|---------|-------|----------|-------|
| Claude Desktop App | ✅ | ✅ | ✅ | ❌ | Supports tools, prompts, and resources |
| Cline | ✅ | ❌ | ✅ | ❌ | Supports tools and resources |
| Continue | ✅ | ✅ | ✅ | ❌ | VS Code extension that supports tools, prompts, and resources |
| Cursor | ❌ | ❌ | ✅ | ❌ | Supports tools only |

*Source: MCP official documentation (modelcontextprotocol.io)*

## Advanced MCP Features

### Roots

Roots are a feature that allow MCP servers to register as a trusted resource provider with specific language models. This is an advanced feature primarily used by system-level MCP implementations.

### Sampling

Sampling controls allow MCP servers to influence the generation parameters of language models, including:
- Temperature
- Top-p (nucleus sampling)
- Frequency penalty
- Maximum token limits

*Note: As of the current implementation, Proethica does not utilize these advanced features.*

## Debugging MCP Servers

### Real-time Logs

When developing or troubleshooting MCP servers, you can follow logs in real-time:

```bash
# For HTTP MCP server
tail -f mcp_server.log

# For debugging connection issues
curl -v http://localhost:5001/api/ontology/engineering-ethics/entities
```

### Testing JSON-RPC Endpoints

Test JSON-RPC endpoints directly with curl:

```bash
curl -X POST http://localhost:5001/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "call_tool", "params": {"name": "get_world_entities", "arguments": {"ontology_source": "engineering-ethics", "entity_type": "roles"}}, "id": 1}'
```

## Best Practices for Client and Server Communication

1. **Implement timeouts**: All MCP clients should implement reasonable timeouts when communicating with servers
2. **Handle connection errors gracefully**: Provide fallback responses when MCP servers are unavailable
3. **Validate server responses**: Always validate that server responses match the expected schema
4. **Cache frequently used data**: Implement caching for frequently requested ontology data
5. **Log both client and server operations**: Maintain logs on both sides for easier troubleshooting

## Related Documents

- [MCP Server Guide](mcp_server_guide.md) - Comprehensive guide on creating and configuring MCP servers
- [Ontology Integration Guide](ontology_mcp_integration_guide.md) - Details on integrating ontologies with MCP
- [Project Reference](mcp_project_reference.md) - Proethica-specific MCP implementation details and best practices
