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
from typing import List

from .edge_extractor_base import StreamingEdgeExtractor
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


class TemporalSequenceExtractor(StreamingEdgeExtractor):
    """LLM-backed chronological-permutation extractor.

    LLM plumbing lives in `StreamingEdgeExtractor`; this class supplies the
    system prompt, the default (non-powerful) model tier, and the permutation
    parse/validation below.
    """

    log_label = "TemporalSequence"
    default_max_tokens = 8192

    def _default_model(self) -> str:
        # Chronological ordering runs on the default tier, not the powerful one.
        from model_config import ModelConfig
        return ModelConfig.get_default_model()

    def _system_prompt(self) -> str:
        return SYSTEM_PROMPT

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

        raw = self._stream_llm(user_prompt)
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
