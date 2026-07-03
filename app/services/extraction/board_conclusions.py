"""
Board-conclusion gap-fill extractor.

For each case where the original `ethical_conclusion` extraction missed a
per-board-question ruling (verified across the study pool, 2026-05-10:
10 board questions across 8 cases lack a primary Board conclusion),
this pass generates one Conclusion grounded in the BER's Discussion
section, paired by `answersQuestions` to the missing board question.

Persistence: new rows in `temporary_rdf_storage` with
`extraction_type='ethical_conclusion'`, `entity_label='Conclusion_N'`
(N = the question number, keeping suf_len <= 2 so the existing
board-detection heuristic in synthesis_view_builder treats them as
board-typed). The driver script (backfill_board_conclusions.py)
identifies gaps and writes back; this module owns the LLM call only.

Reference: proethica/.claude/plans/current-application-roadmap.md
"Q&C Conclusion Extraction Discipline".
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, List, Optional

from .schemas import BoardConclusionExtractionResult, BoardConclusionForQuestion

logger = logging.getLogger(__name__)


# The board-conclusions SYSTEM and user prompts now live in the editable 'board_conclusions' template
# (extraction_prompt_templates); see _load_board_conclusions_template() / build_user_prompt() / _call_llm.
# Seed: docs-internal/scripts/seed_board_conclusions_template.py


@dataclass
class BoardQuestionGap:
    """One board question that needs a board conclusion generated."""
    question_number: int
    question_text: str


def _load_board_conclusions_template():
    """Load the editable 'board_conclusions' prompt template (prompt editor -> Shared prompts ->
    Synthesis & enrichment -> Board conclusions). A separate function so a test can inject a stub
    without a DB / app context. Raises (no fallback) if unseeded."""
    from app.models.extraction_prompt_template import ExtractionPromptTemplate
    tmpl = ExtractionPromptTemplate.get_active_template(0, 'board_conclusions')
    if tmpl is None:
        raise RuntimeError(
            "No 'board_conclusions' prompt template in extraction_prompt_templates. "
            "Seed it: docs-internal/scripts/seed_board_conclusions_template.py")
    return tmpl


def build_user_prompt(
    case_id: int,
    case_title: str,
    gaps: List[BoardQuestionGap],
    discussion_text: str,
    conclusion_text: str = "",
) -> str:
    """Assemble the gap-question lines in code, then render the editable DB template."""
    gap_questions = "\n".join(f"  Q{g.question_number}: {g.question_text}" for g in gaps)
    return _load_board_conclusions_template().render(
        case_id=case_id, case_title=case_title, gap_questions=gap_questions,
        discussion_text=discussion_text.strip(),
        conclusion_text=(conclusion_text or "").strip(), gap_count=len(gaps))


class BoardConclusionExtractor:
    """LLM-backed gap-fill extractor for missing board conclusions."""

    def __init__(
        self,
        llm_client: Any = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ):
        self._llm_client = llm_client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.last_prompt: Optional[str] = None
        self.last_raw_response: Optional[str] = None

    def extract(
        self,
        case_id: int,
        case_title: str,
        gaps: List[BoardQuestionGap],
        discussion_text: str,
        conclusion_text: str = "",
    ) -> BoardConclusionExtractionResult:
        if not gaps:
            return BoardConclusionExtractionResult(conclusions=[])

        user_prompt = build_user_prompt(
            case_id, case_title, gaps, discussion_text, conclusion_text
        )
        self.last_prompt = user_prompt

        raw = self._call_llm(user_prompt)
        self.last_raw_response = raw
        if not raw:
            raise RuntimeError(
                f"case {case_id}: board-conclusion LLM call returned no content"
            )

        result = self._parse(raw)
        self._validate(result, gaps, case_id)
        return result

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
                "BoardConclusionExtractor requires an Anthropic streaming client; got %s",
                type(client).__name__,
            )
            return None

        try:
            from app.utils.llm_utils import direct_call_params
            chunks: List[str] = []
            with client.messages.stream(
                **direct_call_params(model, max_tokens=self.max_tokens,
                                     temperature=self.temperature),
                system=_load_board_conclusions_template().render_system(),
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                for text in stream.text_stream:
                    chunks.append(text)
                final_msg = stream.get_final_message()
            stop_reason = getattr(final_msg, "stop_reason", None)
            usage = getattr(final_msg, "usage", None)
            if usage:
                logger.info(
                    "BoardConclusion stream complete: %d in / %d out, stop=%s",
                    usage.input_tokens, usage.output_tokens, stop_reason,
                )
            return "".join(chunks)
        except Exception as e:
            logger.error("Anthropic board-conclusion stream failed: %s", e)
            return None

    @staticmethod
    def _parse(raw: str) -> BoardConclusionExtractionResult:
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
                    f"board-conclusion response was not JSON: {e}"
                ) from e
            data = json.loads(m.group(0))
        return BoardConclusionExtractionResult(**data)

    @staticmethod
    def _validate(
        result: BoardConclusionExtractionResult,
        gaps: List[BoardQuestionGap],
        case_id: int,
    ) -> None:
        wanted = {g.question_number for g in gaps}
        got = {c.question_number for c in result.conclusions}
        if wanted != got:
            missing = wanted - got
            extra = got - wanted
            raise ValueError(
                f"case {case_id}: board-conclusion result mismatch "
                f"(missing={sorted(missing)}, extra={sorted(extra)})"
            )
        if len(result.conclusions) != len(wanted):
            raise ValueError(
                f"case {case_id}: expected {len(wanted)} conclusions, "
                f"got {len(result.conclusions)}"
            )
