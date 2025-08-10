"""
Debug environment route to force reload environment variables
"""

import os
from flask import Blueprint, jsonify
from dotenv import load_dotenv

debug_env_bp = Blueprint('debug_env', __name__, url_prefix='/debug')

@debug_env_bp.route('/reload-env', methods=['POST'])
def reload_environment():
    """Force reload environment variables from .env file"""
    try:
        # Clear the current BYPASS_AUTH value
        if 'BYPASS_AUTH' in os.environ:
            old_value = os.environ['BYPASS_AUTH']
            del os.environ['BYPASS_AUTH']
        else:
            old_value = 'not set'
        
        # Force reload .env file
        load_dotenv(override=True)
        
        new_value = os.environ.get('BYPASS_AUTH', 'not set')
        
        return jsonify({
            'success': True,
            'message': 'Environment reloaded',
            'old_value': old_value,
            'new_value': new_value,
            'bypass_auth_enabled': new_value.lower() == 'true'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@debug_env_bp.route('/check-env', methods=['GET'])
def check_environment():
    """Check current environment variable values"""
    return jsonify({
        'BYPASS_AUTH': os.environ.get('BYPASS_AUTH', 'not set'),
        'bypass_auth_enabled': os.environ.get('BYPASS_AUTH', 'false').lower() == 'true',
        'all_env_vars': dict(os.environ)
    })