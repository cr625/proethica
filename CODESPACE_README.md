# ProEthica Codespace Configuration Guide

This document provides instructions for running the ProEthica system in a GitHub Codespace environment.

## Table of Contents

- [ProEthica Codespace Configuration Guide](#proethica-codespace-configuration-guide)
  - [Table of Contents](#table-of-contents)
  - [Quick Start](#quick-start)
  - [System Components](#system-components)
  - [Launcher Scripts](#launcher-scripts)
  - [Database Configuration](#database-configuration)
  - [Debugging](#debugging)
  - [Common Issues](#common-issues)

## Quick Start

To get started with ProEthica in your Codespace environment, run the following command:

```bash
./codespace_proethica_launcher.sh
```

This script handles:
1. Setting up PostgreSQL database container
2. Running database initialization
3. Starting the MCP server with guidelines support
4. Launching a debug application for status monitoring

After running the launcher, you can:
- Access the debug interface at http://localhost:5050/
- Run the full web UI with `python codespace_run.py`

## System Components

The ProEthica system in Codespace consists of:

1. **PostgreSQL Database**
   * Running in Docker container on port 5433
   * Uses pgvector for embedding support
   * Database name: `ai_ethical_dm`

2. **MCP Server**
   * Running on port 5001
   * Provides guideline analysis tools
   * Exposes JSONRPC interface

3. **Debug Application**
   * Running on port 5050
   * Shows system status and connections
   * Template-free design for reliability

4. **Full Web Application**
   * Optional component, runs on port 3333
   * Requires proper database initialization
   * Uses the Flask framework

## Launcher Scripts

Several launcher scripts are provided to meet different needs:

1. `codespace_proethica_launcher.sh` - Main launcher for reliable operation
2. `simplest_codespace_starter.sh` - Minimal starter focused on debugging
3. `run_full_proethica_web.sh` - Full application with web UI

## Database Configuration

The PostgreSQL database runs on port 5433 (not the default 5432) to avoid conflicts with any system PostgreSQL installations. The connection string is:

```
postgresql://postgres:postgres@localhost:5433/ai_ethical_dm
```

Database initialization is handled by `codespace_run_db.py`, which:
- Checks if the PostgreSQL container is running
- Creates the database if it doesn't exist
- Initializes minimal schema if needed

## Debugging

For troubleshooting, check the log files in the `logs` directory:
- `logs/mcp_server.log` - MCP server output
- `logs/debug_app.log` - Debug application output

The debug interface at http://localhost:5050/ provides:
- Database connection status
- MCP server connectivity
- List of available MCP tools
- Environment variable configuration

## Common Issues

**Database Connection Issues**
- If you see "Testing database connection..." hanging, the PostgreSQL container may not be properly initialized
- Solution: Run `codespace_run_db.py` to ensure proper database setup

**Circular Import Errors**
- If you see errors related to circular imports, run `python fix_circular_import.py`
- This fixes issues between app/__init__.py and model files

**MCP Server Connection Failures**
- If you see "Failed to connect to MCP server", ensure the MCP server is running
- Check `logs/mcp_server.log` for specific errors

**Template Not Found Errors**
- The system uses simplified interfaces in Codespace to avoid template loading issues
- Use the simplified debug app or modify routes to use simple string responses
