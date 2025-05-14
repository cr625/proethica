# VSCode Debugging Setup for ProEthica

This document explains how to use the VSCode debugger with the ProEthica application.

## Overview

The ProEthica application normally starts using the `start_proethica_updated.sh` shell script, which:
1. Sets up the environment
2. Starts the MCP server
3. Initializes the database
4. Launches the application

For debugging purposes, we've split this process into two parts:
1. A setup script that handles environment setup, MCP server start, and database initialization
2. A VSCode debugger configuration that launches the application with debugging enabled

## How to Use

1. Open the ProEthica project in VSCode
2. Go to the "Run and Debug" panel in VSCode (Ctrl+Shift+D or Cmd+Shift+D)
3. Select "Debug ProEthica Application" from the dropdown menu
4. Click the green "Play" button

This will:
1. Run the setup script first (as a pre-launch task)
2. Once the environment is ready, launch the application with the debugger attached

## Configuration Files

The setup consists of three files:

1. **scripts/setup_debug_environment.sh**
   - A bash script that handles all the environment setup
   - Starts the MCP server
   - Initializes the database
   - Makes sure everything is ready for the application to run

2. **.vscode/launch.json**
   - Contains the VSCode debugger configuration
   - Specifies the entry point (run.py)
   - Sets up environment variables
   - Links to the pre-launch task

3. **.vscode/tasks.json**
   - Defines the pre-launch task to run the setup script

## Troubleshooting

If you encounter issues with the debugger:

1. **MCP Server Not Starting**: Check the logs in the `logs` directory to see why the MCP server failed to start.

2. **Database Connection Issues**: Make sure the PostgreSQL container is running. You can check this with `docker ps`.

3. **Port Conflicts**: If port 5001 or 3333 is already in use, the setup script will attempt to free these ports, but might not succeed. You may need to manually kill processes using these ports.

4. **Environment Variables**: If the application isn't picking up environment variables correctly, check the `.env` file and verify that the setup script is modifying it correctly.

5. **Console Output**: Check the DEBUG CONSOLE panel in VSCode for any error messages or warnings that might explain the issue.
