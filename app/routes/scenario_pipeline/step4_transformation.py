"""
Step 4 Transformation Classification Component

Handles transformation classification endpoints for Step 4 case analysis.
Transformation types based on Marchais-Roubelat & Roubelat (2015):
- Transfer: Resolution transfers obligation to another party
- Stalemate: Competing obligations remain in tension
- Oscillation: Duties shift back and forth between parties
- Phase Lag: Delayed consequences reveal obligations
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Callable

from flask import Blueprint, request, jsonify, Response, stream_with_context

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.llm_utils import get_llm_client
from app.utils.environment_auth import auth_required_for_llm

logger = logging.getLogger(__name__)


def register_transformation_routes(bp: Blueprint, get_all_case_entities: Callable):
    """
    Register transformation-related routes on the provided blueprint.

    Args:
        bp: The Flask blueprint to register routes on
        get_all_case_entities: Helper function to load entities for a case
    """

    @bp.route('/case/<int:case_id>/extract_transformation', methods=['POST'])
    @auth_required_for_llm
    def extract_transformation_individual(case_id):
        """
        Extract transformation classification individually.
        Returns prompt and response for UI display.
        """
        try:
            from app.services.case_analysis.transformation_classifier import TransformationClassifier
            from app.services.case_synthesizer import CaseSynthesizer

            case = Document.query.get_or_404(case_id)

            # Get conclusions for transformation analysis
            conclusions_objs = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='ethical_conclusion'
            ).all()

            if not conclusions_objs:
                return jsonify({
                    'success': False,
                    'error': 'No conclusions found. Extract conclusions first.'
                }), 400

            # Get synthesis model data if available
            synthesizer = CaseSynthesizer()

            # Load Q&C
            questions, conclusions = synthesizer._load_qc(case_id)

            # Create classifier and classify
            classifier = TransformationClassifier(get_llm_client())
            result = classifier.classify(
                case_id=case_id,
                questions=questions,
                conclusions=conclusions,
                case_title=case.title
            )

            # Build status messages for UI display
            status_messages = [
                f"Analyzed {len(questions)} questions and {len(conclusions)} conclusions",
                f"Classification: {result.transformation_type} ({result.confidence * 100:.0f}% confidence)",
                f"Pattern: {result.pattern_description[:100]}..." if len(result.pattern_description) > 100 else f"Pattern: {result.pattern_description}"
            ]

            return jsonify({
                'success': True,
                'prompt': classifier.last_prompt or 'Transformation classification',
                'raw_llm_response': classifier.last_response or '',
                'status_messages': status_messages,
                'result': {
                    'type': result.transformation_type,
                    'confidence': result.confidence,
                    'pattern': result.pattern_description,
                    'reasoning': result.reasoning
                },
                'metadata': {
                    'model': 'claude-opus-4-20250514',
                    'timestamp': datetime.utcnow().isoformat()
                }
            })

        except Exception as e:
            logger.error(f"Error extracting transformation for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/extract_transformation_stream', methods=['POST'])
    @auth_required_for_llm
    def extract_transformation_streaming(case_id):
        """
        Extract transformation classification with SSE streaming for real-time progress.
        Uses academic framework from Marchais-Roubelat & Roubelat (2015).
        """
        import json as json_module

        def sse_msg(data):
            return f"data: {json_module.dumps(data)}\n\n"

        def generate():
            try:
                from app.services.case_analysis.transformation_classifier import TransformationClassifier
                from app.services.case_synthesizer import CaseSynthesizer

                case = Document.query.get_or_404(case_id)

                yield sse_msg({'stage': 'START', 'progress': 5, 'messages': ['Starting transformation analysis...']})

                # Load questions and conclusions
                yield sse_msg({'stage': 'LOADING_QC', 'progress': 10, 'messages': ['Loading questions and conclusions...']})

                synthesizer = CaseSynthesizer()
                questions, conclusions = synthesizer._load_qc(case_id)

                if not conclusions:
                    yield sse_msg({'stage': 'ERROR', 'progress': 100, 'messages': ['No conclusions found. Extract conclusions first.'], 'error': True})
                    return

                yield sse_msg({
                    'stage': 'QC_LOADED',
                    'progress': 15,
                    'messages': [f'Loaded {len(questions)} questions, {len(conclusions)} conclusions']
                })

                # Load case facts
                yield sse_msg({'stage': 'LOADING_FACTS', 'progress': 20, 'messages': ['Loading case facts...']})
                case_facts = ""
                if case.doc_metadata and 'sections_dual' in case.doc_metadata:
                    facts_data = case.doc_metadata['sections_dual'].get('facts', {})
                    if isinstance(facts_data, dict):
                        case_facts = facts_data.get('text', '')
                    else:
                        case_facts = str(facts_data) if facts_data else ''

                facts_preview = case_facts[:100] + '...' if len(case_facts) > 100 else case_facts
                yield sse_msg({
                    'stage': 'FACTS_LOADED',
                    'progress': 25,
                    'messages': [f'Facts loaded: {len(case_facts)} chars' + (f' - "{facts_preview}"' if facts_preview else '')]
                })

                # Load entities from Passes 1-3
                yield sse_msg({'stage': 'LOADING_ENTITIES', 'progress': 28, 'messages': ['Loading extracted entities...']})
                all_entities = get_all_case_entities(case_id)
                entity_count = sum(len(v) for v in all_entities.values() if isinstance(v, list))
                yield sse_msg({
                    'stage': 'ENTITIES_LOADED',
                    'progress': 32,
                    'messages': [f'Loaded {entity_count} entities (roles, obligations, actions, etc.)']
                })

                # Load academic framework context
                yield sse_msg({'stage': 'LOADING_FRAMEWORK', 'progress': 35, 'messages': ['Loading Marchais-Roubelat transformation framework...']})

                try:
                    from app.academic_references.frameworks.transformation_classification import (
                        get_prompt_context, CITATION_SHORT
                    )
                    framework_context = get_prompt_context(include_examples=True, include_mapping=False)
                    yield sse_msg({
                        'stage': 'FRAMEWORK_LOADED',
                        'progress': 40,
                        'messages': [f'Framework loaded: {CITATION_SHORT}']
                    })
                except ImportError:
                    framework_context = None
                    yield sse_msg({
                        'stage': 'FRAMEWORK_SKIP',
                        'progress': 40,
                        'messages': ['Academic framework not available, using built-in definitions']
                    })

                # Create classifier and run classification
                yield sse_msg({'stage': 'CLASSIFYING', 'progress': 45, 'messages': ['Analyzing transformation pattern with LLM...']})

                classifier = TransformationClassifier(get_llm_client())
                result = classifier.classify(
                    case_id=case_id,
                    questions=questions,
                    conclusions=conclusions,
                    case_title=case.title,
                    case_facts=case_facts,
                    all_entities=all_entities
                )

                yield sse_msg({
                    'stage': 'CLASSIFIED',
                    'progress': 70,
                    'messages': [
                        f'Primary type: {result.transformation_type}',
                        f'Confidence: {result.confidence * 100:.0f}%'
                    ]
                })

                # Check for alternative classifications
                if result.alternative_classifications:
                    alt_msgs = [f'Alternative: {alt["type"]} ({alt.get("confidence", 0) * 100:.0f}%)' for alt in result.alternative_classifications[:2]]
                    yield sse_msg({
                        'stage': 'ALTERNATIVES',
                        'progress': 75,
                        'messages': alt_msgs
                    })

                # Store result
                yield sse_msg({'stage': 'STORING', 'progress': 85, 'messages': ['Storing classification result...']})

                # Generate session ID for this extraction
                session_id = str(uuid.uuid4())

                # Save prompt/response to extraction_prompts for UI display
                # NOTE: concept_type must match the mapping in get_saved_step4_prompt()
                try:
                    saved_prompt = ExtractionPrompt.save_prompt(
                        case_id=case_id,
                        concept_type='transformation_classification',  # Must match lookup in get_saved_step4_prompt
                        prompt_text=classifier.last_prompt or '',
                        raw_response=classifier.last_response or '',
                        step_number=4,
                        section_type='synthesis',
                        llm_model='claude-sonnet-4-20250514',
                        extraction_session_id=session_id
                    )
                    logger.info(f"Saved transformation extraction prompt id={saved_prompt.id}")
                except Exception as prompt_err:
                    logger.warning(f"Could not save transformation prompt: {prompt_err}")

                # Save to temporary_rdf_storage for pipeline state tracking
                try:
                    # Clear any existing transformation results
                    TemporaryRDFStorage.query.filter_by(
                        case_id=case_id,
                        extraction_type='transformation_result',
                        is_published=False
                    ).delete(synchronize_session='fetch')

                    # Create new transformation result entity
                    rdf_entity = TemporaryRDFStorage(
                        case_id=case_id,
                        extraction_session_id=session_id,
                        extraction_type='transformation_result',
                        storage_type='individual',
                        entity_label=f"Transformation: {result.transformation_type}",
                        entity_uri=f"proethica:transformation_{case_id}_{result.transformation_type}",
                        entity_type='TransformationClassification',
                        entity_definition=result.pattern_description,
                        rdf_json_ld={
                            'transformation_type': result.transformation_type,
                            'confidence': result.confidence,
                            'reasoning': result.reasoning,
                            'pattern_description': result.pattern_description,
                            'supporting_evidence': result.supporting_evidence,
                            'involved_roles': result.involved_roles,
                            'obligation_shifts': result.obligation_shifts,
                            'alternative_classifications': result.alternative_classifications
                        },
                        is_selected=True,
                        is_reviewed=False,
                        is_published=False
                    )
                    db.session.add(rdf_entity)
                    db.session.commit()
                    logger.info(f"Saved transformation result to temporary_rdf_storage")
                except Exception as rdf_err:
                    logger.warning(f"Could not save transformation to RDF storage: {rdf_err}")
                    db.session.rollback()

                # Also save to case_precedent_features for precedent discovery
                try:
                    classifier.save_to_features(case_id, result)
                    yield sse_msg({'stage': 'STORED', 'progress': 90, 'messages': ['Classification stored successfully']})
                except Exception as store_err:
                    logger.warning(f"Could not store transformation features: {store_err}")
                    yield sse_msg({'stage': 'STORE_SKIP', 'progress': 90, 'messages': ['Classification complete (storage skipped)']})

                # Build status messages
                status_messages = [
                    f"Input: {len(questions)} questions, {len(conclusions)} conclusions",
                    f"Classification: {result.transformation_type} ({result.confidence * 100:.0f}% confidence)",
                    f"Pattern: {result.pattern_description}"
                ]

                if result.supporting_evidence:
                    status_messages.append(f"Evidence: {len(result.supporting_evidence)} supporting indicators")

                yield sse_msg({
                    'stage': 'COMPLETE',
                    'progress': 100,
                    'messages': [f'Transformation analysis complete: {result.transformation_type}'],
                    'status_messages': status_messages,
                    'prompt': classifier.last_prompt or 'Transformation classification',
                    'raw_llm_response': classifier.last_response or '',
                    'result': {
                        'type': result.transformation_type,
                        'confidence': result.confidence,
                        'pattern': result.pattern_description,
                        'reasoning': result.reasoning,
                        'evidence': result.supporting_evidence,
                        'alternatives': result.alternative_classifications
                    },
                    'input_context': {
                        'questions': len(questions),
                        'conclusions': len(conclusions)
                    }
                })

            except Exception as e:
                logger.error(f"Streaming transformation error: {e}")
                import traceback
                traceback.print_exc()
                yield sse_msg({'stage': 'ERROR', 'progress': 100, 'messages': [f'Error: {str(e)}'], 'error': True})

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    # Return the functions so they can be used for CSRF exemption
    return {
        'extract_transformation_individual': extract_transformation_individual,
        'extract_transformation_streaming': extract_transformation_streaming
    }
