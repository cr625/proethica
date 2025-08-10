"""Ontology mapping minimal (Phase A).
Assign BFO / engineering ethics types heuristically.
"""
from __future__ import annotations
from typing import List, Dict, Any

BFO_PROCESS = 'BFO:0000015'  # placeholder CURIE
BFO_PROCESS_BOUNDARY = 'BFO:0000035'
ENGINEERING_DECISION = 'ENGETH:DecisionPoint'


def map_events(events: List[Dict[str, Any]]):
    for ev in events:
        if 'rdf_types' in ev['ontology']:
            continue
        if ev['kind'] == 'decision':
            ev['ontology']['rdf_types'] = [BFO_PROCESS_BOUNDARY, ENGINEERING_DECISION]
        else:
            ev['ontology']['rdf_types'] = [BFO_PROCESS]
