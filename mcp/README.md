# MCP Server Management

This directory contains the Model Context Protocol (MCP) server implementation for the AI Ethical Decision Making application.

## Ontology MCP Server

The MCP server provides access to ontology data through the Model Context Protocol, allowing LLMs and the application to query information about ethical domains, guidelines, and world entities.

### Database-Driven Ontology Access

The MCP server now primarily works with database-stored ontologies:

1. **Direct Database Loading**: The server first attempts to load ontologies from the database
2. **File Fallback**: Falls back to file loading only if the ontology is not found in the database
3. **Consistent Entity Extraction**: Uses the same entity extraction logic as the main application

This approach ensures consistency and allows for proper version control of ontologies.

## Implementation Types

The MCP server is implemented in two versions:

1. **Standard MCP Server** (`ontology_mcp_server.py`): 
   - Uses stdio for communication
   - Primarily used with the development server

2. **HTTP MCP Server** (`http_ontology_mcp_server.py`): 
   - Runs as a web server on a specific port
   - Used with Gunicorn for production

## Singleton Pattern Implementation

To prevent multiple instances of the MCP server from running simultaneously and causing system resource strain, we've implemented a singleton pattern in the `MCPClient` class.

### Key Features

1. **Singleton MCPClient**: The `MCPClient` class uses a singleton pattern to ensure only one instance exists.
   - All calls to `MCPClient()` or `MCPClient.get_instance()` return the same instance
   - Prevents multiple server processes from being spawned

2. **Process Management**: The client keeps track of the server process and ensures proper termination.
   - Uses lock files to track running server processes
   - Handles cleanup of stale lock files

3. **Restart Script**: The `scripts/restart_mcp_server.sh` script manages server instances:
   - Cleans up stale lock files
   - Stops all running instances of the server
   - Starts a new server instance with proper logging
   - Creates a lock file with the new process ID

## Usage

### In Application Code

```python
from app.services.mcp_client import MCPClient

# Get the singleton instance
client = MCPClient.get_instance()

# Use the client to interact with the MCP server
# Note: No need to include .ttl extension
entities = client.get_world_entities("engineering-ethics", entity_type="roles")
```

### Restarting the Server

If you need to restart the MCP server, use the restart script:

```bash
bash scripts/restart_mcp_server.sh
```

This will:
1. Stop all running instances of the server
2. Start a new instance
3. Log output to `mcp/server.log`

## Troubleshooting

If you encounter issues with the MCP server:

1. Check if multiple instances are running:
   ```bash
   ps aux | grep ontology_mcp_server.py
   ```

2. Check the server log:
   ```bash
   tail -f mcp/server.log
   ```

3. Verify the lock file:
   ```bash
   cat /tmp/ontology_mcp_server.lock
   ```

4. Check database connectivity:
   ```bash
   python scripts/check_ontologies_in_db.py
   ```

5. Restart the server:
   ```bash
   bash scripts/restart_mcp_server.sh
   ```

## Entity Types Supported

The MCP server extracts the following entity types from ontologies:

1. **Roles**: Characters or positions (e.g., Engineer, Manager)
2. **Conditions**: States or situations (e.g., ConflictOfInterest)
3. **Resources**: Assets or objects (e.g., Blueprint, Contract)
4. **Events**: Occurrences in the timeline (e.g., Meeting, Accident)
5. **Actions**: Activities that can be performed (e.g., Approve, Review)
6. **Capabilities**: Skills or abilities (e.g., StructuralAnalysis)
