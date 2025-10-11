"""
LangGraph Builder for Enhanced Temporal Dynamics Extraction

Builds a StateGraph with 7 stages for comprehensive temporal analysis.
"""

from langgraph.graph import StateGraph, START, END
import logging

from .state import TemporalDynamicsState
from .nodes.stage1_analysis import analyze_sections
from .nodes.stage2_temporal import extract_temporal_markers

logger = logging.getLogger(__name__)


def build_temporal_dynamics_graph():
    """
    Build the LangGraph state machine for enhanced temporal dynamics extraction.

    Currently implements:
    - Stage 1: Combined section analysis

    TODO: Add stages 2-7:
    - Stage 2: Temporal marker extraction
    - Stage 3: Action extraction
    - Stage 4: Event extraction
    - Stage 5: Causal chain analysis
    - Stage 6: Temporal sequencing
    - Stage 7: RDF storage

    Returns:
        CompiledGraph ready for execution with streaming
    """
    logger.info("Building temporal dynamics LangGraph")

    # Create StateGraph with our state type
    builder = StateGraph(TemporalDynamicsState)

    # === ADD NODES ===
    logger.info("Adding Stage 1: Section Analysis")
    builder.add_node("section_analysis", analyze_sections)

    logger.info("Adding Stage 2: Temporal Markers")
    builder.add_node("temporal_markers", extract_temporal_markers)

    # TODO: Add more stages as they're implemented
    # builder.add_node("action_extraction", extract_actions)
    # builder.add_node("event_extraction", extract_events)
    # builder.add_node("causal_analysis", analyze_causal_chains)
    # builder.add_node("temporal_sequencing", build_timeline)
    # builder.add_node("rdf_storage", store_rdf_entities)

    # === DEFINE EDGES ===
    builder.add_edge(START, "section_analysis")
    builder.add_edge("section_analysis", "temporal_markers")
    builder.add_edge("temporal_markers", END)

    # TODO: Add remaining pipeline edges
    # builder.add_edge("temporal_markers", "action_extraction")
    # builder.add_edge("action_extraction", "event_extraction")
    # builder.add_edge("event_extraction", "causal_analysis")
    # builder.add_edge("causal_analysis", "temporal_sequencing")
    # builder.add_edge("temporal_sequencing", "rdf_storage")
    # builder.add_edge("rdf_storage", END)

    # Compile the graph
    graph = builder.compile()

    logger.info("Temporal dynamics LangGraph compiled successfully")
    logger.info("Current stages: 2 (Section Analysis, Temporal Markers)")

    return graph
