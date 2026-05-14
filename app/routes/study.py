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
import random
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
# v2.1 (2026-04-30): added mention of post-task demographics questionnaire
#   (later removed 2026-05-12; demographics moved to Prolific prescreening).
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
    moment the participant finishes (on retrospective submission) and is
    what they paste into Prolific.
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


def create_preview_consent_session(
    domain: str = 'engineering',
    prolific_pid_hash: str | None = None,
) -> ValidationSession:
    """Create a session for an advisor walking consent -> case -> completion.

    Companion to create_session for the /preview/start?show=consent path.
    Each call produces a fresh session tagged recruitment_source='preview'
    (excluded from study analysis) with exactly one case assigned (case 7
    by default), so multiple advisors can share the same URL without
    picking up each other's state. The Prolific PID stashed upstream by
    the consent-mode preview route is unique per visit, so no two preview
    enrollments collide on prolific_pid_hash even though the duplicate-
    enrollment check is skipped here.
    """
    code = generate_participant_code()
    while ValidationSession.query.filter_by(participant_code=code).first() is not None:
        code = generate_participant_code()

    from app.services.validation.synthesis_view_builder import SynthesisViewBuilder
    view_builder = SynthesisViewBuilder()
    evaluable_cases = view_builder.get_evaluable_cases()
    preferred_case_id = 7
    if any(c['id'] == preferred_case_id for c in evaluable_cases):
        case_id = preferred_case_id
    elif evaluable_cases:
        case_id = evaluable_cases[0]['id']
    else:
        case_id = preferred_case_id  # last-resort fallback

    new_session = ValidationSession(
        session_id=str(uuid.uuid4())[:8],
        evaluator_id=code,
        participant_code=code,
        evaluator_domain=domain,
        recruitment_source='preview',
        prolific_pid_hash=prolific_pid_hash,
        assigned_cases=[case_id],
        completed_cases=[],
        consent_acknowledged_at=datetime.utcnow(),
        info_sheet_version=INFO_SHEET_VERSION_PROLIFIC,
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

    # Stale-cookie guard. If a Prolific entry URL just arrived but the
    # cookied participant_code points at a session that does not belong
    # to this Prolific identity (a prior preview session, a different
    # participant on a shared browser, or any unrelated leftover), clear
    # the cookied code so the consent screen renders for the new
    # arrival. Same-PID resume is handled separately in enroll() via the
    # prolific_pid_hash duplicate-detection branch.
    stashed = get_stashed_prolific()
    if stashed:
        cookied_code = session.get('participant_code')
        if cookied_code:
            cookied_session = load_session(cookied_code)
            arriving_hash = hash_prolific_pid(stashed['prolific_pid'])
            if cookied_session is None or cookied_session.prolific_pid_hash != arriving_hash:
                session.pop('participant_code', None)

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

    # Orientation gate. New sessions (post-2026-05-08) start with
    # orientation_completed_at NULL and are redirected here on first
    # arrival at the dashboard. Legacy sessions backfilled by
    # migrate_study_schema_v10.sql have a non-NULL value and proceed
    # straight to the dashboard.
    if val_session.orientation_completed_at is None:
        return redirect(url_for('study.orientation'))

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

    retrospective_complete = bool(
        val_session.retrospective and val_session.retrospective.is_complete
    )

    return render_template('validation_study/index.html',
                           phase='dashboard',
                           participant_code=code,
                           session=val_session,
                           case_summaries=case_summaries,
                           next_case=next_case,
                           completed_count=len(completed),
                           total_count=len(assigned_ids),
                           retrospective_complete=retrospective_complete)


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
    # Preview-mode enrollment (set by /preview/start?show=consent). Skips the
    # duplicate-enrollment check, tags recruitment_source='preview' for
    # analysis exclusion, and assigns exactly one case. Each consent-mode
    # visit synthesizes a unique Prolific PID upstream, so no two preview
    # visits collide on prolific_pid_hash.
    preview_mode = session.pop('preview_mode', False)
    if prolific:
        pid_hash = hash_prolific_pid(prolific['prolific_pid'])
        if preview_mode:
            val_session = create_preview_consent_session(
                domain='engineering',
                prolific_pid_hash=pid_hash,
            )
        else:
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
    # New sessions land on the orientation page first. The participant code is
    # also surfaced there. The dashboard renders only after orientation submit
    # (or for returning participants whose orientation_completed_at is set).
    return redirect(url_for('study.orientation'))


@study_bp.route('/exit')
def exit_session():
    """Clear the current code from the browser session (code itself still works for return)."""
    session.pop('participant_code', None)
    flash('You have exited. Re-enter your code to return to your session.', 'info')
    return redirect(url_for('study.index'))


@study_bp.route('/orientation', methods=['GET', 'POST'])
def orientation():
    """Post-consent orientation screen.

    First-time participants land here after consent and walk through the
    per-case workflow, the five view glossary, and the post-cases steps
    in a single sequenced page. POST stamps `orientation_completed_at`
    on the session and redirects to the dashboard.

    Returning participants (resume-by-code) skip orientation entirely:
    `study.index` checks `orientation_completed_at` and only redirects
    here when the value is NULL.

    See .claude/plans/participant-onboarding-redesign.md.
    """
    code = get_participant_code()
    if not code:
        flash('Please consent to the study before accessing orientation.', 'warning')
        return redirect(url_for('study.index'))

    val_session = load_session(code)
    if not val_session:
        flash(f'No study session found for code {code}. Please re-enter your code.', 'warning')
        session.pop('participant_code', None)
        return redirect(url_for('study.index'))

    if request.method == 'POST':
        if val_session.orientation_completed_at is None:
            val_session.orientation_completed_at = datetime.utcnow()
            db.session.commit()
        return redirect(url_for('study.index', code=val_session.participant_code))

    # Build the case-summaries metadata the template needs to display
    # "After your N cases" with the right plural N.
    assigned_count = len(val_session.assigned_cases or [])

    return render_template(
        'validation_study/orientation.html',
        participant_code=val_session.participant_code,
        total_count=assigned_count,
        is_prolific=(val_session.recruitment_source in ('prolific_engineering_trained', 'preview')),
        session=val_session,
    )


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
    # URL aliases preserved across the 2026-05-10 step reorg:
    #   - 'utility'    → 'comprehension' (now the Reflection step)
    #   - 'alignment'  → 'reveal'        (alignment merged into the Wrap-up step)
    valid_steps = ['facts', 'views', 'comprehension', 'reveal']
    if step == 'utility':
        return redirect(url_for('study.evaluate_case', case_id=case_id, step='comprehension'))
    if step == 'alignment':
        return redirect(url_for('study.evaluate_case', case_id=case_id, step='reveal'))
    if step not in valid_steps:
        step = 'facts'

    # Server-side rating gates (mirror the JS pill-lock so the gate cannot
    # be bypassed by URL navigation):
    #   - Step 3 (Reflection, URL `comprehension`) requires all 15
    #     per-view utility items rated.
    #   - Step 4 (Wrap-up, URL `reveal`) requires all 18 items rated
    #     (the 15 per-view + 3 Overall items now living on Step 3).
    if step == 'comprehension':
        if not existing_eval or not existing_eval.view_ratings_complete:
            flash('Please complete the per-view ratings before continuing.', 'warning')
            return redirect(url_for('study.evaluate_case', case_id=case_id, step='views'))
    if step == 'reveal':
        if not existing_eval or not existing_eval.all_utility_items_complete:
            flash('Please complete the Overall view rating before continuing.', 'warning')
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

        # Part 2': Reflection (2026-05-10 reorg, design-utility framing).
        # All three fields are optional. Legacy comprehension and alignment
        # fields are still accepted by the form parser so any partially
        # completed pre-reorg sessions don't lose data; new sessions will
        # leave them NULL.
        evaluation.refl_most_useful_view = request.form.get('refl_most_useful_view', '').strip() or None
        evaluation.refl_changes = request.form.get('refl_changes', '').strip() or None
        evaluation.refl_final = request.form.get('refl_final', '').strip() or None

        # Legacy fields — accepted but not required.
        evaluation.comp_main_tensions = request.form.get('comp_main_tensions', '').strip() or evaluation.comp_main_tensions
        evaluation.comp_relevant_provisions = request.form.get('comp_relevant_provisions', '').strip() or evaluation.comp_relevant_provisions
        evaluation.comp_decision_points = request.form.get('comp_decision_points', '').strip() or evaluation.comp_decision_points
        evaluation.comp_deliberation_factors = request.form.get('comp_deliberation_factors', '').strip() or evaluation.comp_deliberation_factors
        evaluation.alignment_self_rating = get_int('alignment_self_rating') or evaluation.alignment_self_rating
        evaluation.alignment_reflection = request.form.get('alignment_reflection', '').strip() or evaluation.alignment_reflection

        # Timing (Fix A, 2026-05-14). The case_evaluation.html template
        # hard-codes `value="0"` on every hidden timer input. When the
        # final submit fires from Step 4 (Wrap-up), the page was
        # re-rendered after the intermediate Step 3→4 save, so the
        # accumulated client-side timer values that were already
        # persisted by the intermediate save would be clobbered with 0
        # by the unconditional assignment that lived here. Guard each
        # write so a posted 0 never overwrites a previously-stored
        # nonzero value; the JS accumulator only ever produces
        # monotonically increasing values, so the larger-of-the-two
        # rule is safe.
        def _set_timer(name):
            val = get_int(name)
            if val is None or val <= 0:
                return
            current = getattr(evaluation, name) or 0
            if val > current:
                setattr(evaluation, name, val)

        _set_timer('time_facts_review')
        _set_timer('time_views_review')
        _set_timer('time_timeline_review')
        _set_timer('time_utility_rating')
        _set_timer('time_comprehension')
        _set_timer('time_alignment')

        # Per-view tab dwell time (inline-layout v8 schema)
        _set_timer('time_view_narrative')
        _set_timer('time_view_timeline')
        _set_timer('time_view_qc')
        _set_timer('time_view_decisions')
        _set_timer('time_view_provisions')

        # Submit semantics depend on which button sent the form. The Wrap-up
        # "Submit Evaluation" button has no `name`, so its submission carries
        # no `next_step` value -- that is the finalize signal. Intermediate
        # "Continue to <step>" buttons carry the target step as `next_step`
        # and only persist progress, even if all 18 utility items are filled.
        next_step = (request.form.get('next_step') or '').strip()
        finalize = (next_step == '') and evaluation.is_complete

        if finalize:
            evaluation.completed_at = datetime.utcnow()
            completed = set(val_session.completed_cases or [])
            completed.add(case_id)
            val_session.completed_cases = list(completed)

            # Time-on-task floor check (Fix C, 2026-05-14; plan
            # validation-study.md §4.5). The pre-2026-05-14 implementation
            # summed three client-side JS timer columns
            # (time_facts_review + time_views_review + time_comprehension),
            # which were systematically zero on every Prolific completion
            # because the Wrap-up step page-reload reset the hidden inputs
            # to value="0" before the final submit (see Fix A above).
            # The flag is now derived from session-level wall-clock divided
            # across the cases the participant has finalized so far, which
            # cannot be reset by template churn. Running average is fine:
            # a participant who paces consistently will get a stable flag
            # across their assigned cases; the few-second-per-case rusher
            # is the screening target, and the running avg flags them
            # at every case.
            if val_session.started_at:
                floor_seconds = int(os.environ.get('STUDY_TIME_FLOOR_SECONDS', '180'))
                session_seconds = (datetime.utcnow() - val_session.started_at).total_seconds()
                avg_seconds_per_case = session_seconds / max(1, len(completed))
                evaluation.low_effort_flag = avg_seconds_per_case < floor_seconds

        db.session.commit()

        if finalize:
            flash('Evaluation submitted successfully.', 'success')
            if val_session.is_complete:
                return redirect(url_for('study.retrospective'))
            return redirect(url_for('study.index'))

        flash('Progress saved.', 'info')
        return redirect(url_for('study.evaluate_case', case_id=case_id, step=next_step or 'comprehension'))

    except Exception as e:
        logger.exception(f"Error submitting evaluation for case {case_id}: {str(e)}")
        db.session.rollback()
        flash(f'Error saving evaluation: {str(e)}', 'error')
        return redirect(url_for('study.evaluate_case', case_id=case_id))


@study_bp.route('/case/<int:case_id>/reveal')
def reveal_conclusions(case_id):
    """Return the BER's discussion + conclusions for the Wrap-up step.

    2026-05-10: gating relaxed. The participant needs an active session
    but the comprehension_complete pre-condition (legacy) is no longer
    enforced.
    """
    val_session, redirect_resp = _require_session()
    if redirect_resp:
        return jsonify({'error': 'no_session'}), 403

    view_builder = SynthesisViewBuilder()
    return jsonify(view_builder.get_board_conclusions(case_id))


# =============================================================================
# RETROSPECTIVE REFLECTION ROUTES
# =============================================================================

# Source-of-truth metadata for the five views shown on the Retrospective
# ranking step. Order is intentionally NOT tab-order on the case page: the
# route below shuffles this list before render so a participant who skips
# the drag step does not implicitly endorse tab order as their ranking.
_RANKING_VIEWS = [
    {
        'slug': 'narrative',
        'name': 'Narrative View',
        'icon_class': 'bi bi-journal-text',
        'icon_color_class': 'text-success',
        'icon_style': '',
        'description': 'Characters with ethical tensions and opening states',
    },
    {
        'slug': 'timeline',
        'name': 'Timeline View',
        'icon_class': 'bi bi-clock-history',
        'icon_color_class': '',
        'icon_style': 'color: #20c997;',
        'description': 'Actions and events in temporal sequence with nested decision points',
    },
    {
        'slug': 'qc',
        'name': 'Conclusions View',
        'icon_class': 'bi bi-question-circle',
        'icon_color_class': '',
        'icon_style': 'color: #6f42c1;',
        'description': "Each board question paired with the Board’s ruling, plus analytical questions for additional perspective.",
    },
    {
        'slug': 'decisions',
        'name': 'Decisions View',
        'icon_class': 'bi bi-signpost-split',
        'icon_color_class': '',
        'icon_style': 'color: #fd7e14;',
        'description': 'Decision points with arguments for and against each option',
    },
    {
        'slug': 'provisions',
        'name': 'Provisions View',
        'icon_class': 'bi bi-book',
        'icon_color_class': 'text-primary',
        'icon_style': '',
        'description': 'Code provisions mapped to case elements',
    },
]


@study_bp.route('/retrospective', methods=['GET', 'POST'])
def retrospective():
    """Post-study retrospective reflection (5-view ranking + open feedback).

    Submission is one-shot. Once the participant has submitted successfully
    (signalled by `completed_at` being stamped on the ValidationSession),
    further GETs and POSTs are bounced to /complete. This prevents both
    accidental form re-entry (browser back) and deliberate edits to the
    ranking or open-text fields after the participant has been shown their
    completion code.
    """
    val_session, redirect_resp = _require_session()
    if redirect_resp:
        return redirect_resp

    if val_session.completed_at:
        if request.method == 'POST':
            flash('Your retrospective has already been recorded. '
                  'Further changes are not accepted.', 'info')
        return redirect(url_for('study.complete'))

    if request.method == 'POST':
        return _submit_retrospective(val_session)

    existing = RetrospectiveReflection.query.filter_by(
        session_id=val_session.id
    ).first()

    # Shuffle the five-view list so the initial rank-list does not match
    # case-page tab order. Hidden-input names are per-view, so submissions
    # map back to the correct view regardless of rendered position.
    ranking_views = list(_RANKING_VIEWS)
    random.shuffle(ranking_views)

    return render_template('validation_study/retrospective.html',
                           participant_code=val_session.participant_code,
                           session=val_session,
                           existing=existing,
                           ranking_views=ranking_views)


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
        if surfaced == 'yes':
            reflection.surfaced_missed_considerations = True
        elif surfaced == 'no':
            reflection.surfaced_missed_considerations = False
        else:
            reflection.surfaced_missed_considerations = None
        reflection.surfaced_considerations_text = request.form.get('surfaced_considerations_text', '').strip()

        reflection.missing_elements = request.form.get('missing_elements', '').strip()
        reflection.improvement_suggestions = request.form.get('improvement_suggestions', '').strip()
        reflection.general_comments = request.form.get('general_comments', '').strip()

        # Finalize: generate completion_code and stamp completed_at.
        # Retrospective submission is the final participant action since
        # the legacy demographics page was removed on 2026-05-11 (IRB
        # Protocol v8 reconciliation: the protocol does not enumerate
        # demographic items, so deployed collection has been retired in
        # favor of the Prolific platform's own prescreen capture).
        if not val_session.completion_code:
            code = generate_completion_code()
            while ValidationSession.query.filter_by(completion_code=code).first() is not None:
                code = generate_completion_code()
            val_session.completion_code = code
        if not val_session.completed_at:
            val_session.completed_at = datetime.utcnow()

        db.session.commit()

        return redirect(url_for('study.complete'))

    except Exception as e:
        logger.exception(f"Error submitting retrospective: {str(e)}")
        db.session.rollback()
        flash(f'Error saving reflection: {str(e)}', 'error')
        return redirect(url_for('study.retrospective'))
# Demographics route retired 2026-05-11 (IRB Protocol v8 reconciliation).
# The protocol references "a brief demographic questionnaire" but does not
# enumerate items, and the Prolific platform captures occupation, industry,
# and degree subject through its own prescreen filters. The legacy
# ValidationSession columns (highest_engineering_degree, years_engineering_experience,
# role_category, nspe_pe_familiarity, prior_ethics_course, demographics_completed_at)
# are retained on the model for back-compat with pre-retirement rows but are
# not populated for new sessions. Completion-code generation moved to
# _submit_retrospective; see above.
#
# Thin GET redirect for any cached links (advisor share URLs, in-flight
# preview tabs that loaded the old form). Anyone landing here lands on the
# completion page; if the session somehow lacks a completion_code (e.g. a
# pre-retirement session whose retrospective submit happened on legacy code
# but whose demographics submit never ran), mint the code now so the
# completion page renders correctly.
@study_bp.route('/demographics')
def demographics():
    val_session, redirect_resp = _require_session()
    if redirect_resp:
        return redirect_resp
    if not val_session.completion_code:
        code = generate_completion_code()
        while ValidationSession.query.filter_by(completion_code=code).first() is not None:
            code = generate_completion_code()
        val_session.completion_code = code
    if not val_session.completed_at:
        val_session.completed_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('study.complete'))


@study_bp.route('/complete')
def complete():
    """Study completion page.

    For Drexel-channel participants: shows the per-session completion_code
    as a small confirmation reference.

    For Prolific-channel participants: shows a "Return to Prolific" button
    that redirects to Prolific's submissions/complete URL with the value
    of PROLIFIC_COMPLETION_CODE_SUCCESS as the cc parameter. Prolific
    verifies cc against the single completion-path code configured in the
    study; sending anything else fails verification and the participant is
    not credited. The same value also appears in the manual-paste fallback
    so the participant has a recovery path if the redirect button fails.

    The per-session completion_code remains on validation_sessions as an
    audit reference and is shown to Drexel-channel participants and in the
    configuration-issue notice; it is not sent to Prolific.

    If the env var is unset, the page degrades to a configuration-issue
    notice instructing the participant to contact the research team.
    """
    code = get_participant_code()
    val_session = load_session(code) if code else None

    completion_code = val_session.completion_code if val_session else None
    is_prolific = (
        val_session is not None
        and val_session.recruitment_source in ('prolific_engineering_trained', 'preview')
    )

    prolific_completion_code = os.environ.get('PROLIFIC_COMPLETION_CODE_SUCCESS', '').strip()
    prolific_return_url = (
        f"{PROLIFIC_COMPLETION_URL_BASE}?cc={prolific_completion_code}"
        if prolific_completion_code and completion_code else None
    )

    return render_template('validation_study/complete.html',
                           participant_code=code,
                           completion_code=completion_code,
                           is_prolific=is_prolific,
                           prolific_completion_code=prolific_completion_code,
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
    (attention-check pass rate, low-effort flags).

    The legacy comparative-prediction system (ExperimentRun / Prediction /
    double-blind evaluation) is intentionally NOT surfaced here during the
    pivot. A collapsed link to `/experiment/` remains for ad-hoc access.
    Revisit post-pivot if the legacy admin panels are still needed for
    Chapter 4 secondary analyses.
    """
    from app.config.study_case_pool import STUDY_CASE_POOL_IDS, STUDY_CASE_POOL_SIZE
    from app.models.view_utility_evaluation import RetrospectiveReflection

    # Real recruitment channels only. `preview` is the demo-walkthrough
    # bypass and `drexel_student` is the dormant legacy default (no live
    # Drexel recruitment under the post-pivot protocol), so both are noise
    # on the operational dashboard. The export endpoint still surfaces
    # them in raw data when needed for archive/audit purposes.
    REAL_SOURCES = ('prolific_engineering_trained',)

    real_session_ids_subq = db.session.query(ValidationSession.id).filter(
        ValidationSession.recruitment_source.in_(REAL_SOURCES)
    ).subquery()

    # Enrollment, by recruitment_source (real channels only).
    by_source_rows = db.session.query(
        ValidationSession.recruitment_source,
        func.count(ValidationSession.id).label('enrolled'),
        func.count(ValidationSession.completed_at).label('completed'),
    ).filter(
        ValidationSession.recruitment_source.in_(REAL_SOURCES)
    ).group_by(ValidationSession.recruitment_source).all()
    by_source = {
        row.recruitment_source: {'enrolled': row.enrolled, 'completed': row.completed}
        for row in by_source_rows
    }
    # Ensure each real channel appears in the UI even at zero.
    for src in REAL_SOURCES:
        by_source.setdefault(src, {'enrolled': 0, 'completed': 0})

    total_enrolled = sum(s['enrolled'] for s in by_source.values())
    total_completed = sum(s['completed'] for s in by_source.values())
    total_in_progress = total_enrolled - total_completed

    # Per-case coverage against the 23-case study pool.
    # Counts distinct evaluators per case (only completed evaluations from
    # real channels).
    coverage_rows = db.session.query(
        ViewUtilityEvaluation.case_id,
        func.count(distinct(ViewUtilityEvaluation.evaluator_id)).label('n_raters'),
    ).filter(
        ViewUtilityEvaluation.case_id.in_(STUDY_CASE_POOL_IDS),
        ViewUtilityEvaluation.completed_at.isnot(None),
        ViewUtilityEvaluation.session_id.in_(real_session_ids_subq),
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

    # Data-quality flags. Restricted to evaluations from real channels.
    real_evals_base = ViewUtilityEvaluation.query.filter(
        ViewUtilityEvaluation.session_id.in_(real_session_ids_subq)
    )
    total_evals = real_evals_base.filter(
        ViewUtilityEvaluation.completed_at.isnot(None)
    ).count()
    # The attention-check item is the reverse-coded Overall item
    # `overall_surfaced_considerations` (pass = response of 1). The dedicated
    # `attention_check_response` column is unpopulated for real sessions
    # because the rendered form field name is the item name, not
    # `attention_check_response`; derive the count from the column that
    # actually carries the participant's response.
    attn_answered = real_evals_base.filter(
        ViewUtilityEvaluation.overall_surfaced_considerations.isnot(None)
    ).count()
    attn_passed = real_evals_base.filter(
        ViewUtilityEvaluation.overall_surfaced_considerations == 1
    ).count()
    low_effort_flagged = real_evals_base.filter(
        ViewUtilityEvaluation.low_effort_flag.is_(True)
    ).count()

    # Recent sessions for the operations table (last 10, real channels only).
    recent_sessions = ValidationSession.query.filter(
        ValidationSession.recruitment_source.in_(REAL_SOURCES)
    ).order_by(
        ValidationSession.started_at.desc()
    ).limit(10).all()

    # =========================================================================
    # Results aggregations (drive the visualization section)
    # =========================================================================

    # Per-view mean utility score (1-7 Likert) across all completed
    # evaluations from real channels. Each view contributes 3 items; the
    # Overall row reverse-codes `overall_surfaced_considerations` via
    # ViewUtilityEvaluation.overall_utility_mean.
    completed_evals = real_evals_base.filter(
        ViewUtilityEvaluation.completed_at.isnot(None)
    ).all()

    def _summarize(values):
        """Return (mean, sd, n) for a list, ignoring None. SD is the
        sample standard deviation (n-1); None when n < 2."""
        clean = [v for v in values if v is not None]
        n = len(clean)
        if n == 0:
            return None, None, 0
        mean = sum(clean) / n
        if n < 2:
            return round(mean, 2), None, n
        variance = sum((v - mean) ** 2 for v in clean) / (n - 1)
        return round(mean, 2), round(variance ** 0.5, 2), n

    view_specs = [
        ('Provisions', 'provisions_view_mean'),
        ('Q&C', 'qc_view_mean'),
        ('Decisions', 'decisions_view_mean'),
        ('Timeline', 'timeline_view_mean'),
        ('Narrative', 'narrative_view_mean'),
        ('Overall', 'overall_utility_mean'),
    ]
    view_means = []
    for label, attr in view_specs:
        mean, sd, n = _summarize([getattr(e, attr) for e in completed_evals])
        view_means.append({'label': label, 'mean': mean, 'sd': sd, 'n': n})

    # Retrospective rankings: rank 1 (most valuable) to 5 (least). For
    # each view, count how many participants placed it at each rank. The
    # stacked-bar chart shows the rank-1 segment at the top, rank-5 at
    # the bottom.
    retros = RetrospectiveReflection.query.filter(
        RetrospectiveReflection.session_id.in_(real_session_ids_subq)
    ).all()
    ranking_specs = [
        ('Provisions', 'rank_provisions_view'),
        ('Q&C', 'rank_qc_view'),
        ('Decisions', 'rank_decisions_view'),
        ('Timeline', 'rank_timeline_view'),
        ('Narrative', 'rank_narrative_view'),
    ]
    ranking_counts = []
    for label, attr in ranking_specs:
        counts = [0, 0, 0, 0, 0]  # index 0 = rank 1
        for r in retros:
            val = getattr(r, attr)
            if val is not None and 1 <= val <= 5:
                counts[val - 1] += 1
        ranking_counts.append({'label': label, 'counts': counts})

    # Per-case mean overall utility (only cases with at least one
    # completed evaluation from a real channel). Sorted descending by mean.
    case_means_by_id = {}
    for e in completed_evals:
        score = e.overall_utility_mean
        if score is None:
            continue
        case_means_by_id.setdefault(e.case_id, []).append(score)
    per_case_means = []
    for cid, scores in case_means_by_id.items():
        per_case_means.append({
            'case_id': cid,
            'title': case_titles.get(cid, f'Case {cid}'),
            'mean': round(sum(scores) / len(scores), 2),
            'n': len(scores),
        })
    per_case_means.sort(key=lambda r: r['mean'], reverse=True)

    results = {
        'view_means': view_means,
        'ranking_counts': ranking_counts,
        'per_case_means': per_case_means,
        'n_completed_evals': len(completed_evals),
        'n_retrospectives': len(retros),
    }

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
        'by_source': by_source,
    }

    return render_template('validation_study/admin_dashboard.html',
                           stats=stats,
                           coverage=coverage,
                           coverage_under=coverage_under,
                           recent_sessions=recent_sessions,
                           results=results)


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

    Threat model. The URL is shareable; anyone who navigates to
    `/preview/start` mints a session that bypasses consent (the route
    stamps `consent_acknowledged_at=datetime.utcnow()` and
    `info_sheet_version='preview'`). This is acceptable because every
    such session is tagged `recruitment_source='preview'` and excluded
    from study analysis at the query layer. Investigators distributing
    the URL should treat it as a public link rather than a credentialed
    channel; sharing it with a non-participant audience does not
    contaminate the dataset and does not violate the IRB protocol
    because the bypass cannot produce a record that enters analysis.
    The completion screen's reference to "the information sheet you
    acknowledged at enrollment" is dangling for any preview session,
    which is an accepted cost of keeping the route open.
    """
    # ?show=consent renders the consent screen using the Prolific v3
    # information sheet so an advisor can walk the full participant flow
    # (consent -> orientation -> 1 case -> retrospective -> completion).
    # Each visit gets a fresh synthetic Prolific PID, so two
    # advisors sharing the URL will not pick up each other's session. The
    # preview_mode flag is honored downstream by /enroll, which creates
    # the session via create_preview_consent_session (tagged
    # recruitment_source='preview', one case assigned).
    show = request.args.get('show')
    if show == 'consent':
        session.clear()
        pid = 'PREVIEW-' + ''.join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        session['prolific'] = {
            'prolific_pid': pid,
            'study_id': 'PREVIEW',
            'session_id': str(uuid.uuid4())[:8],
            'arrived_at': datetime.utcnow().isoformat(),
        }
        session['preview_mode'] = True
        return render_template(
            'validation_study/index.html',
            phase='consent',
            info_sheet_version=INFO_SHEET_VERSION_PROLIFIC,
            is_prolific=True,
        )

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

    # `?show=...` lands the preview on a specific screen. Supported values:
    #   consent       — Prolific consent screen (handled above, returns early)
    #   orientation   — Before-you-start (skips orientation_completed_at stamp)
    #   dashboard     — study dashboard
    #   (default)     — case-evaluation flow (Facts step)
    #   retrospective — post-cases view-ranking page (pre-stamps case as complete)
    #   complete      — final completion page (also pre-stamps ranking + code)
    # The legacy `demographics` value was retired on 2026-05-11 along with
    # the deployed demographic questionnaire (IRB Protocol v8 reconciliation).
    # `show` was read at the top of the function for the consent branch.
    skip_orientation_stamp = (show == 'orientation')
    post_case_show = show in ('retrospective', 'complete')

    val_session = ValidationSession(
        session_id=str(uuid.uuid4())[:8],
        evaluator_id=code,
        participant_code=code,
        evaluator_domain='engineering',
        recruitment_source='preview',
        assigned_cases=[case_id],
        completed_cases=([case_id] if post_case_show else []),
        consent_acknowledged_at=datetime.utcnow(),
        orientation_completed_at=(None if skip_orientation_stamp else datetime.utcnow()),
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

    # Pre-stamp post-case state when previewing later screens, so each page
    # renders with realistic-looking data instead of empty fields.
    if show == 'complete':
        retro = RetrospectiveReflection(
            session_id=val_session.id,
            evaluator_id=code,
            evaluator_domain='engineering',
            rank_narrative_view=1,
            rank_timeline_view=2,
            rank_qc_view=3,
            rank_decisions_view=4,
            rank_provisions_view=5,
            surfaced_missed_considerations=True,
            surfaced_considerations_text='[Demo prefill] The Decisions view raised a tradeoff I had not considered.',
            general_comments='[Demo prefill] The structured views made it easier to track competing obligations.',
        )
        db.session.add(retro)
        completion_code = generate_completion_code()
        while ValidationSession.query.filter_by(completion_code=completion_code).first() is not None:
            completion_code = generate_completion_code()
        val_session.completion_code = completion_code
        val_session.completed_at = datetime.utcnow()

    db.session.commit()
    session['participant_code'] = code
    # The persistent preview banner in _base_study.html already announces
    # preview status; an additional transient flash here would duplicate it.
    if show == 'orientation':
        return redirect(url_for('study.orientation'))
    if show == 'dashboard':
        return redirect(url_for('study.index'))
    if show == 'retrospective':
        return redirect(url_for('study.retrospective'))
    if show == 'complete':
        return redirect(url_for('study.complete'))
    return redirect(url_for('study.evaluate_case', case_id=case_id, step='facts'))
