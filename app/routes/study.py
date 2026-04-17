"""
ProEthica user-study routes (IRB Protocol 2603011709).

Participant flow:
- Landing page displays the HRP-506 Information Sheet and a consent checkbox.
- On consent, the system generates a random 8-character participant code and
  creates a new ValidationSession. The code is the participant's only
  credential for returning to their session.
- Each participant is assigned 3-4 cases from the 23-case pool
  (`app.config.study_case_pool`) via `case_assignment_service.assign_cases`.
- For each case: read Facts, review five synthesis views, rate 18 Likert
  items, answer 4 comprehension questions, reveal board Discussion +
  Conclusions (gated on comprehension completeness), rate alignment.
- After all cases: rank the five views and provide open feedback.

Admin routes stay behind `@admin_required_production`. Participant routes do
NOT require login; authentication is by possession of the random code only.
"""

import logging
import secrets
import uuid
from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, flash, session, jsonify
from flask_wtf.csrf import CSRFError
from app import db
from app.models import Document
from app.models.view_utility_evaluation import (
    ValidationSession, ViewUtilityEvaluation, RetrospectiveReflection
)
from app.services.validation.synthesis_view_builder import SynthesisViewBuilder
from app.services.validation.case_assignment_service import assign_cases

logger = logging.getLogger(__name__)

study_bp = Blueprint('study', __name__)


@study_bp.errorhandler(CSRFError)
def handle_csrf_error(e):
    """Graceful handling for stale CSRF tokens on study forms.

    Most common cause: the dev server restarted between the landing-page load
    and the form submit, invalidating the token. Participant flow should
    bounce back to the landing page (which renders a fresh token) rather
    than show a bare 400 page.
    """
    flash('Your session expired or the page was stale. Please start again.', 'warning')
    return redirect(url_for('study.index'))

# Information Sheet version currently served. Bump this when the .docx changes
# and update `_info_sheet_v2.html` (and this constant) together.
INFO_SHEET_VERSION = 'v2'

# Ambiguity-stripped alphabet for participant codes (no 0/O, 1/I, L).
CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
CODE_LENGTH = 8


def generate_participant_code() -> str:
    """Random 8-character alphanumeric code. No crosswalk to identity."""
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def get_participant_code() -> str | None:
    """Read code from query string or session. Returns None if unknown."""
    code = request.args.get('code', '').strip().upper()
    if code:
        session['participant_code'] = code
        return code
    return session.get('participant_code')


def load_session(code: str) -> ValidationSession | None:
    """Fetch a session by participant code, or None if the code is bogus."""
    if not code:
        return None
    return ValidationSession.query.filter_by(participant_code=code).first()


def create_session(domain: str = 'engineering') -> ValidationSession:
    """Create a new study session with a fresh random code.

    Consent must have been acknowledged before this is called; the caller is
    responsible for setting `consent_acknowledged_at` and `info_sheet_version`.
    """
    code = generate_participant_code()
    # Vanishingly small collision probability, but belt-and-suspenders:
    while ValidationSession.query.filter_by(participant_code=code).first() is not None:
        code = generate_participant_code()

    assigned = assign_cases(code)

    new_session = ValidationSession(
        session_id=str(uuid.uuid4())[:8],
        evaluator_id=code,
        participant_code=code,
        evaluator_domain=domain,
        assigned_cases=assigned,
        completed_cases=[],
        consent_acknowledged_at=datetime.utcnow(),
        info_sheet_version=INFO_SHEET_VERSION,
    )
    db.session.add(new_session)
    db.session.commit()
    session['participant_code'] = code
    return new_session


# =============================================================================
# SESSION MANAGEMENT ROUTES
# =============================================================================

@study_bp.route('/')
def index():
    """Landing page.

    Three possible renderings depending on state:
    1. No code → Information Sheet + consent form (POST to `/enroll`).
    2. Code present, session found → study dashboard with assigned cases.
    3. Code present, no session → invalid-code message + retry form.
    """
    code = get_participant_code()

    if not code:
        return render_template('validation_study/index.html',
                               phase='consent',
                               info_sheet_version=INFO_SHEET_VERSION)

    val_session = load_session(code)
    if not val_session:
        flash(f'No study session found for code {code}. Check for typos or start a new session.', 'warning')
        session.pop('participant_code', None)
        return render_template('validation_study/index.html',
                               phase='consent',
                               info_sheet_version=INFO_SHEET_VERSION,
                               invalid_code=code)

    view_builder = SynthesisViewBuilder()
    assigned_ids = val_session.assigned_cases or []
    completed = set(val_session.completed_cases or [])

    case_summaries = []
    next_case = None
    for cid in assigned_ids:
        doc = Document.query.get(cid)
        if not doc:
            continue
        summary = {
            'id': cid,
            'title': doc.title,
            'case_number': view_builder._extract_case_number(doc),
            'is_complete': cid in completed,
        }
        case_summaries.append(summary)
        if next_case is None and cid not in completed:
            next_case = summary

    return render_template('validation_study/index.html',
                           phase='dashboard',
                           participant_code=code,
                           session=val_session,
                           case_summaries=case_summaries,
                           next_case=next_case,
                           completed_count=len(completed),
                           total_count=len(assigned_ids))


@study_bp.route('/enroll', methods=['POST'])
def enroll():
    """Create a new session after the participant acknowledges the consent."""
    if request.form.get('consent') != 'yes':
        flash('You must acknowledge the information sheet to participate.', 'warning')
        return redirect(url_for('study.index'))

    val_session = create_session(domain='engineering')
    flash(
        f'Your participant code is {val_session.participant_code}. '
        f'Write it down or screenshot it now. You will need this code to return '
        f'to your session. If you lose it, you cannot resume and would need to restart.',
        'info'
    )
    return redirect(url_for('study.index', code=val_session.participant_code))


@study_bp.route('/exit')
def exit_session():
    """Clear the current code from the browser session (code itself still works for return)."""
    session.pop('participant_code', None)
    flash('You have exited. Re-enter your code to return to your session.', 'info')
    return redirect(url_for('study.index'))


@study_bp.route('/session/<session_id>/status')
def session_status(session_id):
    """Get current session status (for AJAX)."""
    val_session = ValidationSession.query.filter_by(session_id=session_id).first_or_404()

    return jsonify({
        'session_id': val_session.session_id,
        'participant_code': val_session.participant_code,
        'progress_percent': val_session.progress_percent,
        'completed_cases': val_session.completed_cases or [],
        'assigned_cases': val_session.assigned_cases or [],
        'is_complete': val_session.is_complete
    })


# =============================================================================
# CASE EVALUATION ROUTES
# =============================================================================

def _require_session():
    """Resolve and return the current session, or a redirect response."""
    code = get_participant_code()
    if not code:
        flash('Please enroll or enter your participant code to continue.', 'warning')
        return None, redirect(url_for('study.index'))
    val_session = load_session(code)
    if not val_session:
        flash(f'No study session found for code {code}.', 'warning')
        session.pop('participant_code', None)
        return None, redirect(url_for('study.index'))
    return val_session, None


@study_bp.route('/case/<int:case_id>', methods=['GET'])
def evaluate_case(case_id):
    """Main evaluation page for a case - implements stepped flow."""
    val_session, redirect_resp = _require_session()
    if redirect_resp:
        return redirect_resp

    assigned_ids = val_session.assigned_cases or []
    if case_id not in assigned_ids:
        flash('This case is not in your assigned set.', 'warning')
        return redirect(url_for('study.index'))

    document = Document.query.get_or_404(case_id)

    view_builder = SynthesisViewBuilder()
    if not view_builder.case_has_synthesis(case_id):
        flash('This case does not have sufficient synthesis data for the study.', 'warning')
        return redirect(url_for('study.index'))

    case_facts = view_builder.get_case_facts(case_id)
    views = view_builder.get_all_views(case_id)

    existing_eval = ViewUtilityEvaluation.query.filter_by(
        session_id=val_session.id,
        case_id=case_id
    ).first()

    step = request.args.get('step', 'facts')
    valid_steps = ['facts', 'views', 'utility', 'comprehension', 'reveal', 'alignment']
    if step not in valid_steps:
        step = 'facts'

    # A10: reveal step is gated on comprehension completeness.
    if step in ('reveal', 'alignment'):
        if not existing_eval or not existing_eval.comprehension_complete:
            flash('Please complete the comprehension questions before revealing the board conclusions.', 'warning')
            return redirect(url_for('study.evaluate_case', case_id=case_id, step='comprehension'))

    return render_template('validation_study/case_evaluation.html',
                           document=document,
                           case_facts=case_facts,
                           views=views,
                           participant_code=val_session.participant_code,
                           session=val_session,
                           existing_eval=existing_eval,
                           current_step=step)


@study_bp.route('/case/<int:case_id>/submit', methods=['POST'])
def submit_evaluation(case_id):
    """Submit evaluation for a case. 18 Likert items + 4 comprehension + alignment."""
    val_session, redirect_resp = _require_session()
    if redirect_resp:
        return redirect_resp

    if case_id not in (val_session.assigned_cases or []):
        flash('This case is not in your assigned set.', 'warning')
        return redirect(url_for('study.index'))

    try:
        evaluation = ViewUtilityEvaluation.query.filter_by(
            session_id=val_session.id,
            case_id=case_id
        ).first()

        if not evaluation:
            evaluation = ViewUtilityEvaluation(
                session_id=val_session.id,
                case_id=case_id,
                evaluator_id=val_session.participant_code,
                started_at=datetime.utcnow()
            )
            db.session.add(evaluation)

        def get_int(name):
            val = request.form.get(name)
            if val is not None and val != '':
                try:
                    return int(val)
                except ValueError:
                    return None
            return None

        # Part 1: 18 Likert items (3 per view × 5 views + 3 overall)

        # Provisions
        evaluation.prov_standards_identified = get_int('prov_standards_identified')
        evaluation.prov_connections_clear = get_int('prov_connections_clear')
        evaluation.prov_normative_foundation = get_int('prov_normative_foundation')

        # Q&C
        evaluation.qc_issues_visible = get_int('qc_issues_visible')
        evaluation.qc_emergence_resolution = get_int('qc_emergence_resolution')
        evaluation.qc_deliberation_needs = get_int('qc_deliberation_needs')

        # Decisions
        evaluation.decs_choices_understood = get_int('decs_choices_understood')
        evaluation.decs_argumentative_structure = get_int('decs_argumentative_structure')
        evaluation.decs_actions_obligations = get_int('decs_actions_obligations')

        # Timeline
        evaluation.timeline_temporal_sequence = get_int('timeline_temporal_sequence')
        evaluation.timeline_causal_links = get_int('timeline_causal_links')
        evaluation.timeline_obligation_activation = get_int('timeline_obligation_activation')

        # Narrative
        evaluation.narr_characters_tensions = get_int('narr_characters_tensions')
        evaluation.narr_relationships_clear = get_int('narr_relationships_clear')
        evaluation.narr_ethical_significance = get_int('narr_ethical_significance')

        # Overall (item 2 is reverse-coded; stored raw)
        evaluation.overall_helped_understand = get_int('overall_helped_understand')
        evaluation.overall_surfaced_considerations = get_int('overall_surfaced_considerations')
        evaluation.overall_useful_deliberation = get_int('overall_useful_deliberation')

        # Part 2A: Comprehension
        evaluation.comp_main_tensions = request.form.get('comp_main_tensions', '').strip()
        evaluation.comp_relevant_provisions = request.form.get('comp_relevant_provisions', '').strip()
        evaluation.comp_decision_points = request.form.get('comp_decision_points', '').strip()
        evaluation.comp_deliberation_factors = request.form.get('comp_deliberation_factors', '').strip()

        # Part 2B: Alignment
        alignment_submitted = bool(request.form.get('alignment_self_rating'))
        if alignment_submitted and not evaluation.comprehension_complete:
            flash('Please complete the comprehension questions before the alignment step.', 'warning')
            return redirect(url_for('study.evaluate_case', case_id=case_id, step='comprehension'))

        evaluation.alignment_self_rating = get_int('alignment_self_rating')
        evaluation.alignment_reflection = request.form.get('alignment_reflection', '').strip()

        # Timing
        evaluation.time_facts_review = get_int('time_facts_review')
        evaluation.time_views_review = get_int('time_views_review')
        evaluation.time_timeline_review = get_int('time_timeline_review')
        evaluation.time_utility_rating = get_int('time_utility_rating')
        evaluation.time_comprehension = get_int('time_comprehension')
        evaluation.time_alignment = get_int('time_alignment')

        # Mark completion
        if evaluation.is_complete:
            evaluation.completed_at = datetime.utcnow()
            completed = set(val_session.completed_cases or [])
            completed.add(case_id)
            val_session.completed_cases = list(completed)

        db.session.commit()

        if evaluation.is_complete:
            flash('Evaluation submitted successfully.', 'success')
            if val_session.is_complete:
                return redirect(url_for('study.retrospective'))
            return redirect(url_for('study.index'))
        else:
            flash('Progress saved. Continue where you left off.', 'info')
            next_step = request.form.get('next_step') or 'utility'
            return redirect(url_for('study.evaluate_case', case_id=case_id, step=next_step))

    except Exception as e:
        logger.exception(f"Error submitting evaluation for case {case_id}: {str(e)}")
        db.session.rollback()
        flash(f'Error saving evaluation: {str(e)}', 'error')
        return redirect(url_for('study.evaluate_case', case_id=case_id))


@study_bp.route('/case/<int:case_id>/reveal')
def reveal_conclusions(case_id):
    """Reveal board conclusions. Gated on comprehension completeness."""
    val_session, redirect_resp = _require_session()
    if redirect_resp:
        return jsonify({'error': 'no_session'}), 403

    existing = ViewUtilityEvaluation.query.filter_by(
        session_id=val_session.id,
        case_id=case_id
    ).first()
    if not existing or not existing.comprehension_complete:
        return jsonify({'error': 'comprehension_required',
                        'message': 'Complete the comprehension questions before revealing.'}), 400

    view_builder = SynthesisViewBuilder()
    return jsonify(view_builder.get_board_conclusions(case_id))


# =============================================================================
# RETROSPECTIVE REFLECTION ROUTES
# =============================================================================

@study_bp.route('/retrospective', methods=['GET', 'POST'])
def retrospective():
    """Post-study retrospective reflection (5-view ranking + open feedback)."""
    val_session, redirect_resp = _require_session()
    if redirect_resp:
        return redirect_resp

    if request.method == 'POST':
        return _submit_retrospective(val_session)

    existing = RetrospectiveReflection.query.filter_by(
        session_id=val_session.id
    ).first()

    return render_template('validation_study/retrospective.html',
                           participant_code=val_session.participant_code,
                           session=val_session,
                           existing=existing)


def _submit_retrospective(val_session):
    """Process retrospective submission. Enforces 1-5 rank permutation."""
    try:
        reflection = RetrospectiveReflection.query.filter_by(
            session_id=val_session.id
        ).first()

        if not reflection:
            reflection = RetrospectiveReflection(
                session_id=val_session.id,
                evaluator_id=val_session.participant_code,
                evaluator_domain=val_session.evaluator_domain
            )
            db.session.add(reflection)

        def get_int(name):
            val = request.form.get(name)
            if val is not None and val != '':
                try:
                    return int(val)
                except ValueError:
                    return None
            return None

        reflection.rank_provisions_view = get_int('rank_provisions_view')
        reflection.rank_qc_view = get_int('rank_qc_view')
        reflection.rank_decisions_view = get_int('rank_decisions_view')
        reflection.rank_timeline_view = get_int('rank_timeline_view')
        reflection.rank_narrative_view = get_int('rank_narrative_view')

        if not reflection.rankings_valid:
            flash('Please assign each view a distinct rank from 1 through 5.', 'warning')
            db.session.rollback()
            return redirect(url_for('study.retrospective'))

        surfaced = request.form.get('surfaced_missed_considerations')
        reflection.surfaced_missed_considerations = (surfaced == 'yes')
        reflection.surfaced_considerations_text = request.form.get('surfaced_considerations_text', '').strip()

        reflection.missing_elements = request.form.get('missing_elements', '').strip()
        reflection.improvement_suggestions = request.form.get('improvement_suggestions', '').strip()
        reflection.general_comments = request.form.get('general_comments', '').strip()

        val_session.completed_at = datetime.utcnow()

        db.session.commit()

        flash('Thank you for completing the study.', 'success')
        return redirect(url_for('study.complete'))

    except Exception as e:
        logger.exception(f"Error submitting retrospective: {str(e)}")
        db.session.rollback()
        flash(f'Error saving reflection: {str(e)}', 'error')
        return redirect(url_for('study.retrospective'))


@study_bp.route('/complete')
def complete():
    """Study completion page."""
    code = get_participant_code()
    return render_template('validation_study/complete.html',
                           participant_code=code)


# =============================================================================
# API ENDPOINTS
# =============================================================================

@study_bp.route('/api/evaluable-cases')
def api_evaluable_cases():
    """Get list of cases available for the study (23-case pool)."""
    view_builder = SynthesisViewBuilder()
    cases = view_builder.get_evaluable_cases()
    return jsonify({'cases': cases, 'count': len(cases)})


@study_bp.route('/api/case/<int:case_id>/views')
def api_case_views(case_id):
    """Get all synthesis views for a case (for AJAX loading)."""
    view_builder = SynthesisViewBuilder()

    if not view_builder.case_has_synthesis(case_id):
        return jsonify({'error': 'Case does not have synthesis data'}), 404

    return jsonify(view_builder.get_all_views(case_id))


@study_bp.route('/api/case/<int:case_id>/facts')
def api_case_facts(case_id):
    """Get case facts only (Discussion/Conclusions withheld)."""
    view_builder = SynthesisViewBuilder()
    return jsonify(view_builder.get_case_facts(case_id))


# =============================================================================
# ADMIN ROUTES (require admin in production)
# =============================================================================

from app.utils.environment_auth import admin_required_production
from flask import Response
from sqlalchemy import func, distinct


@study_bp.route('/admin/')
@admin_required_production
def admin_dashboard():
    """Validation studies management dashboard."""
    from app.models.experiment import ExperimentRun, Prediction, ExperimentEvaluation
    from app.services.experiment.validation_export_service import ValidationExportService

    # Get experiment statistics (old comparative system)
    total_studies = ExperimentRun.query.count()
    completed_studies = ExperimentRun.query.filter_by(status='completed').count()

    # Get prediction statistics
    total_predictions = Prediction.query.count()
    proethica_predictions = Prediction.query.filter_by(condition='proethica').count()
    baseline_predictions = Prediction.query.filter_by(condition='baseline').count()

    # Get evaluation statistics (old system)
    total_evaluations = ExperimentEvaluation.query.count()
    unique_evaluators = db.session.query(
        func.count(distinct(ExperimentEvaluation.evaluator_id))
    ).scalar() or 0

    # Get case statistics
    available_cases = Document.query.filter(
        Document.document_type.in_(['case', 'case_study'])
    ).count()

    # Get cases with predictions
    cases_with_pred_ids = db.session.query(distinct(Prediction.document_id)).all()
    cases_with_predictions_count = len(cases_with_pred_ids)

    # View Utility statistics
    view_utility_sessions = ValidationSession.query.count()
    view_utility_completed_sessions = ValidationSession.query.filter(
        ValidationSession.completed_at.isnot(None)
    ).count()
    view_utility_evaluations = ViewUtilityEvaluation.query.count()
    view_utility_evaluators = db.session.query(
        func.count(distinct(ViewUtilityEvaluation.evaluator_id))
    ).scalar() or 0
    view_utility_retrospectives = RetrospectiveReflection.query.count()

    # Build stats dictionary
    stats = {
        'total_studies': total_studies,
        'completed_studies': completed_studies,
        'total_predictions': total_predictions,
        'proethica_predictions': proethica_predictions,
        'baseline_predictions': baseline_predictions,
        'total_evaluations': total_evaluations,
        'unique_evaluators': unique_evaluators,
        'available_cases': available_cases,
        'cases_with_predictions': cases_with_predictions_count,
        # View utility stats
        'chapter4_sessions': view_utility_sessions,
        'chapter4_completed_sessions': view_utility_completed_sessions,
        'chapter4_evaluations': view_utility_evaluations,
        'chapter4_evaluators': view_utility_evaluators,
        'chapter4_retrospectives': view_utility_retrospectives
    }

    # Get recent studies
    studies = ExperimentRun.query.order_by(
        ExperimentRun.created_at.desc()
    ).limit(10).all()

    # Get cases that have predictions
    cases_with_predictions = []
    if cases_with_pred_ids:
        pred_case_ids = [c[0] for c in cases_with_pred_ids if c[0] is not None]
        if pred_case_ids:
            cases = Document.query.filter(Document.id.in_(pred_case_ids)).all()
            for case in cases:
                from app.models.experiment import Prediction
                prediction_count = Prediction.query.filter_by(document_id=case.id).count()
                case.prediction_count = prediction_count
                cases_with_predictions.append(case)

    # Get all available cases for the generate predictions modal
    all_cases = Document.query.filter(
        Document.document_type.in_(['case', 'case_study'])
    ).order_by(Document.title).all()

    return render_template('validation_study/admin_dashboard.html',
                         stats=stats,
                         studies=studies,
                         cases_with_predictions=cases_with_predictions,
                         all_cases=all_cases)


@study_bp.route('/admin/export')
@admin_required_production
def admin_export():
    """Export validation data for Krippendorff's alpha analysis."""
    from app.services.experiment.validation_export_service import ValidationExportService

    # Get query parameters
    format_type = request.args.get('format', 'csv')
    domain = request.args.get('domain')
    use_means = request.args.get('level', 'means') == 'means'
    experiment_run_id = request.args.get('experiment_run_id', type=int)

    export_service = ValidationExportService()
    content, filename = export_service.export_for_krippendorff(
        experiment_run_id=experiment_run_id,
        domain=domain,
        use_means=use_means,
        format=format_type
    )

    if format_type == 'json':
        mimetype = 'application/json'
    else:
        mimetype = 'text/csv'

    return Response(
        content,
        mimetype=mimetype,
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )


@study_bp.route('/admin/summary')
@admin_required_production
def admin_summary():
    """Get summary statistics comparing baseline vs ProEthica."""
    from app.services.experiment.validation_export_service import ValidationExportService

    domain = request.args.get('domain')
    experiment_run_id = request.args.get('experiment_run_id', type=int)

    export_service = ValidationExportService()
    summary = export_service.export_comparison_summary(
        experiment_run_id=experiment_run_id,
        domain=domain
    )

    return jsonify(summary)


@study_bp.route('/admin/evaluator-progress')
@admin_required_production
def admin_evaluator_progress():
    """Get progress summary for each evaluator."""
    from app.services.experiment.validation_export_service import ValidationExportService

    experiment_run_id = request.args.get('experiment_run_id', type=int)

    export_service = ValidationExportService()
    progress = export_service.get_evaluator_progress(
        experiment_run_id=experiment_run_id
    )

    return jsonify({'evaluators': progress})


# =============================================================================
# STUDY FLOW ROUTES
# =============================================================================

@study_bp.route('/view-synthesis/<int:case_id>')
def view_synthesis(case_id):
    """Redirect to Step 4 Review in validation-study mode (legacy integration)."""
    session['validation_study_mode'] = True
    return redirect(url_for('step4.step4_review', case_id=case_id, validation_mode='1'))


@study_bp.route('/exit-validation-mode')
def exit_validation_mode():
    """Clear validation-study mode from session."""
    session.pop('validation_study_mode', None)
    flash('Exited validation study mode.', 'info')
    return redirect(url_for('main.home'))


# =============================================================================
# DEMO ROUTES (for screenshots and presentation)
# =============================================================================

@study_bp.route('/demo/view/<view_type>')
def demo_view_utility(view_type):
    """Demo page showing a single synthesis view with Likert ratings.

    For screenshots. Not a study route - no participant code required.
    """
    if view_type not in ['provisions', 'qc', 'decisions', 'timeline', 'narrative']:
        view_type = 'provisions'

    view_builder = SynthesisViewBuilder()
    evaluable_cases = view_builder.get_evaluable_cases()

    if not evaluable_cases:
        flash('No cases with complete synthesis available for demo.', 'warning')
        return redirect(url_for('study.index'))

    # Use Case 7 (AI in Engineering) if available, otherwise first pool case
    case_id = 7
    case_exists = any(c['id'] == 7 for c in evaluable_cases)
    if not case_exists:
        case_id = evaluable_cases[0]['id']

    document = Document.query.get_or_404(case_id)
    views = view_builder.get_all_views(case_id)

    view_data = views.get(view_type, views['provisions'])

    return render_template('validation_study/view_utility_demo.html',
                           document=document,
                           view_type=view_type,
                           view_name=view_type,
                           view_data=view_data)
