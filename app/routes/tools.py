"""
Tools routes for ProEthica utilities and reference pages.
"""

from flask import Blueprint, render_template
from app.utils.environment_auth import auth_optional

tools_bp = Blueprint('tools', __name__)


@tools_bp.route('/tools/references')
@auth_optional
def references():
    """Academic references and theoretical foundations page."""
    return render_template('tools/references.html')
