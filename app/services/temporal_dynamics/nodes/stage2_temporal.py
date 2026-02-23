"""
Stage 2: Temporal Marker Extraction

Extracts temporal markers (dates, times, durations) and identifies Allen temporal relations.
Uses LLM for extraction with optional dateutil validation.
"""

from typing import Dict
import logging

from ..state import TemporalDynamicsState

logger = logging.getLogger(__name__)


def extract_temporal_markers(state: TemporalDynamicsState) -> Dict:
    """
    Stage 2: Extract temporal markers and Allen relations

    Args:
        state: Current graph state

    Returns:
        Dict with state updates to merge
    """
    logger.info(f"[Stage 2] Extracting temporal markers for case {state['case_id']}")

    try:
        # Import extractors here to avoid circular dependencies
        from ..extractors.temporal_marker_extractor import (
            extract_temporal_markers_llm,
            validate_dates
        )

        # Get unified narrative from Stage 1
        unified_narrative = state.get('unified_narrative', {})
        timeline_summary = unified_narrative.get('unified_timeline_summary', '')

        # Get original text for detailed extraction
        facts_text = state['facts_text']
        discussion_text = state['discussion_text']

        logger.info("[Stage 2] Calling LLM for temporal marker extraction")

        # Extract temporal markers using LLM
        temporal_markers = extract_temporal_markers_llm(
            facts=facts_text,
            discussion=discussion_text,
            timeline_summary=timeline_summary,
            llm_trace=state.get('llm_trace', [])
        )

        logger.info(f"[Stage 2] Extracted {len(temporal_markers.get('explicit_dates', []))} explicit dates")
        logger.info(f"[Stage 2] Extracted {len(temporal_markers.get('temporal_phrases', []))} temporal phrases")
        logger.info(f"[Stage 2] Identified {len(temporal_markers.get('allen_relations', []))} Allen relations")

        # Validate dates with dateutil (warnings only, non-blocking)
        validation_warnings = validate_dates(temporal_markers)

        if validation_warnings:
            logger.warning(f"[Stage 2] Date validation warnings: {len(validation_warnings)}")

        # Prepare messages
        messages = [
            f'✓ Temporal marker extraction complete',
            f'  Explicit dates: {len(temporal_markers.get("explicit_dates", []))}',
            f'  Temporal phrases: {len(temporal_markers.get("temporal_phrases", []))}',
            f'  Allen relations: {len(temporal_markers.get("allen_relations", []))}'
        ]

        if validation_warnings:
            messages.append(f'  Date validation warnings: {len(validation_warnings)}')

        # Return state updates (including accumulated llm_trace)
        return {
            'temporal_markers': temporal_markers,
            'llm_trace': state.get('llm_trace', []),  # Return accumulated trace
            'current_stage': 'temporal_markers',
            'progress_percentage': 30,
            'stage_messages': messages,
            'errors': validation_warnings if validation_warnings else []
        }

    except Exception as e:
        logger.error(f"[Stage 2] Error: {e}", exc_info=True)
        return {
            'current_stage': 'temporal_markers',
            'progress_percentage': 30,
            'errors': [f'Temporal marker extraction error: {str(e)}'],
            'stage_messages': ['✗ Temporal marker extraction failed']
        }
