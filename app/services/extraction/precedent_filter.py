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

# Precedent-citation markers anywhere in a label or supporting quote:
#   BER [Case] [No.] NN-N -> "BER 07-6", "BER Case 19-3", "BER Case No. 00-5"
#   Case [No.] NN-N       -> "Case 04-11", "Case No. 92-1"
#   Doe                   -> placeholder party from a cited precedent
# The optional "No." token was added 2026-06-18 after a clean-labeled phantom
# ("Public Works Director", attested only by "BER Case No. 00-5 centered on ...")
# slipped the "Case NN-N"-only pattern when the clean-label rule below began testing quotes.
PRECEDENT_REF_RE = re.compile(
    r"\bBER\s+(?:Case\s+)?(?:No\.?\s+)?\d{2}-\d{1,2}\b"
    r"|\bCase\s+(?:No\.?\s+)?\d{2}-\d{1,2}\b"
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
    """True if the label/quote names/derives from a cited precedent case, OR is a generic
    precedent-placeholder label with no present-case content."""
    return bool(label and (PRECEDENT_REF_RE.search(label) or GENERIC_PRECEDENT_RE.match(label)))


# Concept types whose entities are NORMS. A cited precedent is invoked precisely because
# its norms apply to the case under analysis, so a clean-labeled principle/obligation/
# constraint is NOT dropped just because its supporting quote cites the precedent. Fact
# concepts (roles, states, resources, capabilities; and the Step-3 actions/events) get the
# clean-label provenance rule below: a fact attested ONLY in cited-precedent text belongs
# to the precedent, not this case.
NORM_CONCEPT_TYPES = frozenset({"principles", "obligations", "constraints"})


def _all_quotes_are_precedent(quotes: List[str] | None) -> bool:
    """True iff there is at least one supporting quote and EVERY one is a precedent
    reference -- i.e. the entity is attested only in cited-precedent context. A single
    non-precedent quote keeps the entity (it appears in the present case too), so a
    current-case entity that merely mentions a precedent in one quote is preserved."""
    qs = [q for q in (quotes or []) if q and q.strip()]
    return bool(qs) and all(is_precedent_reference(q) for q in qs)


def is_precedent_entity(
    label: str | None,
    quotes: List[str] | None = None,
    concept_type: str | None = None,
) -> bool:
    """Whether an extracted entity should be dropped as precedent contamination.

    Combines the label-marker rule (every concept type -- a citation marker in the label
    is itself a contamination artifact) with clean-label provenance detection (fact
    concepts only): an entity whose label is clean but whose every supporting quote sits
    in cited-precedent context is a phantom precedent entity (e.g. "Public Works Director"
    attested only by "BER Case No. 00-5 centered on ..."). Norm concepts are exempt from
    the clean-label rule because a cited precedent's norms transfer to the present case."""
    if is_precedent_reference(label):
        return True
    if concept_type not in NORM_CONCEPT_TYPES and _all_quotes_are_precedent(quotes):
        return True
    return False


def drop_precedent_entities(
    items: List[T],
    get_label: Callable[[T], str | None],
    get_quotes: Callable[[T], List[str] | None] | None = None,
    concept_type: str | None = None,
) -> Tuple[List[T], List[str]]:
    """Partition items into (kept, dropped_labels). Drops by the label-marker rule (all
    concept types); additionally, when get_quotes is supplied and concept_type is a fact
    concept, by the clean-label provenance rule (every supporting quote is a precedent
    reference). Label-only callers omit get_quotes and keep the original behavior."""
    kept: List[T] = []
    dropped: List[str] = []
    for it in items:
        lbl = get_label(it)
        quotes = get_quotes(it) if get_quotes else None
        if is_precedent_entity(lbl, quotes, concept_type):
            dropped.append(lbl or "")
        else:
            kept.append(it)
    return kept, dropped
