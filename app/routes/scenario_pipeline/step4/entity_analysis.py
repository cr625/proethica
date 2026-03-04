"""
Step 4 Entity Analysis Routes

Entity-grounded argument pipeline (E1-F3) and related endpoints.
Routes: get_entity_grounded_arguments, get_composed_decision_points,
get_principle_alignment, get_obligation_coverage_api.
"""

import logging
import uuid
from datetime import datetime

from flask import jsonify

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.environment_auth import auth_optional

from app.routes.scenario_pipeline.step4.config import STEP4_SECTION_TYPE

logger = logging.getLogger(__name__)


def register_entity_analysis_routes(bp):
    """Register entity analysis routes on the given blueprint."""

    @bp.route('/case/<int:case_id>/entity_arguments')
    def get_entity_grounded_arguments(case_id):
        """
        Get entity-grounded Toulmin-structured arguments for a case.

        Runs the full E1-F3 pipeline:
        - E1: Obligation coverage analysis
        - E2: Action-option mapping with Jones intensity
        - E3: Decision point composition
        - F1: Principle-provision alignment
        - F2: Argument generation (Toulmin structure)
        - F3: Argument validation (3-tier)

        Returns JSON with arguments, decision points, and validation results.
        """
        try:
            from app.services.entity_analysis import (
                compose_decision_points,
                get_principle_provision_alignment,
                ArgumentGenerator,
                ArgumentValidator
            )
            from app.services.entity_analysis.argument_generator import load_canonical_decision_points
            from app.domains import get_domain_config
            from app.models import TemporaryRDFStorage, ExtractionPrompt

            logger.info(f"Running E1-F3 pipeline for case {case_id}")

            # Run pipeline
            domain_config = get_domain_config('engineering')

            # Use canonical decision points if available, otherwise compose fresh
            decision_points = load_canonical_decision_points(case_id)
            if decision_points is None:
                logger.info(f"No canonical decision points found, composing from entities")
                decision_points = compose_decision_points(case_id)
            else:
                logger.info(f"Using {len(decision_points.decision_points)} canonical decision points")

            alignment_map = get_principle_provision_alignment(case_id)

            # Use class methods to pass decision_points and alignment_map
            generator = ArgumentGenerator(domain_config)
            arguments = generator.generate_arguments(case_id, decision_points, alignment_map)

            validator = ArgumentValidator(domain_config)
            validation = validator.validate_arguments(case_id, arguments)

            # Build response
            response_data = {
                'success': True,
                'case_id': case_id,
                'pipeline_summary': {
                    'decision_points_count': len(decision_points.decision_points),
                    'alignment_rate': alignment_map.alignment_rate,
                    'total_arguments': len(arguments.arguments),
                    'pro_arguments': arguments.pro_argument_count,
                    'con_arguments': arguments.con_argument_count,
                    'valid_arguments': validation.valid_arguments,
                    'invalid_arguments': validation.invalid_arguments,
                    'average_score': validation.average_score
                },
                'decision_points': [
                    {
                        'focus_id': dp.focus_id,
                        'description': dp.description,
                        'decision_question': dp.decision_question,
                        'role_label': dp.grounding.role_label,
                        'obligation_label': dp.grounding.obligation_label,
                        'constraint_label': dp.grounding.constraint_label,
                        'intensity_score': dp.intensity_score,
                        'options': [
                            {
                                'option_id': opt.option_id,
                                'action_label': opt.action_label,
                                'description': opt.description,
                                'is_extracted': opt.is_extracted_action
                            }
                            for opt in dp.options
                        ],
                        'board_conclusion': dp.board_conclusion_text
                    }
                    for dp in decision_points.decision_points
                ],
                'arguments': [arg.to_dict() for arg in arguments.arguments],
                'validations': [v.to_dict() for v in validation.validations],
                'validation_summary': {
                    'entity_test_pass_rate': validation.entity_test_pass_rate,
                    'founding_test_pass_rate': validation.founding_test_pass_rate,
                    'virtue_test_pass_rate': validation.virtue_test_pass_rate
                }
            }

            # Arguments are computed on-the-fly for display only (not persisted).
            # The E1-F3 pipeline is algorithmic (no LLM) so recomputing is cheap.
            logger.info(
                f"E1-F3 pipeline complete for case {case_id}: "
                f"{len(arguments.arguments)} arguments, {validation.valid_arguments} valid"
            )

            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error running E1-F3 pipeline for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e),
                'arguments': [],
                'decision_points': []
            }), 500

    @bp.route('/case/<int:case_id>/entity_arguments/decision_points')
    def get_composed_decision_points(case_id):
        """
        Get algorithmically composed decision points (E1-E3 pipeline).

        Alternative to LLM extraction - composes from extracted entities.
        Useful for entity grounding analysis.
        """
        try:
            from app.services.entity_analysis import compose_decision_points
            from app.models import TemporaryRDFStorage, ExtractionPrompt
            import uuid
            from datetime import datetime

            decision_points = compose_decision_points(case_id)

            # Persist the composed decision points
            session_id = str(uuid.uuid4())

            # Clear any previous E1-E3 composed decision points for this case
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='decision_point_composed'
            ).delete()

            # Save each decision point to temporary storage
            for dp in decision_points.decision_points:
                rdf_entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='decision_point_composed',
                    storage_type='individual',
                    entity_type='DecisionPoint',
                    entity_label=dp.focus_id,
                    entity_definition=dp.description,
                    entity_uri=f"case-{case_id}#{dp.focus_id}",
                    rdf_json_ld={
                        '@type': 'proethica-int:DecisionPoint',
                        'focus_id': dp.focus_id,
                        'focus_number': dp.focus_number,
                        'description': dp.description,
                        'decision_question': dp.decision_question,
                        'intensity_score': dp.intensity_score,
                        'grounding': dp.grounding.to_dict(),
                        'options': [opt.to_dict() for opt in dp.options],
                        'provision_uris': dp.provision_uris,
                        'provision_labels': dp.provision_labels,
                        'board_conclusion_text': dp.board_conclusion_text
                    },
                    is_selected=True
                )
                db.session.add(rdf_entity)

            # Record the composition run (no LLM prompt, but track metadata)
            composition_record = ExtractionPrompt(
                case_id=case_id,
                concept_type='decision_point_composed',
                step_number=4,
                section_type=STEP4_SECTION_TYPE,
                extraction_session_id=session_id,
                prompt_text='E1-E3 algorithmic composition (no LLM)',
                llm_model='algorithmic',
                raw_response=f'Composed {len(decision_points.decision_points)} decision points',
                created_at=datetime.utcnow()
            )
            db.session.add(composition_record)
            db.session.commit()

            logger.info(f"Persisted {len(decision_points.decision_points)} composed decision points for case {case_id}")

            return jsonify({
                'success': True,
                'case_id': case_id,
                'count': len(decision_points.decision_points),
                'unmatched_obligations': decision_points.unmatched_obligations,
                'unmatched_actions': decision_points.unmatched_actions,
                'decision_points': [
                    {
                        'focus_id': dp.focus_id,
                        'description': dp.description,
                        'decision_question': dp.decision_question,
                        'intensity_score': dp.intensity_score,
                        'grounding': {
                            'role_uri': dp.grounding.role_uri,
                            'role_label': dp.grounding.role_label,
                            'obligation_uri': dp.grounding.obligation_uri,
                            'obligation_label': dp.grounding.obligation_label,
                            'constraint_uri': dp.grounding.constraint_uri,
                            'constraint_label': dp.grounding.constraint_label
                        },
                        'options': [
                            {
                                'option_id': opt.option_id,
                                'action_uri': opt.action_uri,
                                'action_label': opt.action_label,
                                'description': opt.description,
                                'is_extracted': opt.is_extracted_action,
                                'downstream_event_uris': opt.downstream_event_uris
                            }
                            for opt in dp.options
                        ],
                        'provision_uris': dp.provision_uris,
                        'provision_labels': dp.provision_labels,
                        'board_conclusion': dp.board_conclusion_text
                    }
                    for dp in decision_points.decision_points
                ]
            })

        except Exception as e:
            logger.error(f"Error getting composed decision points for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e),
                'decision_points': []
            }), 500

    @bp.route('/case/<int:case_id>/entity_arguments/alignment')
    def get_principle_alignment(case_id):
        """
        Get principle-provision alignment map (F1 only).

        Returns alignment between principles and code provisions.
        """
        try:
            from app.services.entity_analysis import get_principle_provision_alignment

            alignment_map = get_principle_provision_alignment(case_id)

            return jsonify({
                'success': True,
                'case_id': case_id,
                'total_principles': alignment_map.total_principles,
                'total_provisions': alignment_map.total_provisions,
                'alignment_rate': alignment_map.alignment_rate,
                'unaligned_principles': alignment_map.unaligned_principles,
                'unaligned_provisions': alignment_map.unaligned_provisions,
                'alignments': [a.to_dict() for a in alignment_map.alignments]
            })

        except Exception as e:
            logger.error(f"Error getting principle alignment for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e),
                'alignments': []
            }), 500

    @bp.route('/case/<int:case_id>/entity_arguments/coverage')
    def get_obligation_coverage_api(case_id):
        """
        Get obligation/constraint coverage analysis (E1 only).

        Returns coverage matrix, conflicts, and role-obligation bindings.
        """
        try:
            from app.services.entity_analysis import get_obligation_coverage as e1_coverage

            coverage = e1_coverage(case_id)

            return jsonify({
                'success': True,
                'case_id': case_id,
                'obligations': [
                    {
                        'uri': o.entity_uri,
                        'label': o.entity_label,
                        'definition': o.entity_definition,
                        'role_uri': o.bound_role_uri,
                        'role_label': o.bound_role,
                        'decision_type': o.decision_type,
                        'provisions': o.related_provisions,
                        'is_decision_relevant': o.decision_relevant,
                        'is_instantiated': o.is_instantiated
                    }
                    for o in coverage.obligations
                ],
                'constraints': [
                    {
                        'uri': c.entity_uri,
                        'label': c.entity_label,
                        'definition': c.entity_definition,
                        'role_uri': c.constrained_role_uri,
                        'role_label': c.constrained_role,
                        'founding_value_limit': c.founding_value_limit,
                        'is_instantiated': c.is_instantiated
                    }
                    for c in coverage.constraints
                ],
                'conflict_pairs': coverage.conflict_pairs,
                'role_obligation_map': coverage.role_obligation_map,
                'decision_relevant_count': coverage.decision_relevant_count
            })

        except Exception as e:
            logger.error(f"Error getting obligation coverage for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
