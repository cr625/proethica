"""
Unified API endpoints for document annotations (cases and guidelines)
"""
import logging
from flask import Blueprint, request, jsonify, render_template
from sqlalchemy import and_

from ..services.document_annotation_service import DocumentAnnotationService
from ..services.simplified_llm_annotation_service import SimplifiedLLMAnnotationService
from ..models.document_concept_annotation import DocumentConceptAnnotation
from ..utils.environment_auth import auth_required_for_llm, auth_required_for_write
from .. import db

logger = logging.getLogger(__name__)

# Create the blueprint
bp = Blueprint('api_document_annotations', __name__, url_prefix='/api/document-annotations')

# Function to exempt blueprint from CSRF after app initialization
def init_csrf_exemption(app):
    """Exempt this blueprint from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        app.csrf.exempt(bp)


@bp.route('/<document_type>/<int:document_id>/annotate', methods=['POST'])
@auth_required_for_llm
def generate_annotations(document_type, document_id):
    """Generate annotations for a document using the simplified LLM method"""
    try:
        # Validate document type
        if document_type not in ['case', 'guideline']:
            return jsonify({'error': 'Invalid document type'}), 400
        
        # Get the document
        document = DocumentAnnotationService.get_document_by_id_and_type(document_id, document_type)
        if not document:
            return jsonify({'error': f'{document_type.title()} not found'}), 404
        
        # Get content for annotation
        content = DocumentAnnotationService.get_document_content_for_annotation(document_id, document_type)
        if not content:
            return jsonify({'error': 'No content available for annotation'}), 400
        
        # Get request parameters
        data = request.get_json() or {}
        ontologies = data.get('ontologies', [])
        world_id = data.get('world_id')
        
        # If no world_id provided, try to get it from the document
        if not world_id:
            world_id = getattr(document, 'world_id', None)
        
        # Initialize LLM annotation service
        llm_service = SimplifiedLLMAnnotationService()
        
        # Generate annotations using simplified method
        result = llm_service.annotate_document(
            document_id=document_id,
            document_type=document_type,
            content=content,
            world_id=world_id,
            ontologies=ontologies
        )
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': f'Generated {result.get("annotations_created", 0)} annotations',
                'statistics': {
                    'annotations_created': result.get('annotations_created', 0),
                    'ontologies_used': result.get('ontologies_used', []),
                    'method': 'simplified_llm'
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error occurred')
            }), 500
    
    except Exception as e:
        logger.error(f"Error generating annotations for {document_type} {document_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<document_type>/<int:document_id>/annotations', methods=['GET'])
def get_document_annotations(document_type, document_id):
    """Get annotations for a document"""
    try:
        # Validate document type
        if document_type not in ['case', 'guideline']:
            return jsonify({'error': 'Invalid document type'}), 400
        
        # Get annotations grouped by ontology
        annotations_by_ontology = DocumentAnnotationService.get_annotations_grouped_by_ontology(
            document_id, document_type
        )
        
        # Get statistics
        stats = DocumentAnnotationService.get_annotation_statistics(document_id, document_type)
        
        return jsonify({
            'success': True,
            'document_id': document_id,
            'document_type': document_type,
            'annotations_by_ontology': {
                ontology: [
                    {
                        'id': ann.id,
                        'concept_label': ann.concept_label,
                        'concept_definition': ann.concept_definition,
                        'text_segment': ann.text_segment,
                        'confidence': ann.confidence,
                        'concept_type': ann.concept_type,
                        'validation_status': ann.validation_status,
                        'approval_stage': ann.approval_stage,
                        'llm_reasoning': ann.llm_reasoning,
                        'created_at': ann.created_at.isoformat() if ann.created_at else None
                    } for ann in annotations
                ] for ontology, annotations in annotations_by_ontology.items()
            },
            'statistics': stats
        })
    
    except Exception as e:
        logger.error(f"Error getting annotations for {document_type} {document_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<document_type>/<int:document_id>/annotations/<int:annotation_id>', methods=['GET'])
def get_annotation_details(document_type, document_id, annotation_id):
    """Get detailed information about a specific annotation"""
    try:
        # Validate document type
        if document_type not in ['case', 'guideline']:
            return jsonify({'error': 'Invalid document type'}), 400
        
        # Get the annotation
        annotation = DocumentAnnotationService.get_annotation_by_id(annotation_id)
        
        if not annotation:
            return jsonify({'error': 'Annotation not found'}), 404
        
        # Verify annotation belongs to the specified document
        if annotation.document_id != document_id or annotation.document_type != document_type:
            return jsonify({'error': 'Annotation does not belong to specified document'}), 400
        
        return jsonify({
            'success': True,
            'annotation': {
                'id': annotation.id,
                'document_id': annotation.document_id,
                'document_type': annotation.document_type,
                'concept_label': annotation.concept_label,
                'concept_definition': annotation.concept_definition,
                'concept_uri': annotation.concept_uri,
                'text_segment': annotation.text_segment,
                'start_offset': annotation.start_offset,
                'end_offset': annotation.end_offset,
                'confidence': annotation.confidence,
                'concept_type': annotation.concept_type,
                'validation_status': annotation.validation_status,
                'approval_stage': annotation.approval_stage,
                'llm_reasoning': annotation.llm_reasoning,
                'llm_model': annotation.llm_model,
                'ontology_name': annotation.ontology_name,
                'is_current': annotation.is_current,
                'version_number': annotation.version_number,
                'created_at': annotation.created_at.isoformat() if annotation.created_at else None,
                'updated_at': annotation.updated_at.isoformat() if annotation.updated_at else None
            }
        })
    
    except Exception as e:
        logger.error(f"Error getting annotation details for {document_type} {document_id}, annotation {annotation_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<document_type>/<int:document_id>/annotations/<int:annotation_id>/approve', methods=['POST'])
def approve_annotation(document_type, document_id, annotation_id):
    """Approve an annotation"""
    try:
        # Validate document type
        if document_type not in ['case', 'guideline']:
            return jsonify({'error': 'Invalid document type'}), 400
        
        # Get the annotation
        annotation = DocumentAnnotationService.get_annotation_by_id(annotation_id)
        
        if not annotation:
            return jsonify({'error': 'Annotation not found'}), 404
        
        # Verify annotation belongs to the specified document
        if annotation.document_id != document_id or annotation.document_type != document_type:
            return jsonify({'error': 'Annotation does not belong to specified document'}), 400
        
        # Update approval status
        annotation.approval_stage = 'user_approved'
        annotation.validation_status = 'approved'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Annotation approved successfully'
        })
    
    except Exception as e:
        logger.error(f"Error approving annotation {annotation_id} for {document_type} {document_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<document_type>/<int:document_id>/annotations/<int:annotation_id>/reject', methods=['POST'])
def reject_annotation(document_type, document_id, annotation_id):
    """Reject an annotation"""
    try:
        # Validate document type
        if document_type not in ['case', 'guideline']:
            return jsonify({'error': 'Invalid document type'}), 400
        
        # Get the annotation
        annotation = DocumentAnnotationService.get_annotation_by_id(annotation_id)
        
        if not annotation:
            return jsonify({'error': 'Annotation not found'}), 404
        
        # Verify annotation belongs to the specified document
        if annotation.document_id != document_id or annotation.document_type != document_type:
            return jsonify({'error': 'Annotation does not belong to specified document'}), 400
        
        # Update approval status
        annotation.approval_stage = 'user_rejected'
        annotation.validation_status = 'rejected'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Annotation rejected successfully'
        })
    
    except Exception as e:
        logger.error(f"Error rejecting annotation {annotation_id} for {document_type} {document_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<document_type>/<int:document_id>/annotations/batch/approve', methods=['POST'])
@auth_required_for_write
def batch_approve_annotations(document_type, document_id):
    """Batch approve pending annotations for a document"""
    try:
        # Validate document type
        if document_type not in ['case', 'guideline']:
            return jsonify({'error': 'Invalid document type'}), 400
        
        # Get request data
        data = request.get_json() or {}
        approval_type = data.get('approval_type', 'user')  # 'user' or 'llm'
        
        # Get pending annotations
        pending_annotations = DocumentConceptAnnotation.query.filter(
            and_(
                DocumentConceptAnnotation.document_id == document_id,
                DocumentConceptAnnotation.document_type == document_type,
                DocumentConceptAnnotation.approval_stage == 'pending'
            )
        ).all()
        
        approved_count = 0
        for annotation in pending_annotations:
            if approval_type == 'llm':
                annotation.approval_stage = 'llm_approved'
            else:
                annotation.approval_stage = 'user_approved'
                annotation.validation_status = 'approved'
            approved_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'approved_count': approved_count,
            'message': f'Approved {approved_count} annotations'
        })
    
    except Exception as e:
        logger.error(f"Error batch approving annotations for {document_type} {document_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<document_type>/<int:document_id>/annotations/statistics', methods=['GET'])
def get_annotation_statistics(document_type, document_id):
    """Get annotation statistics for a document"""
    try:
        # Validate document type
        if document_type not in ['case', 'guideline']:
            return jsonify({'error': 'Invalid document type'}), 400
        
        # Get statistics
        stats = DocumentAnnotationService.get_annotation_statistics(document_id, document_type)
        
        # Add additional metrics
        pending_count = DocumentAnnotationService.get_pending_annotations_count(document_id, document_type)
        approved_count = DocumentAnnotationService.get_approved_annotations_count(document_id, document_type)
        
        stats.update({
            'pending_annotations': pending_count,
            'approved_annotations': approved_count
        })
        
        return jsonify({
            'success': True,
            'document_id': document_id,
            'document_type': document_type,
            'statistics': stats
        })
    
    except Exception as e:
        logger.error(f"Error getting annotation statistics for {document_type} {document_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<document_type>/<int:document_id>/annotations/clear', methods=['DELETE'])
def clear_document_annotations(document_type, document_id):
    """Clear all annotations for a document"""
    try:
        # Validate document type
        if document_type not in ['case', 'guideline']:
            return jsonify({'error': 'Invalid document type'}), 400
        
        # Delete all annotations
        deleted_count = DocumentAnnotationService.delete_all_annotations_for_document(document_id, document_type)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Cleared {deleted_count} annotations'
        })
    
    except Exception as e:
        logger.error(f"Error clearing annotations for {document_type} {document_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
