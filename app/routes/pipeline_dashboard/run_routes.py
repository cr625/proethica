"""Pipeline run API (list/get/retry/cancel)."""
from flask import Blueprint, render_template, jsonify, request
from app.models import db
from app.models.pipeline_run import PipelineRun, PipelineQueue, PIPELINE_STATUS
from app.models.document import Document
from app.services.pipeline_state_manager import PipelineStateManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def register_run_routes(bp):
    @bp.route('/api/runs', methods=['GET'])
    def api_list_runs():
        """List all pipeline runs with optional filtering."""
        status = request.args.get('status')
        case_id = request.args.get('case_id', type=int)
        limit = request.args.get('limit', 50, type=int)

        query = PipelineRun.query

        if status:
            query = query.filter_by(status=status)
        if case_id:
            query = query.filter_by(case_id=case_id)

        runs = query.order_by(PipelineRun.created_at.desc()).limit(limit).all()

        return jsonify({
            'runs': [run.to_dict() for run in runs],
            'count': len(runs)
        })


    @bp.route('/api/runs/<int:run_id>', methods=['GET'])
    def api_get_run(run_id):
        """Get details of a specific pipeline run."""
        run = PipelineRun.query.get_or_404(run_id)
        return jsonify(run.to_dict())


    @bp.route('/api/runs/<int:run_id>/retry', methods=['POST'])
    def api_retry_run(run_id):
        """Retry a failed pipeline run (resumes from failed step)."""
        run = PipelineRun.query.get_or_404(run_id)

        if run.status != PIPELINE_STATUS['FAILED']:
            return jsonify({'error': 'Can only retry failed runs'}), 400

        # Import task here to avoid circular imports
        from app.tasks.pipeline_tasks import resume_pipeline_task

        # Resume from the failed step (not a full restart)
        result = resume_pipeline_task.delay(run_id=run.id)

        return jsonify({
            'success': True,
            'message': f'Resuming run {run.id} for case {run.case_id} from step {run.error_step or run.current_step}',
            'task_id': result.id,
            'run_id': run.id,
            'failed_step': run.error_step or run.current_step,
            'steps_completed': run.steps_completed
        })


    @bp.route('/api/runs/<int:run_id>/cancel', methods=['POST'])
    def api_cancel_run(run_id):
        """
    Cancel a running pipeline.

    This will:
    1. Revoke all Celery tasks associated with this run
    2. Mark the pipeline run as 'cancelled'
    3. Optionally clean up partial extraction state

    Args:
        run_id: Pipeline run ID to cancel

    Returns:
        JSON with cancellation result
    """
        from celery_config import get_celery

        run = PipelineRun.query.get_or_404(run_id)

        # Check if run is in a cancellable state
        active_statuses = [
            PIPELINE_STATUS['RUNNING'],
            PIPELINE_STATUS['STEP1_FACTS'],
            PIPELINE_STATUS['STEP1_DISCUSSION'],
            PIPELINE_STATUS['STEP2_FACTS'],
            PIPELINE_STATUS['STEP2_DISCUSSION'],
            PIPELINE_STATUS['STEP3'],
            PIPELINE_STATUS['STEP4'],
            PIPELINE_STATUS['STEP5']
        ]

        if run.status not in active_statuses:
            return jsonify({
                'success': False,
                'error': f'Cannot cancel run with status: {run.status}'
            }), 400

        celery = get_celery()
        revoked_tasks = []

        try:
            # Get Celery inspect to find tasks for this run
            inspect = celery.control.inspect()
            active = inspect.active() or {}
            reserved = inspect.reserved() or {}

            # Find and revoke tasks associated with this run
            # Tasks typically have run_id in their args
            for worker, tasks in {**active, **reserved}.items():
                for task in tasks:
                    task_args = task.get('args', [])
                    # Check if this task is for our run_id
                    if task_args and len(task_args) > 0:
                        if task_args[0] == run_id or (isinstance(task_args[0], dict) and task_args[0].get('run_id') == run_id):
                            task_id = task.get('id')
                            celery.control.revoke(task_id, terminate=True)
                            revoked_tasks.append(task_id)
                            logger.info(f"Revoked task {task_id} for run {run_id}")

            # Also try to revoke by task_id if stored on the run
            if hasattr(run, 'celery_task_id') and run.celery_task_id:
                celery.control.revoke(run.celery_task_id, terminate=True)
                revoked_tasks.append(run.celery_task_id)

            # Update run status
            run.status = 'cancelled'
            run.error_message = f'Cancelled by user at step: {run.current_step}'
            run.completed_at = datetime.utcnow()
            db.session.commit()

            logger.info(f"Pipeline run {run_id} cancelled. Revoked {len(revoked_tasks)} tasks.")

            return jsonify({
                'success': True,
                'message': f'Pipeline run {run_id} cancelled',
                'revoked_tasks': revoked_tasks,
                'previous_step': run.current_step
            })

        except Exception as e:
            logger.error(f"Error cancelling run {run_id}: {e}", exc_info=True)

            # Still mark as cancelled even if task revocation failed
            run.status = 'cancelled'
            run.error_message = f'Cancelled (with errors): {str(e)}'
            run.completed_at = datetime.utcnow()
            db.session.commit()

            return jsonify({
                'success': True,
                'message': f'Pipeline run {run_id} marked as cancelled (task revocation may have failed)',
                'warning': str(e)
            })


