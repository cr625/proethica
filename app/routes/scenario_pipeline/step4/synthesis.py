"""
Step 4 Synthesis Routes

Unified synthesis pipeline, narrative construction, scenario generation,
and related endpoints.
Routes: synthesize_streaming, synthesize_case, synthesize_complete,
get_synthesis_model, get_canonical_decision_points, get_entity_foundation,
generate_scenario_route, extract_decision_synthesis_individual,
extract_narrative_individual.
"""

import logging
from datetime import datetime

from flask import request, jsonify

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.environment_auth import auth_required_for_llm

from app.routes.scenario_pipeline.step4.streaming import synthesize_case_streaming
from app.routes.scenario_pipeline.generate_scenario import generate_scenario_from_case

logger = logging.getLogger(__name__)


def register_synthesis_routes(bp):
    """Register synthesis routes on the given blueprint."""

    @bp.route('/case/<int:case_id>/synthesize_streaming')
    def synthesize_streaming(case_id):
        """
        Execute whole-case synthesis with Server-Sent Events streaming.

        Real-time progress updates showing:
        - Part A: Code Provisions extraction
        - Part B: Questions & Conclusions extraction
        - Part C: Cross-section synthesis
        - LLM prompts and responses for each stage
        """
        return synthesize_case_streaming(case_id)

    @bp.route('/case/<int:case_id>/synthesize', methods=['POST'])
    @auth_required_for_llm
    def synthesize_case(case_id):
        """
        Execute unified case synthesis pipeline.

        Replaces fragmented Part E (LLM) / Part F (algorithmic) approaches
        with single coherent pipeline producing canonical decision points.

        Pipeline:
        1. Load ALL extracted entities (Passes 1-3 + Parts A-D)
        2. Run E1-E3 algorithmic composition for candidates
        3. Use LLM to refine with Q&C as ground truth
        4. Produce canonical decision points
        5. Generate arguments using F1-F3 (optional)

        Reference: docs-internal/UNIFIED_CASE_ANALYSIS_PIPELINE.md
        """
        try:
            from app.services.case_synthesizer import CaseSynthesizer

            case = Document.query.get_or_404(case_id)

            # Check if arguments should be generated
            generate_args = request.args.get('generate_arguments', 'true').lower() == 'true'

            logger.info(f"Starting unified synthesis for case {case_id} (generate_arguments={generate_args})")

            synthesizer = CaseSynthesizer()
            result = synthesizer.synthesize(case_id, generate_arguments=generate_args)

            logger.info(
                f"Synthesis complete: {len(result.canonical_decision_points)} canonical points, "
                f"{result.qc_aligned_count} Q&C aligned"
            )

            return jsonify({
                'success': True,
                'case_id': case_id,
                'message': f'Synthesized {len(result.canonical_decision_points)} canonical decision points',
                'canonical_decision_points': [dp.to_dict() for dp in result.canonical_decision_points],
                'count': len(result.canonical_decision_points),
                'algorithmic_candidates_count': result.algorithmic_candidates_count,
                'qc_aligned_count': result.qc_aligned_count,
                'has_arguments': result.arguments is not None,
                'extraction_session_id': result.extraction_session_id
            })

        except Exception as e:
            logger.error(f"Error in unified synthesis for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/synthesize_complete', methods=['POST'])
    @auth_required_for_llm
    def synthesize_complete(case_id):
        """
        Execute complete four-phase synthesis.

        Phases:
        1. Entity Foundation - gather all entities from Passes 1-3
        2. Analytical Extraction - load provisions, Q&C, transformation type
        3. Decision Point Synthesis - E1-E3 composition + LLM refinement
        4. Narrative Construction - build timeline and scenario seeds

        Returns complete CaseSynthesisModel.
        """
        try:
            from app.services.case_synthesizer import CaseSynthesizer

            case = Document.query.get_or_404(case_id)

            # Check if LLM synthesis should be skipped (for testing)
            skip_llm = request.args.get('skip_llm', 'false').lower() == 'true'

            logger.info(f"Starting complete synthesis for case {case_id} (skip_llm={skip_llm})")

            synthesizer = CaseSynthesizer()
            model = synthesizer.synthesize_complete(case_id, skip_llm_synthesis=skip_llm)

            logger.info(f"Complete synthesis done: {model.summary()}")

            return jsonify({
                'success': True,
                'case_id': case_id,
                'case_title': model.case_title,
                'synthesis': model.to_dict(),
                'summary': model.summary()
            })

        except Exception as e:
            logger.error(f"Error in complete synthesis for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/synthesis_model')
    def get_synthesis_model(case_id):
        """
        Load existing synthesis model from database.

        Returns the stored synthesis results without re-running.
        Includes rich analysis if previously generated.
        """
        try:
            from app.services.case_synthesizer import (
                CaseSynthesizer, CaseSynthesisModel, EntityFoundation,
                CaseNarrative, TimelineEvent, ScenarioSeeds, TransformationAnalysis
            )

            # Get case
            case = Document.query.get_or_404(case_id)

            synthesizer = CaseSynthesizer()

            # Build model from stored data
            foundation = synthesizer._build_entity_foundation(case_id)
            provisions = synthesizer._load_provisions(case_id)
            questions, conclusions = synthesizer._load_qc(case_id)
            transformation = synthesizer._get_transformation_type(case_id)
            canonical_points = synthesizer.load_canonical_points(case_id)

            # Load rich analysis from database
            causal_links, question_emergence, resolution_patterns = synthesizer._load_rich_analysis(case_id)

            # Reconstruct narrative if we have canonical points
            narrative = None
            if canonical_points:
                narrative = synthesizer._construct_narrative(case_id, foundation, canonical_points, conclusions)

            model = CaseSynthesisModel(
                case_id=case_id,
                case_title=case.title,
                entity_foundation=foundation,
                provisions=provisions,
                questions=questions,
                conclusions=conclusions,
                transformation=TransformationAnalysis(
                    transformation_type=transformation,
                    confidence=0.8,
                    reasoning="",
                    pattern_description="",
                    evidence=[]
                ) if transformation else None,
                # Rich analysis from database
                causal_normative_links=causal_links,
                question_emergence=question_emergence,
                resolution_patterns=resolution_patterns,
                # Decision points
                canonical_decision_points=canonical_points,
                algorithmic_candidates_count=len(canonical_points),  # Approximation
                narrative=narrative
            )

            # Check if we have any rich analysis
            has_rich_analysis = len(causal_links) > 0 or len(question_emergence) > 0 or len(resolution_patterns) > 0

            return jsonify({
                'success': True,
                'case_id': case_id,
                'case_title': model.case_title,
                'synthesis': model.to_dict(),
                'summary': model.summary(),
                'has_synthesis': len(canonical_points) > 0,
                'has_rich_analysis': has_rich_analysis
            })

        except Exception as e:
            logger.error(f"Error loading synthesis model for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/canonical_decision_points')
    def get_canonical_decision_points(case_id):
        """
        Load canonical decision points from the unified pipeline.

        Returns decision points that were produced by the synthesize endpoint,
        which combines algorithmic composition with LLM refinement.
        """
        try:
            from app.services.case_synthesizer import CaseSynthesizer

            synthesizer = CaseSynthesizer()
            canonical_points = synthesizer.load_canonical_points(case_id)

            if canonical_points:
                return jsonify({
                    'success': True,
                    'case_id': case_id,
                    'canonical_decision_points': [dp.to_dict() for dp in canonical_points],
                    'count': len(canonical_points),
                    'qc_aligned_count': sum(1 for dp in canonical_points if dp.aligned_question_uri),
                    'source': 'unified_synthesis'
                })
            else:
                return jsonify({
                    'success': True,
                    'case_id': case_id,
                    'canonical_decision_points': [],
                    'count': 0,
                    'message': 'No canonical decision points found. Run "Synthesize" first.'
                })

        except Exception as e:
            logger.error(f"Error loading canonical decision points for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'canonical_decision_points': []
            }), 500

    @bp.route('/case/<int:case_id>/entity_foundation')
    def get_entity_foundation(case_id):
        """
        Get entity foundation (Phase 1) without running full synthesis.

        Returns all entities from Passes 1-3 organized for display.
        """
        try:
            from app.services.case_synthesizer import CaseSynthesizer

            synthesizer = CaseSynthesizer()
            foundation = synthesizer._build_entity_foundation(case_id)

            return jsonify({
                'success': True,
                'case_id': case_id,
                'entity_foundation': foundation.to_dict()
            })

        except Exception as e:
            logger.error(f"Error getting entity foundation for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # Scenario Generation Route
    @bp.route("/case/<int:case_id>/generate_scenario")
    def generate_scenario_route(case_id):
        """
        SSE endpoint for scenario generation.

        Streams progress through all 9 stages of scenario generation.
        """
        return generate_scenario_from_case(case_id)

    @bp.route('/case/<int:case_id>/extract_decision_synthesis', methods=['POST'])
    @auth_required_for_llm
    def extract_decision_synthesis_individual(case_id):
        """
        Run decision point synthesis (E1-E3 + LLM refinement).
        Returns algorithmic results + LLM prompt/response.
        """
        try:
            from app.services.case_synthesizer import CaseSynthesizer

            case = Document.query.get_or_404(case_id)
            synthesizer = CaseSynthesizer()

            # Build foundation
            foundation = synthesizer._build_entity_foundation(case_id)

            # Load Q&C for ground truth
            questions, conclusions = synthesizer._load_qc(case_id)

            # Run algorithmic composition (E1-E3)
            e1_result = synthesizer._run_e1_coverage(case_id)
            e2_result = synthesizer._run_e2_mapping(case_id)
            candidates = synthesizer._run_e3_composition(e1_result, e2_result, case_id)

            # LLM refinement with Q&C as ground truth
            canonical_points, llm_trace = synthesizer._llm_synthesize_decision_points(
                candidates, questions, conclusions, foundation, case_id
            )

            # Store canonical points
            synthesizer._store_canonical_points(canonical_points, case_id)

            return jsonify({
                'success': True,
                'result': {
                    'e1_decision_relevant': e1_result.get('decision_relevant_count', 0),
                    'e2_action_sets': e2_result.get('action_set_count', 0),
                    'e3_candidates': len(candidates),
                    'canonical_count': len(canonical_points),
                    'qc_aligned': sum(1 for dp in canonical_points if dp.get('qc_aligned', False))
                },
                'llm_trace': {
                    'stage': llm_trace.stage if llm_trace else 'decision_synthesis',
                    'prompt': llm_trace.prompt if llm_trace else '',
                    'response': llm_trace.response if llm_trace else '',
                    'model': llm_trace.model if llm_trace else 'unknown'
                } if llm_trace else None,
                'metadata': {
                    'timestamp': datetime.utcnow().isoformat()
                }
            })

        except Exception as e:
            logger.error(f"Error in decision synthesis for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/extract_narrative', methods=['POST'])
    @auth_required_for_llm
    def extract_narrative_individual(case_id):
        """
        Run narrative construction (timeline, summary, scenario seeds).
        Returns LLM prompt/response.
        """
        try:
            from app.services.case_synthesizer import CaseSynthesizer

            case = Document.query.get_or_404(case_id)
            synthesizer = CaseSynthesizer()

            # Build foundation
            foundation = synthesizer._build_entity_foundation(case_id)

            # Load canonical points
            canonical_points = synthesizer.load_canonical_points(case_id)

            # Load conclusions
            _, conclusions = synthesizer._load_qc(case_id)

            # Construct narrative with LLM
            narrative, llm_trace = synthesizer._construct_narrative_with_llm(
                case_id, foundation, canonical_points, conclusions
            )

            return jsonify({
                'success': True,
                'result': {
                    'has_summary': bool(narrative.case_summary),
                    'timeline_events': len(narrative.timeline),
                    'has_scenario_seeds': bool(narrative.scenario_seeds)
                },
                'narrative': {
                    'case_summary': narrative.case_summary,
                    'timeline': [
                        {
                            'sequence': e.sequence,
                            'phase_label': e.phase_label,
                            'description': e.description[:100] + '...' if len(e.description) > 100 else e.description,
                            'event_type': e.event_type
                        }
                        for e in narrative.timeline
                    ],
                    'scenario_seeds': narrative.scenario_seeds.to_dict() if narrative.scenario_seeds else None
                },
                'llm_trace': {
                    'stage': llm_trace.stage if llm_trace else 'narrative',
                    'prompt': llm_trace.prompt if llm_trace else '',
                    'response': llm_trace.response if llm_trace else '',
                    'model': llm_trace.model if llm_trace else 'unknown'
                } if llm_trace else None,
                'metadata': {
                    'timestamp': datetime.utcnow().isoformat()
                }
            })

        except Exception as e:
            logger.error(f"Error in narrative construction for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
