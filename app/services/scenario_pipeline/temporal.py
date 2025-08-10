"""Temporal extraction (Phase A minimal heuristic).

Provides placeholder temporal normalization to support later enhancement.
"""
from __future__ import annotations
import re
from typing import Dict, Any, List

date_pattern = re.compile(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}', re.IGNORECASE)
year_pattern = re.compile(r'\b(19|20)\d{2}\b')


def extract_temporal(sentences: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Return mapping sentence_id -> temporal info.
    temporal info: { 'raw': 'March 2024', 'type': 'interval'|'instant'|'unknown', 'normalized': {...}, 'confidence': float }
    """
    result: Dict[str, Dict[str, Any]] = {}
    for s in sentences:
        txt = s['text']
        match = date_pattern.search(txt)
        if match:
            month_year = match.group(0)
            parts = month_year.split()
            month = parts[0]
            year = parts[1]
            # Simplistic month mapping
            month_num = {
                'january': '01','february': '02','march': '03','april': '04','may': '05','june': '06',
                'july': '07','august': '08','september': '09','october': '10','november': '11','december': '12'
            }[month.lower()]
            start = f"{year}-{month_num}-01"
            result[s['id']] = {
                'raw': month_year,
                'type': 'interval',
                'normalized': {
                    'start': start,
                    'end': None,
                    'granularity': 'month'
                },
                'confidence': 0.8
            }
            continue
        year_match = year_pattern.search(txt)
        if year_match:
            year = year_match.group(0)
            result[s['id']] = {
                'raw': year,
                'type': 'interval',
                'normalized': {
                    'start': f'{year}-01-01',
                    'end': f'{year}-12-31',
                    'granularity': 'year'
                },
                'confidence': 0.5
            }
        else:
            result[s['id']] = {
                'raw': None,
                'type': 'unknown',
                'normalized': {},
                'confidence': 0.0
            }
    return result
