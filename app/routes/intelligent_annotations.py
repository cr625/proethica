"""
API Routes for Intelligent Annotation System

Provides endpoints for the enhanced guideline annotation system
using LLM orchestration and multi-agent reasoning.
"""

from flask import Blueprint, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
import asyncio
import logging
from typing import Dict, Any

from app.models.guideline import Guideline
from app.models import Document
from app.models.world import World
from app.services.guideline_annotation_orchestrator import GuidelineAnnotationOrchestrator
from app.services.intelligent_annotation_service import IntelligentAnnotationService

logger = logging.getLogger(__name__)

# Create blueprint
intelligent_annotations_bp = Blueprint(
    'intelligent_annotations', 
    __name__, 
    url_prefix='/api/annotations/intelligent'
)

# Initialize services
orchestrator = GuidelineAnnotationOrchestrator()
intelligent_service = IntelligentAnnotationService()


@intelligent_annotations_bp.route('/guideline/<int:guideline_id>/annotate', methods=['POST'])
@login_required
def annotate_guideline_intelligent(guideline_id):
    """
    Trigger intelligent annotation process for a guideline.
    
    Uses multi-agent orchestration and semantic analysis for enhanced annotations.
    """
    try:
        # Get guideline - check both Guideline and Document tables
        guideline = Guideline.query.filter_by(id=guideline_id).first()
        if not guideline:
            # Check Document table for guidelines stored there
            guideline = Document.query.filter_by(id=guideline_id, document_type='guideline').first()
        if not guideline:
            return jsonify({
                'success': False,
                'error': f'Guideline {guideline_id} not found'
            }), 404
        
        # Check permissions
        if not guideline.world.can_edit(current_user):
            return jsonify({
                'success': False,
                'error': 'Permission denied'
            }), 403
        
        # Get request parameters
        data = request.get_json() or {}
        force_refresh = data.get('force_refresh', False)
        domain = data.get('domain', 'engineering-ethics')
        
        # Run annotation pipeline asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                orchestrator.annotate_guideline(
                    guideline_id=guideline_id,
                    force_refresh=force_refresh,
                    domain=domain
                )
            )
        finally:
            loop.close()
        
        # Check for errors
        if result.errors:
            return jsonify({
                'success': False,
                'errors': result.errors,
                'result': {
                    'annotations_created': result.annotations_created,
                    'sections_analyzed': result.sections_analyzed,
                    'processing_time_ms': result.processing_time_ms
                }
            }), 500
        
        # Return success response
        return jsonify({
            'success': True,
            'result': {
                'guideline_id': guideline_id,
                'total_sections': result.total_sections,
                'sections_analyzed': result.sections_analyzed,
                'annotations_created': result.annotations_created,
                'conflicts_resolved': result.conflicts_resolved,
                'processing_time_ms': result.processing_time_ms,
                'stage_timings': result.stage_timings
            },
            'message': f'Created {result.annotations_created} intelligent annotations'
        })
        
    except Exception as e:
        logger.exception(f"Error in intelligent annotation for guideline {guideline_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@intelligent_annotations_bp.route('/section/<int:section_id>/analyze', methods=['POST'])
@login_required
def analyze_section(section_id):
    """
    Perform semantic analysis on a specific guideline section.
    
    Returns detailed component identification and ontology matches.
    """
    try:
        from app.models.guideline_section import GuidelineSection
        
        # Get section
        section = GuidelineSection.query.get_or_404(section_id)
        
        # Check permissions via guideline
        guideline = Guideline.query.get(section.guideline_id)
        if not guideline or not guideline.world.can_view(current_user):
            return jsonify({
                'success': False,
                'error': 'Permission denied'
            }), 403
        
        # Get request parameters
        data = request.get_json() or {}
        domain = data.get('domain', 'engineering-ethics')
        include_concepts = data.get('include_concepts', True)
        
        # Perform analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Use ProEthica orchestrator for analysis
            query = f"Analyze section {section.section_code}: {section.section_text}"
            
            response = loop.run_until_complete(
                orchestrator.proethica_orchestrator.process_query(
                    query=query,
                    domain=domain,
                    use_cache=True
                )
            )
            
            # Extract results
            analysis = response.ontology_context.query_analysis
            
            result = {
                'section_code': section.section_code,
                'section_text': section.section_text[:200] + '...' if len(section.section_text) > 200 else section.section_text,
                'identified_components': [
                    {
                        'type': comp.type.value,
                        'text': comp.text,
                        'confidence': comp.confidence
                    }
                    for comp in analysis.identified_components
                ],
                'domain': analysis.domain,
                'query_type': analysis.query_type,
                'confidence': analysis.confidence
            }
            
            # Include ontology concepts if requested
            if include_concepts:
                result['ontology_concepts'] = {}
                for category, entities in response.ontology_context.retrieved_entities.items():
                    result['ontology_concepts'][category] = [
                        {
                            'uri': e.get('uri'),
                            'label': e.get('label'),
                            'description': e.get('description', '')[:100]
                        }
                        for e in entities[:5]  # Limit to top 5 per category
                    ]
            
        finally:
            loop.close()
        
        return jsonify({
            'success': True,
            'analysis': result
        })
        
    except Exception as e:
        logger.exception(f"Error analyzing section {section_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@intelligent_annotations_bp.route('/validate/batch', methods=['POST'])
@login_required
def validate_annotations_batch():
    """
    Validate multiple annotations in batch using ontology consistency checking.
    """
    try:
        data = request.get_json()
        annotation_ids = data.get('annotation_ids', [])
        validation_type = data.get('validation_type', 'consistency')  # 'consistency', 'conflict', 'relevance'
        
        if not annotation_ids:
            return jsonify({
                'success': False,
                'error': 'No annotation IDs provided'
            }), 400
        
        from app.models.document_concept_annotation import DocumentConceptAnnotation
        
        # Get annotations
        annotations = DocumentConceptAnnotation.query.filter(
            DocumentConceptAnnotation.id.in_(annotation_ids)
        ).all()
        
        # Check permissions
        for annotation in annotations:
            document = annotation.get_document()
            if not document or not document.world.can_edit(current_user):
                return jsonify({
                    'success': False,
                    'error': f'Permission denied for annotation {annotation.id}'
                }), 403
        
        # Perform validation
        validation_results = []
        
        for annotation in annotations:
            result = {
                'annotation_id': annotation.id,
                'concept_label': annotation.concept_label,
                'validation_type': validation_type,
                'valid': True,
                'issues': []
            }
            
            # Consistency check
            if validation_type == 'consistency':
                # Check if concept URI is valid
                if not annotation.concept_uri or annotation.concept_uri == '':
                    result['valid'] = False
                    result['issues'].append('Missing concept URI')
                
                # Check confidence threshold
                if annotation.confidence < 0.7:
                    result['valid'] = False
                    result['issues'].append(f'Low confidence: {annotation.confidence:.2f}')
            
            # Conflict check
            elif validation_type == 'conflict':
                # Check for overlapping annotations
                overlapping = DocumentConceptAnnotation.query.filter(
                    DocumentConceptAnnotation.document_type == annotation.document_type,
                    DocumentConceptAnnotation.document_id == annotation.document_id,
                    DocumentConceptAnnotation.id != annotation.id,
                    DocumentConceptAnnotation.start_offset < annotation.end_offset,
                    DocumentConceptAnnotation.end_offset > annotation.start_offset
                ).all()
                
                if overlapping:
                    result['valid'] = False
                    result['issues'].append(f'Overlaps with {len(overlapping)} other annotations')
            
            # Relevance check
            elif validation_type == 'relevance':
                # Check domain relevance
                if 'engineering' not in annotation.ontology_name.lower() and \
                   'proethica' not in annotation.ontology_name.lower():
                    result['valid'] = False
                    result['issues'].append('Low domain relevance')
            
            validation_results.append(result)
        
        # Summary statistics
        valid_count = sum(1 for r in validation_results if r['valid'])
        
        return jsonify({
            'success': True,
            'validation_results': validation_results,
            'summary': {
                'total_validated': len(validation_results),
                'valid_count': valid_count,
                'invalid_count': len(validation_results) - valid_count,
                'validation_type': validation_type
            }
        })
        
    except Exception as e:
        logger.exception(f"Error in batch validation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@intelligent_annotations_bp.route('/stats/<int:guideline_id>', methods=['GET'])
@login_required
def get_annotation_statistics(guideline_id):
    """
    Get detailed statistics for intelligent annotations on a guideline.
    """
    try:
        # Get guideline - check both Guideline and Document tables
        guideline = Guideline.query.filter_by(id=guideline_id).first()
        if not guideline:
            guideline = Document.query.filter_by(id=guideline_id, document_type='guideline').first()
        if not guideline:
            return jsonify({
                'success': False,
                'error': f'Guideline {guideline_id} not found'
            }), 404
        
        # Check permissions
        if not guideline.world.can_view(current_user):
            return jsonify({
                'success': False,
                'error': 'Permission denied'
            }), 403
        
        from app.models.document_concept_annotation import DocumentConceptAnnotation
        from app.models.guideline_section import GuidelineSection
        
        # Get annotations
        annotations = DocumentConceptAnnotation.get_annotations_for_document(
            'guideline', guideline_id
        )
        
        # Get sections
        sections = GuidelineSection.query.filter_by(
            guideline_id=guideline_id
        ).all()
        
        # Calculate statistics
        stats = {
            'total_annotations': len(annotations),
            'total_sections': len(sections),
            'sections_with_annotations': 0,
            'annotations_by_type': {},
            'annotations_by_confidence': {
                'high': 0,    # >= 0.8
                'medium': 0,  # 0.6 - 0.8
                'low': 0      # < 0.6
            },
            'annotations_by_agent': {},
            'annotations_by_section': {},
            'average_confidence': 0.0
        }
        
        if annotations:
            # Calculate average confidence
            total_confidence = sum(a.confidence for a in annotations)
            stats['average_confidence'] = total_confidence / len(annotations)
            
            # Count by type
            for ann in annotations:
                concept_type = ann.concept_type or 'Unknown'
                stats['annotations_by_type'][concept_type] = \
                    stats['annotations_by_type'].get(concept_type, 0) + 1
                
                # Count by confidence level
                if ann.confidence >= 0.8:
                    stats['annotations_by_confidence']['high'] += 1
                elif ann.confidence >= 0.6:
                    stats['annotations_by_confidence']['medium'] += 1
                else:
                    stats['annotations_by_confidence']['low'] += 1
                
                # Count by agent (if available in metadata)
                if hasattr(ann, 'metadata') and ann.metadata:
                    agent = ann.metadata.get('agent_source', 'unknown')
                    stats['annotations_by_agent'][agent] = \
                        stats['annotations_by_agent'].get(agent, 0) + 1
        
        # Count annotations by section
        for section in sections:
            section_annotations = [
                a for a in annotations
                if hasattr(a, 'metadata') and a.metadata and 
                a.metadata.get('section_code') == section.section_code
            ]
            
            if section_annotations:
                stats['sections_with_annotations'] += 1
                stats['annotations_by_section'][section.section_code] = len(section_annotations)
        
        return jsonify({
            'success': True,
            'guideline_id': guideline_id,
            'statistics': stats
        })
        
    except Exception as e:
        logger.exception(f"Error getting annotation statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@intelligent_annotations_bp.route('/config', methods=['GET', 'POST'])
@login_required
def manage_configuration():
    """
    Get or update intelligent annotation configuration.
    """
    try:
        if request.method == 'GET':
            # Return current configuration
            config = {
                'min_confidence_threshold': orchestrator.min_confidence_threshold,
                'max_annotations_per_section': orchestrator.max_annotations_per_section,
                'enable_conflict_resolution': orchestrator.enable_conflict_resolution,
                'enable_validation': orchestrator.enable_validation,
                'semantic_threshold': intelligent_service.semantic_threshold,
                'context_window_size': intelligent_service.context_window_size,
                'cache_statistics': {
                    'orchestrator': orchestrator.get_statistics(),
                    'intelligent_service': {
                        'concept_embeddings_cached': len(intelligent_service._concept_embeddings),
                        'concept_contexts_cached': len(intelligent_service._concept_contexts)
                    }
                }
            }
            
            return jsonify({
                'success': True,
                'configuration': config
            })
        
        elif request.method == 'POST':
            # Update configuration
            if not current_user.is_admin:
                return jsonify({
                    'success': False,
                    'error': 'Admin privileges required'
                }), 403
            
            data = request.get_json()
            
            # Update orchestrator settings
            if 'min_confidence_threshold' in data:
                orchestrator.min_confidence_threshold = float(data['min_confidence_threshold'])
            if 'max_annotations_per_section' in data:
                orchestrator.max_annotations_per_section = int(data['max_annotations_per_section'])
            if 'enable_conflict_resolution' in data:
                orchestrator.enable_conflict_resolution = bool(data['enable_conflict_resolution'])
            if 'enable_validation' in data:
                orchestrator.enable_validation = bool(data['enable_validation'])
            
            # Update intelligent service settings
            if 'semantic_threshold' in data:
                intelligent_service.semantic_threshold = float(data['semantic_threshold'])
            if 'context_window_size' in data:
                intelligent_service.context_window_size = int(data['context_window_size'])
            
            # Clear caches if requested
            if data.get('clear_cache', False):
                orchestrator.clear_cache()
                intelligent_service.clear_cache()
            
            return jsonify({
                'success': True,
                'message': 'Configuration updated successfully'
            })
            
    except Exception as e:
        logger.exception(f"Error managing configuration: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@intelligent_annotations_bp.route('/test', methods=['GET'])
@login_required
def test_intelligent_annotation():
    """
    Test endpoint to verify the intelligent annotation system is working.
    """
    try:
        return jsonify({
            'success': True,
            'message': 'Intelligent annotation system is operational',
            'services': {
                'orchestrator': 'initialized',
                'intelligent_service': 'initialized',
                'statistics': orchestrator.get_statistics()
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Intelligent annotation system test failed'
        }), 500
