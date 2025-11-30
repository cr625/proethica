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
        app.csrf.exempt(api_retry_run)


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

    return render_template(
        'pipeline_dashboard/index.html',
        recent_runs=recent_runs,
        active_runs=active_runs,
        queue_count=queue_count,
        case_count=case_count
    )


@pipeline_bp.route('/queue')
def queue_page():
    """Queue management page for selecting and processing cases."""
    # Get all cases with sections
    cases = Document.query\
        .filter(Document.doc_metadata.isnot(None))\
        .order_by(Document.id)\
        .all()

    # Filter to cases that have sections_dual
    cases_with_sections = []
    for case in cases:
        metadata = case.doc_metadata or {}
        if metadata.get('sections_dual'):
            # Check if already processed or queued
            latest_run = PipelineRun.query\
                .filter_by(case_id=case.id)\
                .order_by(PipelineRun.created_at.desc())\
                .first()

            queue_entry = PipelineQueue.query\
                .filter_by(case_id=case.id, status='queued')\
                .first()

            cases_with_sections.append({
                'id': case.id,
                'title': case.title,
                'latest_run': latest_run,
                'is_queued': queue_entry is not None,
                'has_facts': bool(metadata.get('sections_dual', {}).get('facts')),
                'has_discussion': bool(metadata.get('sections_dual', {}).get('discussion'))
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
    """Retry a failed pipeline run."""
    run = PipelineRun.query.get_or_404(run_id)

    if run.status != PIPELINE_STATUS['FAILED']:
        return jsonify({'error': 'Can only retry failed runs'}), 400

    # Import task here to avoid circular imports
    from app.tasks.pipeline_tasks import run_full_pipeline_task

    # Create new run for retry
    result = run_full_pipeline_task.delay(
        case_id=run.case_id,
        config=run.config
    )

    return jsonify({
        'success': True,
        'message': f'Retry queued for case {run.case_id}',
        'task_id': result.id
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

        # Add to queue
        queue_item = PipelineQueue(
            case_id=case_id,
            priority=priority,
            group_name=group_name
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
