"""
Dynamic Scenario Viewer - Stage 8

Displays assembled scenarios from database (no static files).
"""

import logging
from flask import Blueprint, render_template, jsonify
from sqlalchemy import text
from app.models import db

logger = logging.getLogger(__name__)

scenario_viewer_bp = Blueprint('scenario_viewer', __name__)


@scenario_viewer_bp.route('/scenario_pipeline/case/<int:case_id>/scenario')
def view_scenario(case_id):
    """Display assembled scenario from database."""

    try:
        # Fetch scenario from database
        query = text("""
            SELECT scenario_data, completeness_score, stages_included,
                   total_components, created_at, updated_at
            FROM scenario_assemblies
            WHERE case_id = :case_id
        """)

        result = db.session.execute(query, {'case_id': case_id}).fetchone()

        if not result:
            return render_template('scenarios/no_scenario.html', case_id=case_id)

        scenario_data = result[0]  # JSONB column
        metadata = {
            'completeness_score': result[1],
            'stages_included': result[2],
            'total_components': result[3],
            'created_at': result[4],
            'updated_at': result[5]
        }

        # Analyze completeness
        missing_elements = _analyze_missing_elements(scenario_data)

        return render_template(
            'scenarios/scenario_viewer.html',
            case_id=case_id,
            scenario=scenario_data,
            metadata=metadata,
            missing=missing_elements
        )

    except Exception as e:
        logger.error(f"[Scenario Viewer] Error loading scenario for case {case_id}: {e}", exc_info=True)
        return render_template('scenarios/error.html', case_id=case_id, error=str(e)), 500


def _analyze_missing_elements(scenario_data):
    """Identify missing/incomplete elements."""
    missing = []

    # Check timeline completeness
    timeline = scenario_data.get('timeline', {})
    if not timeline.get('entries'):
        missing.append({
            'section': 'timeline',
            'element': 'No timeline events',
            'severity': 'high'
        })
    elif len(timeline.get('entries', [])) < 3:
        missing.append({
            'section': 'timeline',
            'element': 'Timeline has fewer than 3 events',
            'severity': 'medium'
        })

    # Check participants
    participants = scenario_data.get('participants', {})
    if not participants.get('profiles'):
        missing.append({
            'section': 'participants',
            'element': 'No participant profiles',
            'severity': 'high'
        })
    elif not participants.get('llm_enhanced'):
        missing.append({
            'section': 'participants',
            'element': 'Participants not LLM-enhanced',
            'severity': 'low'
        })

    if not participants.get('relationship_map'):
        missing.append({
            'section': 'participants',
            'element': 'No relationship map',
            'severity': 'low'
        })

    # Check decisions
    decisions = scenario_data.get('decisions', {})
    if not decisions.get('decision_points'):
        missing.append({
            'section': 'decisions',
            'element': 'No decision points identified',
            'severity': 'high'
        })
    elif not decisions.get('has_institutional_analysis'):
        missing.append({
            'section': 'decisions',
            'element': 'Decision points lack institutional analysis (run Step 4 Part D)',
            'severity': 'medium'
        })

    # Check causal chains
    if not scenario_data.get('causal_chains'):
        missing.append({
            'section': 'causal_chains',
            'element': 'No causal chain analysis (run Step 4 Part E)',
            'severity': 'medium'
        })

    # Check normative framework
    if not scenario_data.get('normative_framework'):
        missing.append({
            'section': 'normative_framework',
            'element': 'No normative framework (run Step 4 Part F)',
            'severity': 'medium'
        })

    return missing
