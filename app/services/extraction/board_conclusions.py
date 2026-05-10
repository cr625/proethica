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


SYSTEM_PROMPT = (
    "You are an expert at reading NSPE Board of Ethical Review (BER) "
    "published opinions and identifying the Board's ruling on each "
    "explicit board Question.\n\n"
    "Given a case Discussion section and a list of board Questions for "
    "which a Board conclusion has not yet been extracted, return one "
    "Conclusion per question. Each Conclusion paraphrases the Board's "
    "ruling on that specific question, drawn from the Discussion text. "
    "When the Discussion folds multiple rulings together, identify the "
    "portion that addresses each specific question and paraphrase it.\n\n"
    "Critical rules:\n"
    "- One Conclusion per requested question_number, no more, no less.\n"
    "- The conclusion_text must be the Board's position, not analytical "
    "  commentary or counterfactual reasoning. Do not add 'In response "
    "  to QN:' or similar prefixes.\n"
    "- Cite provisions only when the Discussion explicitly cites them "
    "  in support of the ruling on this question.\n"
    "- One to three sentences per conclusion. Quote sparingly; "
    "  paraphrase otherwise.\n\n"
    "Output JSON only:\n"
    "{\n"
    "  \"conclusions\": [\n"
    "    { \"question_number\": <int>, "
    "\"conclusion_text\": \"...\", \"cited_provisions\": [\"I.1\", ...] },\n"
    "    ...\n"
    "  ]\n"
    "}\n\n"
    "No prose, markdown, or code fences around the JSON."
)


@dataclass
class BoardQuestionGap:
    """One board question that needs a board conclusion generated."""
    question_number: int
    question_text: str


def build_user_prompt(
    case_id: int,
    case_title: str,
    gaps: List[BoardQuestionGap],
    discussion_text: str,
    conclusion_text: str = "",
) -> str:
    lines: List[str] = [
        f"Case ID: {case_id}",
        f"Case title: {case_title}",
        "",
        "Board Questions for which a Board conclusion is needed:",
    ]
    for g in gaps:
        lines.append(f"  Q{g.question_number}: {g.question_text}")
    lines.append("")
    lines.append("Discussion section (Board's reasoning):")
    lines.append(discussion_text.strip())
    if conclusion_text and conclusion_text.strip():
        lines.append("")
        lines.append("Conclusion section (Board's published conclusions, when present):")
        lines.append(conclusion_text.strip())
    lines.append("")
    lines.append(
        f"Return JSON with exactly {len(gaps)} conclusion(s), one per "
        "question_number listed above."
    )
    return "\n".join(lines)


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
