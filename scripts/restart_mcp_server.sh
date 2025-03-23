#!/bin/bash

# Define paths
LOCKFILE="/tmp/ontology_mcp_server.lock"
SERVER_PATH="/home/chris/ai-ethical-dm/mcp/ontology_mcp_server.py"
LOG_PATH="/home/chris/ai-ethical-dm/mcp/server.log"

# Function to check if a process is running
is_process_running() {
    local pid=$1
    if [ -z "$pid" ]; then
        return 1  # Not running
    fi
    
    if ps -p "$pid" > /dev/null; then
        return 0  # Running
    else
        return 1  # Not running
    fi
}

# Function to clean up stale lock file
check_lock_file() {
    if [ -f "$LOCKFILE" ]; then
        echo "Lock file exists. Checking if process is still running..."
        local pid=$(cat "$LOCKFILE" 2>/dev/null)
        
        if is_process_running "$pid"; then
            echo "Process with PID $pid is still running."
        else
            echo "Stale lock file found. Removing it."
            rm -f "$LOCKFILE"
        fi
    fi
}

# Check for stale lock file
check_lock_file

# Find all PIDs of ontology_mcp_server.py
echo "Stopping all running instances of ontology_mcp_server.py..."
PIDS=$(ps aux | grep "ontology_mcp_server.py" | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "No running instances found."
else
    # Kill all found PIDs
    echo "Killing PIDs: $PIDS"
    for PID in $PIDS; do
        echo "$PID"
        kill -9 "$PID" 2>/dev/null
    done
    echo "All instances stopped."
fi

# Remove any existing lock file
rm -f "$LOCKFILE"

# Restart the server
echo "Restarting ontology_mcp_server.py..."
nohup python3 "$SERVER_PATH" > "$LOG_PATH" 2>&1 &
NEW_PID=$!

# Create a lock file with the PID
echo "$NEW_PID" > "$LOCKFILE"
echo "Server restarted with PID $NEW_PID and running in the background."
echo "Logs are being written to $LOG_PATH."
