"""Basic sentence classification heuristics for Phase A.
Classifies sentences into context|action|decision|outcome based on keywords.
"""
from __future__ import annotations
import re
from typing import Dict, Any, List

# Core lexical indicators
DECISION_RE = re.compile(r'\b(should|must|whether|obligation|duty|responsib|ethical|report|disclose)\b', re.IGNORECASE)
ACTION_RE = re.compile(r'\b(implemented|decided|reported|told|requested|met with|informed|refused)\b', re.IGNORECASE)
OUTCOME_RE = re.compile(r'\b(result|therefore|consequently|outcome|led to|as a result)\b', re.IGNORECASE)

# Additional light patterns
FIRST_PERSON_DUTY = re.compile(r"\b(I|we) (should|must|ought to|need to)\b", re.IGNORECASE)
QUESTION_MARK_HINT = re.compile(r'\?\s*$')


def classify_sentences(sentences: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for s in sentences:
        txt = s['text']
        section = s.get('section', '')
        labels = []

        # lexical indicators
        if DECISION_RE.search(txt) or FIRST_PERSON_DUTY.search(txt):
            labels.append('decision')
        if ACTION_RE.search(txt):
            labels.append('action')
        if OUTCOME_RE.search(txt):
            labels.append('outcome')

        # section-based boosts
        if section in ('question',):
            # Questions section sentences often pose dilemmas
            if 'decision' not in labels and (QUESTION_MARK_HINT.search(txt) or len(txt.split()) < 25):
                labels.append('decision')
        if section in ('conclusion',) and 'outcome' not in labels:
            labels.append('outcome')

        if not labels:
            labels.append('context')

        # primary precedence rules (decision strongest, then action, outcome)
        if 'decision' in labels:
            primary = 'decision'
        elif 'action' in labels:
            primary = 'action'
        elif 'outcome' in labels:
            primary = 'outcome'
        else:
            primary = 'context'

        # simple confidence tuning
        if primary == 'decision' and section == 'question':
            conf = 0.8
        elif primary == 'outcome' and section == 'conclusion':
            conf = 0.75
        else:
            conf = 0.6 if primary != 'context' else 0.4

        result[s['id']] = {
            'labels': labels,
            'primary': primary,
            'confidence': conf
        }
    return result
