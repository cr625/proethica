"""Lightweight participant / role extraction heuristics for scenario events.

Extracts role-like entities (Engineer A, Client W, Supervisor, Manager, Director, Inspector,
Consultant) from event text to enrich context for decision refinement and future
ontology alignment.

Environment toggle: DIRECT_SCENARIO_INCLUDE_PARTICIPANTS (default true)
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Set

ROLE_PATTERN = re.compile(r"\b(Engineer|Client|Supervisor|Manager|Director|Inspector|Consultant)\s+[A-Z](?:[a-z]+)?\b")
SIMPLE_ROLE_PATTERN = re.compile(r"\b(Engineer|Client|Supervisor|Manager|Director|Inspector|Consultant)\b", re.IGNORECASE)


def _normalize(token: str) -> str:
    return token.strip()


def extract_participants(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    participants: Set[str] = set()
    for ev in events:
        text = ev.get('text', '')
        found = set(ROLE_PATTERN.findall(text))
        # ROLE_PATTERN returns only the first group; need full span, do manually
        span_matches = []
        for m in ROLE_PATTERN.finditer(text):
            span_matches.append(text[m.start():m.end()])
        if not span_matches:
            # fallback: single role words in question/conclusion sections
            if ev.get('section') in ('question', 'conclusion'):
                for m in SIMPLE_ROLE_PATTERN.finditer(text):
                    span_matches.append(text[m.start():m.end()])
        normed = {_normalize(s) for s in span_matches}
        if normed:
            ev['participants'] = sorted(normed)
            participants.update(normed)
    return {
        'unique_participants': sorted(participants)
    }
