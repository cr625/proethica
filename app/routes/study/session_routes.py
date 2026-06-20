"""Landing/dashboard, consent enrollment, exit, orientation, AJAX session status, plus the bp context_processor (inject_validation_session) and CSRF errorhandler (handle_csrf_error).."""
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
from app.routes.study.helpers import (
    INFO_SHEET_VERSION,
    INFO_SHEET_VERSION_PROLIFIC,
    hash_prolific_pid,
    get_participant_code,
    load_session,
    capture_prolific_params,
    get_stashed_prolific,
    create_session,
    create_preview_consent_session,
)


def register_session_routes(bp):
    @bp.context_processor
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
    @bp.errorhandler(CSRFError)
    def handle_csrf_error(e):
        """Graceful handling for stale CSRF tokens on study forms.

    Most common cause: the dev server restarted between the landing-page load
    and the form submit, invalidating the token. Participant flow should
    bounce back to the landing page (which renders a fresh token) rather
    than show a bare 400 page.
    """
        flash('Your session expired or the page was stale. Please start again.', 'warning')
        return redirect(url_for('study.index'))
    @bp.route('/')
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
    @bp.route('/enroll', methods=['POST'])
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
    @bp.route('/exit')
    def exit_session():
        """Clear the current code from the browser session (code itself still works for return)."""
        session.pop('participant_code', None)
        flash('You have exited. Re-enter your code to return to your session.', 'info')
        return redirect(url_for('study.index'))
    @bp.route('/orientation', methods=['GET', 'POST'])
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
    @bp.route('/session/<session_id>/status')
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
