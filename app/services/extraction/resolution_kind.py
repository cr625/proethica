"""resolutionKind classifier for ResolutionPattern individuals.

Assigns proeth:resolutionKind (override, specification, dissolution) to a
case's existing proeth-cases:ResolutionPattern individuals. Unlike the edge
extractors, this module mints nothing: it adds at most one datatype triple
per already-committed pattern, and abstains where the pattern records plain
violation or compliance reasoning with no two-duty tension.

The value vocabulary matches the proeth:resolutionKind declaration in
proethica-intermediate.ttl. The defeasibility applier independently marks
prevailsOver derivation records "override"; this classifier is the
counterpart for cases the board resolved without defeat edges, the majority
mode identified by the 2026-07-25 recall audit (boundary specification).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import List, Optional

from .edge_extractor_base import StreamingEdgeExtractor
from .schemas import ResolutionKindAssignment, ResolutionKindResult

logger = logging.getLogger(__name__)

_VALID_KINDS = {"override", "specification", "dissolution"}


@dataclass
class PatternContext:
    """One ResolutionPattern individual with its linked conclusion."""
    iri: str
    label: str
    text: str
    conclusion_label: Optional[str] = None
    conclusion_text: Optional[str] = None
    conclusion_type: Optional[str] = None


_SYSTEM_PROMPT = """You classify how an engineering ethics review board resolved an apparent tension between professional obligations, based on resolution-pattern records extracted from board opinions.

DEFAULT TO ABSTAINING. Most patterns record ordinary violation or compliance reasoning and receive NO assignment. Assign a kind ONLY when the pattern text itself names TWO professional obligations of the SAME professional and records the board disposing of the tension between them. An expected corpus-wide outcome is that many cases receive zero assignments.

Kinds:
- "override": the pattern records both duties applying, with the board resolving which one PREVAILS (one duty yields, is overridden, or is subordinated). Reserve this for explicit priority language between two named duties.
- "specification": the pattern records the board resolving the apparent tension by defining a duty's SCOPE or BOUNDARY so that only one duty actually applies (the duty "does not extend to", "applies only when", "arises only if").
- "dissolution": the pattern records the board finding the apparent conflict not real on the facts (no genuine tension existed, or the duties are jointly satisfiable and were both discharged).

NEVER assign for:
- a duty weighed against a party's interest, preference, cost concern, or convenience (that is not a second duty);
- application of a single duty, rule, or code section to facts, however contested;
- duties of two DIFFERENT people or parties adjudicated separately;
- a tension a party alleged but the board did not itself analyze;
- generic balancing rhetoric that does not name both duties.

Rules:
- Use ONLY the pattern IRIs supplied. Never invent an IRI.
- At most one assignment per pattern.
- evidence must be a verbatim fragment of the supplied pattern or conclusion text and must contain the resolving language.
- When it is ambiguous whether a second duty is in play at all, ABSTAIN. Only lower confidence for ambiguity BETWEEN kinds, never as a substitute for abstaining.

Output JSON only:
{"assignments": [{"pattern_iri": "...", "kind": "specification", "evidence": "...", "confidence": 0.8}]}
"""

_REFUTER_SYSTEM_PROMPT = """You adversarially audit proposed classifications of engineering-ethics resolution patterns. Each proposal claims a pattern records the board resolving a tension between TWO professional obligations of the SAME professional, by override (one duty prevails), specification (a duty boundary is defined so only one applies), or dissolution (the conflict is not real on the facts).

For each proposal, try to REFUTE it:
- Does the pattern text actually name two obligations of the same professional, or is one side an interest, preference, cost, or another party's duty?
- Does the board itself do the resolving in the quoted text, or is this single-duty application dressed in balancing rhetoric?
- Is the evidence fragment verbatim and does it carry the resolving language?
- Is the kind right (priority language for override; boundary language for specification; no-real-conflict language for dissolution)?

DEFAULT TO REFUTING when uncertain. Output JSON only:
{"verdicts": [{"pattern_iri": "...", "upheld": true, "note": "..."}]}
"""


def create_resolution_kind_prompt(patterns: List[PatternContext], case_id: int) -> str:
    lines = [
        f"Case {case_id}: classify the resolution kind of each pattern below, "
        "abstaining where no two-duty tension is recorded.",
        "",
    ]
    for p in patterns:
        lines.append(f"PATTERN {p.iri}")
        lines.append(f"  text: {p.text}")
        if p.conclusion_label or p.conclusion_text:
            lines.append(
                f"  resolves conclusion: {p.conclusion_label or ''}"
                + (f" [{p.conclusion_type}]" if p.conclusion_type else "")
            )
            if p.conclusion_text:
                lines.append(f"  conclusion text: {p.conclusion_text}")
        lines.append("")
    return "\n".join(lines)


class ResolutionKindClassifier(StreamingEdgeExtractor):
    """LLM-backed classifier over a case's ResolutionPattern individuals."""

    log_label = "ResolutionKind"
    default_max_tokens = 16000
    # A swallowed stream error would be indistinguishable from corpus-wide
    # abstention (empty result recorded as a successful no_assignments), so
    # let it propagate; the driver reports the case as failed.
    swallow_stream_errors = False

    def _default_model(self) -> str:
        # Mechanical classification over supplied text: default tier, matching
        # the defeasibility extractor's ratified assignment.
        from model_config import ModelConfig
        return ModelConfig.get_claude_model("default")

    def _system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    def classify(
        self, case_id: int, patterns: List[PatternContext],
    ) -> List[ResolutionKindAssignment]:
        """Classify one case's patterns. Returns [] when the case has no
        patterns, the LLM abstains everywhere, or nothing validates."""
        if not patterns:
            return []

        prompt = create_resolution_kind_prompt(patterns, case_id)
        self.last_prompt = prompt
        raw = self._stream_llm(prompt)
        self.last_raw_response = raw
        if not raw:
            logger.warning("Case %s: resolutionKind LLM returned no response", case_id)
            return []

        assignments = self._parse(raw)
        valid_iris = {p.iri for p in patterns}
        kept = []
        seen = {}
        for a in assignments:
            if a.pattern_iri not in valid_iris:
                logger.warning(
                    "Case %s: dropping assignment for unknown pattern IRI %s",
                    case_id, a.pattern_iri,
                )
                continue
            if a.kind not in _VALID_KINDS:
                continue
            prev = seen.get(a.pattern_iri)
            if prev is None or a.confidence > prev.confidence:
                seen[a.pattern_iri] = a
        kept = list(seen.values())
        logger.info(
            "Case %s: %d resolutionKind assignment(s) over %d pattern(s)",
            case_id, len(kept), len(patterns),
        )
        return kept

    def refute(
        self,
        case_id: int,
        patterns: List[PatternContext],
        assignments: List[ResolutionKindAssignment],
    ) -> List[ResolutionKindAssignment]:
        """Adversarial second pass: keep only assignments the refuter upholds.

        The refuter sees the same pattern texts plus the proposals and is
        instructed to refute by default; an assignment survives only on an
        explicit upheld=true verdict for its pattern IRI."""
        if not assignments:
            return []
        by_iri = {p.iri: p for p in patterns}
        lines = [f"Case {case_id}: audit these proposals.", ""]
        for a in assignments:
            p = by_iri.get(a.pattern_iri)
            lines.append(f"PROPOSAL pattern_iri={a.pattern_iri}")
            lines.append(f"  claimed kind: {a.kind} (confidence {a.confidence})")
            lines.append(f"  claimed evidence: {a.evidence}")
            if p:
                lines.append(f"  pattern text: {p.text}")
                if p.conclusion_text:
                    lines.append(f"  conclusion text: {p.conclusion_text}")
            lines.append("")
        prompt = "\n".join(lines)

        original_system = self._system_prompt
        self._system_prompt = lambda: _REFUTER_SYSTEM_PROMPT  # type: ignore[method-assign]
        try:
            raw = self._stream_llm(prompt)
        finally:
            self._system_prompt = original_system  # type: ignore[method-assign]
        if not raw:
            logger.warning(
                "Case %s: resolutionKind refuter returned no response; "
                "keeping nothing (refute-by-default)", case_id)
            return []

        upheld_iris = set()
        data = _decode_json_payload(raw)
        if isinstance(data, dict):
            for v in data.get("verdicts", []):
                if isinstance(v, dict) and v.get("upheld") is True and v.get("pattern_iri"):
                    upheld_iris.add(v["pattern_iri"])
        else:
            for obj in StreamingEdgeExtractor._iter_flat_json_objects(raw):
                if obj.get("upheld") is True and obj.get("pattern_iri"):
                    upheld_iris.add(obj["pattern_iri"])

        kept = [a for a in assignments if a.pattern_iri in upheld_iris]
        logger.info(
            "Case %s: refuter upheld %d of %d assignment(s)",
            case_id, len(kept), len(assignments),
        )
        return kept

    @staticmethod
    def _parse(raw: str) -> List[ResolutionKindAssignment]:
        data = _decode_json_payload(raw)
        if isinstance(data, dict):
            try:
                result = ResolutionKindResult(**data).assignments
            except Exception:
                result = []
            if result:
                return result
            # A clean parse with zero assignments is trusted only when the
            # payload carries no assignment-shaped objects at all; otherwise
            # the top-level key drifted (extra keys are silently ignored by
            # the model config) and the salvage path must run.
            if '"pattern_iri"' not in raw:
                return []
        # Brace-walking recovery, matching the edge-extractor convention:
        # salvage individually valid assignment objects from a truncated,
        # wrapper-damaged, or wrapper-renamed stream.
        out = []
        for obj in StreamingEdgeExtractor._iter_flat_json_objects(raw):
            try:
                out.append(ResolutionKindAssignment(**obj))
            except Exception:
                continue
        return out


def _decode_json_payload(raw: str):
    """Best-effort decode of an LLM JSON payload: tolerates code fences with
    any label casing and prose before or after the JSON object by decoding
    from the first opening brace. Returns None when nothing decodes."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text[:4].lower() == "json":
            text = text[4:]
    start = text.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
        return obj
    except Exception:
        return None
