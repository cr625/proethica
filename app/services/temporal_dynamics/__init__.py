"""
Enhanced Temporal Dynamics Extraction Service

Multi-stage LangGraph orchestration for extracting actions, events, causal chains,
and temporal relationships from ethics cases.

Stages:
1. Combined Section Analysis (Facts + Discussion)
2. Temporal Marker Extraction (dates, times, Allen relations)
3. Action Extraction (volitional decisions with intentions)
4. Event Extraction (occurrences with emergency classification)
5. Causal Chain Analysis (NESS test, responsibility)
6. Temporal Sequencing (timeline construction)
7. RDF Storage (separate actions/events with OWL-Time)
"""

from .graph_builder import build_temporal_dynamics_graph
from .state import TemporalDynamicsState

__all__ = ['build_temporal_dynamics_graph', 'TemporalDynamicsState']
