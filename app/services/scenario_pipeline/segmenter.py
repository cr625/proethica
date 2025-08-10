"""Sentence and paragraph segmentation utilities for scenario pipeline (Phase A).

Deterministic segmentation (no heavy NLP yet) to provide stable sentence IDs.
"""
from __future__ import annotations
import re
from typing import List, Dict, Any

SENT_SPLIT_REGEX = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\(])')


def split_paragraphs(text: str) -> List[str]:
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    if not paras:
        paras = [text.strip()] if text.strip() else []
    return paras


def split_sentences(paragraph: str) -> List[str]:
    if not paragraph:
        return []
    sentences = SENT_SPLIT_REGEX.split(paragraph.strip())
    # Filter tiny fragments
    return [s.strip() for s in sentences if len(s.strip()) > 2]


def segment_sections(sections: Dict[str, Any]) -> Dict[str, Any]:
    """Segment case sections into paragraphs and sentences with IDs.

    This now tolerates alternate plural section keys ("questions", "conclusions") and
    normalises them to singular canonical labels (question, conclusion) for downstream
    heuristics. We keep the original key on each sentence/paragraph in case later
    logic wants the raw variant.

    Returns structure:
    {
        'sentences': [ { 'id': 's1', 'text': '...', 'section': 'facts', 'raw_section': 'facts', ... } ],
        'paragraphs': [ { 'id': 'p1', 'text': '...', 'section': 'facts', 'raw_section': 'facts', ... } ]
    }
    """
    sentences = []
    paragraphs = []
    sid = 1
    pid = 1
    # Candidate keys including plural fallbacks
    ordered_keys = ['facts', 'discussion', 'question', 'questions', 'conclusion', 'conclusions']
    seen_canonical = set()
    for section_key in ordered_keys:
        raw = sections.get(section_key, '')
        if isinstance(raw, dict):
            raw = raw.get('text') or raw.get('content') or ''
        if not raw:
            continue
        # Canonical mapping
        if section_key in ('questions', 'question'):
            canonical = 'question'
        elif section_key in ('conclusions', 'conclusion'):
            canonical = 'conclusion'
        else:
            canonical = section_key
        # If we've already processed a plural/singular variant, skip duplicates
        if canonical in seen_canonical and canonical in ('question', 'conclusion'):
            continue
        seen_canonical.add(canonical)
        paras = split_paragraphs(raw)
        for pi, para in enumerate(paras):
            sent_ids = []
            for si, sent in enumerate(split_sentences(para)):
                sid_str = f's{sid}'
                sentences.append({
                    'id': sid_str,
                    'text': sent,
                    'section': canonical,
                    'raw_section': section_key,
                    'paragraph_index': pi,
                    'sentence_index': si
                })
                sent_ids.append(sid_str)
                sid += 1
            paragraphs.append({
                'id': f'p{pid}',
                'text': para.strip(),
                'section': canonical,
                'raw_section': section_key,
                'sent_ids': sent_ids
            })
            pid += 1
    return {'sentences': sentences, 'paragraphs': paragraphs}
