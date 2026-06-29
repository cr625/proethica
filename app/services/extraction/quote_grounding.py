"""Quote-grounding filter: drop extracted entities whose every supporting quote is fabricated.

The LLM is instructed to populate ``text_references`` with quotes from the case. An entity whose
quotes have no counterpart in the case text is a hallucination. This is a global grounding tool that
mirrors ``precedent_filter``.

NOTE: as of 2026-06-29 this module is NOT wired into live extraction. The model A/B found it over-
corrects on an abstractive model (Opus paraphrases the case, so its faithful ``text_references`` fail
the check) and even the semantic test below cannot separate faithful paraphrase from fabrication on
that output distribution; anti-fabrication is carried by the prompt directive instead. The module is
retained for the offline A/B audit harness and as a candidate for commit-time / review-gate grounding.

A quote is grounded when ANY of three tests passes, cheapest first:
  1. its normalized token string is a contiguous substring of the case (verbatim, any length);
  2. a sufficient fraction of its word 5-gram shingles appear in the case (a lightly reworded quote);
  3. its embedding is close (cosine) to some case sentence (a faithful ABSTRACTIVE paraphrase).

The third test is the load-bearing change. Tests 1-2 are purely LEXICAL: they answer "is this a
verbatim or near-verbatim quote", which is a good proxy for grounding only when the model quotes the
case word-for-word. A more capable model (Opus 4.8) instead writes faithful *summaries* of the case
in ``text_references`` -- the A/B audit (2026-06-28) found it dropped 8 legitimate, ontology-matched
obligations (incl. Confidentiality and Safety) on case 7 because its paraphrases share few exact
n-grams with the source even though their CONTENT is squarely in the case. Grounding is semantic, not
lexical; the embedding test measures whether the quote's MEANING is attested in the case, so it keeps
a faithful paraphrase and still rejects a quote whose content has no neighbor in the case (a true
fabrication). Tests 1-2 remain as free fast-paths so a verbatim quote never pays for an embedding.

Only entities whose EVERY quote is ungrounded are dropped (a single grounded quote keeps the entity),
so the filter is precision-favoring.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, List, Tuple, TypeVar

from app.services.extraction.rules import Rule, RuleSet

T = TypeVar("T")

_WORD = re.compile(r"[a-z0-9]+")
_N = 5                       # shingle size (contiguous words) for the lexical coverage test
_GROUNDED_COVERAGE = 0.5     # a reworded quote is grounded if >= this fraction of its shingles appear
_SEMANTIC_THRESHOLD = 0.6    # a paraphrased quote is grounded if its cosine to some case sentence >= this
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")  # split the case into sentences for the semantic test


def _tokens(text: str | None) -> List[str]:
    return _WORD.findall((text or "").lower())


def _shingles(tokens: List[str], n: int = _N) -> List[str]:
    if len(tokens) < n:
        return [" ".join(tokens)] if tokens else []
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def _sentences(case_text: str) -> List[str]:
    """Split the case into sentence-sized units for the semantic grounding test. Fragments shorter
    than 8 characters (stray tokens, list bullets) are dropped -- they carry no embeddable meaning."""
    return [s.strip() for s in _SENTENCE.split(case_text or "") if len(s.strip()) >= 8]


def _embed(text: str) -> List[float]:
    """Embed text in the local 384-dim space (all-MiniLM-L6-v2). Uses _get_local_embedding directly,
    not get_embedding, so the case sentences and the quotes live in the SAME space and no hosted
    provider (which could return a different dimension, or a random vector on the Claude path) is ever
    consulted. Raises if the local model is unavailable -- a real misconfiguration surfaces here rather
    than being papered over."""
    from app.services.embedding.embedding_service import EmbeddingService
    return EmbeddingService.get_instance()._get_local_embedding(text)


@dataclass(frozen=True)
class GroundingIndex:
    """The case text indexed for grounding: the normalized token string (verbatim substring test), the
    word n-gram shingles (lexical coverage test), and the per-sentence embeddings (semantic test)."""
    token_string: str
    ngrams: frozenset
    sentence_embeddings: Tuple[Tuple[float, ...], ...]


@lru_cache(maxsize=8)
def build_grounding_index(case_text: str, n: int = _N) -> GroundingIndex:
    """Index the case text for grounding. Built once per (case_text, n) and cached: the nine concept
    passes over the same section reuse one embedding pass rather than re-embedding nine times. Pass the
    section text the quotes were drawn from (the live extractor passes the current section)."""
    toks = _tokens(case_text)
    sentence_embeddings = tuple(tuple(_embed(s)) for s in _sentences(case_text))
    return GroundingIndex(
        token_string=" ".join(toks),
        ngrams=frozenset(_shingles(toks, n)),
        sentence_embeddings=sentence_embeddings,
    )


def quote_coverage(quote: str | None, index: GroundingIndex, n: int = _N) -> float:
    """Fraction of the quote's n-gram shingles present in the case (0.0-1.0)."""
    sh = _shingles(_tokens(quote), n)
    if not sh:
        return 0.0
    return sum(1 for s in sh if s in index.ngrams) / len(sh)


def quote_semantic_similarity(quote: str | None, index: GroundingIndex) -> float:
    """Max cosine between the quote's embedding and any case-sentence embedding (0.0 if no sentences).
    This is the semantic grounding signal: high when the quote's meaning is attested somewhere in the
    case, regardless of exact wording."""
    if not (quote and quote.strip()) or not index.sentence_embeddings:
        return 0.0
    from app.services.embedding.similarity_utils import cosine_similarity_list
    qe = _embed(quote)
    return max(cosine_similarity_list(qe, list(se)) for se in index.sentence_embeddings)


def is_grounded(quote: str | None, index: GroundingIndex, threshold: float = _GROUNDED_COVERAGE) -> bool:
    """True if the quote is attested in the case: a verbatim normalized substring (any length), a longer
    quote whose shingle coverage clears ``threshold``, or a paraphrase whose embedding is within
    ``_SEMANTIC_THRESHOLD`` cosine of some case sentence. The lexical tests run first (free); the
    embedding is computed only for a quote that fails both."""
    q = " ".join(_tokens(quote))
    if not q:
        return False
    if q in index.token_string:
        return True
    if quote_coverage(quote, index) >= threshold:
        return True
    return quote_semantic_similarity(quote, index) >= _SEMANTIC_THRESHOLD


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
             "every supporting quote is absent from the case text, lexically and semantically "
             "(a hallucinated entity)",
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
    build_grounding_index over the case text. The single list-level entry point; apply it at each
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
