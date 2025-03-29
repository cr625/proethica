import os
import argparse
import subprocess
import time
from app import create_app

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Run the AI Ethical DM application')
parser.add_argument('--port', type=int, default=3333, help='Port to run the server on')
args = parser.parse_args()

# Restart the MCP server
print("Restarting the MCP server...")
subprocess.run(["./scripts/restart_mcp_server.sh"], shell=True)

# Wait for the MCP server to start
print("Waiting for the MCP server to start...")
time.sleep(5)  # Increased wait time to ensure MCP server is fully initialized

# Set the MCP server URL environment variable - MCP server runs on port 5000
os.environ['MCP_SERVER_URL'] = "http://localhost:5000"
print(f"Set MCP_SERVER_URL to {os.environ['MCP_SERVER_URL']}")

# Note: The web app will run on port 3333 by default, but the MCP server will still run on port 5000

# Create app instance
app = create_app(os.getenv('FLASK_ENV', 'default'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=args.port, debug=True)
