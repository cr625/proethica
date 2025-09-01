"""
Annotation Review Routes

API endpoints for human review of LLM-generated annotations.
"""

import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models.document_concept_annotation import DocumentConceptAnnotation
from app import db
from datetime import datetime

logger = logging.getLogger(__name__)

bp = Blueprint('annotation_review', __name__, url_prefix='/api/annotations')


@bp.route('/<int:annotation_id>/review', methods=['POST'])
@login_required
def review_annotation(annotation_id):
    """
    Handle human review of an annotation (approve or reject).
    
    Args:
        annotation_id: ID of the annotation to review
        
    Request body:
        {
            "action": "approve" | "reject"
        }
    """
    try:
        # Get annotation
        annotation = DocumentConceptAnnotation.query.get_or_404(annotation_id)
        
        # Get action from request
        data = request.get_json()
        action = data.get('action')
        
        if action not in ['approve', 'reject']:
            return jsonify({
                'success': False,
                'error': 'Invalid action. Must be "approve" or "reject".'
            }), 400
        
        # Update annotation status
        if action == 'approve':
            annotation.validation_status = 'approved'
            annotation.validated_by = current_user.id
            annotation.validated_at = datetime.utcnow()
            logger.info(f"Annotation {annotation_id} approved by user {current_user.id}")
        else:
            annotation.validation_status = 'rejected'
            annotation.validated_by = current_user.id
            annotation.validated_at = datetime.utcnow()
            logger.info(f"Annotation {annotation_id} rejected by user {current_user.id}")
        
        # Save changes
        db.session.commit()
        
        return jsonify({
            'success': True,
            'annotation_id': annotation_id,
            'action': action,
            'new_status': annotation.validation_status
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error reviewing annotation {annotation_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500