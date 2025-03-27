# Running Proethica with Agents Enabled

This guide explains how to run the Proethica service with agent orchestration enabled, ensuring proper integration with the ontology MCP server.

## Configuration Overview

The setup consists of two main components:
1. **Ontology MCP Server**: Runs on port 5001, providing access to ontology data
2. **Proethica Application**: Runs on port 5000 using Gunicorn with agent orchestration enabled

## Ontology Files

The system is configured to read from the following ontology files located in `mcp/ontology/`:
- `engineering_ethics.ttl`
- `nj_legal_ethics.ttl`
- `tccc.ttl`

## Step-by-Step Instructions

### 1. Environment Setup

Ensure your `.env` file has the required configurations:

```
# Add these if not already present
MCP_SERVER_URL=http://localhost:5001
USE_AGENT_ORCHESTRATOR=true
```

### 2. Run the Service

You can run the service in two ways:

#### Option A: Using the provided script

```bash
# Make the script executable (if not already)
chmod +x run_with_agents_gunicorn.sh

# Run the script
./run_with_agents_gunicorn.sh
```

This script will:
- Restart the MCP server on port 5001
- Wait for the MCP server to initialize
- Set environment variables for MCP integration and agent orchestration
- Start the Proethica application with Gunicorn on port 5000

#### Option B: Using the systemd service

To run as a system service:

```bash
# Copy the service file to systemd directory
sudo cp server_config/proethica.service /etc/systemd/system/

# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable and start the service
sudo systemctl enable proethica.service
sudo systemctl start proethica.service
```

### 3. Verify Setup

To verify everything is running correctly:

```bash
# Check if both services are running
ps aux | grep -E '(mcp|gunicorn)'

# Check MCP server logs
cat mcp/server_gunicorn.log

# Test API endpoints
curl http://localhost:5001/api/ontology/engineering_ethics.ttl/entities
```

## Troubleshooting

### MCP Server Issues

If the MCP server isn't running or is inaccessible:
1. Check the log file: `cat mcp/server_gunicorn.log`
2. Manually restart the MCP server: `./scripts/restart_mcp_server_gunicorn.sh`
3. Verify it's running on port 5001: `netstat -tuln | grep 5001`

### Agent Orchestrator Issues

If agent orchestration isn't working:
1. Verify the environment variable is set: `echo $USE_AGENT_ORCHESTRATOR`
2. Check application logs for errors related to agent initialization
3. Restart the service with: `./run_with_agents_gunicorn.sh`

## Configuration Details

### MCP Server
- Port: 5001
- Ontology directory: `mcp/ontology/`
- Log file: `mcp/server_gunicorn.log`

### Proethica Application (with Gunicorn)
- Port: 5000
- Workers: 3
- Timeout: 120 seconds
- Environment: 
  - MCP_SERVER_URL=http://localhost:5001
  - USE_AGENT_ORCHESTRATOR=true
