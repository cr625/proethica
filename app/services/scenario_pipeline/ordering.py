"""Ordering logic (Phase A).
Currently linear ordering; placeholder for future temporal graph topological sort.
"""
from __future__ import annotations
from typing import List, Dict, Any


def build_ordering(events: List[Dict[str, Any]]) -> List[str]:
    return [ev['id'] for ev in sorted(events, key=lambda e: e['order'])]
