"""
Step 5: Interactive Scenario Generation

Transforms fully-analyzed cases (Passes 1-3 + Step 4) into interactive teaching scenarios
with three views:
- View 1: Narrative Overview - case story with characters
- View 2: Entity Timeline - chronological visualization
- View 3: Decision Wizard - step through ethical choices
"""

import json
import logging
from flask import Blueprint, render_template, request, jsonify

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.models.scenario_exploration import ScenarioExplorationSession
from app.utils.environment_auth import auth_required_for_llm, auth_optional
from app.services.pipeline_status_service import PipelineStatusService

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
        # Interactive exploration routes
        app.csrf.exempt('step5.start_interactive_exploration')
        app.csrf.exempt('step5.make_choice')


@bp.route('/case/<int:case_id>/step5')
@auth_optional
def step5_scenario_generation(case_id):
    """
    Display Step 5 scenario generation page.

    Shows integrated tabbed interface with:
    - Narrative Overview
    - Event Timeline
    - Decision Wizard
    """
    try:
        case = Document.query.get_or_404(case_id)

        # Check eligibility for scenario generation
        collector = ScenarioDataCollector()
        eligibility = collector.check_eligibility(case_id)

        # Get entity counts for display
        entity_counts = eligibility.entity_counts

        # Load Phase 4 data for all views
        phase4_data = _load_phase4_data(case_id)
        narrative = _load_narrative_elements(case_id)
        timeline = _load_timeline_data(case_id)
        seeds = _load_scenario_seeds(case_id)
        insights = _load_insights(case_id)

        # Get pipeline status for navigation
        pipeline_status = PipelineStatusService.get_step_status(case_id)

        # Count completed exploration sessions
        completed_sessions_count = ScenarioExplorationSession.query.filter_by(
            case_id=case_id,
            status='completed'
        ).count()

        return render_template(
            'scenarios/step5.html',
            case=case,
            eligibility=eligibility,
            entity_counts=entity_counts,
            has_phase4=phase4_data is not None,
            phase4_data=phase4_data,
            narrative=narrative,
            timeline=timeline,
            seeds=seeds,
            insights=insights,
            current_step=5,
            prev_step_url=f"/scenario_pipeline/case/{case_id}/step4",
            next_step_url="#",  # No step 6 yet
            pipeline_status=pipeline_status,
            completed_sessions_count=completed_sessions_count
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


# Timeline Viewer Route
@bp.route('/case/<int:case_id>/timeline')
@auth_optional
def view_timeline_route(case_id):
    """
    View the generated timeline with LLM-enhanced descriptions.

    Shows chronological timeline with phases, narrative descriptions,
    and expandable details for each action/event.
    """
    from .view_timeline import view_timeline
    return view_timeline(case_id)


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


# =============================================================================
# PHASE 4 DATA LOADING
# =============================================================================

def _load_phase4_data(case_id: int):
    """
    Load Phase 4 narrative construction data from database.

    Returns dict with narrative_elements, timeline, scenario_seeds, insights
    """
    # Get the latest Phase 4 extraction prompt
    prompt = ExtractionPrompt.query.filter_by(
        case_id=case_id,
        concept_type='phase4_narrative'
    ).order_by(ExtractionPrompt.created_at.desc()).first()

    if not prompt or not prompt.results_summary:
        return None

    # results_summary is a JSON column - may already be a dict
    if isinstance(prompt.results_summary, dict):
        summary = prompt.results_summary
    else:
        try:
            summary = json.loads(prompt.results_summary)
        except (json.JSONDecodeError, TypeError):
            return None

    # Load the full narrative elements from raw_response if available
    full_data = None
    if prompt.raw_response:
        try:
            full_data = json.loads(prompt.raw_response)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        'has_phase4': True,
        'timestamp': prompt.created_at.isoformat() if prompt.created_at else None,
        'summary': summary,
        'full_data': full_data
    }


def _load_narrative_elements(case_id: int):
    """Load narrative elements (characters, events, conflicts) from Phase 4."""
    from sqlalchemy import text

    result = {
        'characters': [],
        'events': [],
        'conflicts': [],
        'decision_moments': [],
        'setting': None,
        'resolution': None
    }

    # Load from extraction prompts with detailed data
    prompt = ExtractionPrompt.query.filter_by(
        case_id=case_id,
        concept_type='phase4_narrative'
    ).order_by(ExtractionPrompt.created_at.desc()).first()

    if prompt and prompt.raw_response:
        try:
            data = json.loads(prompt.raw_response)
            if 'narrative_elements' in data:
                ne = data['narrative_elements']
                # Check if we have full data (list) or just counts (int)
                chars = ne.get('characters', [])
                if isinstance(chars, list) and len(chars) > 0:
                    # Filter Phase 4 characters: exclude classes and meta-authority
                    result['characters'] = _filter_characters(chars)
                events = ne.get('events', [])
                if isinstance(events, list) and len(events) > 0:
                    result['events'] = events
                conflicts = ne.get('conflicts', [])
                if isinstance(conflicts, list) and len(conflicts) > 0:
                    result['conflicts'] = conflicts
                dms = ne.get('decision_moments', [])
                if isinstance(dms, list) and len(dms) > 0:
                    result['decision_moments'] = dms
                # Setting and resolution
                if ne.get('setting'):
                    result['setting'] = ne['setting']
                if ne.get('resolution'):
                    result['resolution'] = ne['resolution']
        except (json.JSONDecodeError, TypeError):
            pass

    # If we got full data from Phase 4, return it
    if isinstance(result['characters'], list) and len(result['characters']) > 0:
        return result

    # Try to load from temporary_rdf_storage for richer data
    # Characters from Roles - filter to only case-specific individuals
    roles_query = text("""
        SELECT entity_uri, entity_label, entity_type, entity_definition, rdf_json_ld
        FROM temporary_rdf_storage
        WHERE case_id = :case_id AND entity_type = 'Roles'
        ORDER BY entity_label
    """)
    roles = db.session.execute(roles_query, {"case_id": case_id}).fetchall()

    if roles:
        result['characters'] = []
        for r in roles:
            # Filter out role classes (from intermediate/core ontology)
            uri = r.entity_uri or ''
            if _is_ontology_class(uri):
                continue  # Skip ontology classes like "Engineering Mentor Role"

            # Filter out meta-authority (Board of Ethical Review)
            label = r.entity_label or ''
            if _is_meta_authority(label):
                continue  # Skip the NSPE Board - it's the meta-authority for all cases

            rdf_data = r.rdf_json_ld if r.rdf_json_ld else {}
            result['characters'].append({
                'uri': uri,
                'label': label,
                'definition': r.entity_definition or rdf_data.get('definition', ''),
                'role_type': _classify_role_type(label)
            })

    # Events from actions and events
    events_query = text("""
        SELECT entity_uri, entity_label, entity_type, entity_definition, rdf_json_ld
        FROM temporary_rdf_storage
        WHERE case_id = :case_id AND entity_type IN ('actions', 'events')
        ORDER BY entity_type, entity_label
    """)
    events = db.session.execute(events_query, {"case_id": case_id}).fetchall()

    if events:
        result['events'] = []
        for e in events:
            rdf_data = e.rdf_json_ld if e.rdf_json_ld else {}
            result['events'].append({
                'uri': e.entity_uri or '',
                'label': e.entity_label or '',
                'event_type': e.entity_type,
                'description': e.entity_definition or rdf_data.get('definition', '')
            })

    # Decision points
    dp_query = text("""
        SELECT entity_uri, entity_label, entity_type, entity_definition, rdf_json_ld
        FROM temporary_rdf_storage
        WHERE case_id = :case_id AND entity_type = 'decision_point'
        ORDER BY entity_label
    """)
    dps = db.session.execute(dp_query, {"case_id": case_id}).fetchall()

    if dps:
        result['decision_moments'] = []
        for dp in dps:
            rdf_data = dp.rdf_json_ld if dp.rdf_json_ld else {}
            result['decision_moments'].append({
                'uri': dp.entity_uri or '',
                'label': dp.entity_label or '',
                'question': rdf_data.get('decision_question', dp.entity_definition or ''),
                'description': rdf_data.get('description', '')
            })

    # Conclusions
    conc_query = text("""
        SELECT entity_uri, entity_label, entity_type, entity_definition, rdf_json_ld
        FROM temporary_rdf_storage
        WHERE case_id = :case_id AND entity_type = 'conclusions'
        ORDER BY entity_label
    """)
    conclusions = db.session.execute(conc_query, {"case_id": case_id}).fetchall()

    if conclusions:
        result['resolution'] = {
            'conclusions': [
                {
                    'uri': c.entity_uri or '',
                    'label': c.entity_label or '',
                    'text': c.entity_definition or (c.rdf_json_ld.get('definition', '') if c.rdf_json_ld else '')
                }
                for c in conclusions
            ]
        }

    return result


def _filter_characters(characters: list) -> list:
    """
    Filter character list to exclude ontology classes and meta-authority.

    Args:
        characters: List of character dicts from Phase 4

    Returns:
        Filtered list with only case-specific individuals
    """
    filtered = []
    for char in characters:
        uri = char.get('uri', '')
        label = char.get('label', '')

        # Skip ontology classes
        if _is_ontology_class(uri):
            continue

        # Skip meta-authority
        if _is_meta_authority(label):
            continue

        filtered.append(char)

    return filtered


def _is_ontology_class(uri: str) -> bool:
    """
    Check if a URI represents an ontology class rather than a case-specific individual.

    Classes are defined in the intermediate or core ontology and have URIs like:
    - http://proethica.org/ontology/intermediate#EngineeringMentorRole
    - http://proethica.org/ontology/core#SomeClass

    Case-specific individuals have URIs like:
    - http://proethica.org/ontology/case/7#Engineer_A
    """
    class_markers = ['intermediate#', 'core#', '/ontology#']
    return any(marker in uri for marker in class_markers)


def _is_meta_authority(label: str) -> bool:
    """
    Check if a role label represents the meta-authority (Board of Ethical Review).

    The NSPE Board of Ethical Review reviews all cases and should not be shown
    as a character in the case narrative. Case-specific authorities (like local
    compliance boards) should still be shown.
    """
    label_lower = label.lower()
    meta_authority_terms = [
        'board of ethical review',
        'nspe board',
        'ber',  # Board of Ethical Review abbreviation
    ]
    return any(term in label_lower for term in meta_authority_terms)


def _classify_role_type(role_label: str) -> str:
    """Classify a role into narrative role type."""
    label_lower = role_label.lower()

    if any(term in label_lower for term in ['engineer a', 'primary', 'main']):
        return 'protagonist'
    if any(term in label_lower for term in ['manager', 'director', 'supervisor', 'boss']):
        return 'decision-maker'
    # Note: We check for authority but exclude meta-authority (Board of Ethical Review)
    # which is filtered out by _is_meta_authority() before reaching this point
    if any(term in label_lower for term in ['board', 'commission', 'committee', 'authority']):
        return 'authority'
    return 'stakeholder'


def _load_scenario_seeds(case_id: int):
    """Load scenario seeds data."""
    prompt = ExtractionPrompt.query.filter_by(
        case_id=case_id,
        concept_type='phase4_narrative'
    ).order_by(ExtractionPrompt.created_at.desc()).first()

    if prompt and prompt.raw_response:
        try:
            data = json.loads(prompt.raw_response)
            if 'scenario_seeds' in data:
                return data['scenario_seeds']
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        'opening_context': '',
        'branches': [],
        'protagonist_label': '',
        'supporting_characters': []
    }


def _load_timeline_data(case_id: int):
    """Load timeline data for the case."""
    prompt = ExtractionPrompt.query.filter_by(
        case_id=case_id,
        concept_type='phase4_narrative'
    ).order_by(ExtractionPrompt.created_at.desc()).first()

    if prompt and prompt.raw_response:
        try:
            data = json.loads(prompt.raw_response)
            # Only use Phase 4 timeline if it has actual events
            if 'timeline' in data and data['timeline'].get('events'):
                return data['timeline']
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback: build timeline from entities
    from sqlalchemy import text

    timeline = {'events': [], 'event_trace': ''}

    # Load actions and events
    query = text("""
        SELECT entity_uri, entity_label, entity_type, entity_definition, rdf_json_ld
        FROM temporary_rdf_storage
        WHERE case_id = :case_id AND entity_type IN ('actions', 'events')
        ORDER BY entity_type, entity_label
    """)
    results = db.session.execute(query, {"case_id": case_id}).fetchall()

    sequence = 1
    for r in results:
        rdf_data = r.rdf_json_ld if r.rdf_json_ld else {}
        timeline['events'].append({
            'sequence': sequence,
            'event_uri': r.entity_uri or '',
            'event_label': r.entity_label or '',
            'event_type': 'action' if r.entity_type == 'actions' else 'automatic',
            'description': r.entity_definition or rdf_data.get('definition', r.entity_label or ''),
            'phase_label': 'Action' if r.entity_type == 'actions' else 'Event'
        })
        sequence += 1

    return timeline


def _load_insights(case_id: int):
    """Load case insights data."""
    prompt = ExtractionPrompt.query.filter_by(
        case_id=case_id,
        concept_type='phase4_narrative'
    ).order_by(ExtractionPrompt.created_at.desc()).first()

    if prompt and prompt.raw_response:
        try:
            data = json.loads(prompt.raw_response)
            if 'insights' in data:
                return data['insights']
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        'key_takeaways': [],
        'patterns': [],
        'principles_applied': []
    }


# =============================================================================
# STEP 5 VIEW ROUTES
# =============================================================================

@bp.route('/case/<int:case_id>/step5/narrative')
@auth_optional
def narrative_overview(case_id):
    """
    View 1: Narrative Overview

    Shows the case story with:
    - Opening context (protagonist perspective)
    - Character profiles from Roles
    - Key ethical conflicts
    - Resolution summary
    """
    try:
        case = Document.query.get_or_404(case_id)

        # Load Phase 4 data
        phase4_data = _load_phase4_data(case_id)
        narrative = _load_narrative_elements(case_id)
        seeds = _load_scenario_seeds(case_id)
        insights = _load_insights(case_id)

        # Get pipeline status for navigation
        pipeline_status = PipelineStatusService.get_step_status(case_id)

        return render_template(
            'scenarios/step5_narrative.html',
            case=case,
            has_phase4=phase4_data is not None,
            phase4_data=phase4_data,
            narrative=narrative,
            seeds=seeds,
            insights=insights,
            current_step=5,
            prev_step_url=f"/scenario_pipeline/case/{case_id}/step5",
            next_step_url=f"/scenario_pipeline/case/{case_id}/step5/timeline",
            pipeline_status=pipeline_status,
            current_view='narrative'
        )

    except Exception as e:
        logger.error(f"Error loading narrative overview for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return str(e), 500


@bp.route('/case/<int:case_id>/step5/timeline')
@auth_optional
def enhanced_timeline(case_id):
    """
    View 2: Entity Timeline

    Shows chronological visualization with:
    - Timeline events from Phase 4
    - Entity-grounded descriptions
    - Phase labels (Initial, Rising, Conflict, Decision, Resolution)
    - Causal links between events
    """
    try:
        case = Document.query.get_or_404(case_id)

        # Load Phase 4 timeline data
        phase4_data = _load_phase4_data(case_id)
        timeline = _load_timeline_data(case_id)
        narrative = _load_narrative_elements(case_id)

        # Get pipeline status for navigation
        pipeline_status = PipelineStatusService.get_step_status(case_id)

        return render_template(
            'scenarios/step5_timeline.html',
            case=case,
            has_phase4=phase4_data is not None,
            timeline=timeline,
            narrative=narrative,
            current_step=5,
            prev_step_url=f"/scenario_pipeline/case/{case_id}/step5/narrative",
            next_step_url=f"/scenario_pipeline/case/{case_id}/step5/decisions",
            pipeline_status=pipeline_status,
            current_view='timeline'
        )

    except Exception as e:
        logger.error(f"Error loading timeline for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return str(e), 500


def _load_canonical_decision_points(case_id: int) -> list:
    """Load canonical decision points with arguments and resolution patterns."""
    decision_points = []

    # Load canonical decision points from Phase 3
    dp_records = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='canonical_decision_point'
    ).order_by(TemporaryRDFStorage.id).all()

    # Load all arguments for this case
    arg_records = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='argument_generated'
    ).all()

    # Group arguments by decision point
    args_by_dp = {}
    for arg in arg_records:
        data = arg.rdf_json_ld or {}
        dp_id = data.get('decision_point_id', '')
        if dp_id not in args_by_dp:
            args_by_dp[dp_id] = {'pro': [], 'con': []}
        arg_type = data.get('argument_type', 'pro')
        args_by_dp[dp_id][arg_type].append(data)

    # Load resolution patterns
    resolution_records = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='resolution_pattern'
    ).all()
    resolutions = {r.rdf_json_ld.get('conclusion_uri', ''): r.rdf_json_ld for r in resolution_records if r.rdf_json_ld}

    for record in dp_records:
        data = record.rdf_json_ld or {}
        dp_id = data.get('focus_id', '')

        # Get arguments for this decision point
        dp_args = args_by_dp.get(dp_id, {'pro': [], 'con': []})

        # Find matching resolution pattern
        conclusion_uri = data.get('aligned_conclusion_uri', '')
        resolution = resolutions.get(conclusion_uri, {})

        decision_points.append({
            'focus_id': dp_id,
            'focus_number': data.get('focus_number', 0),
            'label': data.get('description', ''),
            'question': data.get('decision_question', ''),
            'role_label': data.get('role_label', ''),
            'obligation_label': data.get('obligation_label', ''),
            'options': data.get('options', []),
            'toulmin': data.get('toulmin', {}),
            'board_resolution': data.get('board_resolution', ''),
            'provisions': data.get('provision_labels', []),
            'qc_alignment_score': data.get('qc_alignment_score', 0),
            'addresses_questions': data.get('addresses_questions', []),
            'pro_arguments': dp_args['pro'][:3],  # Top 3 pro arguments
            'con_arguments': dp_args['con'][:3],  # Top 3 con arguments
            'resolution_pattern': {
                'determinative_principles': resolution.get('determinative_principles', []),
                'determinative_facts': resolution.get('determinative_facts', []),
                'weighing_process': resolution.get('weighing_process', ''),
                'resolution_narrative': resolution.get('resolution_narrative', '')
            }
        })

    return decision_points


@bp.route('/case/<int:case_id>/step5/decisions')
@auth_optional
def decision_wizard(case_id):
    """
    View 3: Decision Analysis

    Analytical view of ethical decisions showing:
    - Board's conclusions with rationale
    - Pros and cons for each option
    - Toulmin argument structure
    - Resolution patterns
    """
    try:
        case = Document.query.get_or_404(case_id)

        # Load Phase 4 data
        phase4_data = _load_phase4_data(case_id)
        seeds = _load_scenario_seeds(case_id)
        narrative = _load_narrative_elements(case_id)
        insights = _load_insights(case_id)

        # Load canonical decision points with rich analysis
        canonical_dps = _load_canonical_decision_points(case_id)

        # Fall back to narrative decision moments if no canonical DPs
        if not canonical_dps:
            canonical_dps = narrative.get('decision_moments', [])

        # Get pipeline status for navigation
        pipeline_status = PipelineStatusService.get_step_status(case_id)

        return render_template(
            'scenarios/step5_decisions.html',
            case=case,
            has_phase4=phase4_data is not None,
            seeds=seeds,
            narrative=narrative,
            decision_points=canonical_dps,
            insights=insights,
            current_step=5,
            prev_step_url=f"/scenario_pipeline/case/{case_id}/step5/timeline",
            next_step_url=f"/scenario_pipeline/case/{case_id}/step5",
            pipeline_status=pipeline_status,
            current_view='decisions'
        )

    except Exception as e:
        logger.error(f"Error loading decision wizard for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return str(e), 500


# =============================================================================
# STEP 5 API ENDPOINTS
# =============================================================================

@bp.route('/case/<int:case_id>/step5/data')
def step5_data_api(case_id):
    """
    API endpoint to get all Step 5 data.

    Returns Phase 4 narrative construction results for frontend use.
    """
    try:
        phase4_data = _load_phase4_data(case_id)

        if not phase4_data:
            return jsonify({
                'success': False,
                'has_phase4': False,
                'message': 'No Phase 4 data found. Run narrative construction from Step 4 first.'
            })

        narrative = _load_narrative_elements(case_id)
        timeline = _load_timeline_data(case_id)
        seeds = _load_scenario_seeds(case_id)
        insights = _load_insights(case_id)

        return jsonify({
            'success': True,
            'has_phase4': True,
            'timestamp': phase4_data.get('timestamp'),
            'summary': phase4_data.get('summary', {}),
            'narrative': narrative,
            'timeline': timeline,
            'seeds': seeds,
            'insights': insights
        })

    except Exception as e:
        logger.error(f"Error loading Step 5 data for case {case_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# REGISTER INTERACTIVE EXPLORATION ROUTES
# =============================================================================

from app.routes.scenario_pipeline.step5_interactive import register_interactive_routes
register_interactive_routes(bp)
