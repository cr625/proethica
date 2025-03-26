"""
Routes for the simulation feature.

This module provides functionality for simulating scenarios.
"""

import logging
from flask import Blueprint, render_template, redirect, url_for
from app.models.scenario import Scenario

# Set up logging
logger = logging.getLogger(__name__)

# Create blueprint
simulation_bp = Blueprint('simulation', __name__, url_prefix='/simulation')

@simulation_bp.route('/scenario/<int:id>', methods=['GET'])
def simulate_scenario(id):
    """Display simulation interface for a scenario."""
    # Get the scenario
    scenario = Scenario.query.get_or_404(id)
    
    # Render the simulation template with the scenario data
    return render_template('simulate_scenario.html', scenario=scenario)
