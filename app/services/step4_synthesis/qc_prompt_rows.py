"""ExtractionPrompt rows for the three Q&C LLM stages (case 8 review, lesson L6).

``_run_qc_unified`` persisted the question-analyzer and conclusion-analyzer
prompts but never the question-conclusion linker call, although that call
produced every ``answersQuestions`` value of the case. The three rows are
built here, in one place, from the analyzers' retained prompt/response text.
The text is stored whole: ``prompt_text`` and ``raw_response`` are ``db.Text``
columns, and the ``[:10000]`` slice that cut rows 8616 and 8617 of case 8 was
removed in 35a80006. ``tests/unit/test_step4_lessons_persistence.py`` guards
both properties. The rows are returned unsaved; the caller adds and commits.
"""
from typing import List

from app.models.extraction_prompt import ExtractionPrompt

QC_LINK_CONCEPT_TYPE = 'qc_link'


def _retained(obj, attr: str) -> str:
    return getattr(obj, attr, None) or ''


def build_qc_prompt_rows(case_id: int, session_id: str, question_analyzer, conclusion_analyzer,
                         linker, *, questions_total: int, conclusions_total: int,
                         board_q_count: int, board_c_count: int, qc_links_count: int,
                         llm_model: str, section_type: str = 'synthesis') -> List[ExtractionPrompt]:
    """The ethical_question, ethical_conclusion and qc_link rows of one run.

    The linker row is emitted whenever the linker retained a prompt (an empty
    run that skipped the LLM leaves no row, as before for the analyzers)."""
    import json

    q_prompt = _retained(question_analyzer, 'last_prompt') or f'LLM extraction of {questions_total} questions'
    q_response = _retained(question_analyzer, 'last_response')
    c_prompt = _retained(conclusion_analyzer, 'last_prompt') or f'LLM extraction of {conclusions_total} conclusions'
    c_response = _retained(conclusion_analyzer, 'last_response')

    rows = [
        ExtractionPrompt(
            case_id=case_id,
            concept_type='ethical_question',
            step_number=4,
            section_type=section_type,
            prompt_text=q_prompt,
            llm_model=llm_model,
            extraction_session_id=session_id,
            raw_response=q_response,
            results_summary=json.dumps({
                'total': questions_total,
                'board_explicit': board_q_count,
                'analytical': questions_total - board_q_count,
            }),
        ),
        ExtractionPrompt(
            case_id=case_id,
            concept_type='ethical_conclusion',
            step_number=4,
            section_type=section_type,
            prompt_text=c_prompt,
            llm_model=llm_model,
            extraction_session_id=session_id,
            raw_response=c_response,
            results_summary=json.dumps({
                'total': conclusions_total,
                'board_explicit': board_c_count,
                'analytical': conclusions_total - board_c_count,
                'qc_links': qc_links_count,
            }),
        ),
    ]

    link_prompt = _retained(linker, 'last_prompt')
    if link_prompt:
        rows.append(ExtractionPrompt(
            case_id=case_id,
            concept_type=QC_LINK_CONCEPT_TYPE,
            step_number=4,
            section_type=section_type,
            prompt_text=link_prompt,
            llm_model=llm_model,
            extraction_session_id=session_id,
            raw_response=_retained(linker, 'last_response'),
            results_summary=json.dumps({
                'questions': questions_total,
                'conclusions': conclusions_total,
                'qc_links': qc_links_count,
            }),
        ))
    return rows
