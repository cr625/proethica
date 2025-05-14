# Running ProEthica in GitHub Codespace

This document provides instructions for running the ProEthica system in a GitHub Codespace environment, with specific focus on the guidelines feature.

## Updated Setup Process

We've created a simplified startup process for the GitHub Codespace environment that automatically:

1. Configures the PostgreSQL database with proper credentials
2. Starts the MCP server for guidelines integration
3. Launches a debug version of the Flask application

## Quick Start

To start the application in the GitHub Codespace environment:

```bash
# Run the simplified startup script
./start_codespace_env.sh
```

This script will check for and start all required services:
- PostgreSQL container (if not running)
- MCP server with guidelines support
- Flask web application

## Troubleshooting

If you encounter issues, you can use the diagnostic script:

```bash
./check_status.sh
```

This will check:
1. Running MCP server processes
2. PostgreSQL container status
3. Database connection
4. MCP server connection

### Common Issues and Solutions

#### Database Connection Issues

If you see database connection errors, ensure the PostgreSQL container is running:

```bash
# Check PostgreSQL container status
docker ps | grep postgres

# If not running, start it
docker start postgres17-pgvector-codespace
```

#### MCP Server Issues

The MCP server should run on port 5001. If you see connection errors:

```bash
# Check for running MCP server
ps -ef | grep "python.*mcp/run_enhanced_mcp"

# Start the MCP server if needed
python mcp/run_enhanced_mcp_server_with_guidelines.py &
```

#### Port Conflicts

If you see "Address already in use" errors, find and stop the conflicting process:

```bash
# Find process using port 5050 (for Flask)
lsof -i :5050
# Then kill the process with: kill <PID>

# Find process using port 5001 (for MCP)
lsof -i :5001
# Then kill the process with: kill <PID>
```

## Internal Services Architecture

The system in the Codespace environment consists of:

1. **PostgreSQL Database**
   - Runs in Docker container on port 5433
   - Database name: ai_ethical_dm
   - Credentials: postgres:postgres

2. **MCP Server**
   - Runs on port 5001
   - Provides guideline analysis tools
   - JSON-RPC API endpoint: http://localhost:5001/jsonrpc

3. **Flask Application**
   - Runs on port 5050
   - Connects to both PostgreSQL and MCP server
