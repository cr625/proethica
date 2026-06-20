"""Case run API (list/run-single/run_step4/status/reprocess)."""
from flask import Blueprint, render_template, jsonify, request
from app.models import db
from app.models.pipeline_run import PipelineRun, PipelineQueue, PIPELINE_STATUS
from app.models.document import Document
from app.services.pipeline_state_manager import PipelineStateManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def register_case_routes(bp):
    @bp.route('/api/cases', methods=['GET'])
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


    @bp.route('/api/run-single', methods=['POST'])
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


    @bp.route('/api/run_step4', methods=['POST'])
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


    @bp.route('/api/step4_status/<int:case_id>', methods=['GET'])
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


    @bp.route('/api/reprocess/<int:case_id>', methods=['POST'])
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
