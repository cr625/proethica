"""
Step 4 Run All - Complete Synthesis with SSE Streaming Progress

Thin route layer that delegates orchestration to step4_orchestration_service.
Provides two endpoints:
  - run_complete_synthesis (POST, blocking JSON) -- legacy
  - run_complete_synthesis_stream (POST, SSE) -- progressive UI updates

Independent phases run in parallel:
  2A||2B -> 2C -> 2D||2E -> Phase 3 -> Phase 4

2C depends on 2A (provisions context) so must run after 2A completes.

Usage: Called by "Run Complete Synthesis" button.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from flask import jsonify, Response, stream_with_context, current_app

from app.utils.environment_auth import auth_required_for_llm
from app.utils.llm_utils import get_llm_client
from app.services.step4_orchestration_service import (
    clear_step4_data,
    run_provisions,
    run_precedents,
    run_qc_unified,
    run_transformation,
    run_rich_analysis,
    run_phase3,
    run_phase4,
)

logger = logging.getLogger(__name__)


def _sse_msg(data):
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _run_in_context(app, func, *args, **kwargs):
    """Run a function inside a Flask app context (for ThreadPoolExecutor)."""
    with app.app_context():
        return func(*args, **kwargs)


def register_run_all_routes(bp):
    """Register the run-all-synthesis route on the blueprint.

    Args:
        bp: The Flask Blueprint to register routes on
    """

    @bp.route('/case/<int:case_id>/run_complete_synthesis', methods=['POST'])
    @auth_required_for_llm
    def run_complete_synthesis(case_id):
        """
        Run complete Step 4 synthesis by calling the same services as UI buttons.

        Non-streaming - runs to completion, returns JSON result.
        """
        try:
            results = {'stages': [], 'success': False}
            llm_client = get_llm_client()

            # =====================================================================
            # STEP 1: Clear existing Step 4 data
            # =====================================================================
            logger.info(f"[RunAll] Clearing Step 4 data for case {case_id}")
            clear_result = clear_step4_data(case_id)
            results['clear'] = clear_result
            results['stages'].append('CLEAR')

            # =====================================================================
            # STEP 2A: Provisions
            # =====================================================================
            logger.info(f"[RunAll] Running provisions extraction for case {case_id}")
            provisions_result = run_provisions(case_id, llm_client)
            results['provisions'] = provisions_result
            results['stages'].append('PROVISIONS')

            if provisions_result.get('error'):
                logger.error(f"[RunAll] Provisions failed: {provisions_result}")
                return jsonify({
                    'success': False,
                    'error': f"Provisions failed: {provisions_result.get('error')}",
                    'results': results
                }), 500

            # =====================================================================
            # STEP 2B: Precedent Cases
            # =====================================================================
            logger.info(f"[RunAll] Running precedent case extraction for case {case_id}")
            precedents_result = run_precedents(case_id, llm_client)
            results['precedents'] = precedents_result
            results['stages'].append('PRECEDENTS')

            # Non-blocking - continue even on error

            # =====================================================================
            # STEP 2C: Q&C Unified
            # =====================================================================
            logger.info(f"[RunAll] Running Q&C extraction for case {case_id}")
            qc_result = run_qc_unified(case_id, llm_client)
            results['qc'] = qc_result
            results['stages'].append('QC')

            if qc_result.get('error'):
                logger.error(f"[RunAll] Q&C failed: {qc_result}")
                return jsonify({
                    'success': False,
                    'error': f"Q&C failed: {qc_result.get('error')}",
                    'results': results
                }), 500

            # =====================================================================
            # STEP 2D: Transformation
            # =====================================================================
            logger.info(f"[RunAll] Running transformation classification for case {case_id}")
            transformation_result = run_transformation(case_id, llm_client)
            results['transformation'] = transformation_result
            results['stages'].append('TRANSFORMATION')

            # Non-blocking - continue even on error

            # =====================================================================
            # STEP 2E: Rich Analysis
            # =====================================================================
            logger.info(f"[RunAll] Running rich analysis for case {case_id}")
            rich_result = run_rich_analysis(case_id)
            results['rich_analysis'] = rich_result
            results['stages'].append('RICH_ANALYSIS')

            # Non-blocking - continue even on error

            # =====================================================================
            # PHASE 3: Decision Synthesis
            # =====================================================================
            logger.info(f"[RunAll] Running Phase 3 decision synthesis for case {case_id}")
            phase3_result = run_phase3(case_id)
            results['phase3'] = phase3_result
            results['stages'].append('PHASE3')

            # Non-blocking - continue even on error

            # =====================================================================
            # PHASE 4: Narrative Construction
            # =====================================================================
            logger.info(f"[RunAll] Running Phase 4 narrative construction for case {case_id}")
            phase4_result = run_phase4(case_id)
            results['phase4'] = phase4_result
            results['stages'].append('PHASE4')

            # Non-blocking - continue even on error

            # =====================================================================
            # COMPLETE
            # =====================================================================
            logger.info(f"[RunAll] Complete synthesis finished for case {case_id}")
            results['success'] = True

            # Collect warnings from all phases
            all_warnings = []
            for phase_key in ['qc', 'rich_analysis', 'phase3', 'phase4']:
                phase_result = results.get(phase_key, {})
                if isinstance(phase_result, dict) and 'warnings' in phase_result:
                    all_warnings.extend(phase_result['warnings'])
            if all_warnings:
                results['warnings'] = all_warnings
                logger.warning(f"[RunAll] Completed with {len(all_warnings)} warnings")

            return jsonify(results)

        except Exception as e:
            logger.error(f"[RunAll] Error in run_complete_synthesis for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/run_complete_synthesis_stream', methods=['POST'])
    @auth_required_for_llm
    def run_complete_synthesis_stream(case_id):
        """Run complete Step 4 synthesis with SSE streaming progress.

        Parallelizes independent phases (2A||2B, then 2C, then 2D||2E) and yields
        progress events so the frontend can update the UI incrementally.
        """
        app = current_app._get_current_object()

        def generate():
            try:
                yield _sse_msg({'stage': 'START', 'progress': 0,
                                'messages': ['Starting complete synthesis...']})

                # -- CLEAR --
                yield _sse_msg({'stage': 'CLEARING', 'progress': 2,
                                'messages': ['Clearing old Step 4 data...'],
                                'clear_ui': True})
                clear_result = clear_step4_data(case_id)
                deleted = clear_result.get('entities_deleted', 0)
                yield _sse_msg({'stage': 'CLEARED', 'progress': 5,
                                'messages': [f'Cleared {deleted} entities, {clear_result.get("prompts_deleted", 0)} prompts']})

                llm_client = get_llm_client()

                # -- 2A + 2B in parallel --
                yield _sse_msg({'stage': 'PHASE2_AB', 'progress': 8,
                                'messages': ['2A+2B: Extracting provisions and precedents...'],
                                'active_dots': ['provisions', 'precedents']})

                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_a = executor.submit(
                        _run_in_context, app, run_provisions,
                        case_id, llm_client)
                    future_b = executor.submit(
                        _run_in_context, app, run_precedents,
                        case_id, llm_client)
                    provisions_result = future_a.result()
                    precedents_result = future_b.result()

                prov_count = provisions_result.get('provisions_count', 0)
                prov_links = provisions_result.get('entity_links', 0)
                yield _sse_msg({'stage': 'PROVISIONS_DONE', 'progress': 20,
                                'messages': [f'2A: {prov_count} provisions, {prov_links} entity links'],
                                'completed_dot': 'provisions',
                                'result': provisions_result})

                prec_count = precedents_result.get('precedents_count', 0)
                yield _sse_msg({'stage': 'PRECEDENTS_DONE', 'progress': 25,
                                'messages': [f'2B: {prec_count} precedent cases'],
                                'completed_dot': 'precedents',
                                'result': precedents_result})

                # Provisions error is blocking for downstream phases
                if provisions_result.get('error'):
                    yield _sse_msg({'stage': 'ERROR', 'progress': 100, 'error': True,
                                    'messages': [f'Provisions failed: {provisions_result["error"]}']})
                    return

                # -- 2C: Q&C (needs provisions context from 2A) --
                yield _sse_msg({'stage': 'PHASE2_C', 'progress': 28,
                                'messages': ['2C: Extracting questions and conclusions...'],
                                'active_dots': ['questions', 'conclusions']})

                qc_result = run_qc_unified(case_id, llm_client)

                q_count = qc_result.get('questions_count', 0)
                c_count = qc_result.get('conclusions_count', 0)
                links = qc_result.get('links_count', 0)
                yield _sse_msg({'stage': 'QC_DONE', 'progress': 40,
                                'messages': [f'2C: {q_count} questions, {c_count} conclusions, {links} Q-C links'],
                                'completed_dots': ['questions', 'conclusions'],
                                'result': qc_result})

                if qc_result.get('error'):
                    yield _sse_msg({'stage': 'ERROR', 'progress': 100, 'error': True,
                                    'messages': [f'Q&C failed: {qc_result["error"]}']})
                    return

                # Report warnings
                qc_warnings = qc_result.get('warnings', [])
                if qc_warnings:
                    yield _sse_msg({'stage': 'QC_WARNINGS', 'progress': 42,
                                    'messages': [f'Warning: {w}' for w in qc_warnings]})

                # -- 2D + 2E in parallel --
                yield _sse_msg({'stage': 'PHASE2_DE', 'progress': 45,
                                'messages': ['2D+2E: Transformation + Rich Analysis...'],
                                'active_dots': ['transformation', 'rich_analysis']})

                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_d = executor.submit(
                        _run_in_context, app, run_transformation,
                        case_id, llm_client)
                    future_e = executor.submit(
                        _run_in_context, app, run_rich_analysis,
                        case_id)
                    transformation_result = future_d.result()
                    rich_result = future_e.result()

                t_type = transformation_result.get('transformation_type', '?')
                yield _sse_msg({'stage': 'TRANSFORMATION_DONE', 'progress': 55,
                                'messages': [f'2D: Transformation type = {t_type}'],
                                'completed_dot': 'transformation',
                                'result': transformation_result})

                cl = rich_result.get('causal_links', 0)
                qe = rich_result.get('question_emergence', 0)
                rp = rich_result.get('resolution_patterns', 0)
                yield _sse_msg({'stage': 'RICH_DONE', 'progress': 60,
                                'messages': [f'2E: {cl} causal links, {qe} question emergence, {rp} resolution patterns'],
                                'completed_dot': 'rich_analysis',
                                'result': rich_result})

                # -- Phase 3 --
                yield _sse_msg({'stage': 'PHASE3_START', 'progress': 63,
                                'messages': ['Phase 3: Decision Point Synthesis (E1-E3 + LLM)...'],
                                'active_phase': 'phase3'})
                phase3_result = run_phase3(case_id)

                canonical = phase3_result.get('canonical_count', 0)
                candidates = phase3_result.get('candidates_count', 0)
                yield _sse_msg({'stage': 'PHASE3_DONE', 'progress': 78,
                                'messages': [f'Phase 3: {canonical} canonical decision points (from {candidates} candidates)'],
                                'completed_phase': 'phase3',
                                'result': phase3_result})

                # -- Phase 4 --
                yield _sse_msg({'stage': 'PHASE4_START', 'progress': 80,
                                'messages': ['Phase 4: Narrative Construction...'],
                                'active_phase': 'phase4'})
                phase4_result = run_phase4(case_id)

                chars = phase4_result.get('characters_count', 0)
                events = phase4_result.get('timeline_events', 0)
                yield _sse_msg({'stage': 'PHASE4_DONE', 'progress': 95,
                                'messages': [f'Phase 4: {chars} characters, {events} timeline events'],
                                'completed_phase': 'phase4',
                                'result': phase4_result})

                # -- COMPLETE --
                all_results = {
                    'provisions': provisions_result,
                    'precedents': precedents_result,
                    'qc': qc_result,
                    'transformation': transformation_result,
                    'rich_analysis': rich_result,
                    'phase3': phase3_result,
                    'phase4': phase4_result,
                }
                yield _sse_msg({'stage': 'COMPLETE', 'progress': 100,
                                'messages': ['Synthesis complete!'],
                                'result': all_results})

            except Exception as e:
                logger.error(f"[RunAll-Stream] Error: {e}")
                import traceback
                traceback.print_exc()
                yield _sse_msg({'stage': 'ERROR', 'progress': 100, 'error': True,
                                'messages': [f'Error: {str(e)}']})

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
            }
        )

    return {
        'run_complete_synthesis': run_complete_synthesis,
        'run_complete_synthesis_stream': run_complete_synthesis_stream,
    }
