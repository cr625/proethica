# How to Start ProEthica

This guide outlines the different ways to start the ProEthica application with all required services.

## Quick Start (Recommended)

The simplest way to start ProEthica with all services properly configured:

```bash
./start_proethica.sh
```

This script will:
1. Ensure all environment variables are correctly set
2. Start the HTTP MCP server on port 5001
3. Launch the Flask application with the correct configuration
4. Enable mock data fallback to ensure roles are always available

## Manual Start Options

### Option 1: Using auto_run.sh

The `auto_run.sh` script automatically detects your environment (development or production) and starts the appropriate configuration:

```bash
./auto_run.sh
```

### Option 2: Direct Flask Run

For development with manual control:

```bash
# Set environment variables
export MCP_SERVER_URL=http://localhost:5001
export USE_MOCK_FALLBACK=true

# Start the MCP server
./scripts/restart_http_mcp_server.sh

# Start the Flask application
python run.py
```

### Option 3: Production Mode

For production deployments:

```bash
# Set environment variables
export ENVIRONMENT=production
export MCP_SERVER_URL=http://localhost:5001
export USE_MOCK_FALLBACK=true

# Start using the production script
./run_proethica_with_agents.sh
```

## Verifying MCP Server

To verify that the MCP server is running correctly and returning roles:

```bash
python scripts/check_mcp_roles.py
```

This script will:
1. Check connection to the MCP server
2. Verify that roles are being retrieved from the ontology
3. Display the available roles

## Common Issues

1. **Port Conflicts**: If port 5001 is already in use, you may need to modify the MCP server port in:
   - `.env` file (MCP_SERVER_URL)
   - `scripts/restart_http_mcp_server.sh` (PORT variable)

2. **Connection Failures**: If the server is not connecting to the MCP service:
   - Ensure the MCP server is running (`ps aux | grep ontology_mcp_server`)
   - Check logs at `/home/chris/ai-ethical-dm/mcp/http_server.log`
   - Verify ontology files exist in `/home/chris/ai-ethical-dm/mcp/ontology/`

3. **Roles Not Appearing**: If roles are not appearing in the dropdown:
   - Set `USE_MOCK_FALLBACK=true` in the `.env` file
   - Run `python scripts/check_mcp_roles.py` to diagnose
   - Check browser console for JavaScript errors
