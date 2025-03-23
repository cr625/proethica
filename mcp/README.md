# MCP Server Management

This directory contains the Model Context Protocol (MCP) server implementation for the AI Ethical Decision Making application.

## Ontology MCP Server

The `ontology_mcp_server.py` script provides access to ontology data through the Model Context Protocol. It allows the application to query information about ethical domains, guidelines, cases, and world entities.

## Singleton Pattern Implementation

To prevent multiple instances of the MCP server from running simultaneously and causing system resource strain, we've implemented a singleton pattern in the `MCPClient` class. This ensures that only one instance of the client is created, which in turn manages a single instance of the server process.

### Key Features

1. **Singleton MCPClient**: The `MCPClient` class now uses a singleton pattern to ensure only one instance exists throughout the application.
   - All calls to `MCPClient()` or `MCPClient.get_instance()` return the same instance.
   - This prevents multiple server processes from being spawned by different parts of the application.

2. **Process Management**: The client keeps track of the server process and ensures it's properly terminated when the application exits.
   - Uses lock files to track running server processes.
   - Handles cleanup of stale lock files.

3. **Restart Script**: The `scripts/restart_mcp_server.sh` script has been improved to:
   - Check for and clean up stale lock files.
   - Stop all running instances of the server.
   - Start a new server instance with proper logging.
   - Create a lock file with the new process ID.

## Usage

### In Application Code

```python
from app.services.mcp_client import MCPClient

# Get the singleton instance
client = MCPClient.get_instance()

# Use the client to interact with the MCP server
entities = client.get_world_entities("engineering_ethics.ttl", entity_type="roles")
```

### Restarting the Server

If you need to restart the MCP server (e.g., after updating the ontology files), use the restart script:

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

4. Restart the server:
   ```bash
   bash scripts/restart_mcp_server.sh
   ```
