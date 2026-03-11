"""Pipeline view routes -- per-case extraction pipeline dashboard.

Phase 1: Read-only status display (15 substeps).
Phase 2: Execution controls (Run single substep, Run All).
Phase 3: Interactive mode (pause after each substep for review).
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
# Step 4 substeps (except step4_provisions) are not individually dispatchable
# until Phase 4 decomposes run_step4_synthesis.
SUBSTEP_DISPATCH = {
    'pass1_facts':       ('run_step1_task', {'section_type': 'facts'}),
    'pass1_discussion':  ('run_step1_task', {'section_type': 'discussion'}),
    'pass2_facts':       ('run_step2_task', {'section_type': 'facts'}),
    'pass2_discussion':  ('run_step2_task', {'section_type': 'discussion'}),
    'pass3':             ('run_step3_task', {}),
    'reconcile':         ('run_reconcile_task', {}),
    'commit_extraction': ('run_commit_task', {'step_name': 'commit_extraction'}),
    'step4_provisions':  ('run_step4_task', {}),  # Runs all of Step 4
    'commit_synthesis':  ('run_commit_task', {'step_name': 'commit_synthesis'}),
}

# Step 4 substeps that are part of the monolithic run_step4_task
STEP4_MONOLITHIC = {
    'step4_precedents', 'step4_qc', 'step4_transformation',
    'step4_rich_analysis', 'step4_phase3', 'step4_phase4',
}


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
    # Only auto-fail PENDING/PAUSED runs stuck >10 minutes since last update.
    if run and run.status in (PIPELINE_STATUS['PENDING'], PIPELINE_STATUS['PAUSED']):
        stale_threshold = datetime.utcnow() - timedelta(minutes=10)
        check_time = run.updated_at or run.created_at
        if check_time < stale_threshold:
            logger.warning(f"Auto-failing stale {run.status} run {run.id} for case {case_id}")
            run.set_error(f"Stale {run.status} run (>10 min)", run.current_step)
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
    )
    return {
        'run_step1_task': run_step1_task,
        'run_step2_task': run_step2_task,
        'run_step3_task': run_step3_task,
        'run_reconcile_task': run_reconcile_task,
        'run_commit_task': run_commit_task,
        'run_step4_task': run_step4_task,
    }[task_name]


def _find_next_substep(case_id):
    """Find the next incomplete, startable substep for interactive dispatch.

    Walks WORKFLOW_DEFINITION in order, skipping complete steps and
    non-dispatchable Step 4 monolithic substeps. Returns the substep name
    or None if all steps are complete (or none can start).
    """
    manager = PipelineStateManager()
    state = manager.get_pipeline_state(case_id)

    for step_name in WORKFLOW_DEFINITION:
        if state.is_complete(step_name):
            continue
        if step_name in STEP4_MONOLITHIC:
            # Not individually dispatchable; check step4_provisions instead
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
            step4_monolithic=STEP4_MONOLITHIC,
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

        if substep in STEP4_MONOLITHIC:
            return jsonify({
                'error': f'{substep} runs as part of Step 4. Use step4_provisions to run all of Step 4.'
            }), 400

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
        ]:
            view_func = app.view_functions.get(endpoint)
            if view_func:
                app.csrf.exempt(view_func)
