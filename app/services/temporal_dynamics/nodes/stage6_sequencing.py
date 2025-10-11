"""
Stage 6 Node: Temporal Sequencing

Constructs chronological timeline from actions and events,
validates temporal consistency, and orders elements.
"""

from typing import Dict
import logging

from ..state import TemporalDynamicsState
from ..utils.timeline_builder import build_timeline

logger = logging.getLogger(__name__)


def construct_timeline(state: TemporalDynamicsState) -> Dict:
    """
    Stage 6: Build chronological timeline and validate consistency

    Args:
        state: Current graph state

    Returns:
        Dict with state updates to merge
    """
    logger.info(f"[Stage 6] Constructing timeline for case {state['case_id']}")

    try:
        # Build timeline from actions, events, and temporal markers
        timeline_data = build_timeline(
            actions=state['actions'],
            events=state['events'],
            temporal_markers=state['temporal_markers']
        )

        # Extract timeline info
        timeline = timeline_data['timeline']
        consistency = timeline_data['temporal_consistency_check']

        logger.info(f"[Stage 6] Timeline with {len(timeline)} timepoints constructed")

        # Build progress message
        message = f'✓ Timeline with {len(timeline)} timepoints constructed'
        if consistency.get('warnings'):
            message += f' ({len(consistency["warnings"])} warnings)'

        # Return state updates
        return {
            'timeline': timeline_data,
            'current_stage': 'temporal_sequencing',
            'progress_percentage': 90,
            'stage_messages': [message]
        }

    except Exception as e:
        logger.error(f"[Stage 6] Error: {e}", exc_info=True)
        return {
            'current_stage': 'temporal_sequencing',
            'progress_percentage': 90,
            'errors': [f'Timeline construction error: {str(e)}']
        }
