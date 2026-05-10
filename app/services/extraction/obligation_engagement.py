"""
Obligation engagement (re)classifier.

Splits each Action's fulfills+violates pool into three buckets:
fulfills (directly satisfied), violates (directly breached), and raises
(put in play but resolved downstream). The pipeline writes back
`proeth:raisesObligation` and rewrites `proeth:fulfillsObligation` and
`proeth:violatesObligation` so the same obligation never appears with
contradictory polarity on adjacent steps in the chain.

Driver: `docs-internal/scripts/backfill_obligation_engagement.py`.

Reference: proethica/.claude/plans/current-application-roadmap.md
"Action Obligation Classification: Choice vs. Execution".
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from .schemas import ObligationEngagementResult, PerActionEngagement

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are an expert at reading professional ethics case opinions and "
    "classifying how each action in the case engages the obligations "
    "previously attributed to it.\n\n"
    "For each Action, you receive a pool of obligation strings already "
    "extracted as either fulfilled or violated. Your task is to "
    "reclassify that pool into three buckets: fulfills, violates, and "
    "raises.\n\n"
    "Definitions:\n"
    "  - fulfills: this specific Action directly satisfies the obligation. "
    "    Use when the action carries out what the obligation requires.\n"
    "  - violates: this specific Action directly breaches the obligation. "
    "    Use when the action does the opposite of what the obligation "
    "    requires.\n"
    "  - raises: this Action puts the obligation in play but does not "
    "    itself resolve it. The fulfillment or violation happens at a "
    "    downstream Action in the same chain (e.g., a choice to use a "
    "    tool raises a competence concern that the later review either "
    "    satisfies or breaches). Use this whenever the case opinion "
    "    treats the obligation as 'at risk' from the choice but actually "
    "    resolved by a subsequent step.\n\n"
    "Critical rules:\n"
    "- The union of fulfills + violates + raises for an Action must "
    "  EQUAL the input pool exactly. Do not invent new obligations. Do "
    "  not drop obligations.\n"
    "- Each obligation belongs in exactly one bucket per Action. Do not "
    "  duplicate within an Action.\n"
    "- Copy the obligation strings VERBATIM. Do not paraphrase.\n"
    "- When the case discussion explicitly says an obligation was met "
    "  by a later review/verification step, classify the upstream choice "
    "  as 'raises' (not 'violates'); the resolution Action gets "
    "  'fulfills' or 'violates' as the discussion concludes.\n"
    "- When in doubt and the action is the moment of resolution "
    "  (review, submission, discovery), prefer fulfills or violates. "
    "  When in doubt and the action is upstream of a clearer "
    "  resolution, prefer raises.\n\n"
    "Output JSON only:\n"
    "{\n"
    "  \"actions\": [\n"
    "    { \"action_iri\": \"<iri>\", "
    "\"fulfills\": [...], \"violates\": [...], \"raises\": [...] },\n"
    "    ...\n"
    "  ],\n"
    "  \"rationale\": \"<brief summary>\"\n"
    "}\n\n"
    "Do not wrap the JSON in prose, markdown, or code fences."
)


@dataclass
class ActionEngagementContext:
    """Compact view of an Action and its current obligation lists."""
    iri: str
    label: str
    description: str
    sequence: Optional[int]
    fulfills: List[str]
    violates: List[str]


def build_user_prompt(
    case_id: int,
    case_title: str,
    actions: List[ActionEngagementContext],
    discussion_excerpt: str = "",
) -> str:
    lines: List[str] = [
        f"Case ID: {case_id}",
        f"Case title: {case_title}",
        f"Actions to reclassify: {len(actions)}",
        "",
    ]
    if discussion_excerpt:
        lines.append("Case discussion (excerpt for grounding):")
        lines.append(discussion_excerpt.strip())
        lines.append("")
    lines.append("Actions in chronological order:")
    lines.append("")
    for a in actions:
        lines.append(f"IRI: {a.iri}")
        lines.append(f"Sequence: {a.sequence if a.sequence is not None else '?'}")
        lines.append(f"Label: {a.label}")
        if a.description:
            lines.append(f"Description: {a.description}")
        lines.append("Fulfills (input):")
        for o in a.fulfills:
            lines.append(f"  - {o}")
        lines.append("Violates (input):")
        for o in a.violates:
            lines.append(f"  - {o}")
        lines.append("")
    lines.append(
        "Reclassify each Action's pool into fulfills / violates / raises. "
        "Return JSON; the union per action must equal the input pool exactly."
    )
    return "\n".join(lines)


class ObligationEngagementExtractor:
    """LLM-backed three-way obligation classifier."""

    def __init__(
        self,
        llm_client: Any = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 16384,
    ):
        self._llm_client = llm_client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.last_prompt: Optional[str] = None
        self.last_raw_response: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        case_id: int,
        case_title: str,
        actions: List[ActionEngagementContext],
        discussion_excerpt: str = "",
    ) -> ObligationEngagementResult:
        if not actions:
            return ObligationEngagementResult(actions=[], rationale=None)

        user_prompt = build_user_prompt(case_id, case_title, actions, discussion_excerpt)
        self.last_prompt = user_prompt

        raw = self._call_llm(user_prompt)
        self.last_raw_response = raw
        if not raw:
            raise RuntimeError(
                f"case {case_id}: obligation-engagement LLM call returned no content"
            )

        result = self._parse(raw)
        self._validate(result, actions, case_id)
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._llm_client is not None:
            return self._llm_client
        from app.utils.llm_utils import get_llm_client
        self._llm_client = get_llm_client()
        return self._llm_client

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        from model_config import ModelConfig
        return ModelConfig.get_default_model()

    def _call_llm(self, user_prompt: str) -> Optional[str]:
        client = self._get_client()
        model = self._resolve_model()

        if not (hasattr(client, "messages") and hasattr(client.messages, "stream")):
            logger.error(
                "ObligationEngagementExtractor requires an Anthropic streaming client; got %s",
                type(client).__name__,
            )
            return None

        try:
            chunks: List[str] = []
            with client.messages.stream(
                model=model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                for text in stream.text_stream:
                    chunks.append(text)
                final_msg = stream.get_final_message()
            stop_reason = getattr(final_msg, "stop_reason", None)
            usage = getattr(final_msg, "usage", None)
            if usage:
                logger.info(
                    "ObligationEngagement stream complete: %d in / %d out, stop=%s",
                    usage.input_tokens, usage.output_tokens, stop_reason,
                )
            if stop_reason == "max_tokens":
                logger.warning(
                    "ObligationEngagement hit max_tokens (%d); response may be truncated",
                    self.max_tokens,
                )
            return "".join(chunks)
        except Exception as e:
            logger.error("Anthropic obligation-engagement stream failed: %s", e)
            return None

    @staticmethod
    def _parse(raw: str) -> ObligationEngagementResult:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n", "", text)
            text = re.sub(r"\n```\s*$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                raise ValueError(
                    f"obligation-engagement response was not JSON: {e}"
                ) from e
            data = json.loads(m.group(0))
        return ObligationEngagementResult(**data)

    @staticmethod
    def _normalize(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip()).lower()

    @classmethod
    def _validate(
        cls,
        result: ObligationEngagementResult,
        actions: List[ActionEngagementContext],
        case_id: int,
    ) -> None:
        input_iris = {a.iri for a in actions}
        output_iris = {pa.action_iri for pa in result.actions}
        if input_iris != output_iris:
            missing = input_iris - output_iris
            extra = output_iris - input_iris
            raise ValueError(
                f"case {case_id}: action_iris in result do not match input "
                f"(missing={sorted(missing)}, extra={sorted(extra)})"
            )

        # Per-action: union must equal input pool, no duplicates within action.
        action_by_iri = {a.iri: a for a in actions}
        for pa in result.actions:
            ctx = action_by_iri[pa.action_iri]
            input_pool: Set[str] = set()
            input_pool.update(cls._normalize(o) for o in ctx.fulfills)
            input_pool.update(cls._normalize(o) for o in ctx.violates)

            output_norms = (
                [cls._normalize(o) for o in pa.fulfills]
                + [cls._normalize(o) for o in pa.violates]
                + [cls._normalize(o) for o in pa.raises]
            )
            output_set = set(output_norms)

            if len(output_norms) != len(output_set):
                seen: Dict[str, int] = {}
                dups: List[str] = []
                for s in output_norms:
                    seen[s] = seen.get(s, 0) + 1
                    if seen[s] == 2:
                        dups.append(s)
                raise ValueError(
                    f"case {case_id} action {pa.action_iri}: an obligation appears in "
                    f"more than one bucket: {dups[:3]}"
                )

            missing = input_pool - output_set
            extra = output_set - input_pool
            if missing or extra:
                raise ValueError(
                    f"case {case_id} action {pa.action_iri}: bucket union does not "
                    f"equal input pool (missing={sorted(missing)[:3]}, "
                    f"extra={sorted(extra)[:3]})"
                )
