"""Per-case evaluation: the _require_session guard, the stepped evaluate_case page, submit_evaluation (18 Likert + comprehension + timers), and the reveal_conclusions JSON endpoint.."""
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
    get_participant_code,
    load_session,
    _require_session,
)


def register_case_routes(bp):
    @bp.route('/case/<int:case_id>', methods=['GET'])
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
    @bp.route('/case/<int:case_id>/submit', methods=['POST'])
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
    @bp.route('/case/<int:case_id>/reveal')
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
