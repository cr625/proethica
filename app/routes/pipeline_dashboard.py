"""
Pipeline Dashboard Routes

Provides web interface for monitoring and managing automated case processing.

Routes:
- /pipeline/dashboard - Main status dashboard
- /pipeline/queue - Queue management page
- /api/pipeline/* - REST API endpoints
"""

from flask import Blueprint, render_template, jsonify, request
from app.models import db
from app.models.pipeline_run import PipelineRun, PipelineQueue, PIPELINE_STATUS
from app.models.document import Document
from app.services.pipeline_state_manager import PipelineStateManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

pipeline_bp = Blueprint('pipeline', __name__, url_prefix='/pipeline')


def init_pipeline_csrf_exemption(app):
    """Exempt pipeline API routes from CSRF protection."""
    if hasattr(app, 'csrf'):
        app.csrf.exempt(api_add_to_queue)
        app.csrf.exempt(api_remove_from_queue)
        app.csrf.exempt(api_update_queue_item)
        app.csrf.exempt(api_start_queue_processing)
        app.csrf.exempt(api_clear_queue)
        app.csrf.exempt(api_run_single_case)
        app.csrf.exempt(api_run_step4)
        app.csrf.exempt(api_retry_run)
        app.csrf.exempt(api_cancel_run)
        app.csrf.exempt(api_service_status)
        app.csrf.exempt(api_reprocess_case)
        app.csrf.exempt(api_set_injection_mode)


@pipeline_bp.route('/api/set_injection_mode', methods=['POST'])
def api_set_injection_mode():
    """Set the ontology injection mode for extraction.

    Used by run_pipeline.py --injection-mode to switch between
    'full' (Phase 1) and 'label_only' (Phase 2).
    """
    from flask import current_app
    data = request.get_json() or {}
    mode = data.get('mode', 'full')
    if mode not in ('full', 'label_only'):
        return jsonify({'error': f'Invalid mode: {mode}'}), 400
    current_app.config['INJECTION_MODE'] = mode
    logger.info(f"Injection mode set to: {mode}")
    return jsonify({'mode': mode, 'success': True})


@pipeline_bp.route('/api/get_injection_mode', methods=['GET'])
def api_get_injection_mode():
    """Get the current ontology injection mode."""
    from flask import current_app
    mode = current_app.config.get('INJECTION_MODE', 'full')
    return jsonify({'mode': mode})


# Web Pages

@pipeline_bp.route('/dashboard')
def dashboard():
    """Main pipeline dashboard showing status of all runs."""
    # Get recent runs
    recent_runs = PipelineRun.query\
        .order_by(PipelineRun.created_at.desc())\
        .limit(20)\
        .all()

    # Get active runs
    active_runs = PipelineRun.query\
        .filter(PipelineRun.status.in_([
            PIPELINE_STATUS['RUNNING'],
            PIPELINE_STATUS['STEP1_FACTS'],
            PIPELINE_STATUS['STEP1_DISCUSSION'],
            PIPELINE_STATUS['STEP2_FACTS'],
            PIPELINE_STATUS['STEP2_DISCUSSION'],
            PIPELINE_STATUS['STEP3'],
            PIPELINE_STATUS['STEP4'],
            PIPELINE_STATUS['STEP5']
        ]))\
        .all()

    # Get queue stats
    queue_count = PipelineQueue.query.filter_by(status='queued').count()

    # Get case count
    case_count = Document.query.filter(
        Document.doc_metadata.isnot(None)
    ).count()

    # Get case IDs that have completed Step 4 synthesis
    # Used to hide Synthesize button for cases already synthesized
    # Check actual artifacts via PipelineStateManager (works for manual synthesis too)
    state_manager = PipelineStateManager()
    all_case_ids = [doc.id for doc in Document.query.filter(Document.doc_metadata.isnot(None)).all()]
    completed_case_ids = set(
        case_id for case_id in all_case_ids
        if state_manager.check_step_complete(case_id, 'step4')
    )

    return render_template(
        'pipeline_dashboard/index.html',
        recent_runs=recent_runs,
        active_runs=active_runs,
        queue_count=queue_count,
        case_count=case_count,
        completed_case_ids=completed_case_ids
    )


@pipeline_bp.route('/queue')
def queue_page():
    """Queue management page for selecting and processing cases."""
    from sqlalchemy import text as sa_text

    # Get all cases with sections
    cases = Document.query\
        .filter(Document.doc_metadata.isnot(None))\
        .order_by(Document.id)\
        .all()

    # Get extraction counts per case (actual entity data)
    extraction_counts = {}
    rows = db.session.execute(sa_text("""
        SELECT case_id, COUNT(*) as total,
               COUNT(DISTINCT extraction_type) as types,
               SUM(CASE WHEN is_published THEN 1 ELSE 0 END) as published
        FROM temporary_rdf_storage
        WHERE case_id IS NOT NULL
        GROUP BY case_id
    """)).fetchall()
    for row in rows:
        extraction_counts[row[0]] = {
            'total': row[1], 'types': row[2], 'published': row[3]
        }

    # Get QC results per case (latest)
    qc_results = {}
    qc_rows = db.session.execute(sa_text("""
        SELECT DISTINCT ON (case_id) case_id, overall_status,
               entity_count_total, extraction_types_count,
               critical_count, warning_count, info_count
        FROM case_verification_results
        ORDER BY case_id, verification_date DESC
    """)).fetchall()
    for row in qc_rows:
        qc_results[row[0]] = {
            'status': row[1], 'total': row[2], 'types': row[3],
            'critical': row[4], 'warning': row[5], 'info': row[6]
        }

    # Detect label_only cases (marked in doc_metadata.extraction_mode)
    label_only_cases = set()
    lo_rows = db.session.execute(sa_text("""
        SELECT id FROM documents
        WHERE doc_metadata->>'extraction_mode' = 'label_only'
    """)).fetchall()
    for row in lo_rows:
        label_only_cases.add(row[0])

    # Filter to cases that have sections_dual
    cases_with_sections = []
    for case in cases:
        metadata = case.doc_metadata or {}
        if metadata.get('sections_dual'):
            latest_run = PipelineRun.query\
                .filter_by(case_id=case.id)\
                .order_by(PipelineRun.created_at.desc())\
                .first()

            queue_entry = PipelineQueue.query\
                .filter_by(case_id=case.id, status='queued')\
                .first()

            ext = extraction_counts.get(case.id)
            qc = qc_results.get(case.id)

            cases_with_sections.append({
                'id': case.id,
                'title': case.title,
                'latest_run': latest_run,
                'is_queued': queue_entry is not None,
                'has_facts': bool(metadata.get('sections_dual', {}).get('facts')),
                'has_discussion': bool(metadata.get('sections_dual', {}).get('discussion')),
                'extraction': ext,
                'qc': qc,
                'is_label_only': case.id in label_only_cases,
            })

    # Get current queue
    queue_items = PipelineQueue.query\
        .filter_by(status='queued')\
        .order_by(PipelineQueue.priority.desc(), PipelineQueue.added_at.asc())\
        .all()

    # Get distinct group names
    groups = db.session.query(PipelineQueue.group_name)\
        .filter(PipelineQueue.group_name.isnot(None))\
        .distinct()\
        .all()
    group_names = [g[0] for g in groups if g[0]]

    return render_template(
        'pipeline_dashboard/queue.html',
        cases=cases_with_sections,
        queue_items=queue_items,
        group_names=group_names
    )


# REST API Endpoints

@pipeline_bp.route('/api/runs', methods=['GET'])
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


@pipeline_bp.route('/api/runs/<int:run_id>', methods=['GET'])
def api_get_run(run_id):
    """Get details of a specific pipeline run."""
    run = PipelineRun.query.get_or_404(run_id)
    return jsonify(run.to_dict())


@pipeline_bp.route('/api/runs/<int:run_id>/retry', methods=['POST'])
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


@pipeline_bp.route('/api/queue', methods=['GET'])
def api_list_queue():
    """List all items in the processing queue."""
    status = request.args.get('status', 'queued')

    items = PipelineQueue.query\
        .filter_by(status=status)\
        .order_by(PipelineQueue.priority.desc(), PipelineQueue.added_at.asc())\
        .all()

    return jsonify({
        'items': [item.to_dict() for item in items],
        'count': len(items)
    })


@pipeline_bp.route('/api/queue', methods=['POST'])
def api_add_to_queue():
    """Add case(s) to the processing queue."""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    case_ids = data.get('case_ids', [])
    if isinstance(data.get('case_id'), int):
        case_ids = [data['case_id']]

    if not case_ids:
        return jsonify({'error': 'No case_ids provided'}), 400

    priority = data.get('priority', 0)
    group_name = data.get('group_name')
    config = data.get('config', {})  # Pipeline config (include_step4, etc.)

    added = []
    skipped = []

    for case_id in case_ids:
        # Check case exists
        case = Document.query.get(case_id)
        if not case:
            skipped.append({'case_id': case_id, 'reason': 'Case not found'})
            continue

        # Check not already queued
        existing = PipelineQueue.query\
            .filter_by(case_id=case_id, status='queued')\
            .first()

        if existing:
            skipped.append({'case_id': case_id, 'reason': 'Already queued'})
            continue

        # Check not currently processing (has active pipeline run)
        active_run = PipelineRun.query\
            .filter_by(case_id=case_id)\
            .filter(PipelineRun.status.notin_([
                PIPELINE_STATUS['COMPLETED'],
                PIPELINE_STATUS['FAILED'],
                PIPELINE_STATUS['EXTRACTED']
            ]))\
            .first()

        if active_run:
            skipped.append({'case_id': case_id, 'reason': f'Currently processing (status: {active_run.status})'})
            continue

        # Add to queue
        queue_item = PipelineQueue(
            case_id=case_id,
            priority=priority,
            group_name=group_name,
            config=config
        )
        db.session.add(queue_item)
        added.append(case_id)

    db.session.commit()

    return jsonify({
        'success': True,
        'added': added,
        'skipped': skipped,
        'message': f'Added {len(added)} cases to queue'
    })


@pipeline_bp.route('/api/queue/<int:queue_id>', methods=['DELETE'])
def api_remove_from_queue(queue_id):
    """Remove an item from the queue."""
    item = PipelineQueue.query.get_or_404(queue_id)

    if item.status != 'queued':
        return jsonify({'error': 'Can only remove queued items'}), 400

    db.session.delete(item)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Removed case {item.case_id} from queue'
    })


@pipeline_bp.route('/api/queue/<int:queue_id>', methods=['PATCH'])
def api_update_queue_item(queue_id):
    """Update queue item (priority, group)."""
    item = PipelineQueue.query.get_or_404(queue_id)
    data = request.get_json()

    if 'priority' in data:
        item.priority = data['priority']
    if 'group_name' in data:
        item.group_name = data['group_name']

    db.session.commit()

    return jsonify({
        'success': True,
        'item': item.to_dict()
    })


@pipeline_bp.route('/api/queue/start', methods=['POST'])
def api_start_queue_processing():
    """Start processing the queue."""
    data = request.get_json() or {}
    limit = data.get('limit', 10)

    # Import task here to avoid circular imports
    from app.tasks.pipeline_tasks import process_queue_task

    result = process_queue_task.delay(limit=limit)

    return jsonify({
        'success': True,
        'message': f'Queue processing started (limit={limit})',
        'task_id': result.id
    })


@pipeline_bp.route('/api/queue/clear', methods=['POST'])
def api_clear_queue():
    """Clear all queued items."""
    deleted = PipelineQueue.query.filter_by(status='queued').delete()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Cleared {deleted} items from queue'
    })


@pipeline_bp.route('/api/cases', methods=['GET'])
def api_list_cases():
    """List all cases available for processing."""
    cases = Document.query\
        .filter(Document.doc_metadata.isnot(None))\
        .order_by(Document.id)\
        .all()

    result = []
    for case in cases:
        metadata = case.doc_metadata or {}
        sections = metadata.get('sections_dual', {})

        if sections:
            # Get latest run status
            latest_run = PipelineRun.query\
                .filter_by(case_id=case.id)\
                .order_by(PipelineRun.created_at.desc())\
                .first()

            result.append({
                'id': case.id,
                'title': case.title,
                'has_facts': bool(sections.get('facts')),
                'has_discussion': bool(sections.get('discussion')),
                'latest_run_status': latest_run.status if latest_run else None,
                'latest_run_id': latest_run.id if latest_run else None
            })

    return jsonify({
        'cases': result,
        'count': len(result)
    })


@pipeline_bp.route('/api/run-single', methods=['POST'])
def api_run_single_case():
    """Start pipeline for a single case immediately (not queued)."""
    data = request.get_json()

    if not data or 'case_id' not in data:
        return jsonify({'error': 'case_id required'}), 400

    case_id = data['case_id']
    config = data.get('config', {})

    # Verify case exists
    case = Document.query.get(case_id)
    if not case:
        return jsonify({'error': f'Case {case_id} not found'}), 404

    # Import task here to avoid circular imports
    from app.tasks.pipeline_tasks import run_full_pipeline_task

    result = run_full_pipeline_task.delay(
        case_id=case_id,
        config=config
    )

    return jsonify({
        'success': True,
        'message': f'Pipeline started for case {case_id}',
        'task_id': result.id
    })


@pipeline_bp.route('/api/run_step4', methods=['POST'])
def api_run_step4():
    """
    Run Step 4 synthesis for a case via Celery.

    Uses the unified synthesis service that runs the same code as
    the manual "Run Complete Synthesis" button.

    Request body:
        case_id: int - Case ID to synthesize

    Returns:
        JSON with task_id for monitoring
    """
    data = request.get_json()

    if not data or 'case_id' not in data:
        return jsonify({'error': 'case_id required'}), 400

    case_id = data['case_id']

    # Verify case exists
    case = Document.query.get(case_id)
    if not case:
        return jsonify({'error': f'Case {case_id} not found'}), 404

    # Check if case has Pass 1-3 complete (required for Step 4)
    from app.models import TemporaryRDFStorage
    entity_count = TemporaryRDFStorage.query.filter_by(case_id=case_id).count()
    if entity_count < 10:
        return jsonify({
            'error': f'Case {case_id} has insufficient entities ({entity_count}). Run Pass 1-3 first.'
        }), 400

    # Create a PipelineRun to track this
    run = PipelineRun(
        case_id=case_id,
        status=PIPELINE_STATUS['STEP4'],
        current_step='step4',
        config={'step4_only': True},
        started_at=datetime.utcnow()  # Set started_at so duration tracks properly
    )
    db.session.add(run)
    db.session.commit()

    # Import task here to avoid circular imports
    from app.tasks.pipeline_tasks import run_step4_task

    result = run_step4_task.delay(run_id=run.id)

    return jsonify({
        'success': True,
        'message': f'Step 4 synthesis started for case {case_id}',
        'task_id': result.id,
        'run_id': run.id
    })


@pipeline_bp.route('/api/step4_status/<int:case_id>', methods=['GET'])
def api_step4_status(case_id):
    """
    Check Step 4 synthesis status for a case.

    Returns:
        JSON with synthesis status (complete, in_progress, not_started)
        and counts of extracted entities.
    """
    from app.models import TemporaryRDFStorage

    # Check for Step 4 entities
    provisions = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type='code_provision_reference').count()
    questions = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type='ethical_question').count()
    conclusions = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type='ethical_conclusion').count()
    decision_points = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type='canonical_decision_point').count()
    causal_links = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type='causal_normative_link').count()

    # Determine status
    if decision_points > 0:
        status = 'complete'
    elif questions > 0 or conclusions > 0:
        status = 'in_progress'
    elif provisions > 0:
        status = 'partial'
    else:
        status = 'not_started'

    return jsonify({
        'case_id': case_id,
        'status': status,
        'entities': {
            'provisions': provisions,
            'questions': questions,
            'conclusions': conclusions,
            'decision_points': decision_points,
            'causal_links': causal_links
        }
    })


@pipeline_bp.route('/api/stats', methods=['GET'])
def api_get_stats():
    """Get pipeline processing statistics."""
    # Count by status
    status_counts = {}
    for status_name, status_value in PIPELINE_STATUS.items():
        count = PipelineRun.query.filter_by(status=status_value).count()
        status_counts[status_name.lower()] = count

    # Queue stats
    queue_queued = PipelineQueue.query.filter_by(status='queued').count()
    queue_processing = PipelineQueue.query.filter_by(status='processing').count()

    # Case stats
    total_cases = Document.query.filter(Document.doc_metadata.isnot(None)).count()

    return jsonify({
        'runs': status_counts,
        'queue': {
            'queued': queue_queued,
            'processing': queue_processing
        },
        'cases': {
            'total': total_cases
        }
    })


@pipeline_bp.route('/api/service-status', methods=['GET'])
def api_service_status():
    """
    Get status of backend services (Redis, Celery).

    Returns:
        JSON with service status including:
        - redis: connection status and info
        - celery: worker status, active tasks, queue depth
    """
    import redis
    from celery_config import get_celery

    status = {
        'redis': {'status': 'unknown', 'error': None},
        'celery': {'status': 'unknown', 'workers': [], 'active_tasks': 0, 'queue_depth': 0, 'error': None}
    }

    # Check Redis
    try:
        r = redis.Redis(host='localhost', port=6379, db=1)
        r.ping()
        info = r.info('server')
        status['redis'] = {
            'status': 'connected',
            'version': info.get('redis_version', 'unknown'),
            'uptime_seconds': info.get('uptime_in_seconds', 0)
        }

        # Get Celery queue depth from Redis
        queue_depth = r.llen('celery')
        status['celery']['queue_depth'] = queue_depth

    except redis.ConnectionError as e:
        status['redis'] = {'status': 'disconnected', 'error': str(e)}
    except Exception as e:
        status['redis'] = {'status': 'error', 'error': str(e)}

    # Check Celery
    try:
        celery = get_celery()
        inspect = celery.control.inspect()

        # Get active workers
        ping_result = inspect.ping()
        if ping_result:
            workers = list(ping_result.keys())
            status['celery']['workers'] = workers
            status['celery']['worker_count'] = len(workers)
            status['celery']['status'] = 'online'

            # Get active tasks
            active = inspect.active()
            if active:
                total_active = sum(len(tasks) for tasks in active.values())
                status['celery']['active_tasks'] = total_active

                # Include task details
                active_details = []
                for worker, tasks in active.items():
                    for task in tasks:
                        active_details.append({
                            'worker': worker,
                            'task_id': task.get('id'),
                            'task_name': task.get('name'),
                            'args': task.get('args', [])[:2]  # Limit args for display
                        })
                status['celery']['active_task_details'] = active_details

            # Get reserved (queued) tasks
            reserved = inspect.reserved()
            if reserved:
                total_reserved = sum(len(tasks) for tasks in reserved.values())
                status['celery']['reserved_tasks'] = total_reserved
        else:
            status['celery']['status'] = 'offline'
            status['celery']['workers'] = []
            status['celery']['worker_count'] = 0

    except Exception as e:
        status['celery']['status'] = 'error'
        status['celery']['error'] = str(e)

    # Overall status
    redis_ok = status['redis'].get('status') == 'connected'
    celery_ok = status['celery'].get('status') == 'online'

    if redis_ok and celery_ok:
        status['overall'] = 'healthy'
    elif redis_ok and not celery_ok:
        status['overall'] = 'degraded'
        status['message'] = 'Celery worker is offline - tasks will not process'
    elif not redis_ok:
        status['overall'] = 'critical'
        status['message'] = 'Redis is not connected - pipeline cannot function'
    else:
        status['overall'] = 'unknown'

    return jsonify(status)


@pipeline_bp.route('/api/runs/<int:run_id>/cancel', methods=['POST'])
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


@pipeline_bp.route('/api/reprocess/<int:case_id>', methods=['POST'])
def api_reprocess_case(case_id):
    """
    Reprocess a case from scratch, clearing existing extractions.

    This allows re-running the pipeline on a completed case to test new changes.

    Options (via JSON body):
        - clear_committed: If true, also clears committed entities (default: true)
        - clear_prompts: If true, clears extraction prompts (default: true)

    Args:
        case_id: Case ID to reprocess

    Returns:
        JSON with reprocessing result and new task ID
    """
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    from app.models.extraction_prompt import ExtractionPrompt

    # Verify case exists
    case = Document.query.get(case_id)
    if not case:
        return jsonify({'error': f'Case {case_id} not found'}), 404

    data = request.get_json() or {}
    clear_committed = data.get('clear_committed', True)
    clear_prompts = data.get('clear_prompts', True)
    config = data.get('config', {})

    cleared_stats = {
        'rdf_entities': 0,
        'extraction_prompts': 0,
        'previous_runs': 0
    }

    try:
        # Clear RDF entities
        if clear_committed:
            # Clear ALL entities for this case
            deleted = TemporaryRDFStorage.query.filter_by(case_id=case_id).delete()
            cleared_stats['rdf_entities'] = deleted
            logger.info(f"Cleared {deleted} RDF entities (including committed) for case {case_id}")
        else:
            # Only clear uncommitted
            deleted = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                is_published=False
            ).delete()
            cleared_stats['rdf_entities'] = deleted
            logger.info(f"Cleared {deleted} uncommitted RDF entities for case {case_id}")

        # Clear extraction prompts
        if clear_prompts:
            deleted = ExtractionPrompt.query.filter_by(case_id=case_id).delete()
            cleared_stats['extraction_prompts'] = deleted
            logger.info(f"Cleared {deleted} extraction prompts for case {case_id}")

        # Mark previous runs as superseded (don't delete, keep history)
        previous_runs = PipelineRun.query.filter_by(case_id=case_id).all()
        for run in previous_runs:
            if run.status not in ['superseded']:
                run.status = 'superseded'
                cleared_stats['previous_runs'] += 1

        db.session.commit()

        # Start new pipeline
        from app.tasks.pipeline_tasks import run_full_pipeline_task

        result = run_full_pipeline_task.delay(
            case_id=case_id,
            config=config
        )

        logger.info(f"Reprocessing case {case_id}: cleared {cleared_stats}, new task {result.id}")

        return jsonify({
            'success': True,
            'message': f'Reprocessing case {case_id}',
            'task_id': result.id,
            'cleared': cleared_stats
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error reprocessing case {case_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
