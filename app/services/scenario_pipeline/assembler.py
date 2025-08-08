"""Event assembly from sentences (Phase A).
Groups sequences of sentences with same primary label (excluding decision boundaries).
"""
from __future__ import annotations
from typing import Dict, Any, List


def assemble_events(sentences: List[Dict[str, Any]], classification: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    buffer: List[Dict[str, Any]] = []

    def flush():
        nonlocal buffer
        if not buffer:
            return
        # Derive kind
        kinds = [classification[s['id']]['primary'] for s in buffer]
        # If any decision inside, handle elsewhere, so only context/action/outcome here
        if 'decision' in kinds:
            # split decisions into single-sentence events separately
            for s in buffer:
                if classification[s['id']]['primary'] == 'decision':
                    events.append(_build_event([s], 'decision'))
                else:
                    events.append(_build_event([s], classification[s['id']]['primary']))
        else:
            kind = kinds[0]
            events.append(_build_event(buffer, kind))
        buffer = []

    for s in sentences:
        label = classification[s['id']]['primary']
        if label == 'decision':
            flush()
            events.append(_build_event([s], 'decision'))
            continue
        if not buffer:
            buffer.append(s)
            continue
        prev_label = classification[buffer[-1]['id']]['primary']
        if prev_label == label:
            buffer.append(s)
        else:
            flush()
            buffer.append(s)
    flush()

    # Assign incremental orders
    for i, ev in enumerate(events):
        ev['order'] = (i + 1) * 10
    return events


def _build_event(sents: List[Dict[str, Any]], kind: str) -> Dict[str, Any]:
    text = ' '.join(s['text'] for s in sents)
    return {
        'id': f"ev_{sents[0]['id']}",
        'kind': kind,
        'sentence_ids': [s['id'] for s in sents],
        'section': sents[0]['section'],
        'text': text,
        'ontology': {},
        'temporal': {},
        'participants': [],
        'precedes': []
    }
