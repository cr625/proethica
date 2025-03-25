# MCP Server Integration

This document describes the integration of the Model Context Protocol (MCP) server with the AI Ethical DM application.

## Overview

The application uses a Model Context Protocol (MCP) server to retrieve entities from ontologies. The MCP server is a separate process that runs alongside the application and provides access to ontology data through a JSON-RPC API.

## MCP Server

The MCP server is implemented in `mcp/ontology_mcp_server.py`. It loads ontology files from the `mcp/ontology/` directory and provides an API to retrieve entities from these ontologies.

The server supports the following ontologies:
- `engineering_ethics.ttl`: Engineering ethics ontology
- `nj_legal_ethics.ttl`: New Jersey legal ethics ontology
- `tccc.ttl`: Tactical Combat Casualty Care ontology

## Starting the MCP Server

The MCP server is started automatically when the application is run with the `run_with_gunicorn.sh` script. The script calls `scripts/restart_mcp_server.sh` to start the MCP server before starting Gunicorn.

You can also start the MCP server manually by running:

```bash
./scripts/restart_mcp_server.sh
```

## MCP Client

The application communicates with the MCP server through the `MCPClient` class implemented in `app/services/mcp_client.py`. The client provides methods to retrieve entities from ontologies, as well as other functionality like retrieving references from Zotero.

The `MCPClient` is implemented as a singleton, so there is only one instance of the client throughout the application. The client is initialized in `app/__init__.py` when the application starts.

## Entity Retrieval

The application retrieves entities from ontologies through the `get_world_entities` method of the `MCPClient`. This method takes an ontology source (e.g., `engineering_ethics.ttl`) and returns a dictionary of entities organized by type (roles, conditions, resources, actions).

If the MCP server is not running or cannot be reached, the client falls back to mock data defined in the `get_mock_entities` method.

## Troubleshooting

If entities are not being retrieved from ontologies, check the following:

1. Make sure the MCP server is running. You can check this by running:
   ```bash
   ps aux | grep ontology_mcp_server.py
   ```

2. Check the MCP server logs for errors:
   ```bash
   cat mcp/server.log
   ```

3. Make sure the ontology files exist in the `mcp/ontology/` directory:
   ```bash
   ls -l mcp/ontology/
   ```

4. Try restarting the MCP server:
   ```bash
   ./scripts/restart_mcp_server.sh
   ```

5. If the MCP server is running but the application is still not retrieving entities, check the application logs for errors related to the MCP client.

## Improving Robustness

To improve the robustness of the MCP server integration, the following changes have been made:

1. The `run_with_gunicorn.sh` script now starts the MCP server before starting Gunicorn, ensuring that the MCP server is running when the application starts.

2. The script waits for 5 seconds after starting the MCP server to give it time to initialize before the application tries to connect to it.

3. The script sets the `MCP_SERVER_URL` environment variable to ensure the application knows where to find the MCP server.

4. The `MCPClient` includes enhanced error handling and logging to gracefully handle cases where the MCP server is not running or cannot be reached.

5. The API routes in `app/routes/mcp_api.py` have been updated to use absolute paths when loading ontology files, ensuring they can be found regardless of the current working directory.

6. Detailed logging has been added throughout the entity retrieval process to help diagnose any issues.
