"""
State definition for Enhanced Temporal Dynamics extraction

Uses LangGraph's TypedDict-based state management.
"""

from typing import TypedDict, List, Dict, Annotated
from langgraph.graph.message import add_messages


class TemporalDynamicsState(TypedDict):
    """
    Shared state for the entire temporal dynamics extraction pipeline.

    LangGraph will automatically merge updates from each node into this state.
    Nodes return only the updates (not the full state).
    """
    # === INPUT DATA ===
    case_id: int
    facts_text: str
    discussion_text: str
    extraction_session_id: str

    # === STAGE OUTPUTS ===
    # Stage 1: Unified narrative from combined sections
    unified_narrative: Dict
    # {
    #   'unified_timeline_summary': str,
    #   'decision_points': List[str],
    #   'temporal_overlap_notes': str,
    #   'competing_priorities_mentioned': List[str]
    # }

    # Stage 2: Temporal markers
    temporal_markers: Dict
    # {
    #   'absolute': List[Dict],  # Absolute dates/times
    #   'relative': List[Dict],  # Relative temporal markers (before/after)
    #   'allen': List[Dict]      # Allen interval relations
    # }

    # Stage 3: Actions (volitional professional decisions)
    actions: List[Dict]
    # [{
    #   'label': str,
    #   'description': str,
    #   'agent': str,
    #   'temporal_marker': str,
    #   'source_section': str,
    #   'intention': {...},
    #   'ethical_context': {...},
    #   'competing_priorities': {...},
    #   'professional_context': {...}
    # }]

    # Stage 4: Events (occurrences, automatic triggers, outcomes)
    events: List[Dict]
    # [{
    #   'label': str,
    #   'description': str,
    #   'temporal_marker': str,
    #   'source_section': str,
    #   'classification': {...},
    #   'urgency': {...},
    #   'triggers': {...},
    #   'causal_context': {...}
    # }]

    # Stage 5: Causal chains
    causal_chains: List[Dict]
    # [{
    #   'cause': str,
    #   'effect': str,
    #   'causal_language': str,
    #   'ness_test': {...},
    #   'responsibility': {...},
    #   'causal_chain': {...}
    # }]

    # Stage 6: Timeline
    timeline: Dict
    # {
    #   'timeline': [{
    #     'timepoint': str,
    #     'iso_duration': str,
    #     'elements': [...]
    #   }],
    #   'temporal_consistency_check': {...}
    # }

    # === PROGRESS TRACKING ===
    current_stage: str  # 'section_analysis', 'temporal_markers', etc.
    progress_percentage: int  # 0-100

    # Messages use add_messages reducer for accumulation
    stage_messages: Annotated[List[str], add_messages]

    errors: List[str]  # Any errors encountered

    # === METADATA ===
    start_time: str  # ISO timestamp when extraction started
    end_time: str  # ISO timestamp when extraction completed

    # === PROMPT/RESPONSE TRACE ===
    # Track all LLM interactions for complete traceability
    llm_trace: List[Dict]
    # [{
    #   'stage': str,  # Which stage this prompt belongs to
    #   'timestamp': str,  # ISO timestamp
    #   'prompt': str,  # Full prompt sent to LLM
    #   'response': str,  # Raw response from LLM
    #   'model': str,  # Model used (e.g., 'claude-sonnet-4-20250514')
    #   'parsed_output': Dict,  # Parsed JSON/structured output
    #   'tokens': Dict  # Token usage if available
    # }]
