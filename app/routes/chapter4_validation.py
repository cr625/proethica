"""
View Utility Study Routes.

Evaluator-facing routes for the synthesis view utility assessment:
- Part 1: Component Utility Assessment (rate each synthesis view)
- Part 2: Ground Truth Alignment (comprehension questions, reveal conclusions)
- Part 3: Retrospective Reflection (rank views, provide feedback)

This evaluates whether structured synthesis VIEWS help evaluators
understand professional ethics cases.
"""

import logging
import hashlib
import uuid
from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Document
from app.models.view_utility_evaluation import (
    ValidationSession, ViewUtilityEvaluation, RetrospectiveReflection
)
from app.services.validation.synthesis_view_builder import SynthesisViewBuilder

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint - evaluator-facing study routes (login required, not admin)
study_bp = Blueprint('study', __name__)


def generate_participant_id():
    """Generate anonymous but consistent participant ID from session/IP."""
    if 'study_participant_id' in session:
        return session['study_participant_id']

    identifier = f"{request.remote_addr}:{request.user_agent.string}"
    hash_val = hashlib.sha256(identifier.encode()).hexdigest()[:8]
    participant_id = f"V{hash_val.upper()}"

    session['study_participant_id'] = participant_id
    return participant_id


def get_or_create_session(evaluator_id: str, domain: str = 'engineering') -> ValidationSession:
    """Get existing session or create new one for evaluator."""
    existing = ValidationSession.query.filter_by(
        evaluator_id=evaluator_id
    ).filter(
        ValidationSession.completed_at.is_(None)
    ).first()

    if existing:
        return existing

    # Create new session
    session_id = str(uuid.uuid4())[:8]
    view_builder = SynthesisViewBuilder()
    evaluable_cases = view_builder.get_evaluable_cases(domain=domain)

    new_session = ValidationSession(
        session_id=session_id,
        evaluator_id=evaluator_id,
        evaluator_domain=domain,
        assigned_cases=[c['id'] for c in evaluable_cases],
        completed_cases=[]
    )
    db.session.add(new_session)
    db.session.commit()

    return new_session


# =============================================================================
# SESSION MANAGEMENT ROUTES
# =============================================================================

@study_bp.route('/')
@login_required
def index():
    """Chapter 4 validation landing page."""
    participant_id = generate_participant_id()
    domain = request.args.get('domain', session.get('evaluator_domain', 'engineering'))
    session['evaluator_domain'] = domain

    # Get or create validation session
    val_session = get_or_create_session(participant_id, domain)

    # Get evaluable cases
    view_builder = SynthesisViewBuilder()
    evaluable_cases = view_builder.get_evaluable_cases(domain=domain)

    # Determine next case to evaluate
    completed = set(val_session.completed_cases or [])
    next_case = None
    for case in evaluable_cases:
        if case['id'] not in completed:
            next_case = case
            break

    return render_template('validation_study/index.html',
                           participant_id=participant_id,
                           domain=domain,
                           session=val_session,
                           evaluable_cases=evaluable_cases,
                           next_case=next_case,
                           completed_count=len(completed),
                           total_count=len(evaluable_cases))


@study_bp.route('/session/<session_id>/status')
@login_required
def session_status(session_id):
    """Get current session status (for AJAX)."""
    val_session = ValidationSession.query.filter_by(session_id=session_id).first_or_404()

    return jsonify({
        'session_id': val_session.session_id,
        'evaluator_id': val_session.evaluator_id,
        'progress_percent': val_session.progress_percent,
        'completed_cases': val_session.completed_cases or [],
        'assigned_cases': val_session.assigned_cases or [],
        'is_complete': val_session.is_complete
    })


# =============================================================================
# CASE EVALUATION ROUTES
# =============================================================================

@study_bp.route('/case/<int:case_id>', methods=['GET'])
@login_required
def evaluate_case(case_id):
    """Main evaluation page for a case - implements stepped flow."""
    participant_id = generate_participant_id()
    domain = session.get('evaluator_domain', 'engineering')

    # Get validation session
    val_session = get_or_create_session(participant_id, domain)

    # Get case document
    document = Document.query.get_or_404(case_id)

    # Get synthesis views
    view_builder = SynthesisViewBuilder()

    if not view_builder.case_has_synthesis(case_id):
        flash('This case does not have sufficient synthesis data for evaluation.', 'warning')
        return redirect(url_for('study.index'))

    # Get all views
    case_facts = view_builder.get_case_facts(case_id)
    views = view_builder.get_all_views(case_id)

    # Check if already evaluated
    existing_eval = ViewUtilityEvaluation.query.filter_by(
        session_id=val_session.id,
        case_id=case_id
    ).first()

    # Determine current step
    step = request.args.get('step', 'facts')
    if step not in ['facts', 'views', 'utility', 'comprehension', 'reveal', 'alignment']:
        step = 'facts'

    return render_template('validation_study/case_evaluation.html',
                           document=document,
                           case_facts=case_facts,
                           views=views,
                           participant_id=participant_id,
                           session=val_session,
                           existing_eval=existing_eval,
                           current_step=step,
                           domain=domain)


@study_bp.route('/case/<int:case_id>/submit', methods=['POST'])
@login_required
def submit_evaluation(case_id):
    """Submit evaluation for a case."""
    participant_id = generate_participant_id()
    domain = session.get('evaluator_domain', 'engineering')

    val_session = get_or_create_session(participant_id, domain)

    try:
        # Create or update evaluation
        evaluation = ViewUtilityEvaluation.query.filter_by(
            session_id=val_session.id,
            case_id=case_id
        ).first()

        if not evaluation:
            evaluation = ViewUtilityEvaluation(
                session_id=val_session.id,
                case_id=case_id,
                evaluator_id=participant_id,
                started_at=datetime.utcnow()
            )
            db.session.add(evaluation)

        # Helper to get form value as integer
        def get_int(name):
            val = request.form.get(name)
            if val is not None and val != '':
                try:
                    return int(val)
                except ValueError:
                    return None
            return None

        # Part 1: View Utility Items (15 items)
        # Provisions View
        evaluation.prov_standards_identified = get_int('prov_standards_identified')
        evaluation.prov_connections_clear = get_int('prov_connections_clear')
        evaluation.prov_normative_foundation = get_int('prov_normative_foundation')

        # Questions View
        evaluation.ques_issues_visible = get_int('ques_issues_visible')
        evaluation.ques_structure_aided = get_int('ques_structure_aided')
        evaluation.ques_deliberation_needs = get_int('ques_deliberation_needs')

        # Decisions View
        evaluation.decs_choices_understood = get_int('decs_choices_understood')
        evaluation.decs_alternatives_context = get_int('decs_alternatives_context')
        evaluation.decs_actions_obligations = get_int('decs_actions_obligations')

        # Narrative View
        evaluation.narr_situation_understood = get_int('narr_situation_understood')
        evaluation.narr_relationships_clear = get_int('narr_relationships_clear')
        evaluation.narr_sequence_clear = get_int('narr_sequence_clear')

        # Overall Utility
        evaluation.overall_helped_understand = get_int('overall_helped_understand')
        evaluation.overall_surfaced_considerations = get_int('overall_surfaced_considerations')
        evaluation.overall_useful_deliberation = get_int('overall_useful_deliberation')

        # Part 2: Comprehension Questions
        evaluation.comp_main_tensions = request.form.get('comp_main_tensions', '').strip()
        evaluation.comp_relevant_provisions = request.form.get('comp_relevant_provisions', '').strip()
        evaluation.comp_decision_points = request.form.get('comp_decision_points', '').strip()
        evaluation.comp_deliberation_factors = request.form.get('comp_deliberation_factors', '').strip()

        # Part 2: Alignment Self-Assessment
        evaluation.alignment_self_rating = get_int('alignment_self_rating')
        evaluation.alignment_reflection = request.form.get('alignment_reflection', '').strip()

        # Track time spent (from hidden fields)
        evaluation.time_facts_review = get_int('time_facts_review')
        evaluation.time_views_review = get_int('time_views_review')
        evaluation.time_utility_rating = get_int('time_utility_rating')
        evaluation.time_comprehension = get_int('time_comprehension')
        evaluation.time_alignment = get_int('time_alignment')

        # Mark completion
        if evaluation.is_complete:
            evaluation.completed_at = datetime.utcnow()

            # Update session completed cases
            completed = set(val_session.completed_cases or [])
            completed.add(case_id)
            val_session.completed_cases = list(completed)

        db.session.commit()

        if evaluation.is_complete:
            flash('Evaluation submitted successfully.', 'success')

            # Check if all cases completed
            if val_session.is_complete:
                return redirect(url_for('study.retrospective'))
            else:
                return redirect(url_for('study.index'))
        else:
            flash('Evaluation saved. Please complete all fields.', 'warning')
            return redirect(url_for('study.evaluate_case', case_id=case_id, step='utility'))

    except Exception as e:
        logger.exception(f"Error submitting evaluation for case {case_id}: {str(e)}")
        db.session.rollback()
        flash(f'Error saving evaluation: {str(e)}', 'error')
        return redirect(url_for('study.evaluate_case', case_id=case_id))


@study_bp.route('/case/<int:case_id>/reveal')
@login_required
def reveal_conclusions(case_id):
    """Reveal board conclusions after comprehension questions."""
    view_builder = SynthesisViewBuilder()
    conclusions = view_builder.get_board_conclusions(case_id)

    return jsonify(conclusions)


# =============================================================================
# RETROSPECTIVE REFLECTION ROUTES
# =============================================================================

@study_bp.route('/retrospective', methods=['GET', 'POST'])
@login_required
def retrospective():
    """Post-study retrospective reflection."""
    participant_id = generate_participant_id()
    domain = session.get('evaluator_domain', 'engineering')

    val_session = get_or_create_session(participant_id, domain)

    if request.method == 'POST':
        return _submit_retrospective(val_session, participant_id, domain)

    # Check if retrospective already submitted
    existing = RetrospectiveReflection.query.filter_by(
        session_id=val_session.id
    ).first()

    return render_template('validation_study/retrospective.html',
                           participant_id=participant_id,
                           domain=domain,
                           session=val_session,
                           existing=existing)


def _submit_retrospective(val_session, participant_id, domain):
    """Process retrospective submission."""
    try:
        reflection = RetrospectiveReflection.query.filter_by(
            session_id=val_session.id
        ).first()

        if not reflection:
            reflection = RetrospectiveReflection(
                session_id=val_session.id,
                evaluator_id=participant_id,
                evaluator_domain=domain
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

        # View rankings
        reflection.rank_provisions_view = get_int('rank_provisions_view')
        reflection.rank_questions_view = get_int('rank_questions_view')
        reflection.rank_decisions_view = get_int('rank_decisions_view')
        reflection.rank_narrative_view = get_int('rank_narrative_view')

        # Surfaced considerations
        surfaced = request.form.get('surfaced_missed_considerations')
        reflection.surfaced_missed_considerations = (surfaced == 'yes')
        reflection.surfaced_considerations_text = request.form.get('surfaced_considerations_text', '').strip()

        # Open feedback
        reflection.missing_elements = request.form.get('missing_elements', '').strip()
        reflection.improvement_suggestions = request.form.get('improvement_suggestions', '').strip()
        reflection.general_comments = request.form.get('general_comments', '').strip()

        # Mark session complete
        val_session.completed_at = datetime.utcnow()

        db.session.commit()

        flash('Thank you for completing the validation study!', 'success')
        return redirect(url_for('study.complete'))

    except Exception as e:
        logger.exception(f"Error submitting retrospective: {str(e)}")
        db.session.rollback()
        flash(f'Error saving reflection: {str(e)}', 'error')
        return redirect(url_for('study.retrospective'))


@study_bp.route('/complete')
@login_required
def complete():
    """Study completion page."""
    participant_id = generate_participant_id()

    return render_template('validation_study/complete.html',
                           participant_id=participant_id)


# =============================================================================
# API ENDPOINTS
# =============================================================================

@study_bp.route('/api/evaluable-cases')
@login_required
def api_evaluable_cases():
    """Get list of cases available for evaluation."""
    domain = request.args.get('domain')
    view_builder = SynthesisViewBuilder()
    cases = view_builder.get_evaluable_cases(domain=domain)
    return jsonify({'cases': cases, 'count': len(cases)})


@study_bp.route('/api/case/<int:case_id>/views')
@login_required
def api_case_views(case_id):
    """Get all synthesis views for a case (for AJAX loading)."""
    view_builder = SynthesisViewBuilder()

    if not view_builder.case_has_synthesis(case_id):
        return jsonify({'error': 'Case does not have synthesis data'}), 404

    return jsonify(view_builder.get_all_views(case_id))


@study_bp.route('/api/case/<int:case_id>/facts')
@login_required
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
