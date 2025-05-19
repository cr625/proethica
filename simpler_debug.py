#!/usr/bin/env python3
"""
Simplified debug app for GitHub Codespaces.
This script provides a minimal Flask application for testing
in the Codespace environment without requiring the full app.
"""

from flask import Flask, render_template, jsonify

app = Flask(__name__, 
            template_folder='app/templates',
            static_folder='app/static')

# Basic configuration
app.config['SECRET_KEY'] = 'debug-key'
app.config['DEBUG'] = True

@app.route('/')
def index():
    """Simple index route."""
    return render_template('debug/codespace_index.html', 
                          title="ProEthica Debug Mode", 
                          message="Running in GitHub Codespaces")

@app.route('/api/status')
def status():
    """API status check endpoint."""
    return jsonify({
        'status': 'ok',
        'environment': 'codespace',
        'mode': 'debug'
    })

@app.route('/test')
def test():
    """Test route."""
    return render_template('debug/test.html', 
                          title="Test Page",
                          message="This is a test page for debugging")

if __name__ == '__main__':
    # Create debug templates directory if it doesn't exist
    import os
    os.makedirs('app/templates/debug', exist_ok=True)
    
    # Create simple template files if they don't exist
    if not os.path.exists('app/templates/debug/codespace_index.html'):
        with open('app/templates/debug/codespace_index.html', 'w') as f:
            f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 40px;
            line-height: 1.6;
            color: #333;
        }
        h1 {
            color: #2c3e50;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        .status {
            padding: 10px;
            background-color: #d4edda;
            border-radius: 5px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ title }}</h1>
        <div class="status">{{ message }}</div>
        <p>This is a simplified debug version of the ProEthica application running in GitHub Codespaces.</p>
        <p>Use this page to test basic functionality and connectivity.</p>
        
        <h2>Available Test Routes:</h2>
        <ul>
            <li><a href="/test">Test Page</a></li>
            <li><a href="/api/status">API Status (JSON)</a></li>
        </ul>
        
        <h2>Environment Information</h2>
        <ul>
            <li>Environment: Codespace</li>
            <li>Debug Mode: Enabled</li>
            <li>Database Port: 5433</li>
        </ul>
    </div>
</body>
</html>
            """)
    
    if not os.path.exists('app/templates/debug/test.html'):
        with open('app/templates/debug/test.html', 'w') as f:
            f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 40px;
            line-height: 1.6;
            color: #333;
        }
        h1 {
            color: #2c3e50;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ title }}</h1>
        <p>{{ message }}</p>
        <p>If you can see this page, the simplified Flask app is working correctly.</p>
        <a href="/">Back to Home</a>
    </div>
</body>
</html>
            """)
    
    # Start the Flask application
    app.run(host='0.0.0.0', port=3333, debug=True)
