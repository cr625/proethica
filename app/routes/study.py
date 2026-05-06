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

import hashlib
import logging
import os
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
from app.services.validation.likert_items import (
    NARR_ITEMS, TIMELINE_ITEMS, QC_ITEMS, DECS_ITEMS, PROV_ITEMS, OVERALL_ITEMS,
)

logger = logging.getLogger(__name__)

study_bp = Blueprint('study', __name__)


@study_bp.context_processor
def inject_validation_session():
    """Make the active ValidationSession available to all study templates.

    Used by _base_study.html to render the preview-mode banner without
    each route having to pass val_session explicitly. Returns under the
    name `validation_session` so it does not collide with Flask's
    request-scoped `session` object.
    """
    code = session.get('participant_code')
    if not code:
        return {'validation_session': None}
    val_session = ValidationSession.query.filter_by(participant_code=code).first()
    return {'validation_session': val_session}


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

# Information Sheet versions. Bump these when the .docx (or template) changes
# and update the corresponding template together.
# v2.1 (2026-04-30): added mention of post-task demographics questionnaire.
# v2.2 (2026-04-30 later): generalized "senior design" language to cover
#   any Drexel student arrival; clarified that comprehension questions are
#   required while other items are skippable (resolves UX walkthrough P1-1
#   info-sheet vs HTML required-attribute conflict).
# v3-prolific updated in lockstep with the comprehension-required clarification.
INFO_SHEET_VERSION = 'v2.2'                  # Drexel-student senior-design channel (HRP-506)
INFO_SHEET_VERSION_PROLIFIC = 'v3-prolific'  # Prolific adult-population channel (HRP-506b)

# Ambiguity-stripped alphabet for participant codes (no 0/O, 1/I, L).
CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
CODE_LENGTH = 8

# Prolific URL parameter names. Prolific's External Study integration injects
# these via {{%PROLIFIC_PID%}}, {{%STUDY_ID%}}, {{%SESSION_ID%}} substitution.
PROLIFIC_PARAMS = ('prolific_pid', 'study_id', 'session_id')

# Prolific submission-completion URL pattern. Participants are redirected here
# after they finish; the `cc` param is the fixed completion code registered in
# the Prolific study config (env: PROLIFIC_COMPLETION_CODE_SUCCESS).
PROLIFIC_COMPLETION_URL_BASE = 'https://app.prolific.com/submissions/complete'


def generate_participant_code() -> str:
    """Random 8-character alphanumeric code. No crosswalk to identity."""
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def generate_completion_code() -> str:
    """Random 8-character completion code, distinct from the participant code.

    Crowdsourcing platforms reject a study that prints the participant code
    as the completion proof. The completion code is generated only at the
    moment the participant finishes (post-demographics) and is what they
    paste into Prolific.
    """
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def hash_prolific_pid(pid: str) -> str:
    """SHA-256 hex of a Prolific PID, for duplicate-enrollment detection.

    The plain PID is never persisted. Only the hash is stored, and only on
    the validation_sessions row.
    """
    return hashlib.sha256(pid.encode('utf-8')).hexdigest()


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


def capture_prolific_params() -> dict | None:
    """Read Prolific URL parameters from the request and stash them in the
    Flask session so they survive the consent submit.

    Returns the captured dict, or None if no Prolific PID is present. Once
    captured, subsequent requests can read them out of `session` without
    relying on the URL.
    """
    pid = request.args.get('prolific_pid', '').strip()
    if not pid:
        return None
    payload = {
        'prolific_pid': pid,
        'study_id': request.args.get('study_id', '').strip(),
        'session_id': request.args.get('session_id', '').strip(),
    }
    session['prolific'] = payload
    return payload


def get_stashed_prolific() -> dict | None:
    """Return the stashed Prolific params dict, or None."""
    return session.get('prolific')


def create_session(
    domain: str = 'engineering',
    recruitment_source: str = 'drexel_student',
    prolific_pid_hash: str | None = None,
    info_sheet_version: str = INFO_SHEET_VERSION,
) -> ValidationSession:
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
        recruitment_source=recruitment_source,
        prolific_pid_hash=prolific_pid_hash,
        assigned_cases=assigned,
        completed_cases=[],
        consent_acknowledged_at=datetime.utcnow(),
        info_sheet_version=info_sheet_version,
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

    Prolific entry: when the URL carries ?prolific_pid=...&study_id=...&session_id=...,
    those values are stashed in the Flask session and the consent screen renders
    the adult-population (HRP-506b) information sheet instead of the
    Drexel-student (HRP-506) one. Both reference the same IRB protocol.
    """
    capture_prolific_params()

    code = get_participant_code()

    is_prolific = get_stashed_prolific() is not None

    if not code:
        return render_template('validation_study/index.html',
                               phase='consent',
                               info_sheet_version=(INFO_SHEET_VERSION_PROLIFIC if is_prolific else INFO_SHEET_VERSION),
                               is_prolific=is_prolific)

    val_session = load_session(code)
    if not val_session:
        flash(f'No study session found for code {code}. Check for typos or start a new session.', 'warning')
        session.pop('participant_code', None)
        return render_template('validation_study/index.html',
                               phase='consent',
                               info_sheet_version=(INFO_SHEET_VERSION_PROLIFIC if is_prolific else INFO_SHEET_VERSION),
                               is_prolific=is_prolific,
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
    """Create a new session after the participant acknowledges the consent.

    Routes the new session into one of two recruitment channels based on
    whether a Prolific PID was stashed during the landing visit:
    - With Prolific PID: 'prolific_engineering_trained', adult-population
      consent (HRP-506b), Prolific completion-code redemption.
    - Without: 'drexel_student', senior-design consent (HRP-506), the
      original protocol channel.

    Same IRB protocol number governs both channels post-amendment.
    Duplicate enrollment from the same Prolific PID (e.g., a participant
    who quit and restarted) is rejected.
    """
    if request.form.get('consent') != 'yes':
        flash('You must acknowledge the information sheet to participate.', 'warning')
        return redirect(url_for('study.index'))

    prolific = get_stashed_prolific()
    if prolific:
        pid_hash = hash_prolific_pid(prolific['prolific_pid'])
        existing = ValidationSession.query.filter_by(prolific_pid_hash=pid_hash).first()
        if existing is not None:
            # Same Prolific account already enrolled. Resume rather than
            # double-enroll. Discard the stashed PID so the resumed session
            # is treated as a normal returning participant.
            session.pop('prolific', None)
            flash(
                'A study session already exists for this Prolific account. '
                f'Resuming your session: code {existing.participant_code}.',
                'info'
            )
            return redirect(url_for('study.index', code=existing.participant_code))

        val_session = create_session(
            domain='engineering',
            recruitment_source='prolific_engineering_trained',
            prolific_pid_hash=pid_hash,
            info_sheet_version=INFO_SHEET_VERSION_PROLIFIC,
        )
    else:
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
                           current_step=step,
                           NARR_ITEMS=NARR_ITEMS,
                           TIMELINE_ITEMS=TIMELINE_ITEMS,
                           QC_ITEMS=QC_ITEMS,
                           DECS_ITEMS=DECS_ITEMS,
                           PROV_ITEMS=PROV_ITEMS,
                           OVERALL_ITEMS=OVERALL_ITEMS)


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

        # Attention check (plan §4.4). Pass = response equals 1 ("Strongly
        # Disagree"). Stored raw; pass/fail derived at analysis time.
        evaluation.attention_check_response = get_int('attention_check_response')

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

        # Per-view tab dwell time (inline-layout v8 schema)
        evaluation.time_view_narrative = get_int('time_view_narrative')
        evaluation.time_view_timeline = get_int('time_view_timeline')
        evaluation.time_view_qc = get_int('time_view_qc')
        evaluation.time_view_decisions = get_int('time_view_decisions')
        evaluation.time_view_provisions = get_int('time_view_provisions')

        # Mark completion
        if evaluation.is_complete:
            evaluation.completed_at = datetime.utcnow()
            completed = set(val_session.completed_cases or [])
            completed.add(case_id)
            val_session.completed_cases = list(completed)

            # Time-on-task floor check (plan validation-study.md §4.5).
            # Tag for analyst review if the content-engagement timer sum
            # (facts + views + comprehension, in ms) is below the configured
            # floor. Leaves NULL when any of the three timers is missing.
            content_timers = (
                evaluation.time_facts_review,
                evaluation.time_views_review,
                evaluation.time_comprehension,
            )
            if all(t is not None for t in content_timers):
                floor_seconds = int(os.environ.get('STUDY_TIME_FLOOR_SECONDS', '180'))
                evaluation.low_effort_flag = sum(content_timers) < floor_seconds * 1000

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

        # Note: completed_at is NOT set here (post-pivot). The study now ends
        # after the demographics page, where completed_at and completion_code
        # are set together. Retrospective submission only persists the rankings
        # and open feedback.
        db.session.commit()

        return redirect(url_for('study.demographics'))

    except Exception as e:
        logger.exception(f"Error submitting retrospective: {str(e)}")
        db.session.rollback()
        flash(f'Error saving reflection: {str(e)}', 'error')
        return redirect(url_for('study.retrospective'))


# Allowed demographic values, narrow enough to keep analysis categorical.
# Free-text not accepted.
_DEGREE_VALUES = {
    'high_school', 'some_college', 'associate',
    'bachelor', 'master', 'doctorate', 'other', 'prefer_not'
}
_EXPERIENCE_VALUES = {
    'student', 'lt_2', '2_5', '6_10', '11_20', 'gt_20', 'prefer_not'
}
_ROLE_VALUES = {
    'student', 'practicing_engineer', 'engineering_manager',
    'engineering_educator', 'former_engineer', 'other', 'prefer_not'
}


@study_bp.route('/demographics', methods=['GET', 'POST'])
def demographics():
    """Post-task demographic capture (plan §4.3).

    Single page between retrospective and complete. 4-6 closed-form items.
    Submitting this page generates the completion_code and finalizes the
    session (completed_at).
    """
    val_session, redirect_resp = _require_session()
    if redirect_resp:
        return redirect_resp

    if request.method == 'POST':
        return _submit_demographics(val_session)

    return render_template('validation_study/demographics.html',
                           participant_code=val_session.participant_code,
                           session=val_session,
                           is_prolific=(val_session.recruitment_source == 'prolific_engineering_trained'))


def _submit_demographics(val_session):
    """Persist demographics, generate completion code, finalize the session."""
    try:
        degree = request.form.get('highest_engineering_degree', '').strip()
        experience = request.form.get('years_engineering_experience', '').strip()
        role = request.form.get('role_category', '').strip()
        familiarity_raw = request.form.get('nspe_pe_familiarity', '').strip()
        prior_ethics_raw = request.form.get('prior_ethics_course', '').strip()

        if degree not in _DEGREE_VALUES:
            flash('Select an option for highest engineering-related degree.', 'warning')
            return redirect(url_for('study.demographics'))
        if experience not in _EXPERIENCE_VALUES:
            flash('Select an option for engineering experience.', 'warning')
            return redirect(url_for('study.demographics'))
        if role not in _ROLE_VALUES:
            flash('Select an option for current role.', 'warning')
            return redirect(url_for('study.demographics'))

        familiarity = None
        if familiarity_raw:
            familiarity = int(familiarity_raw)
            if familiarity < 1 or familiarity > 5:
                flash('NSPE/PE familiarity rating must be between 1 and 5.', 'warning')
                return redirect(url_for('study.demographics'))

        prior_ethics = None
        if prior_ethics_raw == 'yes':
            prior_ethics = True
        elif prior_ethics_raw == 'no':
            prior_ethics = False

        val_session.highest_engineering_degree = degree
        val_session.years_engineering_experience = experience
        val_session.role_category = role
        val_session.nspe_pe_familiarity = familiarity
        val_session.prior_ethics_course = prior_ethics
        val_session.demographics_completed_at = datetime.utcnow()

        # Finalize: generate completion_code and stamp completed_at. The
        # completion_code is what the participant pastes into Prolific.
        if not val_session.completion_code:
            code = generate_completion_code()
            while ValidationSession.query.filter_by(completion_code=code).first() is not None:
                code = generate_completion_code()
            val_session.completion_code = code
        if not val_session.completed_at:
            val_session.completed_at = datetime.utcnow()

        db.session.commit()

        flash('Thank you for completing the study.', 'success')
        return redirect(url_for('study.complete'))

    except Exception as e:
        logger.exception(f"Error submitting demographics: {str(e)}")
        db.session.rollback()
        flash(f'Error saving demographics: {str(e)}', 'error')
        return redirect(url_for('study.demographics'))


@study_bp.route('/complete')
def complete():
    """Study completion page.

    For Drexel-channel participants: shows the per-session completion_code as
    a small confirmation reference.

    For Prolific-channel participants: shows a "Return to Prolific" button
    (auto-redirect to Prolific's submissions/complete URL with the fixed
    completion code from PROLIFIC_COMPLETION_CODE_SUCCESS env var) plus the
    fixed code as a paste fallback. The per-session completion_code is shown
    as a small "Reference" line for our internal audit.

    If the env var is unset (e.g., before the Prolific account exists), the
    page degrades to manual paste of the per-session code only, with a
    dev-only banner noting the missing configuration.
    """
    code = get_participant_code()
    val_session = load_session(code) if code else None

    completion_code = val_session.completion_code if val_session else None
    is_prolific = (
        val_session is not None
        and val_session.recruitment_source == 'prolific_engineering_trained'
    )

    fixed_prolific_cc = os.environ.get('PROLIFIC_COMPLETION_CODE_SUCCESS', '').strip() or None
    prolific_return_url = (
        f"{PROLIFIC_COMPLETION_URL_BASE}?cc={fixed_prolific_cc}"
        if fixed_prolific_cc else None
    )

    return render_template('validation_study/complete.html',
                           participant_code=code,
                           completion_code=completion_code,
                           is_prolific=is_prolific,
                           fixed_prolific_cc=fixed_prolific_cc,
                           prolific_return_url=prolific_return_url)


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
    """Validation study admin dashboard.

    Focused on the active view-utility study (validation pivot, plan
    `proethica/.claude/plans/validation-study.md`). Surfaces the operational metrics
    needed to monitor enrollment, completion, per-case coverage (against
    the 23-case pool with n>=5 threshold), and data-quality flags
    (attention-check pass rate, demographics completion).

    The legacy comparative-prediction system (ExperimentRun / Prediction /
    double-blind evaluation) is intentionally NOT surfaced here during the
    pivot. A collapsed link to `/experiment/` remains for ad-hoc access.
    Revisit post-pivot if the legacy admin panels are still needed for
    Chapter 4 secondary analyses.
    """
    from app.config.study_case_pool import STUDY_CASE_POOL_IDS, STUDY_CASE_POOL_SIZE

    # Enrollment, by recruitment_source.
    by_source_rows = db.session.query(
        ValidationSession.recruitment_source,
        func.count(ValidationSession.id).label('enrolled'),
        func.count(ValidationSession.completed_at).label('completed'),
    ).group_by(ValidationSession.recruitment_source).all()
    by_source = {
        row.recruitment_source: {'enrolled': row.enrolled, 'completed': row.completed}
        for row in by_source_rows
    }
    # Ensure both channels appear in the UI even at zero.
    for src in ('drexel_student', 'prolific_engineering_trained'):
        by_source.setdefault(src, {'enrolled': 0, 'completed': 0})

    total_enrolled = sum(s['enrolled'] for s in by_source.values())
    total_completed = sum(s['completed'] for s in by_source.values())
    total_in_progress = total_enrolled - total_completed

    # Per-case coverage against the 23-case study pool.
    # Counts distinct evaluators per case (only completed evaluations).
    coverage_rows = db.session.query(
        ViewUtilityEvaluation.case_id,
        func.count(distinct(ViewUtilityEvaluation.evaluator_id)).label('n_raters'),
    ).filter(
        ViewUtilityEvaluation.case_id.in_(STUDY_CASE_POOL_IDS),
        ViewUtilityEvaluation.completed_at.isnot(None),
    ).group_by(ViewUtilityEvaluation.case_id).all()
    coverage_map = {row.case_id: row.n_raters for row in coverage_rows}

    # Build coverage list ordered by case_id, with title for display.
    case_titles = {
        d.id: d.title
        for d in Document.query.filter(Document.id.in_(STUDY_CASE_POOL_IDS)).all()
    }
    coverage_threshold = 5  # Krippendorff floor per plan §0 #6
    coverage = []
    for cid in STUDY_CASE_POOL_IDS:
        n = coverage_map.get(cid, 0)
        coverage.append({
            'case_id': cid,
            'title': case_titles.get(cid, f'Case {cid}'),
            'n_raters': n,
            'meets_threshold': n >= coverage_threshold,
        })
    coverage_under = [c for c in coverage if not c['meets_threshold']]

    # Data-quality flags.
    total_evals = ViewUtilityEvaluation.query.filter(
        ViewUtilityEvaluation.completed_at.isnot(None)
    ).count()
    attn_answered = ViewUtilityEvaluation.query.filter(
        ViewUtilityEvaluation.attention_check_response.isnot(None)
    ).count()
    attn_passed = ViewUtilityEvaluation.query.filter(
        ViewUtilityEvaluation.attention_check_response == 1
    ).count()
    low_effort_flagged = ViewUtilityEvaluation.query.filter(
        ViewUtilityEvaluation.low_effort_flag.is_(True)
    ).count()
    demographics_completed = ValidationSession.query.filter(
        ValidationSession.demographics_completed_at.isnot(None)
    ).count()

    # Recent sessions for the operations table (last 10).
    recent_sessions = ValidationSession.query.order_by(
        ValidationSession.started_at.desc()
    ).limit(10).all()

    stats = {
        'total_enrolled': total_enrolled,
        'total_completed': total_completed,
        'total_in_progress': total_in_progress,
        'pool_size': STUDY_CASE_POOL_SIZE,
        'coverage_threshold': coverage_threshold,
        'cases_meeting_threshold': sum(1 for c in coverage if c['meets_threshold']),
        'cases_under_threshold': len(coverage_under),
        'total_evaluations': total_evals,
        'attention_check_answered': attn_answered,
        'attention_check_passed': attn_passed,
        'attention_check_pass_rate': (
            round(100.0 * attn_passed / attn_answered, 1) if attn_answered else None
        ),
        'low_effort_flagged': low_effort_flagged,
        'demographics_completed': demographics_completed,
        'demographics_completion_rate': (
            round(100.0 * demographics_completed / total_completed, 1)
            if total_completed else None
        ),
        'by_source': by_source,
    }

    return render_template('validation_study/admin_dashboard.html',
                           stats=stats,
                           coverage=coverage,
                           coverage_under=coverage_under,
                           recent_sessions=recent_sessions)


@study_bp.route('/admin/export')
@admin_required_production
def admin_export():
    """Export study view-utility data for Krippendorff's alpha analysis.

    Default scope is the engineering domain (IRB-approved pool); pass
    `?domain=all` to include any stray non-engineering sessions.
    `?level=items` returns per-item data for Krippendorff; otherwise view means.
    """
    from app.services.experiment.validation_export_service import ValidationExportService

    format_type = request.args.get('format', 'csv')
    domain_param = request.args.get('domain', 'engineering')
    domain = None if domain_param == 'all' else domain_param
    use_means = request.args.get('level', 'means') == 'means'

    export_service = ValidationExportService()
    content, filename = export_service.export_chapter4_for_krippendorff(
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

@study_bp.route('/preview/start')
def preview_start():
    """Bootstrap a preview session that walks the live case-evaluation flow.

    Creates a ValidationSession with recruitment_source='preview' so that any
    submissions accumulated by reviewers exploring the interface are tagged
    for analysis exclusion. The session is otherwise indistinguishable from
    a real participant session, which means reviewers see the actual
    template, the actual rating UI, and the actual data — not a slimmed
    demo template.

    No participant code, consent screen, or Prolific PID required. The
    preview banner in _base_study.html surfaces the recruitment-source tag
    so the participant-mode framing is unambiguous.
    """
    view_builder = SynthesisViewBuilder()
    evaluable_cases = view_builder.get_evaluable_cases()
    if not evaluable_cases:
        flash('No cases with complete synthesis available for preview.', 'warning')
        return redirect(url_for('study.index'))

    # Case 7 (AI in Engineering) is the canonical demo case; fall back to
    # the first evaluable case if it has been retired.
    preferred_case_id = 7
    case_exists = any(c['id'] == preferred_case_id for c in evaluable_cases)
    case_id = preferred_case_id if case_exists else evaluable_cases[0]['id']

    code = 'PREVIEW-' + ''.join(secrets.choice(CODE_ALPHABET) for _ in range(6))
    while ValidationSession.query.filter_by(participant_code=code).first() is not None:
        code = 'PREVIEW-' + ''.join(secrets.choice(CODE_ALPHABET) for _ in range(6))

    val_session = ValidationSession(
        session_id=str(uuid.uuid4())[:8],
        evaluator_id=code,
        participant_code=code,
        evaluator_domain='engineering',
        recruitment_source='preview',
        assigned_cases=[case_id],
        completed_cases=[],
        consent_acknowledged_at=datetime.utcnow(),
        info_sheet_version='preview',
    )
    db.session.add(val_session)
    db.session.flush()

    # Optional demo prefill (`?prefill=1`). Populates the ViewUtilityEvaluation
    # row with realistic-looking ratings and demo-flagged comprehension answers
    # so the page renders fully filled out for screenshots and walkthroughs.
    # The reverse-coded attention check (overall_surfaced_considerations) is
    # set to 1 so the prefilled session passes the attention gate. Preview
    # rows are tagged for analysis exclusion regardless.
    if request.args.get('prefill'):
        prefilled = ViewUtilityEvaluation(
            session_id=val_session.id,
            case_id=case_id,
            evaluator_id=code,
            started_at=datetime.utcnow(),
            narr_characters_tensions=5, narr_relationships_clear=6, narr_ethical_significance=4,
            timeline_temporal_sequence=6, timeline_causal_links=5, timeline_obligation_activation=5,
            qc_issues_visible=6, qc_emergence_resolution=5, qc_deliberation_needs=6,
            decs_choices_understood=5, decs_argumentative_structure=5, decs_actions_obligations=6,
            prov_standards_identified=6, prov_connections_clear=5, prov_normative_foundation=5,
            overall_helped_understand=6,
            overall_surfaced_considerations=1,
            overall_useful_deliberation=6,
            attention_check_response=1,
            comp_main_tensions='[Demo prefill] Authorship integrity vs. timeline pressure; verification duty under deadline.',
            comp_relevant_provisions='[Demo prefill] II.2.a (competence); II.5 (honesty in services); III.3 (avoiding deceptive acts).',
            comp_decision_points='[Demo prefill] Whether to seal AI-generated content; whether to disclose tool use to client.',
            comp_deliberation_factors='[Demo prefill] Verification depth, client transparency, license obligations, public-safety duty.',
        )
        db.session.add(prefilled)

    db.session.commit()
    session['participant_code'] = code
    flash(
        'Preview mode: this session is tagged for exclusion from study analysis.',
        'info'
    )
    return redirect(url_for('study.evaluate_case', case_id=case_id, step='facts'))
