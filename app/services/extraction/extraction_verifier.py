"""Extraction verification pass: re-ground paraphrased quotes to verified verbatim spans.

The batch-1 corpus review found that Opus 4.8 gets the CONCEPTS right but often composes its
``text_references`` as faithful paraphrases of the case rather than exact spans. A prompt directive
to quote verbatim shifts the distribution but does not guarantee it (it held on case 8, only
partly on case 5). This module makes grounding a VERIFIED post-step instead of a hoped-for prompt
behavior: for every quote that is not already a verbatim substring of the case, it asks Opus 4.8
for the exact supporting span, then CONFIRMS that returned span is a real substring before
accepting it. A paraphrase that no span can support is reported as ungrounded -- a fabrication
candidate to drop or flag.

This is the detection counterpart to the (retired) quote_grounding FILTER. The filter DROPPED an
entity whose quotes looked ungrounded, which over-corrected on an abstractive model; this REPAIRS
the quote to the verbatim span the entity is actually about, and only flags the genuinely
unsupported. The LLM does the span-finding (judgment); code validates the result (the substring
check), so an accepted quote is provably verbatim rather than trusted. Intended to run at the end
of extraction / as the commit-time review gate.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List

from app.services.extraction.quote_grounding import _tokens

logger = logging.getLogger(__name__)

# Strict structured-output schema (additionalProperties:false on every object + every property in
# ``required``), so the re-ground call returns guaranteed-parseable JSON without a free-form parse
# step. Small enough to stay well under the compiled-grammar size ceiling. See
# schemas.to_structured_output_schema for the strictness rationale.
_REGROUND_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["results"],
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "supported", "spans"],
                "properties": {
                    "id": {"type": "integer"},
                    "supported": {"type": "boolean"},
                    "spans": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}


def _verbatim(quote: str | None, token_string: str) -> bool:
    """True if the quote's normalized token string is a contiguous substring of the case token
    string (the layer-1 verbatim test from quote_grounding: exact content, whitespace-insensitive).
    This is both the local pre-filter AND the confirmation applied to an LLM-returned span."""
    q = " ".join(_tokens(quote))
    return bool(q) and q in token_string


@dataclass
class QuoteVerdict:
    """Per-entity outcome of the grounding pass."""
    label: str
    kept_verbatim: List[str] = field(default_factory=list)   # quotes already exact substrings
    regrounded: List[str] = field(default_factory=list)      # paraphrases replaced by a verified span
    unsupported: List[str] = field(default_factory=list)     # paraphrases with no case span (fabrication)


def verify_and_reground(case_text: str, entities: List[Dict], model: str = 'claude-opus-4-8') -> List[QuoteVerdict]:
    """Re-ground each entity's paraphrased quotes to verified verbatim spans.

    ``entities`` is a list of dicts with 'label', 'definition', 'quotes'. Returns one QuoteVerdict
    per entity, aligned by index. Quotes already verbatim pass through untouched; paraphrases are
    sent to Opus for span-finding in ONE batched call, and a returned span is accepted only if it
    is a real substring of the case. Raises rather than silently degrading if no LLM client is
    available (dev-mode contract: surface misconfiguration, do not paper over it)."""
    # The verifier needs only the verbatim substring test, so build the normalized token string
    # directly rather than build_grounding_index (which also embeds every case sentence for the
    # semantic test -- pure waste here).
    ts = " ".join(_tokens(case_text))

    # 1. Local pass (free): partition each entity's quotes into already-verbatim vs needs-regrounding.
    verdicts = [QuoteVerdict(label=str(e.get('label') or '?')) for e in entities]
    pending: List[tuple] = []   # (entity_index, quote) pairs needing a span from the model
    for i, e in enumerate(entities):
        for q in (e.get('quotes') or []):
            if not (q and q.strip()):
                continue
            if _verbatim(q, ts):
                verdicts[i].kept_verbatim.append(q)
            else:
                pending.append((i, q))

    if not pending:
        return verdicts

    # 2. One Opus call to find the verbatim span for each pending paraphrase.
    lines = []
    for pid, (i, q) in enumerate(pending):
        e = entities[i]
        lines.append(f'[{pid}] {e.get("label")} -- {e.get("definition") or ""}\n     current (paraphrase): "{q}"')
    prompt = (
        "Verify quote grounding for extracted ethics concepts. Below is a case text, then entities "
        "each with a label, a definition, and a CURRENT quote that is a paraphrase rather than an "
        "exact quote from the case.\n\n"
        "For each entity id, return the EXACT verbatim span(s) from the case text that support its "
        "label and definition -- copied character-for-character as a real contiguous substring of "
        "the case (1-2 best spans, prefer the single most on-point sentence or clause). If NO span "
        "in the case supports the entity, return supported=false with an empty spans list.\n\n"
        f"CASE TEXT:\n{case_text}\n\nENTITIES:\n" + "\n".join(lines)
    )

    from app.utils.llm_utils import get_llm_client
    client = get_llm_client()
    if not client:
        raise RuntimeError("verify_and_reground: no LLM client available")

    chunks: List[str] = []
    with client.messages.stream(
        model=model,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": _REGROUND_SCHEMA}},
    ) as stream:
        for t in stream.text_stream:
            chunks.append(t)
    data = json.loads("".join(chunks))

    # 3. Confirm each returned span is a real substring before accepting; build per-entity verdicts.
    by_id = {r['id']: r for r in data.get('results', [])}
    for pid, (i, q) in enumerate(pending):
        r = by_id.get(pid)
        accepted = [s for s in (r.get('spans') or []) if r and r.get('supported') and _verbatim(s, ts)]
        if accepted:
            verdicts[i].regrounded.extend(accepted)
        else:
            verdicts[i].unsupported.append(q)
    return verdicts


def grounding_summary(verdicts: List[QuoteVerdict]) -> Dict[str, int]:
    """Aggregate counts for a quick read of a verification pass."""
    return {
        "entities": len(verdicts),
        "already_verbatim": sum(len(v.kept_verbatim) for v in verdicts),
        "regrounded": sum(len(v.regrounded) for v in verdicts),
        "unsupported": sum(len(v.unsupported) for v in verdicts),
        "entities_with_a_fabricated_quote": sum(1 for v in verdicts if v.unsupported),
    }
