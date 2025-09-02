"""
API routes for annotation version management.

Handles the three-stage annotation approval workflow:
1. LLM Extraction (initial)
2. LLM Approval (intermediate validation)
3. User Approval (final human review)
"""

from flask import Blueprint, request, jsonify, current_app
from flask_wtf.csrf import validate_csrf
from datetime import datetime
from werkzeug.exceptions import BadRequest
import logging

from app.models import db
from app.models.document_concept_annotation import DocumentConceptAnnotation
from app.services.llm_annotation_approval_service import LLMAnnotationApprovalService
from app.services.ontserve_annotation_service import OntServeAnnotationService

# Create blueprint
annotation_versions_bp = Blueprint('annotation_versions', __name__, url_prefix='/api/annotations')

logger = logging.getLogger(__name__)

# Initialize services
llm_approval_service = LLMAnnotationApprovalService()
ontserve_service = OntServeAnnotationService()


@annotation_versions_bp.route('/<int:annotation_id>', methods=['GET'])
def get_annotation_details(annotation_id):
    """
    Get detailed annotation information including version history.
    
    Query parameters:
    - include_versions: Include full version history (default: false)
    - include_reasoning: Include LLM reasoning (default: false)
    """
    try:
        annotation = DocumentConceptAnnotation.query.get_or_404(annotation_id)
        
        include_versions = request.args.get('include_versions', 'false').lower() == 'true'
        include_reasoning = request.args.get('include_reasoning', 'false').lower() == 'true'
        
        # Get document context if available
        document_context = None
        try:
            document = annotation.get_document()
            if document and hasattr(document, 'content') and annotation.start_offset is not None:
                content = document.content or ""
                start_pos = max(0, annotation.start_offset - 200)
                end_pos = min(len(content), annotation.end_offset + 200) if annotation.end_offset else len(content)
                document_context = content[start_pos:end_pos]
        except Exception as e:
            logger.warning(f"Could not get document context for annotation {annotation_id}: {e}")
        
        # Build response
        data = annotation.to_dict(
            include_llm_reasoning=include_reasoning,
            include_versions=include_versions
        )
        
        if document_context:
            data['document_context'] = document_context
        
        return jsonify(data)
        
    except Exception as e:
        logger.exception(f"Error getting annotation details for {annotation_id}: {e}")
        return jsonify({'error': 'Failed to load annotation'}), 500


@annotation_versions_bp.route('/<int:annotation_id>/approve', methods=['POST'])
def approve_annotation(annotation_id):
    """
    Approve an annotation, creating a new version with user approval status.
    
    Body can include edits to apply before approval:
    - confidence: New confidence level
    - llm_reasoning: Updated reasoning
    - concept_uri: Different concept URI
    - concept_label: Different concept label
    - concept_definition: Different concept definition
    """
    try:
        # Validate CSRF token
        validate_csrf(request.headers.get('X-CSRFToken'))
        
        annotation = DocumentConceptAnnotation.query.get_or_404(annotation_id)
        
        # Get any edits from request body
        edits = request.get_json() or {}
        
        # Add approval stage to edits
        edits['approval_stage'] = 'user_approved'
        edits['validation_status'] = 'approved'
        edits['validated_by'] = 1  # TODO: Get actual user ID from session
        edits['validated_at'] = datetime.utcnow()
        
        # Create new version with approval
        new_version = annotation.create_new_version(
            updates=edits,
            approval_stage='user_approved'
        )
        
        # Save to database
        db.session.add(new_version)
        db.session.commit()
        
        logger.info(f"User approved annotation {annotation_id}, created version {new_version.id}")
        
        return jsonify({
            'success': True,
            'annotation': new_version.to_dict(include_llm_reasoning=True),
            'message': 'Annotation approved successfully'
        })
        
    except Exception as e:
        logger.exception(f"Error approving annotation {annotation_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to approve annotation'}), 500


@annotation_versions_bp.route('/<int:annotation_id>/edit', methods=['POST'])
def edit_annotation(annotation_id):
    """
    Create a new version of an annotation with user edits.
    
    Body should contain the fields to update:
    - confidence: New confidence level
    - llm_reasoning: Updated reasoning
    - concept_uri: Different concept URI
    - concept_label: Different concept label  
    - concept_definition: Different concept definition
    """
    try:
        # Validate CSRF token
        validate_csrf(request.headers.get('X-CSRFToken'))
        
        annotation = DocumentConceptAnnotation.query.get_or_404(annotation_id)
        
        # Get edits from request body
        edits = request.get_json() or {}
        
        if not edits:
            return jsonify({'error': 'No edits provided'}), 400
        
        # Create new version with edits (but keep same approval stage)
        new_version = annotation.create_new_version(
            updates=edits,
            approval_stage=annotation.approval_stage  # Keep same stage for now
        )
        
        # Save to database
        db.session.add(new_version)
        db.session.commit()
        
        logger.info(f"User edited annotation {annotation_id}, created version {new_version.id}")
        
        return jsonify({
            'success': True,
            'annotation': new_version.to_dict(include_llm_reasoning=True),
            'message': 'Changes saved successfully'
        })
        
    except Exception as e:
        logger.exception(f"Error editing annotation {annotation_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to save changes'}), 500


@annotation_versions_bp.route('/<int:annotation_id>/reject', methods=['POST'])
def reject_annotation(annotation_id):
    """
    Reject an annotation by marking it as rejected.
    """
    try:
        # Validate CSRF token
        validate_csrf(request.headers.get('X-CSRFToken'))
        
        annotation = DocumentConceptAnnotation.query.get_or_404(annotation_id)
        
        # Update annotation status
        annotation.validation_status = 'rejected'
        annotation.validated_by = 1  # TODO: Get actual user ID from session
        annotation.validated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"User rejected annotation {annotation_id}")
        
        return jsonify({
            'success': True,
            'annotation': annotation.to_dict(),
            'message': 'Annotation rejected'
        })
        
    except Exception as e:
        logger.exception(f"Error rejecting annotation {annotation_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to reject annotation'}), 500


@annotation_versions_bp.route('/batch/llm-approve', methods=['POST'])
def batch_llm_approve():
    """
    Trigger LLM approval for a batch of annotations.
    
    Body should contain:
    - annotation_ids: List of annotation IDs to process
    - world_id: World context for ontology access (optional, default: 1)
    """
    try:
        # Validate CSRF token
        validate_csrf(request.headers.get('X-CSRFToken'))
        
        data = request.get_json() or {}
        annotation_ids = data.get('annotation_ids', [])
        world_id = data.get('world_id', 1)
        
        if not annotation_ids:
            return jsonify({'error': 'No annotation IDs provided'}), 400
        
        if len(annotation_ids) > 50:  # Limit batch size
            return jsonify({'error': 'Too many annotations (max 50)'}), 400
        
        # Run LLM approval
        results = llm_approval_service.approve_annotations(annotation_ids, world_id)
        
        successful = len([r for r in results if r.should_approve])
        failed = len([r for r in results if r.error_message])
        
        return jsonify({
            'success': True,
            'results': [
                {
                    'annotation_id': r.annotation_id,
                    'should_approve': r.should_approve,
                    'new_confidence': r.new_confidence,
                    'concerns': r.concerns,
                    'error': r.error_message
                }
                for r in results
            ],
            'summary': {
                'total_processed': len(results),
                'successful': successful,
                'failed': failed
            }
        })
        
    except Exception as e:
        logger.exception(f"Error in batch LLM approval: {e}")
        return jsonify({'error': 'Failed to process batch approval'}), 500


@annotation_versions_bp.route('/pending-approval', methods=['GET'])
def get_pending_approval():
    """
    Get annotations that are ready for user approval.
    
    Query parameters:
    - world_id: Filter by world (optional)
    - limit: Maximum number to return (default: 20)
    - stage: Filter by approval stage (default: llm_approved)
    """
    try:
        world_id = request.args.get('world_id', type=int)
        limit = request.args.get('limit', 20, type=int)
        stage = request.args.get('stage', 'llm_approved')
        
        # Limit the limit
        limit = min(limit, 100)
        
        if stage == 'llm_approved':
            annotations = DocumentConceptAnnotation.get_annotations_for_user_approval(world_id)
        else:
            annotations = DocumentConceptAnnotation.get_annotations_by_stage(stage, current_only=True)
            if world_id:
                annotations = [a for a in annotations if a.world_id == world_id]
        
        # Apply limit
        annotations = annotations[:limit]
        
        return jsonify({
            'annotations': [
                ann.to_dict(include_llm_reasoning=True) 
                for ann in annotations
            ],
            'total': len(annotations),
            'stage': stage
        })
        
    except Exception as e:
        logger.exception(f"Error getting pending approval annotations: {e}")
        return jsonify({'error': 'Failed to load pending annotations'}), 500


@annotation_versions_bp.route('/<int:annotation_id>/versions', methods=['GET'])
def get_annotation_versions(annotation_id):
    """
    Get all versions of a specific annotation.
    """
    try:
        annotation = DocumentConceptAnnotation.query.get_or_404(annotation_id)
        versions = annotation.get_version_history()
        
        return jsonify({
            'versions': [
                version.to_dict(include_llm_reasoning=True)
                for version in versions
            ],
            'total': len(versions),
            'annotation_group_id': annotation.annotation_group_id
        })
        
    except Exception as e:
        logger.exception(f"Error getting versions for annotation {annotation_id}: {e}")
        return jsonify({'error': 'Failed to load version history'}), 500


@annotation_versions_bp.route('/statistics', methods=['GET'])
def get_annotation_statistics():
    """
    Get statistics about annotations and approval workflow.
    
    Query parameters:
    - world_id: Filter by world (optional)
    """
    try:
        world_id = request.args.get('world_id', type=int)
        
        # Get general annotation statistics
        stats = DocumentConceptAnnotation.get_annotation_statistics(world_id)
        
        # Get LLM approval statistics
        llm_stats = llm_approval_service.get_approval_statistics(world_id)
        
        # Combine statistics
        combined_stats = {
            'general': stats,
            'llm_approval': llm_stats,
            'workflow_stages': {
                'llm_extracted': DocumentConceptAnnotation.query.filter_by(
                    approval_stage='llm_extracted', 
                    is_current=True
                ).filter(
                    DocumentConceptAnnotation.world_id == world_id if world_id else True
                ).count(),
                'llm_approved': DocumentConceptAnnotation.query.filter_by(
                    approval_stage='llm_approved', 
                    is_current=True
                ).filter(
                    DocumentConceptAnnotation.world_id == world_id if world_id else True
                ).count(),
                'user_approved': DocumentConceptAnnotation.query.filter_by(
                    approval_stage='user_approved', 
                    is_current=True
                ).filter(
                    DocumentConceptAnnotation.world_id == world_id if world_id else True
                ).count()
            }
        }
        
        return jsonify(combined_stats)
        
    except Exception as e:
        logger.exception(f"Error getting annotation statistics: {e}")
        return jsonify({'error': 'Failed to load statistics'}), 500


# Ontology search endpoint (for the modal)
@annotation_versions_bp.route('/search/concepts', methods=['GET'])
def search_ontology_concepts():
    """
    Search ontology concepts for the approval modal.
    
    Query parameters:
    - q: Search query
    - limit: Maximum results (default: 10)
    - world_id: World context (default: 1)
    """
    try:
        query = request.args.get('q', '').strip()
        limit = min(request.args.get('limit', 10, type=int), 50)
        world_id = request.args.get('world_id', 1, type=int)
        
        if len(query) < 2:
            return jsonify({'concepts': []})
        
        # Get ontology mapping for world
        ontology_mapping = ontserve_service.get_world_ontology_mapping(world_id)
        
        if not ontology_mapping:
            return jsonify({'concepts': []})
        
        # Get concepts from all mapped ontologies
        all_concepts = []
        for ontology_name in ontology_mapping.values():
            try:
                concepts = ontserve_service.get_ontology_concepts([ontology_name])
                for concept in concepts.get(ontology_name, []):
                    concept['ontology_name'] = ontology_name
                    all_concepts.append(concept)
            except Exception as e:
                logger.warning(f"Error getting concepts from {ontology_name}: {e}")
                continue
        
        # Simple text search in labels and definitions
        query_lower = query.lower()
        matching_concepts = []
        
        for concept in all_concepts:
            label = concept.get('label', '').lower()
            definition = concept.get('definition', '').lower()
            
            # Score based on matches
            score = 0
            if query_lower in label:
                score += 10
            if query_lower in definition:
                score += 5
            if any(word in label for word in query_lower.split()):
                score += 3
            
            if score > 0:
                concept['search_score'] = score
                matching_concepts.append(concept)
        
        # Sort by score and limit
        matching_concepts.sort(key=lambda x: x.get('search_score', 0), reverse=True)
        matching_concepts = matching_concepts[:limit]
        
        return jsonify({
            'concepts': matching_concepts,
            'total': len(matching_concepts),
            'query': query
        })
        
    except Exception as e:
        logger.exception(f"Error searching concepts: {e}")
        return jsonify({'error': 'Search failed'}), 500
