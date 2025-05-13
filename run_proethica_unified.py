#!/usr/bin/env python3
"""
ProEthica Unified Runner for GitHub Codespaces
==============================================

This script provides a unified launcher for the ProEthica application
that restores the main UI functionality while incorporating the debug
interfaces added for the GitHub Codespaces environment.

It properly configures database connections, MCP server integration,
and runs the full Flask application with all features intact.
"""

import os
import sys
import json
import logging
import argparse
import requests
import subprocess
import time
from pathlib import Path
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define color codes for terminal output
GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'
BLUE = '\033[0;34m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

# Load environment variables
if os.path.exists('.env'):
    logger.info("Loading environment from .env file")
    load_dotenv()
else:
    logger.warning("No .env file found. Using default environment variables.")

def colorize(text, color):
    """Add color to terminal output"""
    return f"{color}{text}{NC}"

def detect_environment():
    """Detect the current environment (codespace, wsl, development)"""
    if os.environ.get("CODESPACES") == "true":
        return "codespace"
    elif os.path.exists('/proc/version'):
        with open('/proc/version', 'r') as f:
            version_info = f.read().lower()
            if 'microsoft' in version_info:
                return "wsl"
    return "development"

def check_database_connection(db_url):
    """Test database connection"""
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return True, version
    except Exception as e:
        return False, str(e)

def check_mcp_server(url, retry=3, delay=2):
    """Check if MCP server is running and responding"""
    logger.info(f"Checking MCP server at {url}...")
    
    for attempt in range(retry):
        try:
            # Try JSON-RPC endpoint
            response = requests.post(
                f"{url}/jsonrpc",
                json={"jsonrpc": "2.0", "method": "list_tools", "params": {}, "id": 1},
                timeout=5
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "result" in data:
                        tools = data.get("result", {}).get("tools", [])
                        return True, f"Connected to MCP server with {len(tools)} tools"
                except json.JSONDecodeError:
                    logger.warning(f"MCP server returned non-JSON response: {response.text[:50]}...")
                    
            logger.warning(f"Attempt {attempt+1}/{retry}: MCP server returned status code {response.status_code}")
            
        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt+1}/{retry}: Failed to connect to MCP server: {e}")
        
        if attempt < retry - 1:
            logger.info(f"Retrying in {delay} seconds...")
            time.sleep(delay)
    
    return False, "Failed to connect to MCP server after multiple attempts"

def fix_circular_imports():
    """Apply circular import fixes if needed"""
    if os.path.exists("fix_circular_import.py"):
        logger.info("Applying circular import fixes...")
        try:
            subprocess.run([sys.executable, "fix_circular_import.py"], check=True)
            logger.info("Successfully applied circular import fixes")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply circular import fixes: {e}")
    else:
        logger.warning("fix_circular_import.py not found, skipping circular import fixes")
    return False

def run_flask_app():
    """Run the Flask application using the proper runner"""
    logger.info("Starting Flask application...")
    
    # Import the application (after fixes are applied)
    try:
        from app import create_app
        environment = os.environ.get('ENVIRONMENT', 'development')
        app = create_app(environment)
        
        port = int(os.environ.get('PORT', 3333))
        debug = environment != 'production'
        
        logger.info(f"Starting Flask server on port {port} in {environment.upper()} mode...")
        app.run(host='0.0.0.0', port=port, debug=debug)
        
    except ImportError as e:
        logger.error(f"Failed to import application: {e}")
        logger.error("This may indicate unresolved circular imports or missing dependencies.")
        return False
    
    except Exception as e:
        logger.error(f"Failed to run Flask application: {e}")
        return False
    
    return True

def setup_environment():
    """Set up environment variables and configuration"""
    env = detect_environment()
    logger.info(f"Detected environment: {env}")
    
    # Set environment in .env file and os.environ
    os.environ['ENVIRONMENT'] = env
    
    # Set appropriate database URL based on environment
    if env == "codespace":
        db_url = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
        mcp_url = "http://localhost:5001"
    else:
        db_url = os.environ.get('DATABASE_URL', "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm")
        mcp_url = os.environ.get('MCP_SERVER_URL', "http://localhost:5001")
    
    # Update environment variables
    os.environ['DATABASE_URL'] = db_url
    os.environ['MCP_SERVER_URL'] = mcp_url
    os.environ['SQLALCHEMY_DATABASE_URI'] = db_url
    
    # Update .env file if it exists
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            env_content = f.read()
        
        # Update DATABASE_URL
        if 'DATABASE_URL=' in env_content:
            env_content = '\n'.join([
                line if not line.startswith('DATABASE_URL=') else f'DATABASE_URL={db_url}'
                for line in env_content.split('\n')
            ])
        else:
            env_content += f'\nDATABASE_URL={db_url}'
            
        # Update MCP_SERVER_URL
        if 'MCP_SERVER_URL=' in env_content:
            env_content = '\n'.join([
                line if not line.startswith('MCP_SERVER_URL=') else f'MCP_SERVER_URL={mcp_url}'
                for line in env_content.split('\n')
            ])
        else:
            env_content += f'\nMCP_SERVER_URL={mcp_url}'
            
        # Update ENVIRONMENT
        if 'ENVIRONMENT=' in env_content:
            env_content = '\n'.join([
                line if not line.startswith('ENVIRONMENT=') else f'ENVIRONMENT={env}'
                for line in env_content.split('\n')
            ])
        else:
            env_content += f'\nENVIRONMENT={env}'
        
        # Write updated .env file
        with open('.env', 'w') as f:
            f.write(env_content)
    
    return env, db_url, mcp_url

def check_prerequisites():
    """Check if prerequisites are met for running the application"""
    prerequisites_met = True
    
    # Check Python version
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 9):
        logger.warning(f"Python version {python_version.major}.{python_version.minor}.{python_version.micro} may be too old. Recommended: 3.9+")
        prerequisites_met = False
    
    # Check key packages
    try:
        import flask
        import sqlalchemy
        import psycopg2
    except ImportError as e:
        logger.error(f"Missing required package: {e}")
        prerequisites_met = False
    
    return prerequisites_met

def ensure_debug_route():
    """Make sure the debug route is added to the Flask app"""
    # Check if debug_routes.py exists
    debug_routes_path = Path("app/routes/debug_routes.py")
    
    if not debug_routes_path.exists():
        logger.info("Creating debug_routes.py...")
        
        debug_routes_content = """
from flask import Blueprint, render_template, current_app, jsonify, request
import psycopg2
import json
import os
import requests
import sys
import platform

debug_bp = Blueprint('debug', __name__)

@debug_bp.route('/debug')
def debug():
    \"\"\"Debug page with system information\"\"\"
    
    # Get environment variables
    env_vars = {}
    for key in ['FLASK_APP', 'FLASK_ENV', 'DATABASE_URL', 'MCP_SERVER_URL', 
               'ENVIRONMENT', 'USE_AGENT_ORCHESTRATOR']:
        env_vars[key] = os.environ.get(key, 'Not set')
    
    # Get database status
    db_status = {}
    try:
        conn = psycopg2.connect(current_app.config['SQLALCHEMY_DATABASE_URI'])
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_status['version'] = cursor.fetchone()[0]
        
        # Get table counts
        cursor.execute(\"\"\"
            SELECT table_name, (SELECT count(*) FROM information_schema.columns 
                               WHERE table_name=t.table_name) AS columns
            FROM information_schema.tables t
            WHERE table_schema='public'
            ORDER BY table_name;
        \"\"\")
        db_status['tables'] = cursor.fetchall()
        db_status['status'] = 'Connected'
        
        cursor.close()
        conn.close()
    except Exception as e:
        db_status['status'] = f"Error: {str(e)}"
    
    # Get MCP server status
    mcp_status = {}
    try:
        response = requests.post(
            current_app.config['MCP_SERVER_URL'] + '/jsonrpc',
            json={"jsonrpc": "2.0", "method": "list_tools", "params": {}, "id": 1},
            timeout=2
        )
        
        try:
            data = json.loads(response.text)
            tools = data.get("result", {}).get("tools", [])
            mcp_status['status'] = 'Connected'
            mcp_status['tools'] = tools
        except json.JSONDecodeError as e:
            mcp_status['status'] = f"Connected but JSON error: {str(e)}"
            mcp_status['raw_response'] = response.text[:100] + '...'
    except Exception as e:
        mcp_status['status'] = f"Error: {str(e)}"
    
    # System information
    sys_info = {
        'python_version': sys.version,
        'platform': platform.platform(),
        'hostname': platform.node()
    }
    
    return render_template('debug/status.html', 
                          env_vars=env_vars,
                          db_status=db_status,
                          mcp_status=mcp_status,
                          sys_info=sys_info)
"""
        
        os.makedirs(os.path.dirname(debug_routes_path), exist_ok=True)
        with open(debug_routes_path, 'w') as f:
            f.write(debug_routes_content)
        
        logger.info("Created debug routes file")
    
    # Check if debug template exists
    template_dir = Path("app/templates/debug")
    template_path = template_dir / "status.html"
    
    if not template_path.exists():
        logger.info("Creating debug template...")
        
        template_content = """
{% extends 'base.html' %}

{% block title %}System Status{% endblock %}

{% block content %}
<div class="container">
    <div class="row mb-4">
        <div class="col">
            <h1>ProEthica System Status</h1>
            <a href="{{ url_for('main.index') }}" class="btn btn-primary mb-3">Back to Home</a>
            
            <h3>Environment</h3>
            <div class="card mb-4">
                <div class="card-body">
                    <table class="table table-striped">
                        <thead>
                            <tr>
                                <th>Variable</th>
                                <th>Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for key, value in env_vars.items() %}
                            <tr>
                                <td>{{ key }}</td>
                                <td>{{ value }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <h3>Database Status</h3>
            <div class="card mb-4">
                <div class="card-body">
                    {% if db_status.status == 'Connected' %}
                        <div class="alert alert-success">
                            <strong>Connected</strong> - {{ db_status.version }}
                        </div>
                        
                        <h5>Tables</h5>
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>Table Name</th>
                                    <th>Columns</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for table_name, column_count in db_status.tables %}
                                <tr>
                                    <td>{{ table_name }}</td>
                                    <td>{{ column_count }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    {% else %}
                        <div class="alert alert-danger">
                            {{ db_status.status }}
                        </div>
                    {% endif %}
                </div>
            </div>

            <h3>MCP Server Status</h3>
            <div class="card mb-4">
                <div class="card-body">
                    {% if mcp_status.status == 'Connected' %}
                        <div class="alert alert-success">
                            <strong>Connected</strong>
                        </div>
                        
                        <h5>Available Tools</h5>
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>Tool</th>
                                    <th>Description</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for tool in mcp_status.tools %}
                                <tr>
                                    <td>{{ tool.name }}</td>
                                    <td>{{ tool.description }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    {% else %}
                        <div class="alert alert-danger">
                            {{ mcp_status.status }}
                        </div>
                        {% if mcp_status.raw_response %}
                        <pre>{{ mcp_status.raw_response }}</pre>
                        {% endif %}
                    {% endif %}
                </div>
            </div>
            
            <h3>System Information</h3>
            <div class="card mb-4">
                <div class="card-body">
                    <table class="table table-striped">
                        <tbody>
                            {% for key, value in sys_info.items() %}
                            <tr>
                                <th>{{ key|title }}</th>
                                <td>{{ value }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""
        
        os.makedirs(template_dir, exist_ok=True)
        with open(template_path, 'w') as f:
            f.write(template_content)
        
        logger.info("Created debug template")
    
    # Ensure debug blueprint is registered in the app
    app_init_path = Path("app/__init__.py")
    
    if app_init_path.exists():
        with open(app_init_path, 'r') as f:
            app_init_content = f.read()
        
        if 'debug_bp' not in app_init_content:
            logger.info("Ensuring debug blueprint is registered...")
            
            # Find the right place to insert the import
            lines = app_init_content.split('\n')
            import_index = -1
            register_index = -1
            
            for i, line in enumerate(lines):
                if 'import' in line and 'Blueprint' in line:
                    import_index = i
                if 'register_blueprint' in line:
                    register_index = i
            
            if import_index >= 0 and register_index >= 0:
                # Add import
                lines.insert(import_index + 1, "from app.routes.debug_routes import debug_bp")
                
                # Add registration
                lines.insert(register_index + 1, "    app.register_blueprint(debug_bp)")
                
                # Write updated content
                with open(app_init_path, 'w') as f:
                    f.write('\n'.join(lines))
                
                logger.info("Registered debug blueprint in app/__init__.py")

def start_enhanced_mcp_server():
    """Start the enhanced MCP server with guidelines support"""
    logger.info("Starting enhanced MCP server with guidelines support...")
    
    # Path to the server script
    script_path = Path("mcp/run_enhanced_mcp_server_with_guidelines.py")
    
    if not script_path.exists():
        logger.warning(f"Enhanced MCP server script not found at {script_path}")
        return False, "Script not found"
    
    # Make the script executable
    os.chmod(script_path, 0o755)
    
    # Port to use
    port = 5001
    
    # Create logs directory
    os.makedirs("logs", exist_ok=True)
    logfile = f"logs/enhanced_mcp_server_{time.strftime('%Y%m%d_%H%M%S')}.log"
    
    # Start the server in the background
    cmd = [sys.executable, str(script_path)]
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=open(logfile, 'w'),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        
        # Wait briefly to see if it starts
        time.sleep(3)
        
        # Check if the process is still running
        if process.poll() is None:
            logger.info(f"MCP server started with PID {process.pid}")
            return True, process.pid
        else:
            logger.error(f"MCP server failed to start. Exit code: {process.returncode}")
            with open(logfile, 'r') as f:
                logger.error(f"Last 10 lines of log:\n{f.readlines()[-10:]}")
            return False, f"Process exited with code {process.returncode}"
            
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        return False, str(e)

def fix_json_rpc_issues():
    """Apply fixes for JSON-RPC endpoint issues"""
    if Path("fix_mcp_endpoint_json.py").exists():
        logger.info("Applying MCP endpoint JSON fixes...")
        try:
            subprocess.run([sys.executable, "fix_mcp_endpoint_json.py"], check=True)
            logger.info("MCP endpoint JSON fixes applied")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply MCP endpoint JSON fixes: {e}")
    return False

def main():
    """Main function to run the ProEthica application"""
    print(colorize("=== ProEthica Unified Runner ===", BLUE))
    print(colorize("Restoring full UI functionality with debug support", GREEN))
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Run the ProEthica application with restored UI')
    parser.add_argument('--port', type=int, default=3333, help='Port to run the server on')
    parser.add_argument('--skip-mcp', action='store_true', help='Skip starting the MCP server')
    parser.add_argument('--debug-only', action='store_true', help='Only run the debug interface')
    args = parser.parse_args()
    
    # Set up environment
    env, db_url, mcp_url = setup_environment()
    
    # Check prerequisites
    if not check_prerequisites():
        logger.warning("Some prerequisites are not met. The application may not run correctly.")
    
    # Fix circular imports
    fix_circular_imports()
    
    # Fix MCP JSON-RPC issues
    fix_json_rpc_issues()
    
    # Check database connection
    db_ok, db_msg = check_database_connection(db_url)
    if db_ok:
        logger.info(f"Database connection successful: {db_msg}")
    else:
        logger.error(f"Database connection failed: {db_msg}")
    
    # Start MCP server if needed
    if not args.skip_mcp:
        mcp_ok, mcp_details = check_mcp_server(mcp_url)
        if not mcp_ok:
            logger.warning(f"MCP server not running or not responding. Starting MCP server...")
            mcp_started, mcp_result = start_enhanced_mcp_server()
            if mcp_started:
                logger.info(f"MCP server started successfully: PID {mcp_result}")
            else:
                logger.error(f"Failed to start MCP server: {mcp_result}")
    
    # Ensure debug route exists
    ensure_debug_route()
    
    # Run the Flask application
    if args.debug_only:
        logger.info("Running in debug-only mode. Full UI will be disabled.")
        from run_ui_app import app
        app.run(host='0.0.0.0', port=args.port, debug=True)
    else:
        run_flask_app()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
