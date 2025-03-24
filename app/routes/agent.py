from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

# Create blueprint
agent_bp = Blueprint('agent', __name__, url_prefix='/agent')

@agent_bp.route('/', methods=['GET'])
def agent_window():
    """Display the agent window prototype."""
    # This will be our hidden route that requires the URL to access
    return render_template('agent_window.html')

# API endpoints for the agent (to be implemented later)
@agent_bp.route('/api/message', methods=['POST'])
def send_message():
    """Send a message to the agent."""
    # This will be implemented in Step 3
    return jsonify({'status': 'not_implemented'})

@agent_bp.route('/api/options', methods=['GET'])
def get_options():
    """Get available prompt options."""
    # This will be implemented in Step 3
    return jsonify({'status': 'not_implemented'})
