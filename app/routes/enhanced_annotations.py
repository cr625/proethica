"""
Enhanced Annotations API Routes

Provides API endpoints for the enhanced guideline annotation system
with multi-agent orchestration and ontology integration.
"""

from flask import Blueprint, request, jsonify, current_app
import asyncio
import logging
from typing import Dict, Any

from app.services.enhanced_guideline_annotator import EnhancedGuidelineAnnotator
from app.models.document_concept_annotation import DocumentConceptAnnotation

logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint('enhanced_annotations', __name__, url_prefix='/api/annotations/enhanced')


def get_event_loop():
    """Get or create an event loop for async operations."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


@bp.route('/guideline/<int:guideline_id>/annotate', methods=['POST'])
def annotate_guideline_enhanced(guideline_id):
    """
    Enhanced annotation endpoint with full pipeline.
    
    Args:
        guideline_id: ID of the guideline to annotate
        
    Request body (optional):
        {
            "config": {
                "domain": "engineering-ethics",
                "min_confidence": 0.6,
                "max_annotations_per_section": 5,
                "enable_conflict_resolution": true,
                "use_cache": true,
                "force_refresh": false
            }
        }
    
    Returns:
        JSON response with annotation results
    """
    try:
        # Get configuration from request
        data = request.get_json() or {}
        config = data.get('config', {})
        force_refresh = config.pop('force_refresh', False)
        
        # Create annotator with configuration
        annotator = EnhancedGuidelineAnnotator(config)
        
        # Run async annotation
        loop = get_event_loop()
        result = loop.run_until_complete(
            annotator.annotate_guideline(guideline_id, force_refresh)
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.exception(f"Error in enhanced annotation for guideline {guideline_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/batch', methods=['POST'])
def batch_annotate_guidelines():
    """
    Batch annotation for multiple guidelines.
    
    Request body:
        {
            "guideline_ids": [45, 46, 47],
            "config": {
                "domain": "engineering-ethics",
                "min_confidence": 0.6
            }
        }
    
    Returns:
        JSON response with batch results
    """
    try:
        data = request.get_json()
        if not data or 'guideline_ids' not in data:
            return jsonify({
                'success': False,
                'error': 'guideline_ids required'
            }), 400
        
        guideline_ids = data['guideline_ids']
        config = data.get('config', {})
        
        # Create annotator
        annotator = EnhancedGuidelineAnnotator(config)
        
        # Process batch
        results = []
        loop = get_event_loop()
        
        for guideline_id in guideline_ids:
            try:
                result = loop.run_until_complete(
                    annotator.annotate_guideline(guideline_id)
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing guideline {guideline_id}: {e}")
                results.append({
                    'guideline_id': guideline_id,
                    'success': False,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'batch_size': len(guideline_ids),
            'results': results
        })
        
    except Exception as e:
        logger.exception(f"Error in batch annotation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/config/<domain>', methods=['GET'])
def get_annotation_config(domain):
    """
    Get annotation configuration for a domain.
    
    Args:
        domain: Professional domain (e.g., 'engineering-ethics')
    
    Returns:
        JSON configuration for the domain
    """
    try:
        # Domain-specific configurations
        configs = {
            'engineering-ethics': {
                'domain': 'engineering-ethics',
                'pipeline': {
                    'preprocessing': {
                        'section_extraction': True,
                        'context_window_size': 3,
                        'semantic_features': ['entities', 'keywords', 'sentiment', 'structure']
                    },
                    'multi_agent': {
                        'agents': ['principle', 'obligation', 'precedent'],
                        'consensus_method': 'weighted_voting',
                        'confidence_threshold': 0.7
                    },
                    'ontology_matching': {
                        'similarity_threshold': 0.75,
                        'use_hierarchy': True,
                        'max_candidates': 10
                    },
                    'annotation': {
                        'max_per_section': 5,
                        'min_confidence': 0.6,
                        'enable_conflict_resolution': True
                    }
                },
                'caching': {
                    'ttl_seconds': 3600,
                    'max_entries': 1000
                }
            },
            'medical-ethics': {
                'domain': 'medical-ethics',
                'pipeline': {
                    'preprocessing': {
                        'section_extraction': True,
                        'context_window_size': 3,
                        'semantic_features': ['entities', 'keywords', 'sentiment']
                    },
                    'multi_agent': {
                        'agents': ['principle', 'obligation'],
                        'consensus_method': 'weighted_voting',
                        'confidence_threshold': 0.8
                    },
                    'ontology_matching': {
                        'similarity_threshold': 0.8,
                        'use_hierarchy': True,
                        'max_candidates': 8
                    },
                    'annotation': {
                        'max_per_section': 4,
                        'min_confidence': 0.7,
                        'enable_conflict_resolution': True
                    }
                },
                'caching': {
                    'ttl_seconds': 3600,
                    'max_entries': 1000
                }
            },
            'legal-ethics': {
                'domain': 'legal-ethics',
                'pipeline': {
                    'preprocessing': {
                        'section_extraction': True,
                        'context_window_size': 4,
                        'semantic_features': ['entities', 'keywords', 'structure']
                    },
                    'multi_agent': {
                        'agents': ['principle', 'obligation', 'precedent'],
                        'consensus_method': 'weighted_voting',
                        'confidence_threshold': 0.75
                    },
                    'ontology_matching': {
                        'similarity_threshold': 0.7,
                        'use_hierarchy': True,
                        'max_candidates': 12
                    },
                    'annotation': {
                        'max_per_section': 6,
                        'min_confidence': 0.65,
                        'enable_conflict_resolution': True
                    }
                },
                'caching': {
                    'ttl_seconds': 3600,
                    'max_entries': 1000
                }
            }
        }
        
        config = configs.get(domain)
        if not config:
            return jsonify({
                'success': False,
                'error': f'Configuration not found for domain: {domain}'
            }), 404
        
        return jsonify({
            'success': True,
            'domain': domain,
            'config': config
        })
        
    except Exception as e:
        logger.exception(f"Error getting config for domain {domain}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/guideline/<int:guideline_id>/status', methods=['GET'])
def get_annotation_status(guideline_id):
    """
    Get annotation status for a guideline.
    
    Args:
        guideline_id: ID of the guideline
    
    Returns:
        JSON response with annotation status and statistics
    """
    try:
        # Get current annotations
        annotations = DocumentConceptAnnotation.get_annotations_for_document(
            'guideline', guideline_id
        )
        
        if not annotations:
            return jsonify({
                'success': True,
                'guideline_id': guideline_id,
                'status': 'not_annotated',
                'annotation_count': 0
            })
        
        # Calculate statistics
        concept_types = {}
        confidence_sum = 0
        
        for ann in annotations:
            # Count by type
            concept_type = ann.concept_type
            if concept_type not in concept_types:
                concept_types[concept_type] = 0
            concept_types[concept_type] += 1
            
            # Sum confidence
            confidence_sum += ann.confidence
        
        avg_confidence = confidence_sum / len(annotations) if annotations else 0
        
        # Get latest annotation time
        latest_annotation = max(annotations, key=lambda a: a.created_at)
        
        return jsonify({
            'success': True,
            'guideline_id': guideline_id,
            'status': 'annotated',
            'annotation_count': len(annotations),
            'concept_types': concept_types,
            'average_confidence': avg_confidence,
            'latest_annotation': latest_annotation.created_at.isoformat(),
            'llm_model': latest_annotation.llm_model
        })
        
    except Exception as e:
        logger.exception(f"Error getting annotation status for guideline {guideline_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/guideline/<int:guideline_id>/clear', methods=['DELETE'])
def clear_guideline_annotations(guideline_id):
    """
    Clear all annotations for a guideline.
    
    Args:
        guideline_id: ID of the guideline
    
    Returns:
        JSON response confirming deletion
    """
    try:
        # Get existing annotations
        annotations = DocumentConceptAnnotation.get_annotations_for_document(
            'guideline', guideline_id
        )
        
        if not annotations:
            return jsonify({
                'success': True,
                'message': 'No annotations to clear',
                'deleted_count': 0
            })
        
        # Delete annotations
        from app.models import db
        deleted_count = 0
        
        for ann in annotations:
            db.session.delete(ann)
            deleted_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Cleared {deleted_count} annotations',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        logger.exception(f"Error clearing annotations for guideline {guideline_id}: {e}")
        from app.models import db
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/stats', methods=['GET'])
def get_annotation_statistics():
    """
    Get overall annotation statistics.
    
    Returns:
        JSON response with system-wide statistics
    """
    try:
        from sqlalchemy import func
        from app.models import db
        
        # Get total annotations
        total_annotations = db.session.query(
            func.count(DocumentConceptAnnotation.id)
        ).filter_by(document_type='guideline', is_current=True).scalar()
        
        # Get annotated guidelines count
        annotated_guidelines = db.session.query(
            func.count(func.distinct(DocumentConceptAnnotation.document_id))
        ).filter_by(document_type='guideline', is_current=True).scalar()
        
        # Get concept type distribution
        concept_distribution = db.session.query(
            DocumentConceptAnnotation.concept_type,
            func.count(DocumentConceptAnnotation.id)
        ).filter_by(
            document_type='guideline',
            is_current=True
        ).group_by(DocumentConceptAnnotation.concept_type).all()
        
        # Get average confidence
        avg_confidence = db.session.query(
            func.avg(DocumentConceptAnnotation.confidence)
        ).filter_by(document_type='guideline', is_current=True).scalar()
        
        # Get model usage
        model_usage = db.session.query(
            DocumentConceptAnnotation.llm_model,
            func.count(DocumentConceptAnnotation.id)
        ).filter_by(
            document_type='guideline',
            is_current=True
        ).group_by(DocumentConceptAnnotation.llm_model).all()
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_annotations': total_annotations or 0,
                'annotated_guidelines': annotated_guidelines or 0,
                'concept_distribution': {
                    concept_type: count 
                    for concept_type, count in concept_distribution
                },
                'average_confidence': float(avg_confidence) if avg_confidence else 0.0,
                'model_usage': {
                    model: count 
                    for model, count in model_usage
                }
            }
        })
        
    except Exception as e:
        logger.exception(f"Error getting annotation statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/test', methods=['GET'])
def test_enhanced_annotations():
    """
    Test endpoint to verify the enhanced annotations API is working.
    
    Returns:
        JSON response confirming the API is operational
    """
    return jsonify({
        'success': True,
        'message': 'Enhanced Annotations API is operational',
        'version': '1.0.0',
        'endpoints': [
            '/api/annotations/enhanced/guideline/<id>/annotate',
            '/api/annotations/enhanced/batch',
            '/api/annotations/enhanced/config/<domain>',
            '/api/annotations/enhanced/guideline/<id>/status',
            '/api/annotations/enhanced/guideline/<id>/clear',
            '/api/annotations/enhanced/stats',
            '/api/annotations/enhanced/test'
        ]
    })
