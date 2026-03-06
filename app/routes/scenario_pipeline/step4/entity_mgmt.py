"""
Step 4 Entity Management Routes

Entity review/edit CRUD, commit, pipeline_state, prompts, annotations.
"""

import logging
from datetime import datetime

from flask import request, jsonify

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.environment_auth import auth_required_for_llm, auth_required_for_write

from app.routes.scenario_pipeline.step4.config import (
    STEP4_SECTION_TYPE, reset_step4_case_features,
)

logger = logging.getLogger(__name__)


def register_entity_mgmt_routes(bp):
    """Register entity management routes on the blueprint."""

    @bp.route('/case/<int:case_id>/clear_step4', methods=['POST'])
    @auth_required_for_write
    def clear_step4_data(case_id):
        """Clear all Step 4 extractions (Phase 2-4) while preserving Steps 1-3 entities."""
        try:
            extraction_types_to_clear = [
                'code_provision_reference',
                'precedent_case_reference',
                'ethical_question',
                'ethical_conclusion',
                'argument_generated',
                'argument_validation',
                'question_emergence',
                'resolution_pattern',
                'causal_normative_link',
                'rich_analysis_causal',
                'rich_analysis_qe',
                'rich_analysis_rp',
                'canonical_decision_point',
                'decision_point',
                'decision_option',
                'transformation_analysis',
                'case_summary',
                'timeline_event',
                'narrative_element',
                'scenario_seed',
            ]

            deleted_counts = {}
            total_deleted = 0

            for extraction_type in extraction_types_to_clear:
                count = TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type=extraction_type
                ).delete(synchronize_session=False)
                if count > 0:
                    deleted_counts[extraction_type] = count
                    total_deleted += count

            prompts_deleted = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                step_number=4
            ).delete(synchronize_session=False)

            reset_step4_case_features(case_id)

            # Clear Step 4 provenance data
            from app.models.provenance import ProvenanceActivity, ProvenanceEntity, ProvenanceUsage, ProvenanceDerivation

            step4_activities = ProvenanceActivity.query.filter(
                ProvenanceActivity.case_id == case_id,
                ProvenanceActivity.activity_name.like('step4%')
            ).all()

            activity_ids = [a.id for a in step4_activities]
            provenance_deleted = 0

            if activity_ids:
                step4_entity_ids = [
                    e.id for e in ProvenanceEntity.query.filter(
                        ProvenanceEntity.generating_activity_id.in_(activity_ids)
                    ).all()
                ]

                ProvenanceUsage.query.filter(
                    ProvenanceUsage.activity_id.in_(activity_ids)
                ).delete(synchronize_session=False)

                if step4_entity_ids:
                    ProvenanceDerivation.query.filter(
                        db.or_(
                            ProvenanceDerivation.derived_entity_id.in_(step4_entity_ids),
                            ProvenanceDerivation.source_entity_id.in_(step4_entity_ids)
                        )
                    ).delete(synchronize_session=False)

                    entities_deleted = ProvenanceEntity.query.filter(
                        ProvenanceEntity.id.in_(step4_entity_ids)
                    ).delete(synchronize_session=False)
                    provenance_deleted += entities_deleted

                activities_deleted = ProvenanceActivity.query.filter(
                    ProvenanceActivity.id.in_(activity_ids)
                ).delete(synchronize_session=False)
                provenance_deleted += activities_deleted

            db.session.commit()

            logger.info(f"Cleared Step 4 data for case {case_id}: {total_deleted} entities, {prompts_deleted} prompts, {provenance_deleted} provenance records")

            return jsonify({
                'success': True,
                'message': f'Cleared {total_deleted} entities, {prompts_deleted} prompts, {provenance_deleted} provenance records',
                'deleted_counts': deleted_counts,
                'prompts_deleted': prompts_deleted,
                'provenance_deleted': provenance_deleted
            })

        except Exception as e:
            logger.error(f"Error clearing Step 4 for case {case_id}: {e}")
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/commit_step4', methods=['POST'])
    @auth_required_for_llm
    def commit_step4_entities(case_id):
        """Commit Step 4 entities to OntServe."""
        try:
            from app.services.auto_commit_service import AutoCommitService

            case = Document.query.get_or_404(case_id)
            logger.info(f"Committing Step 4 entities for case {case_id}")

            auto_commit_service = AutoCommitService()
            result = auto_commit_service.commit_case_entities(case_id, force=False)

            if result:
                return jsonify({
                    'success': True,
                    'message': f'Committed {result.total_entities} entities ({result.linked_count} linked, {result.new_class_count} new)',
                    'total_entities': result.total_entities,
                    'linked_count': result.linked_count,
                    'new_class_count': result.new_class_count,
                    'ttl_file': result.ttl_file
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'No entities to commit or commit failed'
                }), 400

        except Exception as e:
            logger.error(f"Error committing Step 4 entities for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/<int:entity_id>/review', methods=['POST'])
    @auth_required_for_write
    def update_entity_review(case_id, entity_id):
        """Toggle accept/reject status for an entity."""
        entity = TemporaryRDFStorage.query.filter_by(
            id=entity_id, case_id=case_id
        ).first_or_404()

        data = request.get_json(silent=True) or {}
        action = data.get('action', 'accept')

        if action == 'reject':
            entity.is_selected = False
            entity.is_reviewed = True
        else:
            entity.is_selected = True
            entity.is_reviewed = True

        db.session.commit()
        return jsonify({'success': True, 'is_selected': entity.is_selected})

    @bp.route('/case/<int:case_id>/entities/<int:entity_id>/edit', methods=['POST'])
    @auth_required_for_write
    def edit_entity(case_id, entity_id):
        """Update entity label and/or definition."""
        entity = TemporaryRDFStorage.query.filter_by(
            id=entity_id, case_id=case_id
        ).first_or_404()

        if entity.is_published:
            return jsonify({'success': False, 'error': 'Cannot edit committed entities'}), 400

        data = request.get_json(silent=True) or {}
        label = data.get('label', '').strip()
        definition = data.get('definition', '').strip()

        if label:
            entity.entity_label = label
        if definition:
            entity.entity_definition = definition

        entity.is_reviewed = True
        db.session.commit()

        return jsonify({
            'success': True,
            'entity_label': entity.entity_label,
            'entity_definition': entity.entity_definition
        })

    @bp.route('/case/<int:case_id>/step4_prompts')
    def get_step4_prompts(case_id):
        """API endpoint returning Step 4 extraction prompts for provenance display."""
        try:
            prompts_data = {}
            concept_types = [
                'code_provision_reference',
                'ethical_question',
                'ethical_conclusion',
                'transformation_classification',
                'rich_analysis',
                'phase3_decision_synthesis',
                'phase4_narrative',
                'whole_case_synthesis',
                'decision_point',
                'decision_argument'
            ]

            for concept_type in concept_types:
                prompt = ExtractionPrompt.query.filter_by(
                    case_id=case_id,
                    concept_type=concept_type,
                    step_number=4
                ).order_by(ExtractionPrompt.created_at.desc()).first()

                if prompt:
                    prompts_data[concept_type] = {
                        'id': prompt.id,
                        'concept_type': prompt.concept_type,
                        'section_type': prompt.section_type,
                        'prompt_text': prompt.prompt_text,
                        'raw_response': prompt.raw_response,
                        'llm_model': prompt.llm_model,
                        'created_at': prompt.created_at.isoformat() if prompt.created_at else None,
                        'results_summary': prompt.results_summary,
                        'extraction_session_id': prompt.extraction_session_id
                    }

            return jsonify({
                'success': True,
                'case_id': case_id,
                'prompts': prompts_data,
                'available_types': list(prompts_data.keys())
            })

        except Exception as e:
            logger.error(f"Error getting Step 4 prompts for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'prompts': {}
            }), 500

    @bp.route('/case/<int:case_id>/pipeline_state')
    def get_pipeline_state_api(case_id):
        """Get pipeline state for a case."""
        try:
            from app.services.pipeline_state_manager import get_pipeline_state

            state = get_pipeline_state(case_id)
            return jsonify({
                'success': True,
                **state.to_dict()
            })

        except Exception as e:
            logger.error(f"Error getting pipeline state for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/get_saved_step4_prompt')
    def get_saved_step4_prompt(case_id):
        """Get saved prompt/response for a specific step4 task."""
        try:
            task_type = request.args.get('task_type', '')

            if not task_type:
                return jsonify({
                    'success': False,
                    'error': 'task_type parameter required'
                }), 400

            if task_type == 'provisions':
                provisions = TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type='code_provision_reference'
                ).all()

                if provisions:
                    provision_list = [p.entity_label for p in provisions]
                    return jsonify({
                        'success': True,
                        'prompt_text': f'Extracted {len(provisions)} code provisions from case references',
                        'raw_response': '\n'.join(provision_list),
                        'results_summary': f'{len(provisions)} provisions extracted',
                        'model': 'regex-parser',
                        'timestamp': provisions[0].created_at.isoformat() if provisions[0].created_at else None
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'No provisions extracted'
                    })

            concept_type_map = {
                'precedents': 'precedent_case_reference',
                'questions': 'ethical_question',
                'conclusions': 'ethical_conclusion',
                'transformation': 'transformation_classification',
                'rich_analysis': 'rich_analysis',
                'decision_synthesis': 'phase3_decision_synthesis',
                'narrative': 'phase4_narrative'
            }

            concept_type = concept_type_map.get(task_type, task_type)

            prompt_record = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type=concept_type
            ).order_by(ExtractionPrompt.created_at.desc()).first()

            if not prompt_record:
                return jsonify({
                    'success': False,
                    'message': f'No saved prompt for {task_type}'
                })

            return jsonify({
                'success': True,
                'prompt_text': prompt_record.prompt_text,
                'raw_response': prompt_record.raw_response,
                'results_summary': prompt_record.results_summary,
                'model': prompt_record.llm_model,
                'timestamp': prompt_record.created_at.isoformat()
            })

        except Exception as e:
            logger.error(f"Error getting saved step4 prompt for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/save_streaming_results', methods=['POST'])
    @auth_required_for_llm
    def save_streaming_results(case_id):
        """Save Step 4 streaming synthesis results to database."""
        from app.routes.scenario_pipeline.step4.streaming import save_step4_streaming_results
        return save_step4_streaming_results(case_id)

