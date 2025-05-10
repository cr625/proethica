import os
import argparse
import subprocess
import time
import requests
import socket
from app import create_app
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
if os.path.exists('.env'):
    load_dotenv()

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Run the AI Ethical DM application')
parser.add_argument('--port', type=int, default=3333, help='Port to run the server on')
parser.add_argument('--mcp-port', type=int, default=5001, help='Port for the MCP server')
parser.add_argument('--environment', type=str, help='Environment (development/production)')
args = parser.parse_args()

# Set environment based on argument or env variable, or detect from hostname/git branch
if args.environment:
    environment = args.environment
else:
    environment = os.environ.get('ENVIRONMENT')
    
    if not environment:
        # Try to detect from hostname
        hostname = socket.gethostname()
        # Define production hostnames - could be customized in the future
        production_hostnames = ['proethica.org', 'realm.ai', 'realm.org']
        if hostname in production_hostnames or hostname.startswith('prod-'):
            environment = 'production'
        else:
            # Try to detect from git branch
            try:
                import subprocess
                branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                              stderr=subprocess.DEVNULL).decode().strip()
                if branch in ['main', 'master']:
                    environment = 'production'
                else:
                    environment = 'development'
            except:
                environment = 'development'  # Default to development

print(f"Running in {environment.upper()} mode")

# Set environment variable
os.environ['ENVIRONMENT'] = environment

# Determine MCP server port - default to 5001 to match expected MCP server port
mcp_port = args.mcp_port
os.environ['MCP_SERVER_PORT'] = str(mcp_port)

# Set the MCP server URL environment variable
mcp_url = f"http://localhost:{mcp_port}"
os.environ['MCP_SERVER_URL'] = mcp_url
print(f"Set MCP_SERVER_URL to {mcp_url}")

# Log a clear message about MCP server port configuration
print(f"MCP server will be available at {mcp_url}")

# The enhanced MCP server is started by auto_run.sh before we run this script
print("Checking enhanced MCP server status...")
# Verify that the MCP server is already running
mcp_running = False
try:
    response = requests.get(f"{mcp_url}/api/guidelines/engineering-ethics", timeout=2)
    if response.status_code == 200:
        mcp_running = True
        print("Successfully connected to existing MCP server!")
    else:
        print(f"Warning: MCP server returned status code {response.status_code}")
except requests.exceptions.RequestException as e:
    print(f"Warning: Could not connect to MCP server: {e}")
    
if not mcp_running:
    print("WARNING: MCP server may not be running properly. Continuing anyway...")

# Create app instance with the detected environment
app = create_app(environment)

if __name__ == '__main__':
    print(f"Starting Flask server on port {args.port}...")
    app.run(host='0.0.0.0', port=args.port, debug=(environment == 'development'))
