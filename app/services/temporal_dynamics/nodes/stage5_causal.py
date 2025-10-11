"""
Stage 5 Node: Causal Chain Analysis

Analyzes causal relationships between actions and events with NESS test,
responsibility attribution, and causal chain construction.
"""

from typing import Dict
import logging

from ..state import TemporalDynamicsState
from ..extractors.causal_extractor import analyze_causal_chains

logger = logging.getLogger(__name__)


def analyze_causal_relationships(state: TemporalDynamicsState) -> Dict:
    """
    Stage 5: Analyze causal chains and responsibility attribution

    Args:
        state: Current graph state

    Returns:
        Dict with state updates to merge
    """
    logger.info(f"[Stage 5] Analyzing causal chains for case {state['case_id']}")

    try:
        # Analyze causal relationships using actions and events
        causal_chains = analyze_causal_chains(
            actions=state['actions'],
            events=state['events'],
            case_id=state['case_id'],
            llm_trace=state.get('llm_trace', [])
        )

        logger.info(f"[Stage 5] Identified {len(causal_chains)} causal chains")

        # Return state updates
        return {
            'causal_chains': causal_chains,
            'current_stage': 'causal_analysis',
            'progress_percentage': 80,
            'stage_messages': [f'✓ Identified {len(causal_chains)} causal chains with responsibility attribution']
        }

    except Exception as e:
        logger.error(f"[Stage 5] Error: {e}", exc_info=True)
        return {
            'current_stage': 'causal_analysis',
            'progress_percentage': 80,
            'errors': [f'Causal analysis error: {str(e)}']
        }
