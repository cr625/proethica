"""
Obligation engagement (re)classifier.

Splits each Action's fulfills+violates pool into three buckets:
fulfills (directly satisfied), violates (directly breached), and raises
(put in play but resolved downstream). The pipeline writes back
`proeth:raisesObligation` and rewrites `proeth:fulfillsObligation` and
`proeth:violatesObligation` so the same obligation never appears with
contradictory polarity on adjacent steps in the chain.

Literature grounding. The fulfills / violates pair is the causal-normative
mapping of an action to the obligations it satisfies or breaches (Sarmiento et
al. 2023, NESS causal responsibility; Berreby et al. 2017, obligations as
fulfilled/violated fluents). The third bucket, `raises`, is the temporal
refinement: rather than statically satisfying or breaching a duty, an action can
PUT AN OBLIGATION IN FORCE (at stake) that a later action resolves. This is the
Event Calculus view of an obligation as a fluent INITIATED by one happening and
fulfilled or violated by a subsequent one (Berreby et al. 2017), under the
defeasible/contextual account of obligations that come into force under
conditions (Dennis et al. 2016; Dennis & del Olmo 2021). It is the action-side
analog of the core State linkage proeth-core:activatesObligation /
defeasibleUnder: a happening raises an obligation just as a State activates one.

Driver: `docs-internal/scripts/backfill_obligation_engagement.py`.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .schemas import ObligationEngagementResult, PerActionEngagement

logger = logging.getLogger(__name__)


# The obligation-engagement SYSTEM and user prompts now live in the editable 'obligation_engagement'
# template (extraction_prompt_templates); see _load_obligation_engagement_template() / build_user_prompt() /
# _call_llm. Seed: docs-internal/scripts/seed_obligation_engagement_template.py


@dataclass
class ActionEngagementContext:
    """Compact view of an Action and its current obligation lists."""
    iri: str
    label: str
    description: str
    sequence: Optional[int]
    fulfills: List[str]
    violates: List[str]
    # Obligations already at stake on this Action from a prior engagement pass.
    # Included in the validation pool so a re-run is idempotent (does not flag a
    # previously-raised obligation as an extra).
    raises: List[str] = field(default_factory=list)


def _load_obligation_engagement_template():
    """Load the editable 'obligation_engagement' prompt template (prompt editor -> Shared prompts ->
    Synthesis & enrichment -> Obligation engagement). A separate function so a test can inject a stub
    without a DB / app context. Raises (no fallback) if unseeded."""
    from app.models.extraction_prompt_template import ExtractionPromptTemplate
    tmpl = ExtractionPromptTemplate.get_active_template(0, 'obligation_engagement')
    if tmpl is None:
        raise RuntimeError(
            "No 'obligation_engagement' prompt template in extraction_prompt_templates. "
            "Seed it: docs-internal/scripts/seed_obligation_engagement_template.py")
    return tmpl


def build_user_prompt(
    case_id: int,
    case_title: str,
    actions: List[ActionEngagementContext],
    discussion_excerpt: str = "",
) -> str:
    """Assemble the per-action blocks in code, then render the editable DB template."""
    block_lines: List[str] = []
    for a in actions:
        block_lines.append(f"IRI: {a.iri}")
        block_lines.append(f"Sequence: {a.sequence if a.sequence is not None else '?'}")
        block_lines.append(f"Label: {a.label}")
        if a.description:
            block_lines.append(f"Description: {a.description}")
        block_lines.append("Fulfills (input):")
        for o in a.fulfills:
            block_lines.append(f"  - {o}")
        block_lines.append("Violates (input):")
        for o in a.violates:
            block_lines.append(f"  - {o}")
        if a.raises:
            block_lines.append("Raises (input, already at stake):")
            for o in a.raises:
                block_lines.append(f"  - {o}")
        block_lines.append("")
    return _load_obligation_engagement_template().render(
        case_id=case_id, case_title=case_title, action_count=len(actions),
        discussion_excerpt=(discussion_excerpt or "").strip(),
        actions_block="\n".join(block_lines))


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
        strict: bool = True,
    ) -> ObligationEngagementResult:
        """Re-partition each Action's obligations into fulfills/violates/raises.

        strict=True (default, used by the backfill driver): raise ValueError on
        any validation issue. strict=False (the live apply hook): log the issues
        and return the parsed result anyway, so the caller can reconcile each
        Action deterministically to its input pool instead of dropping the whole
        case's raises buckets.
        """
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
        issues = self._validate(result, actions, case_id)
        if issues:
            msg = f"case {case_id}: obligation-engagement validation: {issues[:3]}"
            if strict:
                raise ValueError(msg)
            logger.warning("%s (lenient; caller will reconcile to the input pool)", msg)
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
                system=_load_obligation_engagement_template().render_system(),
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
    ) -> List[str]:
        """Return human-readable validation issues (empty list == valid).

        Returns issues rather than raising so each caller chooses how to handle
        them: the backfill driver fails hard via extract(strict=True); the live
        apply hook reconciles deterministically. The per-action input pool
        INCLUDES each Action's existing ``raises`` so a re-run does not flag a
        previously-raised obligation as an extra.
        """
        issues: List[str] = []
        input_iris = {a.iri for a in actions}
        output_iris = {pa.action_iri for pa in result.actions}
        if input_iris != output_iris:
            missing = input_iris - output_iris
            extra = output_iris - input_iris
            issues.append(
                f"action_iris do not match input (missing={sorted(missing)}, "
                f"extra={sorted(extra)})"
            )

        # Per-action: union must equal input pool, no duplicates within action.
        action_by_iri = {a.iri: a for a in actions}
        for pa in result.actions:
            ctx = action_by_iri.get(pa.action_iri)
            if ctx is None:
                continue
            input_pool: Set[str] = set()
            input_pool.update(cls._normalize(o) for o in ctx.fulfills)
            input_pool.update(cls._normalize(o) for o in ctx.violates)
            input_pool.update(cls._normalize(o) for o in (ctx.raises or []))

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
                issues.append(
                    f"action {pa.action_iri}: an obligation appears in more than "
                    f"one bucket: {dups[:3]}"
                )

            missing = input_pool - output_set
            extra = output_set - input_pool
            if missing or extra:
                issues.append(
                    f"action {pa.action_iri}: bucket union does not equal input "
                    f"pool (missing={sorted(missing)[:3]}, extra={sorted(extra)[:3]})"
                )
        return issues
