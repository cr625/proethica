"""Pipeline view routes -- per-case extraction pipeline dashboard.

Phase 1: Read-only status display (15 substeps).
Phase 2: Execution controls (Run single substep, Run All).
Phase 3: Interactive mode (pause after each substep for review).
Phase 5: Rollback and re-extraction (cascade clearing + re-run).
"""

from flask import render_template, jsonify, request
from app.models import Document
from app.models.pipeline_run import PipelineRun, PIPELINE_STATUS
from app.services.pipeline_state_manager import PipelineStateManager, WORKFLOW_DEFINITION
from app.utils.environment_auth import auth_required_for_llm
from app import db
import logging

logger = logging.getLogger(__name__)

# Mapping from PSM substep IDs to Celery task dispatch info.
# Each entry: (task_function_name, extra_kwargs)
SUBSTEP_DISPATCH = {
    'pass1_facts':          ('run_step1_task', {'section_type': 'facts'}),
    'pass1_discussion':     ('run_step1_task', {'section_type': 'discussion'}),
    'pass2_facts':          ('run_step2_task', {'section_type': 'facts'}),
    'pass2_discussion':     ('run_step2_task', {'section_type': 'discussion'}),
    'pass3':                ('run_step3_task', {}),
    'reconcile':            ('run_reconcile_task', {}),
    'commit_extraction':    ('run_commit_task', {'step_name': 'commit_extraction'}),
    'step4_provisions':     ('run_step4_substep_task', {'substep': 'step4_provisions'}),
    'step4_precedents':     ('run_step4_substep_task', {'substep': 'step4_precedents'}),
    'step4_qc':             ('run_step4_substep_task', {'substep': 'step4_qc'}),
    'step4_transformation': ('run_step4_substep_task', {'substep': 'step4_transformation'}),
    'step4_rich_analysis':  ('run_step4_substep_task', {'substep': 'step4_rich_analysis'}),
    'step4_phase3':         ('run_step4_substep_task', {'substep': 'step4_phase3'}),
    'step4_phase4':         ('run_step4_substep_task', {'substep': 'step4_phase4'}),
    'commit_synthesis':     ('run_commit_task', {'step_name': 'commit_synthesis'}),
}

# Step 4 substeps that were part of the monolithic run_step4_task.
# Now empty -- all Step 4 substeps are individually dispatchable.
STEP4_MONOLITHIC = set()


def _get_active_run(case_id):
    """Get the active (non-terminal) PipelineRun for a case, if any.

    Runs stuck in PENDING or PAUSED for more than 10 minutes are treated
    as stale and auto-marked FAILED to prevent blocking new dispatches.
    """
    from datetime import datetime, timedelta

    run = PipelineRun.query.filter(
        PipelineRun.case_id == case_id,
        PipelineRun.status.notin_([
            PIPELINE_STATUS['COMPLETED'],
            PIPELINE_STATUS['FAILED'],
            PIPELINE_STATUS['EXTRACTED'],
        ])
    ).order_by(PipelineRun.created_at.desc()).first()

    # WAITING_REVIEW is an intentional pause (interactive mode), not stale.
    # Auto-fail PENDING/PAUSED runs stuck >10 minutes since last update.
    if run and run.status in (PIPELINE_STATUS['PENDING'], PIPELINE_STATUS['PAUSED']):
        stale_threshold = datetime.utcnow() - timedelta(minutes=10)
        check_time = run.updated_at or run.created_at
        if check_time < stale_threshold:
            logger.warning(f"Auto-failing stale {run.status} run {run.id} for case {case_id}")
            run.set_error(f"Stale {run.status} run (>10 min)", run.current_step)
            db.session.commit()
            return None

    # Auto-fail RUNNING runs stuck longer than the Celery task_time_limit (2h)
    # plus a 30-minute buffer. If a worker dies mid-task, the run stays RUNNING
    # permanently and blocks all future dispatches for this case.
    if run and run.status == PIPELINE_STATUS['RUNNING']:
        stale_threshold = datetime.utcnow() - timedelta(hours=2, minutes=30)
        check_time = run.updated_at or run.created_at
        if check_time < stale_threshold:
            logger.warning(f"Auto-failing stuck RUNNING run {run.id} for case {case_id} "
                           f"(no update since {check_time})")
            run.set_error("Stuck RUNNING run (>2.5h with no update)", run.current_step)
            db.session.commit()
            return None

    return run


def _build_pipeline_response(case_id):
    """Build merged pipeline state (PSM data + active run overlay)."""
    manager = PipelineStateManager()
    state = manager.get_pipeline_state(case_id)
    state_dict = state.to_dict()

    active_run = _get_active_run(case_id)
    if active_run:
        state_dict['active_run'] = active_run.to_dict()
    else:
        state_dict['active_run'] = None

    return state_dict


def _get_task_func(task_name):
    """Lazy-import Celery task functions to avoid circular imports."""
    from app.tasks.pipeline_tasks import (
        run_step1_task, run_step2_task, run_step3_task,
        run_reconcile_task, run_commit_task, run_step4_task,
        run_step4_substep_task,
    )
    return {
        'run_step1_task': run_step1_task,
        'run_step2_task': run_step2_task,
        'run_step3_task': run_step3_task,
        'run_reconcile_task': run_reconcile_task,
        'run_commit_task': run_commit_task,
        'run_step4_task': run_step4_task,
        'run_step4_substep_task': run_step4_substep_task,
    }[task_name]


def _find_next_substep(case_id):
    """Find the next incomplete, startable substep for interactive dispatch.

    Walks WORKFLOW_DEFINITION in order, skipping complete steps.
    Returns the substep name or None if all steps are complete.
    """
    manager = PipelineStateManager()
    state = manager.get_pipeline_state(case_id)

    for step_name in WORKFLOW_DEFINITION:
        if state.is_complete(step_name):
            continue
        if step_name not in SUBSTEP_DISPATCH:
            continue
        if state.can_start(step_name):
            return step_name

    return None


def register_pipeline_routes(bp):
    """Register pipeline routes on the cases blueprint."""

    @bp.route('/<int:case_id>/pipeline')
    def case_pipeline(case_id):
        """Per-case pipeline dashboard with execution controls."""
        case = Document.query.get_or_404(case_id)
        pipeline_state = _build_pipeline_response(case_id)
        return render_template(
            'cases/pipeline.html',
            case=case,
            pipeline_state=pipeline_state,
            substep_dispatch=SUBSTEP_DISPATCH,
        )

    @bp.route('/<int:case_id>/pipeline/status')
    def case_pipeline_status(case_id):
        """API endpoint for AJAX status polling. Returns PSM state + active run."""
        Document.query.get_or_404(case_id)
        return jsonify(_build_pipeline_response(case_id))

    @bp.route('/<int:case_id>/pipeline/run', methods=['POST'])
    @auth_required_for_llm
    def case_pipeline_run(case_id):
        """Dispatch a single substep extraction via Celery.

        Request body: {"substep": "pass1_facts"}
        Returns: {"run_id": N, "task_id": "...", "substep": "..."}
        """
        Document.query.get_or_404(case_id)
        data = request.get_json(silent=True) or {}
        substep = data.get('substep', '').strip()

        # Validate substep
        if substep not in WORKFLOW_DEFINITION:
            return jsonify({'error': f'Unknown substep: {substep}'}), 400

        if substep not in SUBSTEP_DISPATCH:
            return jsonify({'error': f'Substep {substep} is not dispatchable'}), 400

        # Check no active run
        active = _get_active_run(case_id)
        if active:
            return jsonify({
                'error': 'A pipeline run is already active for this case',
                'active_run_id': active.id,
            }), 409

        # Check prerequisites (server-side enforcement)
        manager = PipelineStateManager()
        state = manager.get_pipeline_state(case_id)
        if not state.can_start(substep):
            blockers = state.get_blockers(substep)
            return jsonify({
                'error': 'Prerequisites not met',
                'blockers': blockers,
            }), 409

        # Create PipelineRun
        run = PipelineRun(
            case_id=case_id,
            config={'substep': substep, 'mode': 'single'},
        )
        run.set_status(PIPELINE_STATUS['RUNNING'])
        run.current_step = substep
        db.session.add(run)
        db.session.commit()

        # Dispatch Celery task
        task_name, extra_kwargs = SUBSTEP_DISPATCH[substep]
        task_func = _get_task_func(task_name)
        result = task_func.delay(run.id, **extra_kwargs)

        run.celery_task_id = result.id
        db.session.commit()

        logger.info(f"Dispatched {substep} for case {case_id}: run={run.id}, task={result.id}")
        return jsonify({
            'run_id': run.id,
            'task_id': result.id,
            'substep': substep,
        })

    @bp.route('/<int:case_id>/pipeline/run-all', methods=['POST'])
    @auth_required_for_llm
    def case_pipeline_run_all(case_id):
        """Dispatch full pipeline via Celery. Supports automated and interactive modes.

        Request body (all optional):
            mode: 'run_all' (default, automated) or 'interactive' (pause after each)
            include_step4: bool (default True)
            commit_to_ontserve: bool (default True)

        Interactive mode dispatches one substep at a time; after each completes
        the run enters WAITING_REVIEW. Use /pipeline/continue to advance.

        Returns: {"run_id": N, "task_id": "...", "mode": "..."}
        """
        Document.query.get_or_404(case_id)

        # Check no active run
        active = _get_active_run(case_id)
        if active:
            return jsonify({
                'error': 'A pipeline run is already active for this case',
                'active_run_id': active.id,
            }), 409

        data = request.get_json(silent=True) or {}
        mode = data.get('mode', 'run_all')
        if mode not in ('run_all', 'interactive'):
            return jsonify({'error': f'Invalid mode: {mode}'}), 400

        config = {
            'mode': mode,
            'include_step4': data.get('include_step4', True),
            'commit_to_ontserve': data.get('commit_to_ontserve', True),
        }

        if mode == 'interactive':
            # Interactive: dispatch first available substep only
            next_substep = _find_next_substep(case_id)
            if not next_substep:
                return jsonify({'error': 'No remaining substeps to run'}), 409

            run = PipelineRun(case_id=case_id, config=config)
            run.set_status(PIPELINE_STATUS['RUNNING'])
            run.current_step = next_substep
            db.session.add(run)
            db.session.commit()

            task_name, extra_kwargs = SUBSTEP_DISPATCH[next_substep]
            task_func = _get_task_func(task_name)
            result = task_func.delay(run.id, **extra_kwargs)

            run.celery_task_id = result.id
            db.session.commit()

            logger.info(f"Dispatched interactive run for case {case_id}: "
                        f"substep={next_substep}, run={run.id}, task={result.id}")
            return jsonify({
                'run_id': run.id,
                'task_id': result.id,
                'mode': 'interactive',
                'substep': next_substep,
            })

        # Automated: dispatch full pipeline
        run = PipelineRun(case_id=case_id, config=config)
        run.set_status(PIPELINE_STATUS['RUNNING'])
        run.current_step = 'initializing'
        db.session.add(run)
        db.session.commit()

        from app.tasks.pipeline_tasks import run_full_pipeline_task
        result = run_full_pipeline_task.delay(
            case_id=case_id, config=config, run_id=run.id,
        )

        run.celery_task_id = result.id
        db.session.commit()

        logger.info(f"Dispatched run-all for case {case_id}: run={run.id}, task={result.id}")
        return jsonify({
            'run_id': run.id,
            'task_id': result.id,
            'mode': 'run_all',
        })

    @bp.route('/<int:case_id>/pipeline/continue', methods=['POST'])
    @auth_required_for_llm
    def case_pipeline_continue(case_id):
        """Continue an interactive pipeline run by dispatching the next substep.

        Only valid when an active run exists in WAITING_REVIEW status.
        Finds the next incomplete substep, dispatches it, and sets the run
        back to RUNNING.

        Returns: {"run_id": N, "task_id": "...", "substep": "..."}
        """
        Document.query.get_or_404(case_id)

        active = _get_active_run(case_id)
        if not active:
            return jsonify({'error': 'No active pipeline run to continue'}), 409

        if active.status != PIPELINE_STATUS['WAITING_REVIEW']:
            return jsonify({
                'error': f'Run is not waiting for review (status: {active.status})',
            }), 409

        next_substep = _find_next_substep(case_id)
        if not next_substep:
            # All substeps complete -- mark the run as done
            active.set_status(PIPELINE_STATUS['COMPLETED'])
            db.session.commit()
            return jsonify({
                'run_id': active.id,
                'completed': True,
                'message': 'All pipeline substeps complete',
            })

        # Resume the existing run with the next substep
        active.set_status(PIPELINE_STATUS['RUNNING'])
        active.current_step = next_substep
        db.session.commit()

        task_name, extra_kwargs = SUBSTEP_DISPATCH[next_substep]
        task_func = _get_task_func(task_name)
        result = task_func.delay(active.id, **extra_kwargs)

        active.celery_task_id = result.id
        db.session.commit()

        logger.info(f"Continued interactive run {active.id} for case {case_id}: "
                    f"substep={next_substep}, task={result.id}")
        return jsonify({
            'run_id': active.id,
            'task_id': result.id,
            'substep': next_substep,
        })

    @bp.route('/<int:case_id>/pipeline/stop', methods=['POST'])
    @auth_required_for_llm
    def case_pipeline_stop(case_id):
        """Stop an interactive pipeline run.

        Sets the run to COMPLETED (partial). The user can start a new run later.
        Only valid for runs in WAITING_REVIEW status.

        Returns: {"run_id": N, "stopped": true}
        """
        Document.query.get_or_404(case_id)

        active = _get_active_run(case_id)
        if not active:
            return jsonify({'error': 'No active pipeline run to stop'}), 409

        if active.status != PIPELINE_STATUS['WAITING_REVIEW']:
            return jsonify({
                'error': f'Can only stop runs in review state (status: {active.status})',
            }), 409

        active.set_status(PIPELINE_STATUS['COMPLETED'])
        db.session.commit()

        logger.info(f"Stopped interactive run {active.id} for case {case_id}")
        return jsonify({
            'run_id': active.id,
            'stopped': True,
        })

    @bp.route('/<int:case_id>/pipeline/force-cancel', methods=['POST'])
    @auth_required_for_llm
    def case_pipeline_force_cancel(case_id):
        """Force-cancel a stuck RUNNING pipeline run.

        Marks the run as FAILED regardless of current status (except terminal).
        Use when a Celery worker died and the run is stuck permanently.

        Returns: {"run_id": N, "cancelled": true}
        """
        Document.query.get_or_404(case_id)

        active = _get_active_run(case_id)
        if not active:
            return jsonify({'error': 'No active pipeline run to cancel'}), 409

        logger.warning(f"Force-cancelling run {active.id} for case {case_id} "
                       f"(was {active.status})")
        active.set_error("Force-cancelled by user", active.current_step)
        db.session.commit()

        return jsonify({
            'run_id': active.id,
            'cancelled': True,
        })

    @bp.route('/<int:case_id>/pipeline/rerun-preview')
    def case_pipeline_rerun_preview(case_id):
        """Preview what cascade clearing would affect for a substep re-run.

        Query param: substep (required)
        Returns cascade preview data for a confirmation dialog.
        """
        Document.query.get_or_404(case_id)
        substep = request.args.get('substep', '').strip()

        if not substep:
            return jsonify({'error': 'substep parameter required'}), 400

        from app.services.cascade_clearing_service import get_cascade_preview
        preview = get_cascade_preview(substep)

        if 'error' in preview:
            return jsonify(preview), 400

        return jsonify(preview)

    @bp.route('/<int:case_id>/pipeline/rerun', methods=['POST'])
    @auth_required_for_llm
    def case_pipeline_rerun(case_id):
        """Clear downstream data and re-run a substep.

        Request body: {"substep": "pass1_facts"}

        Performs cascade clearing (deletes downstream artifacts), then
        dispatches the substep for re-extraction via Celery.

        Returns: {"run_id": N, "task_id": "...", "substep": "...", "cleared": {...}}
        """
        Document.query.get_or_404(case_id)
        data = request.get_json(silent=True) or {}
        substep = data.get('substep', '').strip()

        if substep not in WORKFLOW_DEFINITION:
            return jsonify({'error': f'Unknown substep: {substep}'}), 400

        if substep not in SUBSTEP_DISPATCH:
            return jsonify({'error': f'Substep {substep} is not dispatchable'}), 400

        # Check no active run
        active = _get_active_run(case_id)
        if active:
            return jsonify({
                'error': 'A pipeline run is already active for this case',
                'active_run_id': active.id,
            }), 409

        # Execute cascade clearing (no commit -- bundled with PipelineRun creation)
        from app.services.cascade_clearing_service import clear_cascade
        clear_stats = clear_cascade(case_id, substep)

        if 'error' in clear_stats:
            db.session.rollback()
            return jsonify(clear_stats), 500

        # Create PipelineRun, flush to get run.id for task dispatch
        run = PipelineRun(
            case_id=case_id,
            config={'substep': substep, 'mode': 'single', 'rerun': True},
        )
        run.set_status(PIPELINE_STATUS['RUNNING'])
        run.current_step = substep
        db.session.add(run)
        db.session.flush()

        # Dispatch Celery task before committing -- if dispatch fails,
        # rollback undoes both cascade clearing and PipelineRun creation.
        task_name, extra_kwargs = SUBSTEP_DISPATCH[substep]
        task_func = _get_task_func(task_name)
        try:
            result = task_func.delay(run.id, **extra_kwargs)
        except Exception as e:
            logger.error(f"Failed to dispatch rerun task for {substep}: {e}")
            db.session.rollback()
            return jsonify({'error': f'Task dispatch failed: {e}'}), 500

        run.celery_task_id = result.id
        db.session.commit()

        logger.info(f"Re-run {substep} for case {case_id}: run={run.id}, "
                    f"cleared {clear_stats['substeps_cleared']} substeps")
        return jsonify({
            'run_id': run.id,
            'task_id': result.id,
            'substep': substep,
            'cleared': clear_stats,
        })


def init_pipeline_csrf_exemption(app):
    """Exempt pipeline POST endpoints from CSRF protection.

    Called after blueprint registration in app/__init__.py.
    Uses function references (not string names) for Flask-WTF compatibility.
    """
    if hasattr(app, 'csrf') and app.csrf:
        # Access the view functions through the app's view_functions dict
        for endpoint in [
            'cases.case_pipeline_run', 'cases.case_pipeline_run_all',
            'cases.case_pipeline_continue', 'cases.case_pipeline_stop',
            'cases.case_pipeline_force_cancel', 'cases.case_pipeline_rerun',
        ]:
            view_func = app.view_functions.get(endpoint)
            if view_func:
                app.csrf.exempt(view_func)
