"""
Step 4 Decision Legacy Routes

Legacy decision point extraction and argument generation (Parts E/F).
Routes: get_decision_points, extract_decision_points, get_arguments,
generate_arguments, get_llm_decision_points.
"""

import logging

from flask import jsonify

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.environment_auth import auth_required_for_llm

from app.routes.scenario_pipeline.step4.config import STEP4_SECTION_TYPE

logger = logging.getLogger(__name__)


def register_decision_legacy_routes(bp):
    """Register legacy decision point and argument routes on the given blueprint."""

    @bp.route('/case/<int:case_id>/decision_points')
    def get_decision_points(case_id):
        """
        API endpoint returning decision points for a case.

        Returns JSON with extracted decision points including:
        - Decision points with options
        - Involved roles and provisions
        - Board resolution and reasoning
        """
        try:
            from app.services.decision_focus_extractor import DecisionFocusExtractor

            extractor = DecisionFocusExtractor()
            points = extractor.load_from_database(case_id)

            # Convert to JSON-serializable format
            points_data = []
            for point in points:
                points_data.append({
                    'point_id': point.focus_id,
                    'point_number': point.focus_number,
                    'description': point.description,
                    'decision_question': point.decision_question,
                    'involved_roles': point.involved_roles,
                    'applicable_provisions': point.applicable_provisions,
                    'options': [
                        {
                            'option_id': opt.option_id,
                            'description': opt.description,
                            'is_board_choice': opt.is_board_choice
                        }
                        for opt in point.options
                    ],
                    'board_resolution': point.board_resolution,
                    'board_reasoning': point.board_reasoning,
                    'confidence': point.confidence
                })

            return jsonify({
                'success': True,
                'case_id': case_id,
                'decision_points': points_data,
                'count': len(points_data)
            })

        except Exception as e:
            logger.error(f"Error getting decision points for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e),
                'decision_points': []
            }), 500

    @bp.route('/case/<int:case_id>/extract_decision_points', methods=['POST'])
    @auth_required_for_llm
    def extract_decision_points(case_id):
        """
        Extract decision points from a case using LLM.

        Part E of Step 4 synthesis - identifies key decision points
        where ethical choices must be made.
        """
        try:
            from app.services.decision_focus_extractor import DecisionFocusExtractor

            case = Document.query.get_or_404(case_id)

            logger.info(f"Extracting decision points for case {case_id}")

            extractor = DecisionFocusExtractor()
            points = extractor.extract_decision_focuses(case_id)

            if points:
                # Save to database
                extractor.save_to_database(case_id, points)

                logger.info(f"Extracted and saved {len(points)} decision points for case {case_id}")

                # Return the decision points
                points_data = []
                for point in points:
                    points_data.append({
                        'point_id': point.focus_id,
                        'point_number': point.focus_number,
                        'description': point.description,
                        'decision_question': point.decision_question,
                        'involved_roles': point.involved_roles,
                        'applicable_provisions': point.applicable_provisions,
                        'options': [
                            {
                                'option_id': opt.option_id,
                                'description': opt.description,
                                'is_board_choice': opt.is_board_choice
                            }
                            for opt in point.options
                        ],
                        'board_resolution': point.board_resolution,
                        'board_reasoning': point.board_reasoning,
                        'confidence': point.confidence
                    })

                return jsonify({
                    'success': True,
                    'message': f'Extracted {len(points)} decision points',
                    'decision_points': points_data,
                    'count': len(points)
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'No decision points extracted',
                    'decision_points': []
                }), 400

        except Exception as e:
            logger.error(f"Error extracting decision points for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/arguments', methods=['GET'])
    def get_arguments(case_id):
        """
        Load existing arguments for a case.

        Part F of Step 4 synthesis - pros/cons for decision options.
        """
        try:
            from app.services.argument_generator import ArgumentGenerator

            generator = ArgumentGenerator()
            arguments = generator.load_from_database(case_id)

            if arguments:
                args_data = []
                for dp_args in arguments:
                    args_data.append({
                        'decision_point_id': dp_args.decision_point_id,
                        'decision_description': dp_args.decision_description,
                        'option_id': dp_args.option_id,
                        'option_description': dp_args.option_description,
                        'pro_arguments': [
                            {
                                'argument_id': arg.argument_id,
                                'claim': arg.claim,
                                'provision_citations': arg.provision_citations,
                                'precedent_references': arg.precedent_references,
                                'strength': arg.strength
                            }
                            for arg in dp_args.pro_arguments
                        ],
                        'con_arguments': [
                            {
                                'argument_id': arg.argument_id,
                                'claim': arg.claim,
                                'provision_citations': arg.provision_citations,
                                'precedent_references': arg.precedent_references,
                                'strength': arg.strength
                            }
                            for arg in dp_args.con_arguments
                        ],
                        'evaluation_summary': dp_args.evaluation_summary
                    })

                return jsonify({
                    'success': True,
                    'arguments': args_data,
                    'count': len(args_data)
                })
            else:
                return jsonify({
                    'success': True,
                    'arguments': [],
                    'count': 0,
                    'message': 'No arguments found. Run "Generate Arguments" first.'
                })

        except Exception as e:
            logger.error(f"Error loading arguments for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/generate_arguments', methods=['POST'])
    @auth_required_for_llm
    def generate_arguments(case_id):
        """
        Generate pro/con arguments for decision points.

        Part F of Step 4 synthesis - creates balanced arguments for each
        decision option, citing code provisions and precedent cases.
        """
        try:
            from app.services.argument_generator import ArgumentGenerator

            case = Document.query.get_or_404(case_id)

            logger.info(f"Generating arguments for case {case_id}")

            generator = ArgumentGenerator()
            arguments = generator.generate_arguments(case_id)

            if arguments:
                # Save to database
                generator.save_to_database(case_id, arguments)

                # Count total arguments
                total_pro = sum(len(a.pro_arguments) for a in arguments)
                total_con = sum(len(a.con_arguments) for a in arguments)

                logger.info(f"Generated {total_pro} pro and {total_con} con arguments for case {case_id}")

                # Return the arguments
                args_data = []
                for dp_args in arguments:
                    args_data.append({
                        'decision_point_id': dp_args.decision_point_id,
                        'decision_description': dp_args.decision_description,
                        'option_id': dp_args.option_id,
                        'option_description': dp_args.option_description,
                        'pro_arguments': [
                            {
                                'argument_id': arg.argument_id,
                                'claim': arg.claim,
                                'provision_citations': arg.provision_citations,
                                'precedent_references': arg.precedent_references,
                                'strength': arg.strength
                            }
                            for arg in dp_args.pro_arguments
                        ],
                        'con_arguments': [
                            {
                                'argument_id': arg.argument_id,
                                'claim': arg.claim,
                                'provision_citations': arg.provision_citations,
                                'precedent_references': arg.precedent_references,
                                'strength': arg.strength
                            }
                            for arg in dp_args.con_arguments
                        ],
                        'evaluation_summary': dp_args.evaluation_summary
                    })

                return jsonify({
                    'success': True,
                    'message': f'Generated {total_pro} pro and {total_con} con arguments',
                    'arguments': args_data,
                    'pro_count': total_pro,
                    'con_count': total_con
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'No arguments generated. Ensure decision points are extracted first.',
                    'arguments': []
                }), 400

        except Exception as e:
            logger.error(f"Error generating arguments for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/llm_decision_points')
    def get_llm_decision_points(case_id):
        """
        Get LLM-extracted decision points from Step 4 Synthesis.

        These are the quality decision points extracted by LLM, not algorithmic composition.
        """
        try:
            from app.models import TemporaryRDFStorage, ExtractionPrompt

            # Load decision points extracted by LLM
            decision_point_entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='decision_point'
            ).all()

            # Load options for these decision points
            option_entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='decision_option'
            ).all()

            # Get the extraction prompt for provenance
            extraction_prompt = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type='decision_point',
                section_type=STEP4_SECTION_TYPE
            ).order_by(ExtractionPrompt.created_at.desc()).first()

            # Build response
            decision_points = []
            for dp in decision_point_entities:
                json_ld = dp.rdf_json_ld or {}

                # Find options for this decision point
                dp_options = []
                dp_label = dp.entity_label
                for opt in option_entities:
                    opt_json = opt.rdf_json_ld or {}
                    opt_for = opt_json.get('optionFor', '') or opt.entity_definition or ''
                    # Match options to decision points by text similarity
                    if dp_label.lower() in opt_for.lower() or any(
                        word in opt_for.lower() for word in dp_label.lower().split()[:5]
                    ):
                        dp_options.append({
                            'option_id': f"O{len(dp_options)+1}",
                            'label': opt.entity_label,
                            'description': opt.entity_definition,
                            'is_extracted': True,
                            'json_ld': opt_json
                        })

                decision_points.append({
                    'id': dp.id,
                    'focus_id': f"DP{len(decision_points)+1}",
                    'label': dp.entity_label,
                    'description': dp.entity_definition,
                    'decision_question': dp.entity_label,  # The label IS the question
                    'options': dp_options,
                    'json_ld': json_ld,
                    'is_selected': dp.is_selected
                })

            return jsonify({
                'success': True,
                'case_id': case_id,
                'source': 'llm_extraction',
                'count': len(decision_points),
                'decision_points': decision_points,
                'extraction_info': {
                    'model': extraction_prompt.llm_model if extraction_prompt else None,
                    'created_at': extraction_prompt.created_at.isoformat() if extraction_prompt else None,
                    'prompt_preview': (extraction_prompt.prompt_text[:200] + '...') if extraction_prompt and extraction_prompt.prompt_text else None
                }
            })

        except Exception as e:
            logger.error(f"Error loading LLM decision points for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e),
                'decision_points': []
            }), 500
