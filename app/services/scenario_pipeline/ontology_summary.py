"""Heuristic ontology category summarization for interim scenario view.

Maps event texts and participants to proethica-intermediate categories using lightweight
keyword heuristics (no full NLP). Provides counts and extracted term snippets.
"""
from __future__ import annotations
from typing import List, Dict, Any

PRINCIPLE_TERMS = [
    'honesty', 'integrity', 'safety', 'sustainable', 'sustainability', 'justice', 'fairness', 'welfare'
]
OBLIGATION_TERMS = [
    'duty', 'obligation', 'responsibility', 'must', 'should', 'required', 'obliged'
]
CONSTRAINT_TERMS = [
    'deadline', 'time pressure', 'time constraint', 'budget', 'cost overrun', 'regulation', 'requirement'
]
STATE_TERMS = [
    'risk', 'hazard', 'uncertainty', 'pressure', 'issue', 'problem', 'concern'
]
RESOURCE_TERMS = [
    'data', 'report', 'software', 'tool', 'document', 'specification', 'design'
]

def _contains_any(text: str, terms: List[str]) -> List[str]:
    lt = text.lower()
    found = []
    for t in terms:
        if t in lt:
            found.append(t)
    return found

def build_ontology_summary(events: List[Dict[str, Any]], participants: List[str]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        'Role': participants,
        'Principle': [],
        'Obligation': [],
        'State': [],
        'Resource': [],
        'Action': [],
        'Event': [],
        'Capability': [],  # placeholder
        'Constraint': []
    }
    for ev in events:
        txt = ev.get('text', '')
        if ev.get('kind') == 'action':
            summary['Action'].append(ev['id'])
        if ev.get('kind') in ('action', 'context', 'decision', 'outcome'):
            summary['Event'].append(ev['id'])
        for term in _contains_any(txt, PRINCIPLE_TERMS):
            summary['Principle'].append({'event': ev['id'], 'term': term})
        for term in _contains_any(txt, OBLIGATION_TERMS):
            summary['Obligation'].append({'event': ev['id'], 'term': term})
        for term in _contains_any(txt, STATE_TERMS):
            summary['State'].append({'event': ev['id'], 'term': term})
        for term in _contains_any(txt, RESOURCE_TERMS):
            summary['Resource'].append({'event': ev['id'], 'term': term})
        for term in _contains_any(txt, CONSTRAINT_TERMS):
            summary['Constraint'].append({'event': ev['id'], 'term': term})
    summary['Action'] = list(dict.fromkeys(summary['Action']))
    summary['Event'] = list(dict.fromkeys(summary['Event']))
    return summary
