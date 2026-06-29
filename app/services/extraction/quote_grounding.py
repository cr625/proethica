"""Quote-grounding filter: drop extracted entities whose every supporting quote is fabricated.

The LLM is instructed to populate ``text_references`` with verbatim quotes from the case. An entity
whose quotes do not appear in the case text is a hallucination (e.g. the case-7 "Responsible Charge
Principle" carried the quote "bore responsible charge over AI-assisted design documents", which has
zero hits in the case). This centralizes the check so every extractor applies the same rule, mirroring
``precedent_filter``. Deterministic, no LLM.

A quote is grounded when EITHER its normalized token string is a contiguous substring of the case
(verbatim, any length), OR a sufficient fraction of its word 5-gram shingles appear in the case (a
lightly reworded real quote). The two-test design matters: a plain substring check over-flags real
quotes the LLM normalized; bag-of-words coverage under-flags a fabrication that reuses the case's own
words in an invented phrasing (its words are present but its contiguous sequences are not). Together
they pass verbatim and lightly-reworded quotes while rejecting invented phrasings. Only entities whose
EVERY quote is ungrounded are dropped (a single grounded quote keeps the entity), so the filter is
precision-favoring.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Tuple, TypeVar

from app.services.extraction.rules import Rule, RuleSet

T = TypeVar("T")

_WORD = re.compile(r"[a-z0-9]+")
_N = 5                       # shingle size (contiguous words) for the coverage fallback
_GROUNDED_COVERAGE = 0.5     # a longer reworded quote is grounded if >= this fraction of shingles appear


def _tokens(text: str | None) -> List[str]:
    return _WORD.findall((text or "").lower())


def _shingles(tokens: List[str], n: int = _N) -> List[str]:
    if len(tokens) < n:
        return [" ".join(tokens)] if tokens else []
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


@dataclass(frozen=True)
class GroundingIndex:
    """The case text indexed for grounding: the normalized token string (for substring matching, any
    quote length) and the set of word n-gram shingles (for the reworded-quote coverage fallback)."""
    token_string: str
    ngrams: frozenset


def build_grounding_index(case_text: str, n: int = _N) -> GroundingIndex:
    """Index the FULL case text (all sections) for grounding. Build once per case."""
    toks = _tokens(case_text)
    return GroundingIndex(token_string=" ".join(toks), ngrams=frozenset(_shingles(toks, n)))


def quote_coverage(quote: str | None, index: GroundingIndex, n: int = _N) -> float:
    """Fraction of the quote's n-gram shingles present in the case (0.0-1.0)."""
    sh = _shingles(_tokens(quote), n)
    if not sh:
        return 0.0
    return sum(1 for s in sh if s in index.ngrams) / len(sh)


def is_grounded(quote: str | None, index: GroundingIndex, threshold: float = _GROUNDED_COVERAGE) -> bool:
    """True if the quote is attested in the case: a verbatim normalized substring (any length), or a
    longer quote whose shingle coverage clears the threshold."""
    q = " ".join(_tokens(quote))
    if not q:
        return False
    if q in index.token_string:
        return True
    return quote_coverage(quote, index) >= threshold


def all_quotes_ungrounded(quotes: List[str] | None, index: GroundingIndex) -> bool:
    """True iff there is at least one supporting quote and EVERY one is ungrounded (fabricated). An
    entity with no quotes is NOT flagged (absence of quotes is a separate quality concern); a single
    grounded quote keeps the entity."""
    qs = [q for q in (quotes or []) if q and q.strip()]
    return bool(qs) and all(not is_grounded(q, index) for q in qs)


@dataclass(frozen=True)
class GroundingContext:
    """What the quote-grounding rule may inspect about an extracted entity."""
    label: str | None
    quotes: Tuple[str, ...] | None
    index: GroundingIndex


GROUNDING_RULES: RuleSet[GroundingContext] = RuleSet(
    name="quote_grounding",
    rules=[
        Rule("fabricated_all_quotes_ungrounded",
             "every supporting quote is absent from the case text (a hallucinated entity)",
             lambda c: all_quotes_ungrounded(list(c.quotes or ()), c.index)),
    ],
)


def drop_ungrounded_entities(
    items: List[T],
    get_label: Callable[[T], str | None],
    get_quotes: Callable[[T], List[str] | None],
    index: GroundingIndex,
) -> Tuple[List[T], List[str]]:
    """Partition items into (kept, dropped_labels) by GROUNDING_RULES: drop entities whose every
    supporting quote is fabricated (absent from the case text). ``index`` comes from
    build_grounding_index over the full case text. The single list-level entry point; apply it at each
    extraction site alongside drop_contaminated_entities, and only when the index is non-empty (an
    empty case text would score every quote ungrounded)."""
    def to_ctx(it: T) -> GroundingContext:
        quotes = get_quotes(it)
        return GroundingContext(
            label=get_label(it),
            quotes=tuple(quotes) if quotes else None,
            index=index,
        )

    kept, hits = GROUNDING_RULES.partition(items, to_ctx, get_label)
    return kept, [h.label for h in hits]
