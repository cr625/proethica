"""Pipeline view routes -- per-case extraction pipeline dashboard.

Phase 1: Read-only status display (15 substeps).
Phase 2: Execution controls (Run single substep, Run All).
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
    """Get the active (non-terminal) PipelineRun for a case, if any."""
    return PipelineRun.query.filter(
        PipelineRun.case_id == case_id,
        PipelineRun.status.notin_([
            PIPELINE_STATUS['COMPLETED'],
            PIPELINE_STATUS['FAILED'],
            PIPELINE_STATUS['EXTRACTED'],
        ])
    ).order_by(PipelineRun.created_at.desc()).first()


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
        """Dispatch full pipeline (all remaining substeps) via Celery.

        Returns: {"run_id": N, "task_id": "..."}
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
        config = {
            'mode': 'run_all',
            'include_step4': data.get('include_step4', True),
            'commit_to_ontserve': data.get('commit_to_ontserve', True),
        }

        # Create PipelineRun in the route (not the task) to prevent race conditions.
        # The task receives run_id and uses the existing record.
        run = PipelineRun(
            case_id=case_id,
            config=config,
        )
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


def init_pipeline_csrf_exemption(app):
    """Exempt pipeline POST endpoints from CSRF protection.

    Called after blueprint registration in app/__init__.py.
    Uses function references (not string names) for Flask-WTF compatibility.
    """
    if hasattr(app, 'csrf') and app.csrf:
        # Access the view functions through the app's view_functions dict
        for endpoint in ['cases.case_pipeline_run', 'cases.case_pipeline_run_all']:
            view_func = app.view_functions.get(endpoint)
            if view_func:
                app.csrf.exempt(view_func)
