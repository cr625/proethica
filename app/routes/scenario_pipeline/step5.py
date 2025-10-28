"""
Step 5: Interactive Scenario Generation

Transforms fully-analyzed cases (Passes 1-3 + Step 4) into interactive teaching scenarios
with real-time SSE progress streaming.
"""

import logging
from flask import Blueprint, render_template, request, jsonify

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.environment_auth import auth_required_for_llm, auth_optional

# Import scenario generation
from app.routes.scenario_pipeline.generate_scenario import generate_scenario_from_case
from app.services.scenario_generation import ScenarioDataCollector

logger = logging.getLogger(__name__)

bp = Blueprint('step5', __name__, url_prefix='/scenario_pipeline')


def init_step5_csrf_exemption(app):
    """Exempt Step 5 scenario generation routes from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        from app.routes.scenario_pipeline.generate_scenario import generate_scenario_from_case
        app.csrf.exempt(generate_scenario_from_case)


@bp.route('/case/<int:case_id>/step5')
@auth_optional
def step5_scenario_generation(case_id):
    """
    Display Step 5 scenario generation page.

    Shows eligibility status and scenario generation controls.
    """
    try:
        case = Document.query.get_or_404(case_id)

        # Check eligibility for scenario generation
        collector = ScenarioDataCollector()
        eligibility = collector.check_eligibility(case_id)

        # Get entity counts for display
        entity_counts = eligibility.entity_counts

        return render_template(
            'scenarios/step5.html',
            case=case,
            eligibility=eligibility,
            entity_counts=entity_counts,
            current_step=5,
            prev_step_url=f"/scenario_pipeline/case/{case_id}/step4",
            next_step_url="#"  # No step 6 yet
        )

    except Exception as e:
        logger.error(f"Error displaying Step 5 for case {case_id}: {e}")
        return str(e), 500


# Scenario Generation Route (SSE Endpoint)
@bp.route('/case/<int:case_id>/generate_scenario')
def generate_scenario_route(case_id):
    """
    SSE endpoint for scenario generation.

    Streams progress through all 9 stages of scenario generation.
    """
    return generate_scenario_from_case(case_id)


def get_entities_summary(case_id):
    """
    Get entity counts summary for all passes.

    Returns:
        Dictionary with entity counts by type
    """
    from sqlalchemy import text

    query = text("""
        SELECT entity_type, COUNT(*) as count
        FROM temporary_rdf_storage
        WHERE case_id = :case_id
        GROUP BY entity_type
        ORDER BY entity_type
    """)
    results = db.session.execute(query, {"case_id": case_id}).fetchall()

    counts = {row.entity_type: row.count for row in results}

    # Calculate totals
    pass1_types = ['Role', 'State', 'Resource']
    pass2_types = ['Principle', 'Obligation', 'Constraint', 'Capability']
    pass3_types = ['Action', 'Event']

    return {
        'roles': counts.get('Role', 0),
        'states': counts.get('State', 0),
        'resources': counts.get('Resource', 0),
        'pass1_total': sum(counts.get(t, 0) for t in pass1_types),

        'principles': counts.get('Principle', 0),
        'obligations': counts.get('Obligation', 0),
        'constraints': counts.get('Constraint', 0),
        'capabilities': counts.get('Capability', 0),
        'pass2_total': sum(counts.get(t, 0) for t in pass2_types),

        'actions': counts.get('Action', 0),
        'events': counts.get('Event', 0),
        'pass3_total': sum(counts.get(t, 0) for t in pass3_types),

        'total': sum(counts.values())
    }
