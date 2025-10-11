"""
Stage 4 Node: Event Extraction

Extracts occurrences (non-volitional events) with emergency classification,
urgency levels, triggers, and causal context.
"""

from typing import Dict
import logging

from ..state import TemporalDynamicsState
from ..extractors.event_extractor import extract_events_with_classification

logger = logging.getLogger(__name__)


def extract_events(state: TemporalDynamicsState) -> Dict:
    """
    Stage 4: Extract events (occurrences, not volitional decisions)

    Args:
        state: Current graph state

    Returns:
        Dict with state updates to merge
    """
    logger.info(f"[Stage 4] Extracting events for case {state['case_id']}")

    try:
        # Extract events using narrative, temporal markers, and actions
        events = extract_events_with_classification(
            narrative=state['unified_narrative'],
            temporal_markers=state['temporal_markers'],
            actions=state['actions'],
            case_id=state['case_id'],
            llm_trace=state.get('llm_trace', [])
        )

        # Count emergency events
        emergency_count = sum(
            1 for e in events
            if e.get('classification', {}).get('emergency_status', '').lower() in ['critical', 'high']
        )

        logger.info(f"[Stage 4] Extracted {len(events)} events ({emergency_count} emergency)")

        # Build progress message
        message = f'✓ Extracted {len(events)} events'
        if emergency_count > 0:
            message += f' ({emergency_count} emergency)'

        # Return state updates
        return {
            'events': events,
            'current_stage': 'event_extraction',
            'progress_percentage': 65,
            'stage_messages': [message]
        }

    except Exception as e:
        logger.error(f"[Stage 4] Error: {e}", exc_info=True)
        return {
            'current_stage': 'event_extraction',
            'progress_percentage': 65,
            'errors': [f'Event extraction error: {str(e)}']
        }
