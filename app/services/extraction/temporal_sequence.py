"""
Temporal sequence extractor.

Returns a chronological permutation of a case's Action/Event IRIs. Used by
the backfill driver to populate `proeth:temporalSequence` on existing
`temporary_rdf_storage` rows whose order today reflects extractor-pass
order (Actions first, Events second), not chronology.

Design choices:
- LLM is asked to return an ordered list of IRIs, not per-IRI integers.
  Set-equality validation against the input IRIs cheaply rejects
  non-permutations.
- Streaming Anthropic call (matches DefeasibilityEdgeExtractor); the
  ordering reasoning can be long for cases with 15+ entries.
- Temperature is low (0.1): chronological ordering is supposed to be
  deterministic given the inputs.

Reference: proethica/.claude/plans/current-application-roadmap.md
"Timeline Chronological Ordering".
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, List, Optional

from .schemas import TemporalSequenceResult

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are an expert at reading professional ethics case narratives and "
    "establishing the chronological order of the actions taken and events "
    "that occurred. The case is presented as a set of Action and Event "
    "individuals with labels, free-text temporal markers, and rich "
    "narrative descriptions.\n\n"
    "Your task: return a permutation of the input IRIs that places them "
    "in chronological order, earliest first. Use the temporal markers, "
    "the descriptions, and ordinary world knowledge of how engineering "
    "projects unfold to break ties. When two entries clearly happen "
    "concurrently, place the one whose effects propagate first (e.g., a "
    "data exposure before the downstream draft generation) earlier.\n\n"
    "Output JSON only, matching this schema:\n"
    "{\n"
    "  \"ordered_iris\": [\"<iri-1>\", \"<iri-2>\", ...],\n"
    "  \"rationale\": \"<one or two sentences>\"\n"
    "}\n\n"
    "Critical rules:\n"
    "- Every input IRI must appear exactly once.\n"
    "- Do not invent IRIs not present in the input.\n"
    "- Do not omit any IRI.\n"
    "- Do not wrap the JSON in prose, markdown, or code fences."
)


@dataclass
class TemporalEntryContext:
    """Compact view of an Action or Event for the prompt."""
    iri: str
    kind: str              # "Action" or "Event"
    label: str
    temporal_marker: str
    description: str


def build_user_prompt(case_id: int, entries: List[TemporalEntryContext]) -> str:
    """Render the per-entry block fed to the LLM."""
    lines: List[str] = [
        f"Case ID: {case_id}",
        f"Number of entries: {len(entries)}",
        "",
        "Entries (in arbitrary order; your job is to chronologize them):",
        "",
    ]
    for e in entries:
        lines.append(f"IRI: {e.iri}")
        lines.append(f"Kind: {e.kind}")
        lines.append(f"Label: {e.label}")
        if e.temporal_marker:
            lines.append(f"TemporalMarker: {e.temporal_marker}")
        if e.description:
            lines.append(f"Description: {e.description}")
        lines.append("")
    lines.append(
        "Return JSON with `ordered_iris` containing all of the above IRIs in "
        "chronological order (earliest first)."
    )
    return "\n".join(lines)


class TemporalSequenceExtractor:
    """LLM-backed chronological-permutation extractor."""

    def __init__(
        self,
        llm_client: Any = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 8192,
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
        entries: List[TemporalEntryContext],
    ) -> TemporalSequenceResult:
        if not entries:
            return TemporalSequenceResult(ordered_iris=[], rationale=None)

        user_prompt = build_user_prompt(case_id, entries)
        self.last_prompt = user_prompt

        raw = self._call_llm(user_prompt)
        self.last_raw_response = raw
        if not raw:
            raise RuntimeError(
                f"case {case_id}: temporal sequence LLM call returned no content"
            )

        result = self._parse(raw)
        self._validate_permutation(result.ordered_iris, entries, case_id)
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
                "TemporalSequenceExtractor requires an Anthropic streaming client; got %s",
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
                    "TemporalSequence stream complete: %d in / %d out, stop=%s",
                    usage.input_tokens, usage.output_tokens, stop_reason,
                )
            if stop_reason == "max_tokens":
                logger.warning(
                    "TemporalSequence hit max_tokens (%d); response may be truncated",
                    self.max_tokens,
                )
            return "".join(chunks)
        except Exception as e:
            logger.error("Anthropic temporal-sequence stream failed: %s", e)
            return None

    @staticmethod
    def _parse(raw: str) -> TemporalSequenceResult:
        # The system prompt forbids code fences, but tolerate them anyway.
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n", "", text)
            text = re.sub(r"\n```\s*$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            # Try extracting the first {...} block for partial recovery.
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                raise ValueError(
                    f"temporal sequence response was not JSON: {e}"
                ) from e
            data = json.loads(m.group(0))
        return TemporalSequenceResult(**data)

    @staticmethod
    def _validate_permutation(
        ordered: List[str],
        entries: List[TemporalEntryContext],
        case_id: int,
    ) -> None:
        input_set = {e.iri for e in entries}
        output_set = set(ordered)
        if len(ordered) != len(input_set):
            raise ValueError(
                f"case {case_id}: ordered_iris length {len(ordered)} "
                f"!= input length {len(input_set)}"
            )
        missing = input_set - output_set
        extra = output_set - input_set
        if missing or extra:
            raise ValueError(
                f"case {case_id}: ordered_iris is not a permutation of the "
                f"input IRIs (missing={sorted(missing)}, extra={sorted(extra)})"
            )
        if len(set(ordered)) != len(ordered):
            seen: dict = {}
            dups = []
            for iri in ordered:
                seen[iri] = seen.get(iri, 0) + 1
                if seen[iri] == 2:
                    dups.append(iri)
            raise ValueError(
                f"case {case_id}: ordered_iris contains duplicates: {dups}"
            )
