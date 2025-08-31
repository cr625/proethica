"""
Routes for document concept annotation functionality.
"""
from flask import Blueprint, request, jsonify, flash, redirect, url_for, render_template
from flask_login import login_required, current_user
from app.models.guideline import Guideline
from app.models.document import Document
from app.models.document_concept_annotation import DocumentConceptAnnotation
from app.models.world import World
from app.services.document_annotation_pipeline import DocumentAnnotationPipeline
from app.services.simple_annotation_service import SimpleAnnotationService
from app.services.ontserve_annotation_service import OntServeAnnotationService
import logging

logger = logging.getLogger(__name__)

annotations_bp = Blueprint('annotations', __name__, url_prefix='/annotations')

@annotations_bp.route('/guideline/<int:guideline_id>/annotate', methods=['POST'])
@login_required
def annotate_guideline(guideline_id):
    """Trigger annotation process for a guideline."""
    try:
        # Try Guideline table first, then Document table
        guideline = Guideline.query.filter_by(id=guideline_id).first()
        if not guideline:
            guideline = Document.query.filter_by(id=guideline_id, document_type='guideline').first()
        if not guideline:
            flash(f'Guideline {guideline_id} not found.', 'error')
            return redirect(url_for('guidelines.index'))
        
        # Check permissions
        if not guideline.world.can_edit(current_user):
            flash('You do not have permission to annotate this guideline.', 'error')
            return redirect(url_for('guidelines.view', id=guideline_id))
        
        # Check if annotations already exist
        force_refresh = request.json.get('force_refresh', False) if request.is_json else False
        
        existing = DocumentConceptAnnotation.get_annotations_for_document(
            'guideline', guideline_id
        )
        
        if existing and not force_refresh:
            # Check if newer ontology versions are available
            ontserve_service = OntServeAnnotationService()
            updates_available = ontserve_service.check_for_ontology_updates(existing)
            
            if any(updates_available.values()):
                ontologies_with_updates = [ont for ont, has_update in updates_available.items() if has_update]
                message = f'Newer ontology versions available for: {", ".join(ontologies_with_updates)}. Re-annotating...'
                flash(message, 'info')
                force_refresh = True
            else:
                flash('Document already annotated with current ontology versions.', 'info')
                return redirect(url_for('guidelines.view', id=guideline_id))
        
        # Run annotation pipeline (using simple service for reliability)
        simple_service = SimpleAnnotationService()
        annotations = simple_service.annotate_document('guideline', guideline_id, guideline.world_id, force_refresh)
        
        if annotations:
            flash(f'Successfully annotated document with {len(annotations)} concepts from ontology.', 'success')
        else:
            flash('No annotations were created. Please check the logs for details.', 'warning')
        
        # Return JSON for AJAX requests
        if request.is_json:
            return jsonify({
                'success': True,
                'annotation_count': len(annotations),
                'message': f'Created {len(annotations)} annotations'
            })
        
        return redirect(url_for('guidelines.view', id=guideline_id))
        
    except Exception as e:
        logger.exception(f"Error annotating guideline {guideline_id}: {e}")
        message = f'Error during annotation: {str(e)}'
        
        if request.is_json:
            return jsonify({'success': False, 'error': message}), 500
        
        flash(message, 'error')
        return redirect(url_for('guidelines.view', id=guideline_id))

@annotations_bp.route('/case/<int:case_id>/annotate', methods=['POST'])
@login_required
def annotate_case(case_id):
    """Trigger annotation process for a case study."""
    try:
        case = Document.query.get_or_404(case_id)
        
        # Check permissions
        if not case.world.can_edit(current_user):
            flash('You do not have permission to annotate this case.', 'error')
            return redirect(url_for('cases.view_case', id=case_id))
        
        # Check if annotations already exist
        force_refresh = request.json.get('force_refresh', False) if request.is_json else False
        
        existing = DocumentConceptAnnotation.get_annotations_for_document('case', case_id)
        
        if existing and not force_refresh:
            flash('Case already annotated. Use force refresh to re-annotate.', 'info')
            if request.is_json:
                return jsonify({'success': True, 'annotation_count': len(existing)})
            return redirect(url_for('cases.view_case', id=case_id))
        
        # Run annotation pipeline (using simple service for reliability)
        simple_service = SimpleAnnotationService()
        annotations = simple_service.annotate_document('case', case_id, case.world_id, force_refresh)
        
        if annotations:
            flash(f'Successfully annotated case with {len(annotations)} concepts from ontology.', 'success')
        else:
            flash('No annotations were created. Please check the logs for details.', 'warning')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'annotation_count': len(annotations),
                'message': f'Created {len(annotations)} annotations'
            })
        
        return redirect(url_for('cases.view_case', id=case_id))
        
    except Exception as e:
        logger.exception(f"Error annotating case {case_id}: {e}")
        message = f'Error during annotation: {str(e)}'
        
        if request.is_json:
            return jsonify({'success': False, 'error': message}), 500
        
        flash(message, 'error')
        return redirect(url_for('cases.view_case', id=case_id))

@annotations_bp.route('/api/<document_type>/<int:document_id>')
def get_annotations(document_type, document_id):
    """API endpoint to get annotations for a document."""
    try:
        if document_type not in ['guideline', 'case']:
            return jsonify({'error': 'Invalid document type'}), 400
        
        # Verify document exists and user has access
        if document_type == 'guideline':
            # Try Guideline table first, then Document table
            document = Guideline.query.filter_by(id=document_id).first()
            if not document:
                # Check Document table for guidelines stored there
                document = Document.query.filter_by(id=document_id, document_type='guideline').first()
            if not document:
                return jsonify({'error': f'Guideline {document_id} not found'}), 404
            if not document.world.can_view(current_user):
                return jsonify({'error': 'Access denied'}), 403
        elif document_type == 'case':
            document = Document.query.get_or_404(document_id)
            if not document.world.can_view(current_user):
                return jsonify({'error': 'Access denied'}), 403
        
        # Get annotations
        annotations = DocumentConceptAnnotation.get_annotations_for_document(
            document_type, document_id
        )
        
        # Filter by ontology if specified
        ontology_filter = request.args.get('ontology')
        if ontology_filter and ontology_filter != 'all':
            annotations = [a for a in annotations if a.ontology_name == ontology_filter]
        
        # Convert to JSON
        annotation_data = []
        for annotation in annotations:
            data = annotation.to_dict()
            data['confidence_level'] = annotation.get_confidence_level()
            data['confidence_badge_class'] = annotation.get_confidence_badge_class()
            annotation_data.append(data)
        
        return jsonify({
            'annotations': annotation_data,
            'total_count': len(annotation_data),
            'document_type': document_type,
            'document_id': document_id
        })
        
    except Exception as e:
        logger.exception(f"Error getting annotations for {document_type} {document_id}: {e}")
        return jsonify({'error': str(e)}), 500

@annotations_bp.route('/api/<document_type>/<int:document_id>/summary')
def get_annotation_summary(document_type, document_id):
    """API endpoint to get annotation summary for a document."""
    try:
        if document_type not in ['guideline', 'case']:
            return jsonify({'error': 'Invalid document type'}), 400
        
        # Get summary using pipeline service
        pipeline = DocumentAnnotationPipeline()
        summary = pipeline.get_annotation_summary(document_type, document_id)
        
        return jsonify(summary)
        
    except Exception as e:
        logger.exception(f"Error getting annotation summary for {document_type} {document_id}: {e}")
        return jsonify({'error': str(e)}), 500

@annotations_bp.route('/api/annotation/<int:annotation_id>/validate', methods=['POST'])
@login_required
def validate_annotation(annotation_id):
    """API endpoint to validate (approve/reject) an annotation."""
    try:
        annotation = DocumentConceptAnnotation.query.get_or_404(annotation_id)
        
        # Check permissions - user should be able to edit the document's world
        document = annotation.get_document()
        if not document or not document.world.can_edit(current_user):
            return jsonify({'error': 'Permission denied'}), 403
        
        data = request.get_json()
        action = data.get('action')  # 'approve' or 'reject'
        
        if action == 'approve':
            annotation.approve(current_user.id)
            message = 'Annotation approved'
        elif action == 'reject':
            annotation.reject(current_user.id)
            message = 'Annotation rejected'
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
        return jsonify({
            'success': True,
            'message': message,
            'annotation': annotation.to_dict()
        })
        
    except Exception as e:
        logger.exception(f"Error validating annotation {annotation_id}: {e}")
        return jsonify({'error': str(e)}), 500

@annotations_bp.route('/api/world/<int:world_id>/ontology-mapping', methods=['GET', 'POST'])
@login_required
def manage_world_ontology_mapping(world_id):
    """API endpoint to get or update world ontology mapping."""
    try:
        world = World.query.get_or_404(world_id)
        
        if not world.can_edit(current_user):
            return jsonify({'error': 'Permission denied'}), 403
        
        if request.method == 'GET':
            # Get current mapping
            ontserve_service = OntServeAnnotationService()
            mapping = ontserve_service.get_world_ontology_mapping(world_id)
            
            return jsonify({
                'world_id': world_id,
                'world_name': world.name,
                'ontology_mapping': mapping
            })
        
        elif request.method == 'POST':
            # Update mapping
            data = request.get_json()
            new_mapping = data.get('ontology_mapping', {})
            
            ontserve_service = OntServeAnnotationService()
            success = ontserve_service.update_world_ontology_mapping(world_id, new_mapping)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Ontology mapping updated successfully',
                    'ontology_mapping': new_mapping
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update ontology mapping'
                }), 400
                
    except Exception as e:
        logger.exception(f"Error managing ontology mapping for world {world_id}: {e}")
        return jsonify({'error': str(e)}), 500

@annotations_bp.route('/api/ontology-updates/check')
@login_required
def check_ontology_updates():
    """API endpoint to check for available ontology updates across all worlds."""
    try:
        # Get all worlds user has access to
        if current_user.is_admin:
            worlds = World.query.all()
        else:
            worlds = World.query.filter_by(created_by=current_user.id).all()
        
        updates_info = {}
        ontserve_service = OntServeAnnotationService()
        
        for world in worlds:
            # Get annotations for this world
            annotations = DocumentConceptAnnotation.get_annotations_for_world(world.id)
            
            if annotations:
                updates_available = ontserve_service.check_for_ontology_updates(annotations)
                
                if any(updates_available.values()):
                    updates_info[world.id] = {
                        'world_name': world.name,
                        'updates_available': updates_available,
                        'annotation_count': len(annotations)
                    }
        
        return jsonify({
            'worlds_with_updates': updates_info,
            'total_worlds_checked': len(worlds)
        })
        
    except Exception as e:
        logger.exception(f"Error checking ontology updates: {e}")
        return jsonify({'error': str(e)}), 500

@annotations_bp.route('/validation-dashboard')
@login_required
def validation_dashboard():
    """Dashboard for managing annotation validations."""
    try:
        # Get pending validations
        pending_annotations = DocumentConceptAnnotation.get_pending_validations()
        
        # Filter by user permissions
        accessible_annotations = []
        for annotation in pending_annotations:
            document = annotation.get_document()
            if document and document.world.can_view(current_user):
                accessible_annotations.append(annotation)
        
        # Group by world and document type
        by_world = {}
        for annotation in accessible_annotations:
            world_id = annotation.world_id
            if world_id not in by_world:
                by_world[world_id] = {
                    'world_name': annotation.world.name if annotation.world else 'Unknown',
                    'guidelines': [],
                    'cases': []
                }
            
            if annotation.document_type == 'guideline':
                by_world[world_id]['guidelines'].append(annotation)
            elif annotation.document_type == 'case':
                by_world[world_id]['cases'].append(annotation)
        
        return render_template('annotations/validation_dashboard.html',
                             pending_annotations=accessible_annotations,
                             by_world=by_world,
                             total_pending=len(accessible_annotations))
        
    except Exception as e:
        logger.exception(f"Error loading validation dashboard: {e}")
        flash(f'Error loading validation dashboard: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))

@annotations_bp.route('/clear/<document_type>/<int:document_id>', methods=['POST'])
@login_required
def clear_annotations(document_type, document_id):
    """Clear all annotations for a document to allow re-annotation."""
    try:
        if document_type not in ['guideline', 'case']:
            return jsonify({'error': 'Invalid document type'}), 400
        
        # Get document and check permissions
        if document_type == 'guideline':
            # Try Guideline table first, then Document table
            document = Guideline.query.filter_by(id=document_id).first()
            if not document:
                document = Document.query.filter_by(id=document_id, document_type='guideline').first()
            if not document:
                return jsonify({'error': f'Guideline {document_id} not found'}), 404
        else:
            document = Document.query.get_or_404(document_id)
        
        if not document.world.can_edit(current_user):
            return jsonify({'error': 'Permission denied'}), 403
        
        # Delete existing annotations
        from app.models import db
        existing = DocumentConceptAnnotation.get_annotations_for_document(document_type, document_id)
        count = len(existing)
        
        for annotation in existing:
            db.session.delete(annotation)
        
        db.session.commit()
        
        message = f'Cleared {count} existing annotations'
        logger.info(f"Cleared annotations for {document_type} {document_id}: {count} annotations removed")
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': message,
                'cleared_count': count
            })
        
        flash(message, 'info')
        if document_type == 'guideline':
            return redirect(url_for('guidelines.view', id=document_id))
        else:
            return redirect(url_for('cases.view_case', id=document_id))
        
    except Exception as e:
        logger.exception(f"Error clearing annotations for {document_type} {document_id}: {e}")
        message = f'Error clearing annotations: {str(e)}'
        
        if request.is_json:
            return jsonify({'success': False, 'error': message}), 500
        
        flash(message, 'error')
        return redirect(url_for('dashboard.index'))

@annotations_bp.route('/statistics')
@login_required
def annotation_statistics():
    """View annotation statistics across all accessible worlds."""
    try:
        # Get accessible worlds
        if current_user.is_admin:
            worlds = World.query.all()
        else:
            worlds = World.query.filter_by(created_by=current_user.id).all()
        
        world_stats = []
        total_stats = {
            'total_annotations': 0,
            'by_ontology': {},
            'by_confidence': {'high': 0, 'medium': 0, 'low': 0},
            'by_status': {'pending': 0, 'approved': 0, 'rejected': 0}
        }
        
        for world in worlds:
            stats = DocumentConceptAnnotation.get_annotation_statistics(world.id)
            stats['world_name'] = world.name
            stats['world_id'] = world.id
            world_stats.append(stats)
            
            # Aggregate totals
            total_stats['total_annotations'] += stats['total']
            
            for ontology, count in stats['ontology_counts'].items():
                if ontology not in total_stats['by_ontology']:
                    total_stats['by_ontology'][ontology] = 0
                total_stats['by_ontology'][ontology] += count
            
            for level, count in stats['confidence_levels'].items():
                total_stats['by_confidence'][level] += count
            
            total_stats['by_status']['approved'] += stats['approved']
            total_stats['by_status']['rejected'] += stats['rejected']
            total_stats['by_status']['pending'] += stats['pending']
        
        return render_template('annotations/statistics.html',
                             world_stats=world_stats,
                             total_stats=total_stats,
                             worlds_count=len(worlds))
        
    except Exception as e:
        logger.exception(f"Error loading annotation statistics: {e}")
        flash(f'Error loading statistics: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))
