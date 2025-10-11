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
import asyncio

from app.models import Document
from app.services.temporal_dynamics import build_temporal_dynamics_graph
from app.utils.environment_auth import auth_required_for_llm

logger = logging.getLogger(__name__)


@auth_required_for_llm
def extract_enhanced_temporal_dynamics(case_id):
    """
    Execute enhanced temporal dynamics extraction with real-time progress streaming.

    Uses Server-Sent Events (SSE) to stream progress updates to the frontend.
    Currently implements Stage 1 (section analysis) as proof of concept.

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

        def generate():
            """Generator for Server-Sent Events"""
            try:
                logger.info("[Enhanced TD] Starting graph execution")

                # Send initial event
                yield f"data: {json.dumps({'stage': 'init', 'progress': 0, 'messages': ['Starting enhanced temporal extraction...']})}\n\n"

                # Execute graph synchronously with streaming
                # Note: Using stream() not astream() since Flask doesn't support async generators easily
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
                            'llm_trace': updates.get('llm_trace', [])  # Include LLM trace data
                        }

                        logger.info(f"[Enhanced TD] Streaming: {node_name} - {progress_data['progress']}% - Trace entries: {len(progress_data['llm_trace'])}")

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
