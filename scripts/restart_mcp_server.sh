#!/bin/bash

LOCKFILE="/tmp/ontology_mcp_server.lock"

# Check if the lock file exists
if [ -f "$LOCKFILE" ]; then
    echo "Another instance of ontology_mcp_server.py is already running. Exiting."
    exit 1
fi

# Create a lock file
touch "$LOCKFILE"

# Ensure the lock file is removed on script exit
trap "rm -f $LOCKFILE" EXIT

# Find all PIDs of ontology_mcp_server.py
echo "Stopping all running instances of ontology_mcp_server.py..."
PIDS=$(ps aux | grep "ontology_mcp_server.py" | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "No running instances found."
else
    # Kill all found PIDs
    echo "Killing PIDs: $PIDS"
    kill -9 $PIDS
    echo "All instances stopped."
fi

# Restart the server
echo "Restarting ontology_mcp_server.py..."
nohup python3 /home/chris/ai-ethical-dm/mcp/ontology_mcp_server.py > /home/chris/ai-ethical-dm/mcp/server.log 2>&1 &
echo "Server restarted and running in the background. Logs are being written to server.log."