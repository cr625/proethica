"""
API endpoints for case pipeline progress tracking.
"""

import logging
from flask import Blueprint, jsonify, request
from app.services.case_pipeline_progress import CasePipelineProgress
from app.models import Document

logger = logging.getLogger(__name__)

# Create blueprint
case_progress_bp = Blueprint('case_progress', __name__, url_prefix='/api/case')


@case_progress_bp.route('/<int:case_id>/progress', methods=['GET'])
def get_case_progress(case_id):
    """
    Get comprehensive progress information for a case.

    Returns JSON with:
    - Overall progress summary
    - Step-by-step completion status
    - Entity counts per extraction type
    - Next available step

    Example:
        GET /api/case/8/progress

    Returns:
        {
            "success": true,
            "case_id": 8,
            "case_title": "Case 8...",
            "summary": {
                "total_steps": 5,
                "completed_steps": 3,
                "progress_percentage": 60.0,
                "total_entities": 150,
                "next_step": 4,
                "is_complete": false
            },
            "steps": {
                "1": {
                    "name": "Contextual Framework",
                    "complete": true,
                    "extractions": {"roles": 12, "states": 15, "resources": 21},
                    "total_entities": 48,
                    "can_proceed": true
                },
                ...
            }
        }
    """
    try:
        # Verify case exists
        case = Document.query.get_or_404(case_id)

        # Get progress summary
        summary = CasePipelineProgress.get_progress_summary(case_id)

        return jsonify({
            'success': True,
            'case_id': case_id,
            'case_title': case.title,
            'summary': {
                'total_steps': summary['total_steps'],
                'completed_steps': summary['completed_steps'],
                'progress_percentage': summary['progress_percentage'],
                'total_entities': summary['total_entities'],
                'next_step': summary['next_step'],
                'is_complete': summary['is_complete']
            },
            'steps': summary['steps']
        })

    except Exception as e:
        logger.error(f"Error getting progress for case {case_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@case_progress_bp.route('/<int:case_id>/progress/<int:step_number>', methods=['GET'])
def get_step_progress(case_id, step_number):
    """
    Get progress information for a specific step.

    Returns JSON with:
    - Step completion status
    - Entity counts
    - Whether user can proceed

    Example:
        GET /api/case/8/progress/1

    Returns:
        {
            "success": true,
            "case_id": 8,
            "step_number": 1,
            "complete": true,
            "can_access": true,
            "can_proceed": true,
            "extractions": {"roles": 12, "states": 15, "resources": 21},
            "total_entities": 48
        }
    """
    try:
        # Verify case exists
        case = Document.query.get_or_404(case_id)

        # Get full progress
        progress = CasePipelineProgress.get_case_progress(case_id)

        if step_number not in progress:
            return jsonify({
                'success': False,
                'error': f'Invalid step number: {step_number}'
            }), 400

        step_data = progress[step_number]

        return jsonify({
            'success': True,
            'case_id': case_id,
            'step_number': step_number,
            'step_name': step_data['name'],
            'complete': step_data['complete'],
            'can_access': CasePipelineProgress.can_access_step(case_id, step_number),
            'can_proceed': step_data['can_proceed'],
            'extractions': step_data['extractions'],
            'total_entities': step_data['total_entities']
        })

    except Exception as e:
        logger.error(f"Error getting step {step_number} progress for case {case_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@case_progress_bp.route('/<int:case_id>/can-proceed/<int:step_number>', methods=['GET'])
def can_proceed_from_step(case_id, step_number):
    """
    Quick check if user can proceed from a given step.

    Example:
        GET /api/case/8/can-proceed/1

    Returns:
        {
            "success": true,
            "can_proceed": true,
            "next_step": 2,
            "reason": "Step 1 complete"
        }
    """
    try:
        # Verify case exists
        case = Document.query.get_or_404(case_id)

        is_complete = CasePipelineProgress.is_step_complete(case_id, step_number)
        next_step = step_number + 1

        return jsonify({
            'success': True,
            'can_proceed': is_complete,
            'next_step': next_step if is_complete else None,
            'reason': f'Step {step_number} complete' if is_complete else f'Step {step_number} incomplete'
        })

    except Exception as e:
        logger.error(f"Error checking can proceed for case {case_id} step {step_number}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
