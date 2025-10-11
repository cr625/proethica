"""
Stage 3 Node: Action Extraction

Extracts volitional professional decisions with rich metadata including
intentions, mental states, competing priorities, and ethical context.
"""

from typing import Dict
import logging

from ..state import TemporalDynamicsState
from ..extractors.action_extractor import extract_actions_with_metadata

logger = logging.getLogger(__name__)


def extract_actions(state: TemporalDynamicsState) -> Dict:
    """
    Stage 3: Extract actions (volitional professional decisions)

    Args:
        state: Current graph state

    Returns:
        Dict with state updates to merge
    """
    logger.info(f"[Stage 3] Extracting actions for case {state['case_id']}")

    try:
        # Extract actions using unified narrative and temporal markers
        actions = extract_actions_with_metadata(
            narrative=state['unified_narrative'],
            temporal_markers=state['temporal_markers'],
            case_id=state['case_id'],
            llm_trace=state.get('llm_trace', [])
        )

        logger.info(f"[Stage 3] Extracted {len(actions)} actions")

        # Return state updates (including accumulated llm_trace)
        return {
            'actions': actions,
            'llm_trace': state.get('llm_trace', []),  # Return accumulated trace
            'current_stage': 'action_extraction',
            'progress_percentage': 45,
            'stage_messages': [f'✓ Extracted {len(actions)} volitional actions with intentions']
        }

    except Exception as e:
        logger.error(f"[Stage 3] Error: {e}", exc_info=True)
        return {
            'current_stage': 'action_extraction',
            'progress_percentage': 45,
            'errors': [f'Action extraction error: {str(e)}']
        }
