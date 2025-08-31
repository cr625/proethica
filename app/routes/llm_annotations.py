"""
LLM-Enhanced Annotation Routes

API endpoints for intelligent annotation using LLM capabilities.
"""

import logging
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models import Guideline, World
from app.models.document_concept_annotation import DocumentConceptAnnotation
from app import db
from app.services.llm_enhanced_annotation_service import (
    LLMEnhancedAnnotationService,
    EnhancedAnnotationResult
)
from datetime import datetime

logger = logging.getLogger(__name__)

bp = Blueprint('llm_annotations', __name__, url_prefix='/api/llm-annotations')


@bp.route('/guideline/<int:guideline_id>/annotate', methods=['POST'])
@login_required
def annotate_guideline_enhanced(guideline_id):
    """
    Perform enhanced LLM-powered annotation on a guideline.
    
    This endpoint uses intelligent term extraction and semantic matching
    to dramatically improve annotation quality compared to basic keyword matching.
    
    Returns:
        JSON response with annotation results including:
        - matches: List of semantic matches with ontology concepts
        - gaps: Terms that couldn't be matched (for ontology improvement)
        - statistics: Success rate, processing time, etc.
    """
    try:
        # Get guideline
        guideline = Guideline.query.get_or_404(guideline_id)
        
        # Check permissions - allow if user is logged in and world is accessible
        # For now, we'll allow any logged-in user to annotate
        # You can make this stricter later if needed
        if not current_user.is_authenticated:
            return jsonify({
                'success': False,
                'error': 'You must be logged in to annotate guidelines'
            }), 403
        
        # Get target ontologies from request or use world mapping
        target_ontologies = request.json.get('ontologies', None) if request.json else None
        
        # Initialize enhanced annotation service
        service = LLMEnhancedAnnotationService()
        
        # Perform enhanced annotation
        logger.info(f"Starting enhanced annotation for guideline {guideline_id}")
        result = service.annotate_text(
            guideline.content,
            world_id=guideline.world_id,
            target_ontologies=target_ontologies
        )
        
        # Store successful matches as annotations
        annotations_created = 0
        for match in result.matches:
            try:
                # Check if annotation already exists
                existing = DocumentConceptAnnotation.query.filter_by(
                    document_type='guideline',
                    document_id=guideline_id,
                    concept_uri=match.concept_uri,
                    text_segment=match.extracted_term.term
                ).first()
                
                if not existing:
                    # Create new annotation
                    annotation = DocumentConceptAnnotation(
                        document_type='guideline',
                        document_id=guideline_id,
                        world_id=guideline.world_id,
                        concept_uri=match.concept_uri,
                        concept_label=match.concept_label,
                        text_segment=match.extracted_term.term,
                        start_offset=match.extracted_term.start_offset,
                        end_offset=match.extracted_term.end_offset,
                        confidence=match.similarity_score,
                        ontology_name=match.concept_ontology,
                        concept_definition=match.concept_definition,
                        concept_type='llm_enhanced',
                        llm_model='claude-sonnet',
                        llm_reasoning=match.reasoning,
                        validation_status='pending'
                    )
                    db.session.add(annotation)
                    annotations_created += 1
                    
            except Exception as e:
                logger.error(f"Error storing annotation: {e}")
                continue
        
        # Commit all annotations
        if annotations_created > 0:
            db.session.commit()
            logger.info(f"Created {annotations_created} new annotations")
        
        # Generate report
        report = service.generate_annotation_report(result)
        
        # Prepare response
        response_data = {
            'success': True,
            'guideline_id': guideline_id,
            'statistics': {
                'terms_extracted': result.total_terms_extracted,
                'successful_matches': result.successful_matches,
                'failed_matches': result.failed_matches,
                'annotations_created': annotations_created,
                'success_rate': (result.successful_matches / result.total_terms_extracted * 100) 
                              if result.total_terms_extracted > 0 else 0,
                'processing_time_ms': result.processing_time_ms
            },
            'matches': [
                {
                    'term': match.extracted_term.term,
                    'concept_label': match.concept_label,
                    'concept_uri': match.concept_uri,
                    'ontology': match.concept_ontology,
                    'similarity_score': match.similarity_score,
                    'confidence': match.confidence,
                    'match_type': match.match_type,
                    'reasoning': match.reasoning,
                    'context': match.extracted_term.context,
                    'start_offset': match.extracted_term.start_offset,
                    'end_offset': match.extracted_term.end_offset
                }
                for match in result.matches
            ],
            'ontology_gaps': result.ontology_gaps,
            'report': report,
            'errors': result.errors
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.exception(f"Error in enhanced annotation for guideline {guideline_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/guideline/<int:guideline_id>/compare', methods=['GET'])
@login_required
def compare_annotation_methods(guideline_id):
    """
    Compare basic vs enhanced annotation methods for a guideline.
    
    Returns side-by-side comparison of:
    - Basic keyword matching results
    - Enhanced LLM semantic matching results
    """
    try:
        guideline = Guideline.query.get_or_404(guideline_id)
        
        # Check permissions - allow if user is logged in
        if not current_user.is_authenticated:
            return jsonify({
                'success': False,
                'error': 'You must be logged in to compare annotations'
            }), 403
        
        # Get existing basic annotations
        basic_annotations = DocumentConceptAnnotation.query.filter_by(
            document_type='guideline',
            document_id=guideline_id,
            llm_model=None  # Basic annotations don't use LLM
        ).all()
        
        # Get enhanced annotations (if any)
        enhanced_annotations = DocumentConceptAnnotation.query.filter_by(
            document_type='guideline',
            document_id=guideline_id
        ).filter(DocumentConceptAnnotation.llm_model.isnot(None)).all()
        
        comparison = {
            'guideline_id': guideline_id,
            'basic': {
                'count': len(basic_annotations),
                'annotations': [
                    {
                        'text': ann.text_segment,
                        'concept': ann.concept_label,
                        'confidence': ann.confidence
                    }
                    for ann in basic_annotations
                ]
            },
            'enhanced': {
                'count': len(enhanced_annotations),
                'annotations': [
                    {
                        'text': ann.text_segment,
                        'concept': ann.concept_label,
                        'confidence': ann.confidence,
                        'llm_reasoning': ann.llm_reasoning
                    }
                    for ann in enhanced_annotations
                ]
            },
            'improvement_factor': (len(enhanced_annotations) / len(basic_annotations)) 
                                if len(basic_annotations) > 0 else 0
        }
        
        return jsonify(comparison)
        
    except Exception as e:
        logger.exception(f"Error comparing annotation methods: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/status', methods=['GET'])
@login_required
def get_llm_status():
    """
    Check if LLM annotation service is available and configured.
    """
    try:
        service = LLMEnhancedAnnotationService()
        
        # Check if LLM service is available
        llm_available = hasattr(service, 'llm_service') and service.llm_service is not None
        
        # Check if ontology service is available
        ontology_available = hasattr(service, 'ontserve_service') and service.ontserve_service is not None
        
        status = {
            'available': llm_available and ontology_available,
            'llm_service': llm_available,
            'ontology_service': ontology_available,
            'features': {
                'term_extraction': True,
                'semantic_matching': True,
                'gap_analysis': True,
                'confidence_scoring': True
            }
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error checking LLM annotation status: {e}")
        return jsonify({
            'available': False,
            'error': str(e)
        })
