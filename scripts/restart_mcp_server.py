#!/usr/bin/env python3
"""
Script to restart the MCP server to ensure it recognizes domain ID changes.
"""
import os
import sys
import subprocess
import time

def restart_mcp_server():
    """
    Restart the MCP server to ensure it recognizes domain ID changes.
    """
    print("Restarting MCP server...")
    
    # Check if restart_http_mcp_server.sh exists
    restart_script = os.path.join('scripts', 'restart_http_mcp_server.sh')
    if not os.path.exists(restart_script):
        print(f"Error: MCP restart script not found at {restart_script}")
        return False
    
    try:
        # Make sure the script is executable
        subprocess.run(['chmod', '+x', restart_script], check=True)
        
        # Run the restart script
        print("Executing restart script...")
        result = subprocess.run(['./scripts/restart_http_mcp_server.sh'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True)
        
        print(f"Restart script exit code: {result.returncode}")
        if result.stdout:
            print(f"Output: {result.stdout}")
        if result.stderr:
            print(f"Errors: {result.stderr}")
            
        # Wait for the server to start up
        print("Waiting for MCP server to restart...")
        time.sleep(5)
        
        # Check if the server is running
        print("Checking if MCP server is running...")
        check_process = subprocess.run(['ps', 'aux'], 
                                      stdout=subprocess.PIPE, 
                                      text=True)
        
        if 'ontology_mcp_server' in check_process.stdout:
            print("MCP server is running.")
            return True
        else:
            print("Warning: MCP server process not found after restart.")
            return False
            
    except Exception as e:
        print(f"Error restarting MCP server: {str(e)}")
        return False

if __name__ == "__main__":
    restart_mcp_server()
