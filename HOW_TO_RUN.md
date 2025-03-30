# How to Run ProEthica

This guide explains the different ways to run the ProEthica application.

## Recommended Method: Automatic Environment Detection

The simplest and recommended way to run ProEthica is using the automatic environment detection script:

```bash
./auto_run.sh
```

This script will:
1. Automatically detect whether to run in development or production mode based on:
   - The `ENVIRONMENT` environment variable if set
   - The hostname (production if running on proethica.org)
   - The git branch (production if on main/master)
2. Configure the appropriate environment variables in `.env`
3. Start the appropriate services:
   - In development mode: MCP server + Flask development server
   - In production mode: MCP server with Gunicorn + ProEthica with Gunicorn

## Alternative Run Methods

If you need more control over the startup process, you can use these alternative methods:

### 1. Basic Development Run

```bash
python run.py
```

This is the simplest way to run the application for development. It:
- Restarts the MCP (Model Context Protocol) server
- Sets the MCP server URL environment variable
- Starts the Flask development server

Optional arguments:
- `--port <number>`: Run on a specific port (default is 3333)

Example: `python run.py --port 8000`

### 2. Server Restart Script

```bash
./restart_server.sh
```

This script:
- Stops any running Flask or Python processes
- Sets environment variables (FLASK_APP, FLASK_ENV)
- Restarts the server using `run.py`

Use this when you want to make sure all previous instances are killed before starting.

### 3. Full Production Setup with Agent Orchestration

```bash
./run_proethica_with_agents.sh
```

This is the comprehensive option for production environments. It:
- Checks for and creates `.env` file if needed
- Ensures MCP environment variables are set
- Verifies ontology files exist
- Stops any running MCP server or Gunicorn processes
- Checks if required ports are available
- Starts the MCP server using Gunicorn
- Starts ProEthica with agent orchestration enabled using Gunicorn

This script is used for production as it:
- Uses Gunicorn instead of the Flask development server
- Properly handles the MCP server setup
- Enables the agent orchestration system

## Choosing Between Development and Production Modes

The application can run in two main modes:

1. **Development Mode**:
   - Uses Flask's built-in development server
   - Provides debug information and auto-reloading
   - MCP server runs on port 5000
   - Ideal for local development

2. **Production Mode**:
   - Uses Gunicorn for better performance and security
   - No debug information or auto-reloading
   - MCP server runs on port 5001
   - Required for production deployment

You can explicitly set the mode with the `ENVIRONMENT` variable in your `.env` file:
```
ENVIRONMENT=development  # or "production"
```

## Debugging Startup Issues

If you encounter issues starting the application:

1. Check the `.env` file exists and contains the necessary variables
2. Ensure the MCP server is running (check `ps aux | grep ontology_mcp_server.py`)
3. Verify that the required ports are available
4. Check logs for error messages:
   - Development: Terminal output
   - Production: `mcp/server_gunicorn.log`

## Key Environment Variables

These variables affect application behavior:

- `ENVIRONMENT`: Set to 'development' or 'production'
- `FLASK_ENV`: Set to 'development' for debug mode
- `MCP_SERVER_URL`: URL for the MCP server (differs by environment)
- `USE_AGENT_ORCHESTRATOR`: Set to 'true' to enable agent orchestration

These can be set in the `.env` file or directly in your environment.
