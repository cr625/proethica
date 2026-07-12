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
from typing import Dict, List, Optional

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
    """True if the quote's normalized token string is a contiguous TOKEN-ALIGNED substring of
    the case token string (the layer-1 verbatim test from quote_grounding: exact content,
    whitespace-insensitive). Both sides are space-padded so the match anchors on token
    boundaries -- the raw substring test accepted mid-word fragments ('pared the structural'
    inside 'prepared the structural'). This is both the local pre-filter AND the confirmation
    applied to an LLM-returned span."""
    q = " ".join(_tokens(quote))
    return bool(q) and f" {q} " in f" {token_string} "


# Minimum token length for an ACCEPTED repair span: without a floor, a stopword
# or word-fragment span ('the') would pass the substring confirmation and become
# an entity's sole committed grounding.
_MIN_REPAIR_SPAN_TOKENS = 3


def _structured_stream_json(client, model: str, prompt: str, schema: Dict,
                            max_tokens: int, cache_prompt: bool = False) -> Dict:
    """Stream one structured-output call and parse its JSON, retrying once on a partial response.

    Structured outputs guarantee FORMAT only for a COMPLETE response: a stream cut by max_tokens
    or a dropped connection delivers unparseable partial JSON (case-6 run 30 lost a whole commit
    sub-task to one ~450-char partial over-reach vote response). The retry doubles the token cap
    in case the cut was max_tokens; a second failure propagates -- the callers' contract is
    surface-the-error, and the commit path re-runs the gate on its next sub-task.

    ``cache_prompt`` marks the prompt as a cached prefix (5-minute TTL). Set it ONLY where the
    identical prompt is re-sent within the TTL (the over-reach vote panel sends it five times);
    a breakpoint on a never-re-read prompt just pays the 1.25x cache-write premium. Below the
    model's minimum cacheable length (4096 tokens on the Opus gate tier) the marker is a silent
    no-op -- no write premium, no reads -- so short-case prompts neither pay nor save."""
    content = ([{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}]
               if cache_prompt else prompt)
    for attempt in range(2):
        chunks: List[str] = []
        with client.messages.stream(
            model=model, max_tokens=max_tokens * (attempt + 1),
            messages=[{"role": "user", "content": content}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        ) as stream:
            for t in stream.text_stream:
                chunks.append(t)
            final = stream.get_final_message()
        text = "".join(chunks)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            if attempt == 0:
                logger.warning(
                    f"structured stream returned unparseable JSON "
                    f"(stop={final.stop_reason}, {len(text)} chars): {e}; retrying once")
                continue
            raise


@dataclass
class QuoteVerdict:
    """Per-entity outcome of the grounding pass."""
    label: str
    kept_verbatim: List[str] = field(default_factory=list)   # quotes already exact substrings
    regrounded: List[str] = field(default_factory=list)      # paraphrases replaced by a verified span
    unsupported: List[str] = field(default_factory=list)     # paraphrases with no case span (fabrication)


def verify_and_reground(case_text: str, entities: List[Dict], model: Optional[str] = None) -> List[QuoteVerdict]:
    """Re-ground each entity's paraphrased quotes to verified verbatim spans.

    ``entities`` is a list of dicts with 'label', 'definition', 'quotes'. Returns one QuoteVerdict
    per entity, aligned by index. Quotes already verbatim pass through untouched; paraphrases are
    sent to Opus for span-finding in ONE batched call, and a returned span is accepted only if it
    is a real substring of the case. Raises rather than silently degrading if no LLM client is
    available (dev-mode contract: surface misconfiguration, do not paper over it)."""
    from model_config import ModelConfig
    model = model or ModelConfig.get_claude_model("gate")
    # The verifier needs only the verbatim substring test, so build the normalized token string
    # directly rather than build_grounding_index (which also embeds every case sentence for the
    # semantic test -- pure waste here).
    ts = " ".join(_tokens(case_text))

    # 1. Local pass (free): partition each entity's quotes into already-verbatim vs needs-regrounding.
    verdicts = [QuoteVerdict(label=str(e.get('label') or '?')) for e in entities]
    pending: List[tuple] = []   # (entity_index, quote) pairs needing a span from the model
    for i, e in enumerate(entities):
        quotes = [q for q in (e.get('quotes') or []) if q and str(q).strip()]
        for q in quotes:
            if _verbatim(q, ts):
                verdicts[i].kept_verbatim.append(q)
            else:
                pending.append((i, q))
        if not quotes and e.get('require_quote'):
            # Quoteless entity in a component whose contract is verbatim
            # grounding: previously it skipped this pass entirely (the one
            # bypass of the fabrication check -- text_references=[] meant no
            # grounding ever ran). Ask for a span supporting the entity
            # itself; a confirmed span repairs it (the entity gains its
            # grounding), no span marks it a fabrication candidate.
            pending.append((i, None))

    if not pending:
        return verdicts

    # 2. One Opus call to find the verbatim span for each pending paraphrase.
    lines = []
    for pid, (i, q) in enumerate(pending):
        e = entities[i]
        if q is None:
            lines.append(f'[{pid}] {e.get("label")} -- {e.get("definition") or ""}\n'
                         f'     current: NONE (extracted without any quote; find the supporting span)')
        else:
            lines.append(f'[{pid}] {e.get("label")} -- {e.get("definition") or ""}\n     current (paraphrase): "{q}"')
    prompt = (
        "Verify quote grounding for extracted ethics concepts. Below is a case text, then entities "
        "each with a label, a definition, and a CURRENT quote that is a paraphrase rather than an "
        "exact quote from the case (or NONE when the entity was extracted without any quote).\n\n"
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

    data = _structured_stream_json(client, model, prompt, _REGROUND_SCHEMA, max_tokens=8000)

    # 3. Confirm each returned span is a real substring before accepting; build per-entity verdicts.
    by_id = {r['id']: r for r in data.get('results', []) if isinstance(r, dict) and 'id' in r}
    if pending and not by_id:
        # The schema guarantees per-result shape, not one result per pending
        # item: an empty results array is a whole-call model failure, not a
        # verdict on any entity. Surface it; the commit stage re-runs the gate.
        raise RuntimeError(f"verify_and_reground: re-ground response carried no results "
                           f"for {len(pending)} pending quotes")
    missing = sum(1 for pid in range(len(pending)) if pid not in by_id)
    if missing:
        logger.warning(f"verify_and_reground: {missing}/{len(pending)} pending quotes got "
                       f"no result id; treating each as unsupported")
    for pid, (i, q) in enumerate(pending):
        r = by_id.get(pid)
        spans = (r.get('spans') or []) if (r and r.get('supported')) else []
        accepted = [s for s in spans
                    if _verbatim(s, ts) and len(_tokens(s)) >= _MIN_REPAIR_SPAN_TOKENS]
        if accepted:
            verdicts[i].regrounded.extend(accepted)
        else:
            verdicts[i].unsupported.append(q if q is not None else '(no quote extracted)')
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


# ----------------------------------------------------------------------------------------------------
# Over-reach detection: the verifier's SECOND check.
#
# The modality/scope over-reach (a duty stated broader or harder than the case holds) is the issue a
# prompt directive could NOT reliably prevent -- case 8's "Proactive Risk Disclosure ... before risks
# are fully quantified" and "Corrective Action Monitoring ... during periods of suspended work"
# survived the modality directive, and a keyword scan missed them because the violation lives in the
# DEFINITION, not the label. An LLM reading the definition against the case and the board's holding
# catches it. Unlike the code-guaranteed verbatim check, this is LLM JUDGMENT, so it supports
# multi-vote: run N independent passes and flag on majority. The limiting_quote it cites is confirmed
# to be a real case substring, so a flag points at an actual holding, never a hallucinated one.
# ----------------------------------------------------------------------------------------------------

_OVERREACH_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["results"],
    "properties": {"results": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["id", "overreach", "reason", "limiting_quote"],
        "properties": {
            "id": {"type": "integer"},
            "overreach": {"type": "boolean"},
            "reason": {"type": "string"},
            "limiting_quote": {"type": "string"},
        },
    }}},
}


@dataclass
class OverreachVerdict:
    label: str
    overreach: bool
    votes_for: int
    votes_total: int
    reason: str
    limiting_quote: str   # verbatim case span that limits the duty (confirmed substring), or ""


def _overreach_once(case_text: str, duty_entities: List[Dict], model: str) -> Dict[int, tuple]:
    """One judgment pass. Returns {entity_index: (overreach, reason, limiting_quote)}."""
    lines = [f'[{i}] {e.get("label")} -- {e.get("definition") or ""}' for i, e in enumerate(duty_entities)]
    prompt = (
        "Check extracted ethics duties for OVER-REACH. Below is a case (its facts and the board's "
        "discussion/holding), then extracted obligations and constraints, each with a label and "
        "definition.\n\n"
        "For each entity decide whether its definition asserts a duty BROADER or STRONGER than the case "
        "actually holds the actor responsible for. Over-reach includes: a duty attributed to an actor or "
        "role the case does not establish; an escalation, oversight, or systemic-failure duty the board "
        "does not impose; a duty asserted unconditionally or as a mandate where the case makes it "
        "conditional or discretionary ('not required until X', 'may', 'should consider', 'must decide "
        "whether to'). A duty the case genuinely holds, at the scope and strength the case states, is NOT "
        "over-reach.\n\n"
        "For each id return: overreach (true/false); reason (one sentence); and limiting_quote (the EXACT "
        "verbatim span from the case or the board's holding that limits or contradicts the asserted duty, "
        "or an empty string when not over-reach).\n\n"
        f"CASE (facts + discussion/holding):\n{case_text}\n\nENTITIES:\n" + "\n".join(lines)
    )
    from app.utils.llm_utils import get_llm_client
    client = get_llm_client()
    if not client:
        raise RuntimeError("detect_overreach: no LLM client available")
    # cache_prompt: the vote panel sends this identical prompt N times within
    # seconds -- vote 1 writes the prefix, votes 2..N read it at ~0.1x.
    data = _structured_stream_json(client, model, prompt, _OVERREACH_SCHEMA, max_tokens=4000,
                                   cache_prompt=True)
    return {r["id"]: (bool(r["overreach"]), r.get("reason", ""), r.get("limiting_quote", ""))
            for r in data.get("results", [])}


def detect_overreach(case_text: str, duty_entities: List[Dict], model: Optional[str] = None,
                     votes: int = 1) -> List[OverreachVerdict]:
    """Flag duty entities (obligations + constraints) whose definition over-reaches what the case holds.

    LLM judgment, so it supports multi-vote: runs ``votes`` independent passes and flags an entity when
    a strict majority call it over-reach (votes=1 is a single pass). The limiting quote is taken from a
    flagging pass and confirmed to be a real case substring, so the flag cites an actual holding."""
    from model_config import ModelConfig
    model = model or ModelConfig.get_claude_model("gate")
    ts = " ".join(_tokens(case_text))
    tally: List[List[tuple]] = [[] for _ in duty_entities]
    for _ in range(max(1, votes)):
        res = _overreach_once(case_text, duty_entities, model)
        for i in range(len(duty_entities)):
            tally[i].append(res.get(i, (False, "", "")))

    verdicts: List[OverreachVerdict] = []
    for i, e in enumerate(duty_entities):
        passes = tally[i]
        n_over = sum(1 for o, _, _ in passes if o)
        reason, lim = "", ""
        for o, r, q in passes:
            if o:
                reason = reason or r
                if not lim and q and _verbatim(q, ts):
                    lim = q
        verdicts.append(OverreachVerdict(
            label=str(e.get('label') or '?'),
            overreach=(n_over * 2 > len(passes)),
            votes_for=n_over, votes_total=len(passes), reason=reason, limiting_quote=lim))
    return verdicts
