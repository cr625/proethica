"""Stats + service-status API."""
from flask import Blueprint, render_template, jsonify, request
from app.models import db
from app.models.pipeline_run import PipelineRun, PipelineQueue, PIPELINE_STATUS
from app.models.document import Document
from app.services.pipeline_state_manager import PipelineStateManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def register_stats_routes(bp):
    @bp.route('/api/stats', methods=['GET'])
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


    @bp.route('/api/service-status', methods=['GET'])
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


