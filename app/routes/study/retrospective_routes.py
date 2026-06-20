"""Post-study retrospective ranking/feedback (retrospective + _submit_retrospective helper), the demographics redirect shim, and the completion page.."""
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
    PROLIFIC_COMPLETION_URL_BASE,
    generate_completion_code,
    get_participant_code,
    load_session,
    _RANKING_VIEWS,
    _require_session,
)


def register_retrospective_routes(bp):
    @bp.route('/retrospective', methods=['GET', 'POST'])
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
    @bp.route('/demographics')
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
    @bp.route('/complete')
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
