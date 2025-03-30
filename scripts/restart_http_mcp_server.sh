#!/bin/bash

# Define paths
LOCKFILE="/tmp/http_ontology_mcp_server.lock"
SERVER_PATH="/home/chris/ai-ethical-dm/mcp/http_ontology_mcp_server.py"
LOG_PATH="/home/chris/ai-ethical-dm/mcp/http_server.log"
PORT=${MCP_SERVER_PORT:-5001}  # Use environment variable or default to 5001

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

# Find all running instances
echo "Stopping all running instances of HTTP MCP server..."

# Find by http_ontology_mcp_server.py
HTTP_PIDS=$(ps aux | grep "http_ontology_mcp_server.py" | grep -v grep | awk '{print $2}')

if [ -n "$HTTP_PIDS" ]; then
    echo "Killing HTTP MCP server PIDs: $HTTP_PIDS"
    for PID in $HTTP_PIDS; do
        echo "Killing HTTP MCP server PID: $PID"
        kill -9 "$PID" 2>/dev/null
    done
fi

# Also stop any ontology_mcp_server.py processes
ONTO_PIDS=$(ps aux | grep "ontology_mcp_server.py" | grep -v grep | awk '{print $2}')

if [ -n "$ONTO_PIDS" ]; then
    echo "Killing ontology_mcp_server.py PIDs: $ONTO_PIDS"
    for PID in $ONTO_PIDS; do
        echo "Killing ontology_mcp_server.py PID: $PID"
        kill -9 "$PID" 2>/dev/null
    done
fi

if [ -z "$HTTP_PIDS" ] && [ -z "$ONTO_PIDS" ]; then
    echo "No running instances found."
else
    echo "All instances stopped."
fi

# Remove any existing lock file
rm -f "$LOCKFILE"

# Create parent directory for log file if it doesn't exist
mkdir -p "$(dirname "$LOG_PATH")"

# Restart the server
echo "Starting HTTP MCP server on port $PORT..."
export MCP_SERVER_PORT=$PORT
echo "Setting MCP_SERVER_PORT=$PORT"

# Clear previous log
> "$LOG_PATH"

# Start the server
nohup python3 "$SERVER_PATH" > "$LOG_PATH" 2>&1 &
NEW_PID=$!

# Create a lock file with the PID
echo "$NEW_PID" > "$LOCKFILE"
echo "HTTP MCP server started with PID $NEW_PID and running in the background."
echo "Logs are being written to $LOG_PATH"

# Wait a moment and check if the server is still running
sleep 2
if is_process_running "$NEW_PID"; then
    echo "HTTP MCP server is running."
    
    # Print the first few lines of the log to check for errors
    echo "--- Log file contents ---"
    head -n 10 "$LOG_PATH"
    echo "--- End of log preview ---"
else
    echo "WARNING: HTTP MCP server may have failed to start. Check the log file for details."
    echo "--- Log file contents ---"
    cat "$LOG_PATH"
    echo "--- End of log file ---"
fi
