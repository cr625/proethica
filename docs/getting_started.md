# Getting Started with ProEthica

This guide outlines how to start and use the ProEthica application with all required services.

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

## Environment Detection

The application automatically detects whether to run in development or production mode based on:
- The `ENVIRONMENT` environment variable if set
- The hostname (production if running on proethica.org)
- The git branch (production if on main/master branch)

This automatic detection happens in both `auto_run.sh` and `run.py` to ensure consistent operation.

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

## Choosing Between Development and Production Modes

The application can run in two distinct modes:

1. **Development Mode**:
   - Uses Flask's built-in development server
   - Provides debug information and auto-reloading
   - Better for local development and testing
   - Configuration optimized for ease of debugging

2. **Production Mode**:
   - Uses Gunicorn for better performance and security
   - No debug information or auto-reloading
   - Required for production deployment
   - Runs with more workers for improved performance

## Key Environment Variables

These variables affect application behavior:

- `ENVIRONMENT`: Set to 'development' or 'production'
- `FLASK_ENV`: Set to 'development' for debug mode
- `MCP_SERVER_URL`: URL for the MCP server (typically http://localhost:5001)
- `USE_MOCK_FALLBACK`: Set to 'true' to enable fallback to mock data when the MCP server fails
- `USE_AGENT_ORCHESTRATOR`: Set to 'true' to enable agent orchestration
- `MCP_SERVER_PORT`: Port for the MCP server (typically 5001)

These can be set in the `.env` file or directly in your environment.

## Debugging Startup Issues

If you encounter issues starting the application:

1. Check the `.env` file exists and contains the necessary variables
2. Ensure the MCP server is running and accessible:
   - Use `scripts/check_mcp_roles.py` to verify
   - Check process status: `ps aux | grep ontology_mcp_server`
3. Verify that the required ports are available:
   - Flask app typically uses port 3333
   - MCP server typically uses port 5001
4. Check logs for error messages:
   - Development: Terminal output
   - MCP server log: `mcp/http_server.log`
   - Production: `mcp/server_gunicorn.log`

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
   - Check logs at `mcp/http_server.log`
   - Verify ontology files exist in `mcp/ontology/`

3. **Roles Not Appearing**: If roles are not appearing in the dropdown:
   - Set `USE_MOCK_FALLBACK=true` in the `.env` file
   - Run `python scripts/check_mcp_roles.py` to diagnose
   - Check browser console for JavaScript errors
