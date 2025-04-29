#!/usr/bin/env python3
"""
Environment-aware MCP server manager.
This script loads environment-specific configuration and passes it to the MCP server.
"""

import os
import sys
import subprocess
import logging

# Add the project root directory to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import environment configuration
try:
    from config.environment import (
        ENVIRONMENT, MCP_SERVER_PORT, LOCK_FILE_PATH, 
        LOG_DIR, VERBOSE_LOGGING
    )
    logger.info(f"Loaded configuration for environment: {ENVIRONMENT}")
except ImportError:
    logger.error("Failed to import environment configuration.")
    ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')
    MCP_SERVER_PORT = os.environ.get('MCP_SERVER_PORT', 5001)
    LOCK_FILE_PATH = "./tmp/enhanced_mcp_server.lock" if ENVIRONMENT == 'development' else "/tmp/enhanced_mcp_server.lock"
    LOG_DIR = "./logs" if ENVIRONMENT == 'development' else "/var/log/proethica"
    VERBOSE_LOGGING = ENVIRONMENT == 'development'
    logger.warning(f"Using fallback configuration for environment: {ENVIRONMENT}")

# Create log directory if it doesn't exist
LOG_FILE = os.path.join(LOG_DIR, "enhanced_mcp_server.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def run_command(command, capture_output=True):
    """Run a shell command and return its output."""
    try:
        if VERBOSE_LOGGING:
            logger.info(f"Running command: {command}")
        result = subprocess.run(
            command, shell=True, check=False, 
            capture_output=capture_output, text=True
        )
        return result
    except subprocess.SubprocessError as e:
        logger.error(f"Error running command: {e}")
        return None

def is_port_in_use(port):
    """Check if the port is in use."""
    # Try lsof first
    result = run_command(f"lsof -i:{port} -sTCP:LISTEN")
    if result and result.returncode == 0 and result.stdout.strip():
        return True
    
    # Try netstat as fallback
    result = run_command(f"netstat -tuln | grep ':{port} '")
    if result and result.returncode == 0 and result.stdout.strip():
        return True
    
    return False

def stop_mcp_servers():
    """Stop all running MCP server processes."""
    logger.info("Stopping all running instances of MCP servers...")
    
    # Define patterns to search for
    patterns = [
        "python3 mcp/run_enhanced_mcp_server.py",
        "python mcp/run_enhanced_mcp_server.py",
        "http_ontology_mcp_server.py",
        "ontology_mcp_server.py"
    ]
    
    # Find and kill processes matching the patterns
    for pattern in patterns:
        pids_result = run_command(f"ps aux | grep '{pattern}' | grep -v grep | awk '{{print $2}}'")
        if pids_result and pids_result.stdout.strip():
            pids = pids_result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    logger.info(f"Killing process {pid} matching '{pattern}'")
                    run_command(f"kill -9 {pid}")
    
    # Use pkill as a backup method
    run_command("pkill -f 'run_enhanced_mcp_server.py'")
    run_command("pkill -f 'http_ontology_mcp_server.py'")
    run_command("pkill -f 'ontology_mcp_server.py'")
    
    # Give processes time to shut down
    import time
    time.sleep(2)
    
    # Check if the port is still in use
    if is_port_in_use(MCP_SERVER_PORT):
        logger.error(f"Port {MCP_SERVER_PORT} is still in use after stopping all known MCP processes")
        
        # Try to find what's using the port
        run_command(f"lsof -i:{MCP_SERVER_PORT} -sTCP:LISTEN", capture_output=False)
        run_command(f"netstat -tuln | grep ':{MCP_SERVER_PORT} '", capture_output=False)
        
        try_pid_command = f"fuser {MCP_SERVER_PORT}/tcp 2>/dev/null"
        pid_result = run_command(try_pid_command)
        if pid_result and pid_result.stdout.strip():
            using_pid = pid_result.stdout.strip()
            logger.error(f"Process ID using port {MCP_SERVER_PORT}: {using_pid}")
            run_command(f"ps -p {using_pid} -f", capture_output=False)
        
        return False
    
    return True

def check_lock_file():
    """Check and clean up stale lock file."""
    if os.path.exists(LOCK_FILE_PATH):
        logger.info(f"Lock file exists at {LOCK_FILE_PATH}. Checking if process is still running...")
        
        try:
            with open(LOCK_FILE_PATH, 'r') as f:
                pid = f.read().strip()
                
            if pid:
                # Check if process is running
                result = run_command(f"ps -p {pid}")
                if result and result.returncode == 0:
                    logger.info(f"Process with PID {pid} is still running")
                    return False
        except Exception as e:
            logger.warning(f"Error reading lock file: {e}")
        
        # If we get here, remove the stale lock file
        logger.info(f"Removing stale lock file: {LOCK_FILE_PATH}")
        try:
            os.remove(LOCK_FILE_PATH)
        except Exception as e:
            logger.error(f"Failed to remove lock file: {e}")
            return False
    
    return True

def start_mcp_server():
    """Start the enhanced MCP server."""
    # Ensure the directory for the lock file exists
    lock_dir = os.path.dirname(LOCK_FILE_PATH)
    if lock_dir and not os.path.exists(lock_dir):
        os.makedirs(lock_dir, exist_ok=True)
    
    # Start the server
    server_script = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        "mcp", "run_enhanced_mcp_server.py"
    ))
    
    logger.info(f"Starting enhanced MCP server on port {MCP_SERVER_PORT}")
    os.environ['MCP_SERVER_PORT'] = str(MCP_SERVER_PORT)
    
    # Make sure the script exists
    if not os.path.exists(server_script):
        logger.error(f"Server script not found: {server_script}")
        return False
    
    # Start the server as a background process
    command = f"python3 {server_script} > {LOG_FILE} 2>&1 &"
    run_command(command)
    
    # Get the PID
    time.sleep(1)  # Give it a moment to start
    pid_result = run_command(f"ps aux | grep '{server_script}' | grep -v grep | awk '{{print $2}}'")
    if not pid_result or not pid_result.stdout.strip():
        logger.error("Failed to get PID of the MCP server process")
        return False
    
    pid = pid_result.stdout.strip().split('\n')[0]  # Take first PID if multiple
    logger.info(f"Enhanced MCP server started with PID {pid}")
    
    # Create a lock file with the PID
    try:
        with open(LOCK_FILE_PATH, 'w') as f:
            f.write(pid)
    except Exception as e:
        logger.error(f"Failed to create lock file: {e}")
    
    # Wait for the server to initialize
    max_wait = 15
    counter = 0
    while counter < max_wait:
        time.sleep(1)
        counter += 1
        
        # Check if the process is still running
        result = run_command(f"ps -p {pid}")
        if result and result.returncode != 0:
            logger.error("Enhanced MCP server process terminated")
            logger.error("Check the log file for details:")
            run_command(f"tail -n 20 {LOG_FILE}", capture_output=False)
            return False
        
        # Check if the server is listening on the port
        if is_port_in_use(MCP_SERVER_PORT):
            logger.info(f"Port {MCP_SERVER_PORT} is now active. Checking API responsiveness...")
            
            # Give the API a moment to fully initialize
            time.sleep(1)
            
            # Check if the API is responsive
            api_result = run_command(f"curl -s --max-time 2 'http://localhost:{MCP_SERVER_PORT}/api/guidelines/engineering_ethics'")
            if api_result and api_result.returncode == 0:
                logger.info("✅ Server is fully initialized and API is responsive")
                break
            else:
                logger.info("Port is open but API is not yet responsive. Waiting...")
        else:
            logger.info(f"Waiting for server to start listening on port {MCP_SERVER_PORT}... ({counter}/{max_wait})")
        
        # If we've reached the maximum wait time, exit with an error
        if counter == max_wait:
            logger.error("⚠️ ERROR: Timed out waiting for server to initialize")
            logger.error(f"Server process is running but not listening on port {MCP_SERVER_PORT}")
            logger.error("Check the log file for details:")
            run_command(f"tail -n 20 {LOG_FILE}", capture_output=False)
            return False
    
    # Display server status
    logger.info(f"Enhanced MCP server is running and listening on port {MCP_SERVER_PORT}")
    logger.info(f"Process ID: {pid}")
    
    # Check the log file for any startup information
    logger.info("--- Log file preview ---")
    run_command(f"tail -n 10 {LOG_FILE}", capture_output=False)
    logger.info("--- End of log preview ---")
    
    # Verify API access
    logger.info("Verifying API access...")
    api_result = run_command(f"curl -s 'http://localhost:{MCP_SERVER_PORT}/api/guidelines/engineering_ethics'")
    if api_result and api_result.returncode == 0:
        logger.info("✅ API is accessible")
        logger.info(f"Response: {api_result.stdout[:100]}..." if len(api_result.stdout) > 100 else f"Response: {api_result.stdout}")
    else:
        logger.warning("⚠️ WARNING: API verification failed, but server is running")
    
    logger.info("Enhanced MCP server has been successfully started")
    logger.info(f"Log file: {LOG_FILE}")
    
    return True

def restart_mcp_server():
    """Stop and restart the MCP server."""
    logger.info(f"Restarting MCP server for environment: {ENVIRONMENT}")
    logger.info(f"Using configuration: PORT={MCP_SERVER_PORT}, LOCK_FILE={LOCK_FILE_PATH}, LOG_FILE={LOG_FILE}")
    
    check_lock_file()
    if not stop_mcp_servers():
        logger.error("Failed to stop existing MCP servers. Please resolve port conflicts manually.")
        return False
        
    return start_mcp_server()

if __name__ == "__main__":
    # Add console output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if restart_mcp_server():
        sys.exit(0)
    else:
        sys.exit(1)
