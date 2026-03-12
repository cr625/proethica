"""
Interactive Scenario Builder Routes

Blueprint hub for the scenario_pipeline URL namespace. Step 1-3 extraction
pages have been replaced by the unified pipeline dashboard at /cases/<id>/pipeline.
Remaining routes: overview, complete analysis, and step 4/entity review (registered
via their own blueprints).
"""

import logging
from flask import Blueprint, redirect, url_for
from app.utils.environment_auth import auth_optional

logger = logging.getLogger(__name__)

# Create the blueprint
interactive_scenario_bp = Blueprint('scenario_pipeline', __name__, url_prefix='/scenario_pipeline')


def init_csrf_exemption(app):
    """No-op. Step 1-3 endpoints that required CSRF exemption have been removed."""
    pass


@interactive_scenario_bp.route('/case/<int:case_id>')
@auth_optional
def scenario_pipeline_builder(case_id):
    """Redirect legacy builder landing page to the unified pipeline dashboard."""
    return redirect(url_for('cases.case_pipeline', case_id=case_id))


@interactive_scenario_bp.route('/case/<int:case_id>/overview')
@auth_optional
def overview(case_id):
    """Route handler for Case Overview"""
    from .overview import step1 as overview_handler
    return overview_handler(case_id)


@interactive_scenario_bp.route('/case/<int:case_id>/debug')
def debug_overview_route(case_id):
    """Debug route for overview processing"""
    from .overview import debug_step1 as debug_handler
    return debug_handler(case_id)


@interactive_scenario_bp.route('/case/<int:case_id>/complete')
def complete_analysis(case_id):
    """Route handler for Complete Analysis: Modular Pipeline for All Case Elements"""
    from .complete_analysis import complete_analysis as complete_handler
    return complete_handler(case_id)


@interactive_scenario_bp.route('/case/<int:case_id>/complete_analysis_execute', methods=['POST'])
def execute_complete_analysis(case_id):
    """API endpoint to execute complete modular analysis"""
    from .complete_analysis import execute_complete_analysis as execute_handler
    return execute_handler(case_id)
