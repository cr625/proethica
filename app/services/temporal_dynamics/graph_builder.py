"""
LangGraph Builder for Enhanced Temporal Dynamics Extraction

Builds a StateGraph with 7 stages for comprehensive temporal analysis.
"""

from langgraph.graph import StateGraph, START, END
import logging

from .state import TemporalDynamicsState
from .nodes.stage1_analysis import analyze_sections
from .nodes.stage2_temporal import extract_temporal_markers
from .nodes.stage3_actions import extract_actions
from .nodes.stage4_events import extract_events
from .nodes.stage5_causal import analyze_causal_relationships
from .nodes.stage6_sequencing import construct_timeline
from .nodes.stage7_storage import store_rdf_entities

logger = logging.getLogger(__name__)


def build_temporal_dynamics_graph():
    """
    Build the LangGraph state machine for enhanced temporal dynamics extraction.

    Implements all 7 stages:
    - Stage 1: Combined section analysis
    - Stage 2: Temporal marker extraction
    - Stage 3: Action extraction (volitional decisions)
    - Stage 4: Event extraction (occurrences)
    - Stage 5: Causal chain analysis (NESS test, responsibility)
    - Stage 6: Temporal sequencing (timeline construction)
    - Stage 7: RDF storage (separate actions/events)

    Returns:
        CompiledGraph ready for execution with streaming
    """
    logger.info("Building temporal dynamics LangGraph with all 7 stages")

    # Create StateGraph with our state type
    builder = StateGraph(TemporalDynamicsState)

    # === ADD NODES ===
    # NOTE: Node names must not conflict with state field names
    # State has: unified_narrative, temporal_markers, actions, events, causal_chains, timeline
    # So we use different node names: analyze_*, extract_*, construct_*, store_*

    logger.info("Adding Stage 1: Section Analysis")
    builder.add_node("analyze_sections_node", analyze_sections)

    logger.info("Adding Stage 2: Temporal Markers")
    builder.add_node("extract_temporal_node", extract_temporal_markers)

    logger.info("Adding Stage 3: Action Extraction")
    builder.add_node("extract_actions_node", extract_actions)

    logger.info("Adding Stage 4: Event Extraction")
    builder.add_node("extract_events_node", extract_events)

    logger.info("Adding Stage 5: Causal Analysis")
    builder.add_node("analyze_causal_node", analyze_causal_relationships)

    logger.info("Adding Stage 6: Temporal Sequencing")
    builder.add_node("construct_timeline_node", construct_timeline)

    logger.info("Adding Stage 7: RDF Storage")
    builder.add_node("store_rdf_node", store_rdf_entities)

    # === DEFINE EDGES (Linear pipeline flow) ===
    builder.add_edge(START, "analyze_sections_node")
    builder.add_edge("analyze_sections_node", "extract_temporal_node")
    builder.add_edge("extract_temporal_node", "extract_actions_node")
    builder.add_edge("extract_actions_node", "extract_events_node")
    builder.add_edge("extract_events_node", "analyze_causal_node")
    builder.add_edge("analyze_causal_node", "construct_timeline_node")
    builder.add_edge("construct_timeline_node", "store_rdf_node")
    builder.add_edge("store_rdf_node", END)

    # Compile the graph
    graph = builder.compile()

    logger.info("Temporal dynamics LangGraph compiled successfully")
    logger.info("All 7 stages wired and ready for execution")

    return graph
