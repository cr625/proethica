"""Shared filter for precedent-case contamination in extracted entities.

NSPE Board opinions discuss prior BER cases by number ("BER Case 19-3", "Case
04-11"). The LLM extractors readily pull the *actors* and entities described inside
those cited precedents (e.g. "Defendant Attorney BER Case 19-3", "BER Case 04-11
Situation 1 Engineer") into the present case as first-class roles/states/etc. Those
are phantom entities: they belong to the precedent, not the case under analysis.

This centralizes the detection so every extractor (Step-1 roles, the case-pipeline
UnifiedDualExtractor, Step-3 storage, the Step-4 narrative character pass, and any future
use) applies the same rule. Matches the NSPE precedent-citation forms anywhere in a label:

  * ``BER Case 19-3`` / ``Case 04-11``  (the "Case NN-N" form)
  * ``BER 07-6`` / ``BER 84-5``         (the bare "BER NN-N" form, no "Case" keyword)
  * ``Doe`` as a standalone word         (the placeholder party name -- in NSPE opinions
                                          "Engineer Doe"/"John Doe" appear only inside cited
                                          precedents; present-case actors are "Engineer A/B/L")

The "BER NN-N" and "Doe" forms were added 2026-05-28 after the case-8 Stage-1 re-extraction
pilot showed the original "Case NN-N"-only pattern leaving ~24 phantom precedent entities
(see docs-internal/reextraction/Stage1_Pilot_Case8_Results_2026-05-28.md, Finding 1). A bare
"BER" with no following number is deliberately NOT matched, to preserve legitimate present-case
entities that merely reference precedent practice (e.g. "Engineer L BER Precedent Synthesis").
"""
from __future__ import annotations

import re
from typing import Callable, List, Tuple, TypeVar

# Precedent-citation markers anywhere in a label:
#   BER [Case] NN-N   -> "BER 07-6", "BER Case 19-3"   (BER + optional "Case" + NN-N)
#   Case NN-N         -> "Case 04-11"                  (the "Case NN-N" form without BER)
#   Doe               -> placeholder party from a cited precedent
PRECEDENT_REF_RE = re.compile(
    r"\bBER\s+(?:Case\s+)?\d{2}-\d{1,2}\b"
    r"|\bCase\s+\d{2}-\d{1,2}\b"
    r"|\bDoe\b",
    re.IGNORECASE,
)

# Generic precedent PLACEHOLDER label: the WHOLE label is just the precedent phrase with no
# present-case content (e.g. "BER Case Precedent", "Precedent Reference"). The case-15 run-54
# baseline minted "BER Case Precedent" as a Resource -- a meta-reference to the citation
# mechanism, not a resource in the case. This is anchored to the full label so it does NOT
# touch legitimate present-case entities that merely mention precedent (e.g. "Engineer L BER
# Precedent Synthesis"), which the bare-"BER" exclusion above deliberately preserves.
GENERIC_PRECEDENT_RE = re.compile(
    r"^\s*(?:BER\s+)?(?:Case\s+)?Precedent(?:\s+(?:Reference|Case))?\s*$",
    re.IGNORECASE,
)

T = TypeVar("T")


def is_precedent_reference(label: str | None) -> bool:
    """True if the label names/derives from a cited precedent case, OR is a generic
    precedent-placeholder label with no present-case content."""
    return bool(label and (PRECEDENT_REF_RE.search(label) or GENERIC_PRECEDENT_RE.match(label)))


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
