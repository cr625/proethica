import os
import argparse
import subprocess
import time
import requests
import socket
from app import create_app
from dotenv import load_dotenv

# Load environment variables - shared config first, then local overrides
# This ensures consistent LLM API keys across all applications
shared_env_path = os.path.join(os.path.dirname(__file__), '..', 'shared', '.env')
if os.path.exists(shared_env_path):
    load_dotenv(shared_env_path)
    print(f"✅ Loaded shared environment config: {shared_env_path}")

# Load local .env for application-specific overrides
if os.path.exists('.env'):
    load_dotenv(override=False)  # Don't override shared config
    print(f"✅ Loaded local environment config: .env")

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

# Determine MCP server settings
mcp_port = int(os.environ.get('MCP_SERVER_PORT', args.mcp_port))
os.environ['MCP_SERVER_PORT'] = str(mcp_port)

# Respect pre-set MCP_SERVER_URL (e.g., Docker compose: http://mcp:5001)
mcp_url = os.environ.get('MCP_SERVER_URL') or f"http://localhost:{mcp_port}"
os.environ['MCP_SERVER_URL'] = mcp_url
print(f"MCP_SERVER_URL set to {mcp_url}")

# Log a clear message about MCP server port configuration
print(f"MCP server will be available at {mcp_url}")

# Check MCP server availability with retry logic for compound launches
print("Checking enhanced MCP server status...")
mcp_running = False
max_retries = 10
retry_delay = 1

for attempt in range(max_retries):
    try:
        test_url = f"{mcp_url}/api/guidelines/engineering-ethics"
        if attempt == 0:
            print(f"Testing connection to MCP server at {test_url}...")
        response = requests.get(test_url, timeout=2)
        if response.status_code == 200:
            mcp_running = True
            print("✅ Successfully connected to MCP server!")
            break
        else:
            print(f"⚠️  MCP server returned status code {response.status_code}")
    except requests.exceptions.RequestException as e:
        if attempt < max_retries - 1:
            print(f"🔄 Waiting for MCP server... (attempt {attempt + 1}/{max_retries})")
            time.sleep(retry_delay)
        else:
            print(f"⚠️  Could not connect to MCP server after {max_retries} attempts: {e}")
    
if not mcp_running:
    print("⚠️  MCP server connection failed - some features may be limited. Flask app will continue...")

# Create app instance with the proper configuration module
app = create_app('config')

if __name__ == '__main__':
    print(f"Starting Flask server on port {args.port}...")
    
    # Start the Flask development server
    try:
        app.run(
            host='0.0.0.0',
            port=args.port,
            debug=(environment == 'development'),
            use_reloader=False  # Disable reloader to avoid conflicts with debugger
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error starting server: {e}")
        raise
