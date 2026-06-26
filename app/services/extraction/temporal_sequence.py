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


# The temporal-sequence SYSTEM prompt and user prompt now live in the editable 'temporal_sequence'
# template (extraction_prompt_templates); see _load_temporal_template() / build_user_prompt() /
# TemporalSequenceExtractor._system_prompt(). Seed: docs-internal/scripts/seed_temporal_sequence_template.py


@dataclass
class TemporalEntryContext:
    """Compact view of an Action or Event for the prompt."""
    iri: str
    kind: str              # "Action" or "Event"
    label: str
    temporal_marker: str
    description: str


def _load_temporal_template():
    """Load the editable 'temporal_sequence' prompt template (prompt editor -> Shared prompts ->
    Synthesis & enrichment -> Temporal sequence). A separate function so a test can inject a stub
    without a DB / app context. Raises (no fallback) if unseeded."""
    from app.models.extraction_prompt_template import ExtractionPromptTemplate
    tmpl = ExtractionPromptTemplate.get_active_template(0, 'temporal_sequence')
    if tmpl is None:
        raise RuntimeError(
            "No 'temporal_sequence' prompt template in extraction_prompt_templates. "
            "Seed it: docs-internal/scripts/seed_temporal_sequence_template.py")
    return tmpl


def build_user_prompt(case_id: int, entries: List[TemporalEntryContext]) -> str:
    """Render the per-entry block fed to the LLM, from the editable DB template."""
    item_lines: List[str] = []
    for e in entries:
        item_lines.append(f"IRI: {e.iri}")
        item_lines.append(f"Kind: {e.kind}")
        item_lines.append(f"Label: {e.label}")
        if e.temporal_marker:
            item_lines.append(f"TemporalMarker: {e.temporal_marker}")
        if e.description:
            item_lines.append(f"Description: {e.description}")
        item_lines.append("")
    return _load_temporal_template().render(
        case_id=case_id, n_entries=len(entries), items="\n".join(item_lines))


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
        return _load_temporal_template().render_system()

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
