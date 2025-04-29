#!/bin/bash
# Enhanced restart script for the MCP ontology server
# Improved to handle port conflicts and ensure clean server restarts

# Configuration
LOCKFILE="/tmp/enhanced_mcp_server.lock"
LOG_FILE="$(pwd)/mcp/enhanced_server.log"
PORT=${MCP_SERVER_PORT:-5001}  # Use environment variable or default to 5001
SERVER_SCRIPT="$(pwd)/mcp/run_enhanced_mcp_server.py"
MAX_WAIT=15  # Maximum seconds to wait for server to start

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

# Function to check if port is in use
is_port_in_use() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -i:"$PORT" -sTCP:LISTEN >/dev/null 2>&1
        return $?
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tuln | grep ":$PORT " >/dev/null 2>&1
        return $?
    else
        # Fallback to a direct socket test if neither lsof nor netstat is available
        (echo > /dev/tcp/127.0.0.1/$PORT) >/dev/null 2>&1
        return $?
    fi
}

# Function to check if the API is responsive
is_api_responsive() {
    # Try to access a simple endpoint
    if command -v curl >/dev/null 2>&1; then
        curl -s --max-time 2 "http://localhost:$PORT/api/guidelines/engineering_ethics" >/dev/null
        return $?
    elif command -v wget >/dev/null 2>&1; then
        wget -q --timeout=2 -O /dev/null "http://localhost:$PORT/api/guidelines/engineering_ethics" >/dev/null 2>&1
        return $?
    else
        # If neither curl nor wget is available, assume it's responsive if the port is open
        return 0
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

# Create log directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Add timestamp to log file
echo "=======================================" >> "$LOG_FILE"
echo "MCP Server Restart - $(date)" >> "$LOG_FILE"
echo "=======================================" >> "$LOG_FILE"

# Use a temp file for the current session's output
TEMP_LOG=$(mktemp)

# Redirect output to both console and log files
exec > >(tee -a "$TEMP_LOG") 2>&1

echo "========================================"
echo "MCP Server Restart - $(date)"
echo "========================================"

# Check for stale lock file
check_lock_file

# Stop all existing MCP server processes
echo "Stopping all running instances of MCP servers..."

# Array of patterns to search for
PATTERNS=(
    "python3 mcp/run_enhanced_mcp_server.py"
    "python mcp/run_enhanced_mcp_server.py"
    "http_ontology_mcp_server.py"
    "ontology_mcp_server.py"
)

# Kill all processes matching the patterns
for PATTERN in "${PATTERNS[@]}"; do
    PIDS=$(ps aux | grep "$PATTERN" | grep -v grep | awk '{print $2}')
    if [ -n "$PIDS" ]; then
        echo "Killing processes matching '$PATTERN': $PIDS"
        for PID in $PIDS; do
            echo "Killing PID: $PID"
            kill -9 "$PID" 2>/dev/null || true
        done
    fi
done

# Alternatively, use pkill with multiple patterns
echo "Using pkill as a backup method..."
pkill -f "run_enhanced_mcp_server.py" || true
pkill -f "http_ontology_mcp_server.py" || true
pkill -f "ontology_mcp_server.py" || true

# Give processes time to shut down
sleep 2

# Check if port is still in use
if is_port_in_use; then
    echo "ERROR: Port $PORT is still in use after stopping all known MCP processes."
    echo "Attempting to find process using port $PORT..."
    
    if command -v lsof >/dev/null 2>&1; then
        echo "Process using port $PORT:"
        lsof -i:"$PORT" -sTCP:LISTEN
    elif command -v netstat >/dev/null 2>&1; then
        echo "Process using port $PORT:"
        netstat -tuln | grep ":$PORT "
        
        if command -v fuser >/dev/null 2>&1; then
            USING_PID=$(fuser $PORT/tcp 2>/dev/null)
            if [ -n "$USING_PID" ]; then
                echo "Process ID using port $PORT: $USING_PID"
                echo "Process details:"
                ps -p "$USING_PID" -f
            fi
        fi
    fi
    
    echo "Please manually stop the process using port $PORT before continuing."
    echo "You can use: sudo kill \$(lsof -t -i:$PORT) or sudo kill \$(fuser $PORT/tcp)"
    # Append this session's output to the main log file
    cat "$TEMP_LOG" >> "$LOG_FILE"
    rm "$TEMP_LOG"
    exit 1
fi

# Remove any existing lock file
rm -f "$LOCKFILE"

# Start the enhanced MCP server
echo "Starting enhanced MCP server on port $PORT..."
export MCP_SERVER_PORT=$PORT
echo "Setting MCP_SERVER_PORT=$PORT"

# Start the server
python3 "$SERVER_SCRIPT" > "$LOG_FILE" 2>&1 &
NEW_PID=$!

# Create a lock file with the PID
echo "$NEW_PID" > "$LOCKFILE"
echo "Enhanced MCP server started with PID $NEW_PID"

# Wait for the server to initialize and start listening on the port
echo "Waiting for server to initialize and start listening on port $PORT..."
COUNTER=0
while [ $COUNTER -lt $MAX_WAIT ]; do
    sleep 1
    COUNTER=$((COUNTER + 1))
    
    # Check if the process is still running
    if ! is_process_running "$NEW_PID"; then
        echo "⚠️ ERROR: Enhanced MCP server process terminated."
        echo "Check the log file for details:"
        echo "--- Last lines of log file ---"
        tail -n 20 "$LOG_FILE"
        echo "--- End of log file ---"
        # Append this session's output to the main log file
        cat "$TEMP_LOG" >> "$LOG_FILE"
        rm "$TEMP_LOG"
        exit 1
    fi
    
    # Check if the server is listening on the port
    if is_port_in_use; then
        echo "Port $PORT is now active. Checking API responsiveness..."
        
        # Give the API a moment to fully initialize
        sleep 1
        
        # Check if the API is responsive
        if is_api_responsive; then
            echo "✅ Server is fully initialized and API is responsive."
            break
        else
            echo "Port is open but API is not yet responsive. Waiting..."
        fi
    else
        echo "Waiting for server to start listening on port $PORT... ($COUNTER/$MAX_WAIT)"
    fi
    
    # If we've reached the maximum wait time, exit with an error
    if [ $COUNTER -eq $MAX_WAIT ]; then
        echo "⚠️ ERROR: Timed out waiting for server to initialize."
        echo "Server process is running but not listening on port $PORT."
        echo "Check the log file for details:"
        echo "--- Last lines of log file ---"
        tail -n 20 "$LOG_FILE"
        echo "--- End of log file ---"
        # Append this session's output to the main log file
        cat "$TEMP_LOG" >> "$LOG_FILE"
        rm "$TEMP_LOG"
        exit 1
    fi
done

# Display server status
echo "Enhanced MCP server is running and listening on port $PORT."
echo "Process ID: $NEW_PID"

# Check the log file for any startup information
echo "--- Log file preview ---"
tail -n 10 "$LOG_FILE" 
echo "--- End of log preview ---"

# Verify API access
echo "Verifying API access..."
API_RESPONSE=$(curl -s "http://localhost:$PORT/api/guidelines/engineering_ethics" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "✅ API is accessible."
    echo "Response: $API_RESPONSE"
else
    echo "⚠️ WARNING: API verification failed, but server is running."
fi

echo "Enhanced MCP server has been successfully restarted."
echo "Log file: $LOG_FILE"

# Append this session's output to the main log file
cat "$TEMP_LOG" >> "$LOG_FILE"
rm "$TEMP_LOG"
