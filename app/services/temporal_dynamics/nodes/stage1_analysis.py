"""
Stage 1: Combined Section Analysis

Analyzes Facts and Discussion sections together to understand the unified temporal narrative.
"""

from typing import Dict
import logging

from ..state import TemporalDynamicsState

logger = logging.getLogger(__name__)


def analyze_sections(state: TemporalDynamicsState) -> Dict:
    """
    Stage 1: Analyze combined Facts and Discussion sections

    Args:
        state: Current graph state

    Returns:
        Dict with state updates to merge (not full state)
    """
    logger.info(f"[Stage 1] Analyzing sections for case {state['case_id']}")

    try:
        # Import extractor here to avoid circular dependencies
        from ..extractors.temporal_extractor import analyze_combined_sections

        # Extract text from state
        facts_text = state['facts_text']
        discussion_text = state['discussion_text']

        logger.info(f"[Stage 1] Facts length: {len(facts_text)} chars")
        logger.info(f"[Stage 1] Discussion length: {len(discussion_text)} chars")

        # Call LLM to analyze combined sections (returns analysis + trace)
        unified_narrative, trace = analyze_combined_sections(
            facts=facts_text,
            discussion=discussion_text
        )

        logger.info("[Stage 1] Section analysis complete")
        logger.info(f"[Stage 1] Found {len(unified_narrative.get('decision_points', []))} decision points")
        logger.info(f"[Stage 1] Token usage: {trace.get('tokens', {})}")

        # Prepare llm_trace update (LangGraph will append to existing list)
        llm_trace_update = state.get('llm_trace', []) + [trace]

        # Return only state updates (LangGraph merges automatically)
        return {
            'unified_narrative': unified_narrative,
            'llm_trace': llm_trace_update,
            'current_stage': 'section_analysis',
            'progress_percentage': 15,
            'stage_messages': [
                f'✓ Combined section analysis complete',
                f'  Found {len(unified_narrative.get("decision_points", []))} key decision points',
                f'  Identified {len(unified_narrative.get("competing_priorities_mentioned", []))} potential priority conflicts',
                f'  Tokens used: {trace.get("tokens", {}).get("total_tokens", 0)}'
            ]
        }

    except Exception as e:
        logger.error(f"[Stage 1] Error: {e}", exc_info=True)
        return {
            'current_stage': 'section_analysis',
            'progress_percentage': 15,
            'errors': [f'Section analysis error: {str(e)}'],
            'stage_messages': ['✗ Section analysis failed']
        }
