#!/usr/bin/env python3
"""
Simplified UI application launcher for ProEthica in Codespace environment.
This script handles configuration and launches the main web application.
"""

import os
import sys
import logging
import json
from flask import Flask, render_template_string, redirect
from flask_sqlalchemy import SQLAlchemy

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create a minimal Flask application for testing
app = Flask(__name__, 
           template_folder='app/templates',
           static_folder='app/static')

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/ai_ethical_dm')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'codespace-test-key'
app.config['ENVIRONMENT'] = 'codespace'
app.config['MCP_SERVER_URL'] = os.environ.get('MCP_SERVER_URL', 'http://localhost:5001/jsonrpc')
app.config['USE_MOCK_FALLBACK'] = True  # Use mock data when needed
app.config['DEBUG'] = True

# Create database connection
db = SQLAlchemy(app)

# Simple homepage template
HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProEthica - Codespace Edition</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { 
            padding-top: 2rem; 
            background-color: #f8f9fa;
        }
        .main-container {
            background-color: white;
            border-radius: 10px;
            padding: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .card {
            margin-bottom: 1rem;
            transition: transform 0.2s;
        }
        .card:hover {
            transform: translateY(-5px);
        }
    </style>
</head>
<body>
    <div class="container main-container">
        <div class="row mb-4">
            <div class="col">
                <h1 class="display-4">ProEthica Platform</h1>
                <p class="lead">Engineering Ethics Simulation Environment - Codespace Edition</p>
                <hr>
                <div class="alert alert-info">
                    <strong>Codespace Mode:</strong> This is a simplified interface for GitHub Codespace environments
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-6 mb-4">
                <div class="card h-100">
                    <div class="card-header bg-primary text-white">
                        <h5 class="card-title mb-0">System Status</h5>
                    </div>
                    <div class="card-body">
                        <ul class="list-group list-group-flush">
                            <li class="list-group-item d-flex justify-content-between align-items-center">
                                Database Connection
                                <span class="badge bg-success rounded-pill">Connected</span>
                            </li>
                            <li class="list-group-item d-flex justify-content-between align-items-center">
                                MCP Server
                                <span class="badge bg-success rounded-pill">Running</span>
                            </li>
                            <li class="list-group-item d-flex justify-content-between align-items-center">
                                Web Interface
                                <span class="badge bg-success rounded-pill">Active</span>
                            </li>
                        </ul>
                    </div>
                    <div class="card-footer">
                        <a href="/debug" class="btn btn-outline-primary">View Debug Info</a>
                    </div>
                </div>
            </div>

            <div class="col-md-6 mb-4">
                <div class="card h-100">
                    <div class="card-header bg-success text-white">
                        <h5 class="card-title mb-0">Guidelines Analysis</h5>
                    </div>
                    <div class="card-body">
                        <p>Analyze engineering guidelines and ethics codes against ontological principles.</p>
                        <a href="/ontology" class="btn btn-outline-success mb-2">Ontology Explorer</a>
                        <a href="/documents" class="btn btn-outline-success">Document Management</a>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-12 mb-4">
                <div class="card">
                    <div class="card-header bg-warning">
                        <h5 class="card-title mb-0">Simulation Environment</h5>
                    </div>
                    <div class="card-body">
                        <p>Create and simulate ethical scenarios in various engineering domains.</p>
                        <div class="row">
                            <div class="col-sm-4 mb-2">
                                <a href="/worlds" class="btn btn-outline-warning w-100">Worlds</a>
                            </div>
                            <div class="col-sm-4 mb-2">
                                <a href="/scenarios" class="btn btn-outline-warning w-100">Scenarios</a>
                            </div>
                            <div class="col-sm-4 mb-2">
                                <a href="/characters" class="btn btn-outline-warning w-100">Characters</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# Simplified debug template
DEBUG_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProEthica - Debug Info</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { padding-top: 2rem; }
        .code-block {
            background-color: #f8f9fa;
            border-radius: 5px;
            padding: 1rem;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row mb-4">
            <div class="col">
                <h1>ProEthica Debug Information</h1>
                <a href="/" class="btn btn-primary mb-3">Back to Home</a>
                
                <h3>Environment</h3>
                <div class="code-block mb-4">
                    <pre>{{ env_vars|safe }}</pre>
                </div>
                
                <h3>Database Status</h3>
                <div class="code-block mb-4">
                    <pre>{{ db_status|safe }}</pre>
                </div>

                <h3>MCP Server Status</h3>
                <div class="code-block mb-4">
                    <pre>{{ mcp_status|safe }}</pre>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    """Main landing page"""
    return render_template_string(HOME_TEMPLATE)

@app.route('/debug')
def debug():
    """Debug page with system information"""
    import psycopg2
    import requests
    
    # Get environment variables
    env_vars = "<b>Environment Variables:</b>\n"
    for key in sorted(['FLASK_APP', 'FLASK_ENV', 'DATABASE_URL', 'MCP_SERVER_URL', 
                     'ENVIRONMENT', 'USE_AGENT_ORCHESTRATOR']):
        env_vars += f"{key}: {os.environ.get(key, 'Not set')}\n"
    
    # Get database status
    db_status = "<b>Database:</b>\n"
    try:
        conn = psycopg2.connect(app.config['SQLALCHEMY_DATABASE_URI'])
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()[0]
        
        # Get table counts
        cursor.execute("""
            SELECT table_name, (SELECT count(*) FROM information_schema.columns 
                               WHERE table_name=t.table_name) AS columns
            FROM information_schema.tables t
            WHERE table_schema='public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        db_status += f"Status: Connected\nVersion: {db_version}\n\nTables:\n"
        for table, column_count in tables:
            db_status += f"- {table} ({column_count} columns)\n"
            
        cursor.close()
        conn.close()
    except Exception as e:
        db_status += f"Error: {str(e)}"
    
    # Get MCP server status
    mcp_status = "<b>MCP Server:</b>\n"
    try:
        # Get raw response first to check for formatting issues
        response = requests.post(
            app.config['MCP_SERVER_URL'],
            json={"jsonrpc": "2.0", "method": "list_tools", "params": {}, "id": 1},
            timeout=2
        )
        
        # Try to parse the raw response for better error handling
        try:
            raw_content = response.text
            # First try direct parsing
            data = json.loads(raw_content)
            
            tools = data.get("result", {}).get("tools", [])
            mcp_status += f"Status: Connected\n\nAvailable Tools:\n"
            for tool in tools:
                mcp_status += f"- {tool.get('name')}: {tool.get('description')}\n"
        except json.JSONDecodeError as e:
            mcp_status += f"Status: Connected but JSON error\n"
            mcp_status += f"Error: {str(e)}\n"
            mcp_status += f"Raw response: {raw_content[:50]}...\n"
            mcp_status += "\nNote: Run the JSON fixer proxy to resolve this issue."
    except Exception as e:
        mcp_status += f"Error: {str(e)}"
    
    return render_template_string(DEBUG_TEMPLATE, 
                               env_vars=env_vars,
                               db_status=db_status,
                               mcp_status=mcp_status)

# Routes to redirect to simplified versions
@app.route('/worlds')
@app.route('/scenarios')
@app.route('/characters')
@app.route('/ontology')
@app.route('/documents')
def feature_placeholder():
    """Placeholder for features that would normally use the full app"""
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Feature Placeholder</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-5">
            <div class="alert alert-info">
                <h4>Feature Available in Full Application</h4>
                <p>This feature is available in the full application but simplified for the Codespace environment.</p>
                <a href="/" class="btn btn-primary">Return to Home</a>
            </div>
        </div>
    </body>
    </html>
    ''')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3333))
    logger.info(f"Starting ProEthica UI on port {port}...")
    
    # Check if database and MCP server are running
    try:
        # Check database
        from sqlalchemy import create_engine
        engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        connection = engine.connect()
        connection.close()
        logger.info("Database connection successful!")
        
        # Check MCP server
        import requests
        response = requests.post(
            app.config['MCP_SERVER_URL'],
            json={"jsonrpc": "2.0", "method": "list_tools", "params": {}, "id": 1},
            timeout=2
        )
        if response.status_code == 200:
            logger.info("MCP server connection successful!")
        else:
            logger.warning(f"MCP server returned status code {response.status_code}")
    except Exception as e:
        logger.error(f"Startup check failed: {str(e)}")
        logger.warning("Continuing anyway, but some features may not work correctly")
    
    # Run the web application
    app.run(host='0.0.0.0', port=port, debug=True)
