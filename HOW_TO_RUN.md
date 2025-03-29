# How to Run ProEthica

This guide explains the different ways to run the ProEthica application.

## Available Run Methods

There are three main ways to run ProEthica:

### 1. Basic Development Run

```bash
python run.py
```

This is the simplest way to run the application. It:
- Restarts the MCP (Model Context Protocol) server
- Sets the MCP server URL environment variable
- Starts the Flask development server

Optional arguments:
- `--port <number>`: Run on a specific port (default is 5000)

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

### 3. Full Setup with Agent Orchestration (Recommended)

```bash
./run_proethica_with_agents.sh
```

This is the most comprehensive option and recommended for full functionality. It:
- Checks for and creates `.env` file if needed
- Ensures MCP environment variables are set
- Verifies ontology files exist
- Stops any running MCP server or Gunicorn processes
- Checks if required ports are available
- Starts the MCP server using Gunicorn
- Starts ProEthica with agent orchestration enabled using Gunicorn

This script is recommended for production-like environments as it:
- Uses Gunicorn instead of the Flask development server
- Properly handles the MCP server setup
- Enables the agent orchestration system

## Recommended Approach

For most users, we recommend:

1. For development and testing: `python run.py`
2. For production-like environments: `./run_proethica_with_agents.sh`

## Debugging Startup Issues

If you encounter issues starting the application:

1. Check the `.env` file exists and contains the necessary variables
2. Ensure the MCP server is running (should be on port 5001)
3. Verify that the required ports (5000 and 5001) are available
4. Check logs for error messages

## Ports

- ProEthica Web App: http://localhost:5000
- MCP Server: http://localhost:5001

## Environment Variables

Key environment variables that affect application behavior:

- `FLASK_ENV`: Set to 'development' for debug mode
- `MCP_SERVER_URL`: URL for the MCP server (default: http://localhost:5001)
- `USE_AGENT_ORCHESTRATOR`: Set to 'true' to enable agent orchestration

These can be set in the `.env` file or directly in your environment.
