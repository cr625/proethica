"""Queue API (list/add/remove/update/start/clear)."""
from flask import Blueprint, render_template, jsonify, request
from app.models import db
from app.models.pipeline_run import PipelineRun, PipelineQueue, PIPELINE_STATUS
from app.models.document import Document
from app.services.pipeline_state_manager import PipelineStateManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def register_queue_routes(bp):
    @bp.route('/api/queue', methods=['GET'])
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


    @bp.route('/api/queue', methods=['POST'])
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


    @bp.route('/api/queue/<int:queue_id>', methods=['DELETE'])
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


    @bp.route('/api/queue/<int:queue_id>', methods=['PATCH'])
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


    @bp.route('/api/queue/start', methods=['POST'])
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


    @bp.route('/api/queue/clear', methods=['POST'])
    def api_clear_queue():
        """Clear all queued items."""
        deleted = PipelineQueue.query.filter_by(status='queued').delete()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Cleared {deleted} items from queue'
        })


