"""Decision point extraction utilities (Phase A).
Wraps events labeled decision; generate placeholder options.
"""
from __future__ import annotations
from typing import List, Dict, Any
import uuid

GENERIC_OPTIONS = [
    ("Act Transparently", "Fully disclose to relevant stakeholders"),
    ("Partial Disclosure", "Share limited information initially"),
    ("Escalate Internally", "Consult internal oversight before external action")
]

def enrich_decisions(events: List[Dict[str, Any]], max_initial: int = 20):
    """Attach generic options and optionally prune over-detected decisions.

    Heuristic pruning: limit total decision events before LLM refinement so we
    reduce later token usage. Preference order:
      1. Events originating from 'question' section
      2. Short interrogative sentences (contain '?')
      3. Earlier chronological order
    """
    decision_indices = [i for i, ev in enumerate(events) if ev['kind'] == 'decision']
    if len(decision_indices) > max_initial:
        scored = []
        for idx in decision_indices:
            ev = events[idx]
            base = 0
            if ev.get('section') == 'question':
                base += 3
            txt = ev.get('text', '')
            if '?' in txt:
                base += 2
            if len(txt) < 120:
                base += 1
            scored.append((base, idx))
        # sort descending score then ascending index
        scored.sort(key=lambda x: (-x[0], x[1]))
        keep_set = {idx for _, idx in scored[:max_initial]}
        for i, ev in enumerate(events):
            if ev['kind'] == 'decision' and i not in keep_set:
                ev['kind'] = 'context'  # demote
                ev.pop('options', None)

    # Attach generic options to remaining decisions
    for ev in events:
        if ev['kind'] != 'decision':
            continue
        ev['options'] = [
            {
                'id': str(uuid.uuid4()),
                'label': label,
                'description': desc
            } for label, desc in GENERIC_OPTIONS
        ]
        ev['ontology']['rdf_types'] = ['DecisionJuncture']
