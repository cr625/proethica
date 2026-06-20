"""Study-flow/demo routes: view-synthesis redirect into step4, exit-validation-mode, and the preview/start bootstrap (consent-walk and prefilled demo sessions).."""
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
    INFO_SHEET_VERSION_PROLIFIC,
    CODE_ALPHABET,
    generate_completion_code,
    create_preview_consent_session,
)


def register_flow_demo_routes(bp):
    @bp.route('/view-synthesis/<int:case_id>')
    def view_synthesis(case_id):
        """Redirect to Step 4 Review in validation-study mode (legacy integration)."""
        session['validation_study_mode'] = True
        return redirect(url_for('step4.step4_review', case_id=case_id, validation_mode='1'))
    @bp.route('/exit-validation-mode')
    def exit_validation_mode():
        """Clear validation-study mode from session."""
        session.pop('validation_study_mode', None)
        flash('Exited validation study mode.', 'info')
        return redirect(url_for('main.home'))
    @bp.route('/preview/start')
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
