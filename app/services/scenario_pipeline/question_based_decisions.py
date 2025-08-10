"""Question-based decision extraction leveraging case Questions section.

Parses the Questions section into individual ethical decision questions and constructs
decision events with higher-quality question wording and contextualized option sets.
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Optional
import uuid

ETHICAL_KEYWORDS = [
    'ethical', 'ethics', 'should', 'appropriate', 'proper', 'right', 'wrong',
    'duty', 'obligation', 'responsibility', 'professional', 'code', 'disclose', 'ai'
]

QUESTION_SPLIT_RE = re.compile(r'\?(?=\s+[A-Z]|\s*Should|\s*Would|\s*Is\s+it)')

def extract_question_decisions(sections: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Original section-based extraction (fallback).

    Retained for backwards compatibility; prefers explicit questions_list if available
    via extract_question_decisions_from_metadata.
    """
    raw_q = sections.get('question') or sections.get('questions') or ''
    if isinstance(raw_q, dict):
        raw_q = raw_q.get('text') or raw_q.get('content') or ''
    if not raw_q:
        return []
    return _questions_to_decisions(_split_questions(raw_q))


def extract_question_decisions_from_metadata(metadata: Dict[str, Any], sections: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Preferred extraction using metadata['questions_list'] if present.

    Falls back to section HTML if list absent. De-duplicates and normalizes trailing '?'.
    """
    questions: List[str] = []
    qlist = (metadata or {}).get('questions_list') or []
    if qlist:
        # Some entries may include HTML; strip tags quickly.
        for q in qlist:
            if not q:
                continue
            qt = re.sub(r'<[^>]+>', ' ', str(q)).strip()
            if qt and qt not in questions:
                questions.append(qt)
    if not questions and sections:
        raw_q = sections.get('question') or sections.get('questions') or ''
        if isinstance(raw_q, dict):
            raw_q = raw_q.get('text') or raw_q.get('content') or ''
        if raw_q:
            questions.extend(_split_questions(raw_q))
    return _questions_to_decisions(questions)


def _split_questions(raw_q: str) -> List[str]:
    text = re.sub(r'<[^>]+>', ' ', raw_q)
    parts = [p.strip() for p in QUESTION_SPLIT_RE.split(text) if p.strip()]
    normalized: List[str] = []
    for p in parts:
        if not p.endswith('?'):
            p = p + '?'
        if p not in normalized:
            normalized.append(p)
    return normalized


def _questions_to_decisions(questions: List[str]) -> List[Dict[str, Any]]:
    decisions: List[Dict[str, Any]] = []
    seq = 1
    for q in questions:
        low = q.lower()
        if not any(k in low for k in ETHICAL_KEYWORDS):
            continue
        decisions.append(_build_decision_event(q, seq))
        seq += 1
    return decisions

def _build_decision_event(question: str, seq: int) -> Dict[str, Any]:
    opts = _generate_options(question)
    return {
        'id': f'qdec_{seq}',
        'kind': 'decision',
        'section': 'question',
        'sentence_ids': [],
        'text': question,
        'question': question,
        'title': _short_title_from_question(question),
        'options': opts,
        'custom_options': True,
        'ontology': {'rdf_types': ['DecisionJuncture']},
        'participants': [],
        'temporal': {},
        'precedes': [],
        'order': (seq + 1000) * 10,
        'question_source': True
    }

def _short_title_from_question(q: str) -> str:
    q_clean = q.rstrip(' ?')
    if len(q_clean) > 80:
        q_clean = q_clean[:77] + '…'
    q_clean = re.sub(r'^(Should|Would|Is|Was|Were)\s+', '', q_clean, flags=re.I)
    return q_clean[:1].upper() + q_clean[1:]

def _generate_options(question: str) -> List[Dict[str, Any]]:
    ql = question.lower()
    base: List[Dict[str, Any]] = []
    def opt(label, desc):
        return {'id': str(uuid.uuid4()), 'label': label, 'description': desc}
    if 'disclos' in ql:
        base = [
            opt('Full Disclosure', 'Explicitly disclose AI assistance / issue to all stakeholders'),
            opt('Selective Disclosure', 'Disclose only to internal management or client lead'),
            opt('Defer Disclosure', 'Delay disclosure pending further clarification'),
            opt('No Disclosure', 'Treat as ordinary tool use and do not disclose')
        ]
    elif 'ai' in ql and ('ethical' in ql or 'appropriate' in ql):
        base = [
            opt('Use With Oversight', 'Use AI but perform rigorous human review and validation'),
            opt('Limited Use', 'Use AI only for drafting non-technical sections'),
            opt('Full Reliance', 'Rely extensively on AI generated content'),
            opt('Do Not Use', 'Avoid AI entirely for this task')
        ]
    elif 'report' in ql and 'accuracy' in ql:
        base = [
            opt('Independent Verification', 'Cross-check all AI outputs with independent calculations'),
            opt('Spot Check', 'Verify only critical sections of the report'),
            opt('Accept Output', 'Accept AI drafted report with minimal edits')
        ]
    else:
        base = [
            opt('Escalate', 'Seek guidance or oversight before acting'),
            opt('Proceed with Caution', 'Continue while monitoring ethical risk'),
            opt('Pause & Reassess', 'Temporarily halt to gather more information'),
            opt('Maintain Status Quo', 'Change nothing until required')
        ]
    return base[:5]
