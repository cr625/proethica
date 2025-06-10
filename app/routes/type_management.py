"""
Type Management Routes

Provides UI and API endpoints for reviewing and managing concept type mappings.
This includes reviewing type mapping decisions, approving new types, and 
managing the type mapping workflow.
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from sqlalchemy import desc, func
import logging

from app import db
from app.models.entity_triple import EntityTriple
from app.models.guideline import Guideline
from app.models.concept_type_mapping import ConceptTypeMapping
from app.models.pending_concept_type import PendingConceptType

# Set up logging
logger = logging.getLogger(__name__)

# Create blueprint
type_management_bp = Blueprint('type_management', __name__, url_prefix='/type-management')

@type_management_bp.route('/')
def dashboard():
    """
    Type Review Dashboard - main overview page.
    Shows concepts needing review, mapping statistics, and quick actions.
    """
    try:
        # Get concepts needing review
        concepts_needing_review = EntityTriple.query.filter_by(
            needs_type_review=True,
            entity_type='guideline_concept'
        ).order_by(desc(EntityTriple.id)).limit(20).all()
        
        # Get recent mappings
        recent_mappings = EntityTriple.query.filter(
            EntityTriple.original_llm_type.isnot(None),
            EntityTriple.entity_type == 'guideline_concept'
        ).order_by(desc(EntityTriple.id)).limit(10).all()
        
        # Get mapping statistics
        try:
            mapping_stats = ConceptTypeMapping.get_mapping_statistics()
        except Exception as e:
            logger.warning(f"Could not get mapping statistics: {e}")
            mapping_stats = {}
        
        # Get pending types
        try:
            pending_types = PendingConceptType.query.filter_by(status='pending').all()
        except Exception as e:
            logger.warning(f"Could not get pending types: {e}")
            pending_types = []
        
        # Calculate confidence distribution
        confidence_stats = db.session.query(
            func.avg(EntityTriple.type_mapping_confidence).label('avg_confidence'),
            func.min(EntityTriple.type_mapping_confidence).label('min_confidence'),
            func.max(EntityTriple.type_mapping_confidence).label('max_confidence'),
            func.count(EntityTriple.id).label('total_concepts')
        ).filter(
            EntityTriple.type_mapping_confidence.isnot(None),
            EntityTriple.entity_type == 'guideline_concept'
        ).first()
        
        # Type distribution
        type_distribution = db.session.query(
            EntityTriple.object_literal,
            func.count(EntityTriple.id).label('count')
        ).filter(
            EntityTriple.entity_type == 'guideline_concept',
            EntityTriple.predicate == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
        ).group_by(EntityTriple.object_literal).all()
        
        return render_template('type_management/dashboard.html',
                             concepts_needing_review=concepts_needing_review,
                             recent_mappings=recent_mappings,
                             mapping_stats=mapping_stats,
                             pending_types=pending_types,
                             confidence_stats=confidence_stats,
                             type_distribution=type_distribution)
        
    except Exception as e:
        logger.error(f"Error loading type management dashboard: {str(e)}")
        flash(f"Error loading dashboard: {str(e)}", 'error')
        return render_template('type_management/dashboard.html',
                             concepts_needing_review=[],
                             recent_mappings=[],
                             mapping_stats={},
                             pending_types=[],
                             confidence_stats=None,
                             type_distribution=[])

@type_management_bp.route('/concepts')
def concept_list():
    """
    List all concepts with filtering and sorting options.
    """
    try:
        # Get filter parameters
        filter_type = request.args.get('filter', 'all')  # all, needs_review, low_confidence
        sort_by = request.args.get('sort', 'recent')  # recent, confidence, name
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Build query - only show rdf:type triples (concept type definitions)
        query = EntityTriple.query.filter(
            EntityTriple.entity_type == 'guideline_concept',
            EntityTriple.predicate == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
        )
        
        # Apply filters
        if filter_type == 'needs_review':
            query = query.filter_by(needs_type_review=True)
        elif filter_type == 'low_confidence':
            query = query.filter(EntityTriple.type_mapping_confidence < 0.7)
        elif filter_type == 'with_metadata':
            query = query.filter(EntityTriple.original_llm_type.isnot(None))
        
        # Apply sorting
        if sort_by == 'confidence':
            query = query.order_by(EntityTriple.type_mapping_confidence.asc().nullslast())
        elif sort_by == 'name':
            query = query.order_by(EntityTriple.subject_label)
        else:  # recent
            query = query.order_by(desc(EntityTriple.id))
        
        # Paginate
        concepts = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return render_template('type_management/concept_list.html',
                             concepts=concepts,
                             filter_type=filter_type,
                             sort_by=sort_by)
        
    except Exception as e:
        logger.error(f"Error loading concept list: {str(e)}")
        flash(f"Error loading concepts: {str(e)}", 'error')
        return redirect(url_for('type_management.dashboard'))

@type_management_bp.route('/concept/<int:concept_id>')
def concept_detail(concept_id):
    """
    Detailed view of a single concept with edit capabilities.
    """
    try:
        concept = EntityTriple.query.get_or_404(concept_id)
        
        # Get related triples for this concept
        related_triples = EntityTriple.query.filter_by(
            subject=concept.subject
        ).all()
        
        # Get guideline info
        guideline = None
        if concept.guideline_id:
            guideline = Guideline.query.get(concept.guideline_id)
        
        # Get similar concepts (same original LLM type)
        similar_concepts = []
        if concept.original_llm_type:
            similar_concepts = EntityTriple.query.filter_by(
                original_llm_type=concept.original_llm_type,
                entity_type='guideline_concept'
            ).filter(EntityTriple.id != concept.id).limit(5).all()
        
        return render_template('type_management/concept_detail.html',
                             concept=concept,
                             related_triples=related_triples,
                             guideline=guideline,
                             similar_concepts=similar_concepts)
        
    except Exception as e:
        logger.error(f"Error loading concept detail: {str(e)}")
        flash(f"Error loading concept: {str(e)}", 'error')
        return redirect(url_for('type_management.dashboard'))

@type_management_bp.route('/concept/<int:concept_id>/update', methods=['POST'])
def update_concept_type(concept_id):
    """
    Update the type of a concept and its review status.
    """
    try:
        concept = EntityTriple.query.get_or_404(concept_id)
        
        new_type = request.form.get('new_type')
        review_status = request.form.get('review_status') == 'approved'
        notes = request.form.get('notes', '')
        
        if not new_type:
            flash('New type is required', 'error')
            return redirect(url_for('type_management.concept_detail', concept_id=concept_id))
        
        # Update the concept
        old_type = concept.object_literal
        concept.object_literal = new_type
        concept.object_label = new_type.title()
        concept.needs_type_review = not review_status
        
        # Add update metadata
        concept.mapping_justification = f"Manual update: {old_type} → {new_type}. {notes}".strip()
        concept.type_mapping_confidence = 1.0 if review_status else concept.type_mapping_confidence
        
        # Create or update type mapping record
        try:
            ConceptTypeMapping.create_or_update_mapping(
                llm_type=concept.original_llm_type or old_type,
                mapped_type=new_type,
                confidence=1.0 if review_status else 0.8,
                is_automatic=False
            )
        except Exception as e:
            logger.warning(f"Could not update mapping record: {e}")
        
        db.session.commit()
        
        flash(f'Concept type updated: {old_type} → {new_type}', 'success')
        return redirect(url_for('type_management.concept_detail', concept_id=concept_id))
        
    except Exception as e:
        logger.error(f"Error updating concept type: {str(e)}")
        db.session.rollback()
        flash(f"Error updating concept: {str(e)}", 'error')
        return redirect(url_for('type_management.concept_detail', concept_id=concept_id))

@type_management_bp.route('/mappings')
def mapping_statistics():
    """
    View type mapping statistics and patterns.
    """
    try:
        # Get all mappings with usage statistics
        mappings = ConceptTypeMapping.query.order_by(
            desc(ConceptTypeMapping.usage_count)
        ).all()
        
        # Get mapping accuracy over time
        accuracy_stats = db.session.query(
            func.date(EntityTriple.created_at).label('date'),
            func.avg(EntityTriple.type_mapping_confidence).label('avg_confidence'),
            func.count(EntityTriple.id).label('concept_count')
        ).filter(
            EntityTriple.type_mapping_confidence.isnot(None),
            EntityTriple.entity_type == 'guideline_concept'
        ).group_by(func.date(EntityTriple.created_at)).all()
        
        # Most common mappings
        common_mappings = db.session.query(
            EntityTriple.original_llm_type,
            EntityTriple.object_literal,
            func.count(EntityTriple.id).label('count'),
            func.avg(EntityTriple.type_mapping_confidence).label('avg_confidence')
        ).filter(
            EntityTriple.original_llm_type.isnot(None),
            EntityTriple.entity_type == 'guideline_concept'
        ).group_by(
            EntityTriple.original_llm_type,
            EntityTriple.object_literal
        ).order_by(desc('count')).limit(20).all()
        
        return render_template('type_management/mapping_statistics.html',
                             mappings=mappings,
                             accuracy_stats=accuracy_stats,
                             common_mappings=common_mappings)
        
    except Exception as e:
        logger.error(f"Error loading mapping statistics: {str(e)}")
        flash(f"Error loading statistics: {str(e)}", 'error')
        return redirect(url_for('type_management.dashboard'))

@type_management_bp.route('/pending-types')
def pending_types():
    """
    Manage pending concept types awaiting approval.
    """
    try:
        pending = PendingConceptType.query.order_by(desc(PendingConceptType.created_at)).all()
        
        return render_template('type_management/pending_types.html',
                             pending_types=pending)
        
    except Exception as e:
        logger.error(f"Error loading pending types: {str(e)}")
        flash(f"Error loading pending types: {str(e)}", 'error')
        return redirect(url_for('type_management.dashboard'))

@type_management_bp.route('/api/batch-approve', methods=['POST'])
def batch_approve_concepts():
    """
    API endpoint for batch approving concept types.
    """
    try:
        concept_ids = request.json.get('concept_ids', [])
        action = request.json.get('action', 'approve')  # approve, reject, needs_review
        
        if not concept_ids:
            return jsonify({'error': 'No concept IDs provided'}), 400
        
        concepts = EntityTriple.query.filter(EntityTriple.id.in_(concept_ids)).all()
        
        updated_count = 0
        for concept in concepts:
            if action == 'approve':
                concept.needs_type_review = False
                concept.type_mapping_confidence = 1.0
                concept.mapping_justification = f"Batch approved. {concept.mapping_justification or ''}".strip()
            elif action == 'reject':
                concept.needs_type_review = True
                concept.mapping_justification = f"Batch rejected - needs manual review. {concept.mapping_justification or ''}".strip()
            elif action == 'needs_review':
                concept.needs_type_review = True
            
            updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'updated_count': updated_count,
            'message': f'{action.title()}ed {updated_count} concepts'
        })
        
    except Exception as e:
        logger.error(f"Error in batch approve: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Register the blueprint in the main app
def register_type_management_routes(app):
    """Register type management routes with the Flask app."""
    app.register_blueprint(type_management_bp)