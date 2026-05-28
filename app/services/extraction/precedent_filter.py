"""Shared filter for precedent-case contamination in extracted entities.

NSPE Board opinions discuss prior BER cases by number ("BER Case 19-3", "Case
04-11"). The LLM extractors readily pull the *actors* and entities described inside
those cited precedents (e.g. "Defendant Attorney BER Case 19-3", "BER Case 04-11
Situation 1 Engineer") into the present case as first-class roles/states/etc. Those
are phantom entities: they belong to the precedent, not the case under analysis.

This centralizes the detection so every extractor (Step-1 roles, the Step-4 narrative
character pass, and any future use) applies the same rule. Matches the NSPE
case-number format ``[BER ]Case NN-N`` anywhere in a label.
"""
from __future__ import annotations

import re
from typing import Callable, List, Tuple, TypeVar

# [BER ]Case NN-N  (two-digit year, dash, 1-2 digit number) anywhere in the label.
PRECEDENT_REF_RE = re.compile(r"\b(?:BER\s+)?Case\s+\d{2}-\d{1,2}\b", re.IGNORECASE)

T = TypeVar("T")


def is_precedent_reference(label: str | None) -> bool:
    """True if the label names/derives from a cited precedent case."""
    return bool(label and PRECEDENT_REF_RE.search(label))


def drop_precedent_entities(
    items: List[T], get_label: Callable[[T], str | None]
) -> Tuple[List[T], List[str]]:
    """Partition items into (kept, dropped_labels) by the precedent-ref test."""
    kept: List[T] = []
    dropped: List[str] = []
    for it in items:
        lbl = get_label(it)
        if is_precedent_reference(lbl):
            dropped.append(lbl or "")
        else:
            kept.append(it)
    return kept, dropped
