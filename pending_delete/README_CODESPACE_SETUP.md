# ProEthica Codespace Setup Guide

This guide explains how to properly set up and run the ProEthica engineering ethics platform in GitHub Codespaces, ensuring that the main UI functionality is preserved while providing debugging capabilities.

## Overview of Issues Fixed

When migrating to GitHub Codespaces, we encountered several issues that needed to be addressed:

1. **Database Connection Issues**: 
   - Password authentication failures with PostgreSQL
   - Different port usage in Codespaces environment (5433 vs 5432)

2. **MCP Server Integration Problems**: 
   - The MCP server that provides guideline extraction capabilities had JSON-RPC endpoint issues
   - Malformed JSON responses needed to be fixed to ensure proper communication

3. **Missing Main UI**: 
   - The main UI was replaced with a debug interface, losing core functionality
   - Circular import issues prevented proper module loading

## Solution Components

We've implemented several fixes to address these issues:

1. **Database Fix**: `fix_db_password.py`
   - Updates the database URL in `.env` file
   - Sets the correct PostgreSQL password for Codespaces environment
   - Tests the connection to ensure it's working

2. **MCP Server JSON Fixer**: `mcp_json_fixer.py`
   - Creates a proxy that sits between the application and MCP server
   - Fixes malformed JSON responses from the server
   - Runs on port 5002 and forwards requests to the real MCP server on port 5001

3. **Unified Runner**: `run_proethica_unified.py`
   - Restores the main UI functionality while preserving debug capabilities
   - Creates a dedicated `/debug` route that doesn't interfere with main functionality
   - Detects environment, fixes circular imports, and configures services accordingly

4. **Automated Launcher**: `codespace_launcher.sh`
   - Orchestrates the entire startup process
   - Applies database fixes
   - Starts the JSON fixer proxy
   - Updates the MCP server URL to use the proxy
   - Runs the unified ProEthica application

## Starting ProEthica in Codespaces

To start the complete ProEthica environment with all fixes applied:

```bash
./codespace_launcher.sh
```

This script will:
1. Fix the database connection
2. Start the MCP JSON fixer proxy in the background
3. Update environment variables to use the proxy
4. Launch the full ProEthica application with UI restored

## Individual Components

If you need to run components separately:

### Fix Database Connection

```bash
python fix_db_password.py
```

### Start MCP JSON Fixer Proxy

```bash
python mcp_json_fixer.py
```

### Run ProEthica with Full UI

```bash
python run_proethica_unified.py
```

### Run Debug Interface Only

```bash
python run_proethica_unified.py --debug-only
```

## Verifying it Works

1. **Database Connection**: 
   - The main UI should display all worlds and guidelines
   - You should see tables in the database debug view

2. **MCP Server Integration**: 
   - Guideline upload and analysis should work
   - Concept extraction should complete successfully

3. **UI Functionality**: 
   - Both the main UI and debug interface should be accessible
   - Debug interface at `/debug` provides system status

## Troubleshooting

### Database Errors

If you see database connection errors:
- Check PostgreSQL service is running in Codespaces
- Verify password in `.env` file is set to "postgres"
- Ensure port 5433 is being used

### MCP Server Issues

If guideline extraction fails:
- Check both MCP server and JSON fixer proxy are running
- Verify MCP_SERVER_URL points to `http://localhost:5002`
- Look at logs in `logs/` directory for errors

### UI Problems

If UI doesn't load properly:
- Check for circular import errors in console output
- Run `python fix_circular_import.py` to resolve issues
- Verify environment variable `ENVIRONMENT` is set to `codespace`

## Important Files

- `.env`: Environment configuration, including database and MCP server URLs
- `app/routes/debug_routes.py`: Debug interface routes
- `app/templates/debug/status.html`: Debug interface template
- `mcp/run_enhanced_mcp_server_with_guidelines.py`: Enhanced MCP server script

## Technical Notes

- The JSON fixer proxy needs to be running for guideline functionality to work
- Codespace environment uses port 5433 for PostgreSQL
- Original UI functionality is preserved while adding debug capabilities
