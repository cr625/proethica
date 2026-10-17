"""Byte-parity tests for the batch-qc Step-4 prompt sidecars (P1-P5).

Goldens in tests/fixtures/step4_prompt_golden/ were captured from the
pre-migration hardcoded builders running on the inputs in
step4_qc_fixtures. Each test rebuilds the template variables through the
live variable builders, renders the sidecar body directly (no DB, no
seeded template row), and asserts byte equality with the golden.

Deliberate deviations (case 8 review, lesson L5, 2026-10-17): the
step4_q_analytical__batch1 golden carries the implicit-question GROUNDING
bullet and the grounding_fact example field, and the two step4_c_analytical
goldens carry the analytical-extension ATTRIBUTION bullet and the
discussion_quote example field. Both blocks are code-built category text
(question_analyzer / conclusion_analyzer _analytical_prompt_variables), so
the goldens were re-captured from the live builders; the sidecar frames are
unchanged. The doubled-brace wrapper around the analytical output-JSON
examples (a pre-existing artifact of the old string assembly) is preserved
verbatim.
"""

from pathlib import Path

import pytest
from jinja2 import Template

from app.utils.seed_step4_prompts import SIDECAR_DIR, parse_sidecar, check_variables
from tests.extraction import step4_qc_fixtures as fx

GOLDEN_DIR = Path(__file__).resolve().parents[1] / 'fixtures' / 'step4_prompt_golden'


def render_sidecar(concept_type: str, variables: dict) -> str:
    path = SIDECAR_DIR / f'{concept_type}.md'
    meta, body = parse_sidecar(path)
    check_variables(path, meta, body)
    # Same render path as ExtractionPromptTemplate.render (default Jinja2 env).
    return Template(body).render(**variables)


def golden(name: str) -> str:
    return (GOLDEN_DIR / f'{name}.txt').read_text()


def test_q_board_parity():
    from app.services.step4_synthesis.question_analyzer import QuestionAnalyzer
    variables = QuestionAnalyzer()._board_extraction_variables(
        fx.QUESTIONS_SECTION_TEXT, fx.ALL_ENTITIES, fx.CODE_PROVISIONS)
    assert render_sidecar('step4_q_board', variables) == golden('step4_q_board')


@pytest.mark.parametrize('variant', ['batch1', 'batch2'])
def test_q_analytical_parity(variant):
    """Both live category subsets; batch2 also covers the empty
    board-questions and empty case_conclusion template branches."""
    from app.services.step4_synthesis.question_analyzer import QuestionAnalyzer
    kwargs = fx.q_analytical_variants()[variant]
    variables = QuestionAnalyzer()._analytical_prompt_variables(**kwargs)
    assert render_sidecar('step4_q_analytical', variables) == golden(
        f'step4_q_analytical__{variant}')


def test_c_board_parity():
    from app.services.step4_synthesis.conclusion_analyzer import ConclusionAnalyzer
    variables = ConclusionAnalyzer()._board_extraction_variables(
        fx.CONCLUSIONS_SECTION_TEXT, fx.ALL_ENTITIES, fx.CODE_PROVISIONS)
    assert render_sidecar('step4_c_board', variables) == golden('step4_c_board')


@pytest.mark.parametrize('variant', ['full', 'single'])
def test_c_analytical_parity(variant):
    """'full' = default all-three category expansion; 'single' = the live
    one-category call shape with the empty-context template branches."""
    from app.services.step4_synthesis.conclusion_analyzer import ConclusionAnalyzer
    kwargs = fx.c_analytical_variants()[variant]
    variables = ConclusionAnalyzer()._analytical_prompt_variables(**kwargs)
    assert render_sidecar('step4_c_analytical', variables) == golden(
        f'step4_c_analytical__{variant}')


def test_qc_link_parity():
    from app.services.step4_synthesis.question_conclusion_linker import QuestionConclusionLinker
    variables = QuestionConclusionLinker()._linking_prompt_variables(
        fx.linker_questions(), fx.linker_conclusions())
    assert render_sidecar('step4_qc_link', variables) == golden('step4_qc_link')
