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
        if hostname == 'proethica.org' or hostname.startswith('prod-'):
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

# Determine MCP server port - default to 5001 to match http_ontology_mcp_server.py
mcp_port = args.mcp_port
os.environ['MCP_SERVER_PORT'] = str(mcp_port)

# Set the MCP server URL environment variable
mcp_url = f"http://localhost:{mcp_port}"
os.environ['MCP_SERVER_URL'] = mcp_url
print(f"Set MCP_SERVER_URL to {mcp_url}")

# Log a clear message about MCP server port configuration
print(f"MCP server will be available at {mcp_url}")

# Check if we should skip starting the MCP server
if os.environ.get('SKIP_MCP_SERVER', '').lower() in ('true', '1', 'yes'):
    print("Skipping MCP server startup, using existing MCP server...")
    # Verify that the MCP server is already running
    mcp_running = False
    try:
        response = requests.get(f"{mcp_url}/api/guidelines/engineering-ethics", timeout=2)
        if response.status_code == 200:
            mcp_running = True
            print("Successfully connected to existing MCP server!")
        else:
            print(f"Warning: Existing MCP server returned status code {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Warning: Could not connect to existing MCP server: {e}")
        
    if not mcp_running:
        print("WARNING: Existing MCP server may not be running properly. Continuing anyway...")
else:
    # Restart the HTTP MCP server
    print("Starting the HTTP MCP server...")
    subprocess.run(["./scripts/restart_http_mcp_server.sh"], shell=True)

    # Wait for the MCP server to start with verification
    print("Waiting for the MCP server to start...")
    max_retries = 12  # 60 seconds total waiting time
    retry_interval = 5  # seconds
    mcp_running = False

    for i in range(max_retries):
        try:
            # Try to connect to the MCP server
            print(f"Attempt {i+1}/{max_retries} to connect to MCP server at {mcp_url}...")
            
            # Check if process is running
            ps_check = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            if "ontology_mcp_server.py" in ps_check.stdout:
                print("Found ontology_mcp_server.py process running")
                
                # Try to connect to the server API
                try:
                    requests.get(f"{mcp_url}/api/ping", timeout=2)
                    mcp_running = True
                    print("Successfully connected to MCP server API!")
                    break
                except requests.exceptions.ConnectionError:
                    print(f"MCP server process is running but API not responding yet")
            else:
                print("No ontology_mcp_server.py process found running")
                
            time.sleep(retry_interval)
        except Exception as e:
            print(f"Error checking MCP server: {str(e)}")
            time.sleep(retry_interval)

    if not mcp_running:
        print("WARNING: MCP server may not be running properly. Continuing anyway...")

# Create app instance with the detected environment
app = create_app(environment)

if __name__ == '__main__':
    print(f"Starting Flask server on port {args.port}...")
    app.run(host='0.0.0.0', port=args.port, debug=(environment == 'development'))
