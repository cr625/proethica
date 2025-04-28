# MCP Server Integration Guide

This document provides guidance on integrating the Model Context Protocol (MCP) server with the Proethica application, including setup, configuration, and best practices.

## Overview

The Proethica project uses Model Context Protocol (MCP) to provide LLMs with access to ontological knowledge and domain-specific information. This integration enhances the capabilities of models like Claude by giving them access to structured ethical knowledge.

## Current Implementation

The current MCP server implementation is an HTTP-based server located in `mcp/http_ontology_mcp_server.py`. This server:

1. Loads ontologies from the database with file-based fallback
2. Exposes entity data through both JSON-RPC and REST endpoints
3. Supports multiple entity types (roles, conditions, resources, events, actions)
4. Integrates with the main application through a singleton client pattern

## Setup and Configuration

### Environment Variables

The MCP server uses the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| ONTOLOGY_DIR | `mcp/ontology` | Directory for ontology files (fallback) |
| DEFAULT_DOMAIN | `military-medical-triage` | Default domain when none specified |
| MCP_SERVER_PORT | `5001` | HTTP server port |

### Starting the Server

The server can be started using the provided scripts:

```bash
# Start the MCP server
./scripts/restart_mcp_server.sh

# Start the HTTP MCP server
./scripts/restart_http_mcp_server.sh
```

## Integration with Claude

The Proethica application integrates with Claude through the MCP server using:

1. The `ClaudeService` class (`app/services/claude_service.py`)
2. The `ProethicaAdapter` class (`app/agent_module/adapters/proethica.py`)
3. Environment variables for API configuration

### API Configuration

Proper API configuration in `.env` is essential:

```
ANTHROPIC_API_KEY=your_api_key_here
USE_MOCK_FALLBACK=false  # Set to true to use mock responses instead of Claude API
```

## Security Considerations

When working with the MCP server:

1. **API Key Protection**: Never commit API keys to version control
2. **Environment Separation**: Use different API keys for development and production
3. **Access Control**: The MCP server should only be accessible locally, not exposed publicly
4. **Logging**: Implement proper logging but avoid logging sensitive information

## Testing

### API Endpoint Testing

Test the MCP server endpoints using:

```bash
# Test REST endpoint
curl http://localhost:5001/api/ontology/engineering-ethics/entities

# Test JSON-RPC endpoint
curl -X POST http://localhost:5001/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "call_tool", "params": {"name": "get_world_entities", "arguments": {"ontology_source": "engineering-ethics", "entity_type": "roles"}}, "id": 1}'
```

### Claude Integration Testing

To test Claude integration with MCP:

```bash
# Using the verification script
./scripts/run_with_env.sh python scripts/verify_anthropic_fix.py
```

## Troubleshooting

Common issues and solutions:

1. **Connection Errors**: Ensure the MCP server is running on the correct port
2. **Authentication Errors**: Verify environment variables are properly loaded
3. **Missing Ontologies**: Check both database storage and file fallbacks
4. **Performance Issues**: Consider implementing caching for frequently requested data

## Client Applications

The following applications support MCP integration with Proethica:

| Client | Support Level | Notes |
|--------|--------------|-------|
| Claude Desktop App | Full | Supports tools, prompts, and resources |
| Cline | Partial | Supports tools and resources |
| Continue | Full | VS Code extension with full MCP support |
| Cursor | Limited | Supports tools only |

## Further Documentation

For more detailed information, refer to:

- [MCP Server Guide](docs/mcp_docs/mcp_server_guide.md)
- [Ontology Integration Guide](docs/mcp_docs/ontology_mcp_integration_guide.md)
- [MCP Project Reference](docs/mcp_docs/mcp_project_reference.md)
- [MCP Clients and Advanced Features](docs/mcp_docs/mcp_clients_and_advanced_features.md)
