"""
Enhanced Temporal Dynamics Pass (Step 3)

Multi-stage LangGraph orchestration with Server-Sent Events streaming for progress tracking.
"""

from flask import Response, jsonify
from flask import current_app as app
import json
import logging
import uuid
from datetime import datetime

from app.models import Document
from app.services.temporal_dynamics import build_temporal_dynamics_graph
from app.services.case_entity_storage_service import CaseEntityStorageService
from app.utils.environment_auth import auth_required_for_llm

logger = logging.getLogger(__name__)


# --- SSE entity summary helpers ---

def _summarize_actions(actions):
    """Produce card-friendly action summaries for SSE transmission."""
    return [{
        'label': a.get('label', 'Unknown'),
        'description': (a.get('description', '') or '')[:200],
        'agent': a.get('agent', ''),
        'temporal_marker': a.get('temporal_marker', ''),
        'intention': (a.get('intention') or {}).get('mental_state', ''),
    } for a in actions]


def _summarize_events(events):
    """Produce card-friendly event summaries for SSE transmission."""
    return [{
        'label': e.get('label', 'Unknown'),
        'description': (e.get('description', '') or '')[:200],
        'temporal_marker': e.get('temporal_marker', ''),
        'classification': (e.get('classification') or {}).get('event_type', ''),
        'urgency': (e.get('urgency') or {}).get('urgency_level', ''),
    } for e in events]


def _summarize_causal_chains(chains):
    """Produce card-friendly causal chain summaries for SSE transmission."""
    return [{
        'cause': c.get('cause', ''),
        'effect': c.get('effect', ''),
        'responsibility_type': (c.get('responsibility') or {}).get('responsibility_type', ''),
        'counterfactual': (c.get('ness_test') or {}).get('counterfactual', ''),
    } for c in chains]


def _summarize_allen_relations(relations):
    """Produce card-friendly Allen relation summaries for SSE transmission."""
    return [{
        'entity1': r.get('entity1', ''),
        'relation': r.get('relation', ''),
        'entity2': r.get('entity2', ''),
    } for r in relations]


def _summarize_timeline(timeline):
    """Produce card-friendly timeline summary for SSE transmission."""
    elements = timeline.get('timeline', [])
    return {
        'total_elements': timeline.get('total_elements', len(elements)),
        'actions': timeline.get('actions', 0),
        'events': timeline.get('events', 0),
        'timepoints': [e.get('timepoint', '') for e in elements[:10]],
    }


@auth_required_for_llm
def extract_enhanced_temporal_dynamics(case_id):
    """
    Execute enhanced temporal dynamics extraction with real-time progress streaming.

    Uses Server-Sent Events (SSE) to stream progress updates and extracted entities
    to the frontend as each LangGraph stage completes.

    Args:
        case_id: Case ID to extract from

    Returns:
        SSE response stream
    """
    try:
        logger.info(f"[Enhanced TD] Starting extraction for case {case_id}")

        # Get case data
        case = Document.query.get_or_404(case_id)

        # Extract section texts - sections are stored as plain strings
        sections = case.doc_metadata.get('sections', {})
        facts_text = sections.get('facts', '') if isinstance(sections.get('facts'), str) else ''
        discussion_text = sections.get('discussion', '') if isinstance(sections.get('discussion'), str) else ''

        if not facts_text:
            logger.error(f"[Enhanced TD] No facts section found for case {case_id}")
            return jsonify({'error': 'Facts section not found'}), 400

        logger.info(f"[Enhanced TD] Facts: {len(facts_text)} chars, Discussion: {len(discussion_text)} chars")

        # Auto-clear: Remove any uncommitted Pass 3 entities before running new extraction
        # This prevents duplicate entities when re-running extraction
        clear_result = CaseEntityStorageService.clear_extraction_pass(
            case_id=case_id,
            extraction_pass='pass3'
        )
        if clear_result.get('success'):
            cleared_count = clear_result.get('entities_cleared', 0) + clear_result.get('prompts_cleared', 0)
            if cleared_count > 0:
                logger.info(f"[Enhanced TD] Auto-cleared {cleared_count} uncommitted entities/prompts before extraction")
        else:
            logger.warning(f"[Enhanced TD] Auto-clear failed: {clear_result.get('error', 'Unknown error')}")

        # Initialize state
        initial_state = {
            'case_id': case_id,
            'facts_text': facts_text,
            'discussion_text': discussion_text,
            'extraction_session_id': str(uuid.uuid4()),
            'unified_narrative': {},
            'temporal_markers': {},
            'actions': [],
            'events': [],
            'causal_chains': [],
            'timeline': {},
            'current_stage': '',
            'progress_percentage': 0,
            'stage_messages': [],
            'errors': [],
            'start_time': datetime.utcnow().isoformat(),
            'end_time': '',
            'llm_trace': []
        }

        # Build graph
        logger.info("[Enhanced TD] Building LangGraph")
        graph = build_temporal_dynamics_graph()

        # Capture Flask app reference before entering generator
        # (generator can lose request context during long-running LangGraph execution)
        flask_app = app._get_current_object()

        def generate():
            """Generator for Server-Sent Events"""
            try:
                logger.info("[Enhanced TD] Starting graph execution")

                # Send initial event
                yield f"data: {json.dumps({'stage': 'init', 'progress': 0, 'messages': ['Starting enhanced temporal extraction...']})}\n\n"

                # Execute graph synchronously with streaming
                for chunk in graph.stream(
                    initial_state,
                    stream_mode="updates"
                ):
                    # chunk is {node_name: state_updates}
                    logger.info(f"[Enhanced TD] Received chunk: {list(chunk.keys())}")

                    for node_name, updates in chunk.items():
                        # Format progress data
                        progress_data = {
                            'node': node_name,
                            'stage': updates.get('current_stage', ''),
                            'progress': updates.get('progress_percentage', 0),
                            'messages': updates.get('stage_messages', []),
                            'errors': updates.get('errors', []),
                            'llm_trace': updates.get('llm_trace', []),
                        }

                        # Include entity data from entity-producing stages
                        if updates.get('actions'):
                            progress_data['entities'] = {
                                'type': 'actions',
                                'items': _summarize_actions(updates['actions']),
                            }
                        if updates.get('events'):
                            progress_data['entities'] = {
                                'type': 'events',
                                'items': _summarize_events(updates['events']),
                            }
                        if updates.get('causal_chains'):
                            progress_data['entities'] = {
                                'type': 'causal_chains',
                                'items': _summarize_causal_chains(updates['causal_chains']),
                            }

                        # Allen relations are nested inside temporal_markers
                        markers = updates.get('temporal_markers')
                        if markers and markers.get('allen_relations'):
                            progress_data['allen_relations'] = _summarize_allen_relations(
                                markers['allen_relations']
                            )

                        # Timeline (algorithmic, no LLM)
                        if updates.get('timeline'):
                            progress_data['timeline'] = _summarize_timeline(updates['timeline'])

                        logger.info(f"[Enhanced TD] Streaming: {node_name} - {progress_data['progress']}%")

                        # Send as SSE
                        yield f"data: {json.dumps(progress_data)}\n\n"

                # Send completion event
                logger.info("[Enhanced TD] Graph execution complete")
                yield f"data: {json.dumps({'complete': True, 'progress': 100, 'messages': ['Enhanced temporal extraction complete!']})}\n\n"

            except Exception as e:
                logger.error(f"[Enhanced TD] Error during streaming: {e}", exc_info=True)
                error_data = {
                    'error': str(e),
                    'progress': 0,
                    'messages': [f'Error: {str(e)}']
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        # Return SSE response
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',  # Disable nginx buffering
                'Connection': 'keep-alive'
            }
        )

    except Exception as e:
        logger.error(f"[Enhanced TD] Error in setup: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
