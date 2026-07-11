"""Byte-parity tests for the batch-narrative Step-4 prompt migration (P19-P27).

Golden files were captured from the PRE-migration inline builders with the
inputs in step4_narrative_fixtures (scratch capture script, 2026-07-10).
Each test drives the MIGRATED builder on the same inputs with
get_step4_template stubbed to render the sidecar body directly (jinja2, no
seeded DB, no LLM) and asserts the produced prompt is byte-identical to the
golden.

Documented deviations, applied to the goldens at capture time (per
.claude/plans/step4-template-migration.md): step4_case_summary and
step4_timeline_phases (case_synthesizer/narrative.py) previously lacked
STYLE_FORMATTING_LINE; the migration adds it, so those two goldens carry the
STYLE line the pre-migration builders did not emit.

The batch's templates contain no Jinja conditionals (all list blocks are
code-built and passed as strings), so most prompts need one golden;
step4_narrative_tensions additionally exercises the builder's empty-tensions
fallback ('None identified yet') as a reduced variant.
"""

from pathlib import Path

import jinja2
import pytest

from app.utils.seed_step4_prompts import SIDECAR_DIR, parse_sidecar, check_variables
from tests.extraction import step4_narrative_fixtures as fx

REPO = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO / 'tests' / 'fixtures' / 'step4_prompt_golden'

BATCH_CONCEPT_TYPES = [
    'step4_narrative_characters',
    'step4_narrative_tensions',
    'step4_narrative_timeline',
    'step4_narrative_option_label',
    'step4_narrative_option_set',
    'step4_narrative_opening',
    'step4_narrative_insights',
    'step4_case_summary',
    'step4_timeline_phases',
]


class SidecarTemplate:
    """DB-row stand-in: renders the sidecar body exactly as
    ExtractionPromptTemplate.render does (default jinja2 settings)."""

    def __init__(self, concept_type):
        path = SIDECAR_DIR / f'{concept_type}.md'
        meta, body = parse_sidecar(path)
        check_variables(path, meta, body)
        self.body = body

    def render(self, **variables):
        return jinja2.Template(self.body).render(**variables)


def _fake_loader(concept_type):
    return SidecarTemplate(concept_type)


def golden(name):
    return (GOLDEN_DIR / f'{name}.txt').read_text()


@pytest.mark.parametrize('concept_type', BATCH_CONCEPT_TYPES)
def test_sidecar_declares_all_body_variables(concept_type):
    path = SIDECAR_DIR / f'{concept_type}.md'
    meta, body = parse_sidecar(path)
    check_variables(path, meta, body)


def test_characters_prompt_parity(monkeypatch):
    from app.services.narrative import narrative_element_extractor as mod

    monkeypatch.setattr(mod, 'get_step4_template', _fake_loader)
    captured = {}
    monkeypatch.setattr(
        'app.utils.llm_utils.streaming_completion',
        fx.make_fake_streaming('{"enhancements": [], "missing_characters": []}', captured))

    ex = mod.NarrativeElementExtractor.__new__(mod.NarrativeElementExtractor)
    ex.llm_client = object()
    ex._load_case_facts = lambda cid: fx.FACTS
    _, trace = ex._enhance_characters_with_llm(fx.characters(), fx.foundation(), fx.CASE_ID)

    assert trace is not None
    assert captured['prompt'] == golden('step4_narrative_characters')
    assert trace['prompt'] == captured['prompt']


def test_tensions_prompt_parity_full(monkeypatch):
    from app.services.narrative import narrative_element_extractor as mod

    monkeypatch.setattr(mod, 'get_step4_template', _fake_loader)
    captured = {}
    monkeypatch.setattr(
        'app.utils.llm_utils.streaming_completion',
        fx.make_fake_streaming('{"ratings": [], "additional": []}', captured))

    ex = mod.NarrativeElementExtractor.__new__(mod.NarrativeElementExtractor)
    ex.llm_client = object()
    _, trace = ex._enhance_tensions_with_llm(fx.tensions(), fx.foundation(), fx.CASE_ID)

    assert trace is not None
    assert captured['prompt'] == golden('step4_narrative_tensions')


def test_tensions_prompt_parity_empty(monkeypatch):
    from app.services.narrative import narrative_element_extractor as mod

    monkeypatch.setattr(mod, 'get_step4_template', _fake_loader)
    captured = {}
    monkeypatch.setattr(
        'app.utils.llm_utils.streaming_completion',
        fx.make_fake_streaming('{"ratings": [], "additional": []}', captured))

    ex = mod.NarrativeElementExtractor.__new__(mod.NarrativeElementExtractor)
    ex.llm_client = object()
    _, trace = ex._enhance_tensions_with_llm([], fx.foundation(), fx.CASE_ID)

    assert trace is not None
    assert captured['prompt'] == golden('step4_narrative_tensions__empty')


def test_timeline_prompt_parity(monkeypatch):
    from app.services.narrative import timeline_constructor as mod

    monkeypatch.setattr(mod, 'get_step4_template', _fake_loader)
    captured = {}
    monkeypatch.setattr(
        'app.utils.llm_utils.streaming_completion',
        fx.make_fake_streaming('[]', captured))

    tc = mod.TimelineConstructor.__new__(mod.TimelineConstructor)
    tc.llm_client = object()
    _, trace = tc._enhance_timeline_with_llm(fx.timeline_events(), None, fx.CASE_ID)

    assert trace is not None
    assert captured['prompt'] == golden('step4_narrative_timeline')


def test_option_label_prompt_parity(monkeypatch):
    from app.services.narrative import scenario_seed_generator as mod

    monkeypatch.setattr(mod, 'get_step4_template', _fake_loader)
    gen = mod.ScenarioSeedGenerator.__new__(mod.ScenarioSeedGenerator)
    gen.use_llm = True
    gen.llm_client = fx.FakeAnthropicClient(
        ['LABEL: Report to the building authority\nDESCRIPTION: Notify the authority of the hazard.'])

    label, _ = gen._generate_option_label_llm(fx.QUESTION, 0, True, fx.COMPETING_OBLIGATIONS)

    assert label == 'Report to the building authority'
    assert gen.llm_client.messages.prompts[0] == golden('step4_narrative_option_label')


def test_option_set_prompt_parity(monkeypatch):
    from app.services.narrative import scenario_seed_generator as mod

    monkeypatch.setattr(mod, 'get_step4_template', _fake_loader)
    gen = mod.ScenarioSeedGenerator.__new__(mod.ScenarioSeedGenerator)
    gen.use_llm = True
    gen.llm_client = fx.FakeAnthropicClient(
        ['OPTION1_LABEL: Report the hazard\nOPTION1_DESC: a\n'
         'OPTION2_LABEL: Maintain confidentiality\nOPTION2_DESC: b'])

    opts = gen._generate_options_llm(fx.QUESTION, fx.COMPETING_OBLIGATIONS, 0, 'branch_2')

    assert opts and len(opts) == 2
    assert gen.llm_client.messages.prompts[0] == golden('step4_narrative_option_set')


def test_opening_prompt_parity(monkeypatch):
    from app.services.narrative import scenario_seed_generator as mod

    monkeypatch.setattr(mod, 'get_step4_template', _fake_loader)
    gen = mod.ScenarioSeedGenerator.__new__(mod.ScenarioSeedGenerator)
    gen.use_llm = True
    gen.llm_client = fx.FakeAnthropicClient(['You are Engineer A.'])
    gen._load_case_facts = lambda cid: fx.FACTS

    _, trace = gen._enhance_opening_with_llm(
        '', fx.narrative_elements_for_opening(), fx.CASE_ID, fx.branches())

    assert trace is not None
    assert gen.llm_client.messages.prompts[0] == golden('step4_narrative_opening')
    assert trace['prompt'] == gen.llm_client.messages.prompts[0]


def test_insights_prompt_parity(monkeypatch):
    from app.services.narrative import insight_deriver as mod

    monkeypatch.setattr(mod, 'get_step4_template', _fake_loader)
    captured = {}
    monkeypatch.setattr(
        'app.utils.llm_utils.streaming_completion',
        fx.make_fake_streaming('{}', captured))

    ins = mod.InsightDeriver.__new__(mod.InsightDeriver)
    ins.llm_client = object()
    _, trace = ins._generate_insights_with_llm(
        fx.narrative_elements_for_insights(), fx.principles(), [], fx.TRANSFORMATION_TYPE)

    assert trace is not None
    assert captured['prompt'] == golden('step4_narrative_insights')


def test_case_summary_and_timeline_phases_parity(monkeypatch):
    # DEVIATION (documented in the migration plan): these two goldens carry
    # STYLE_FORMATTING_LINE, which the pre-migration builders did not emit;
    # it was inserted into the captured prompts at golden-capture time.
    from app.services.case_synthesizer import narrative as mod

    monkeypatch.setattr(mod, 'get_step4_template', _fake_loader)
    mix = mod.NarrativeConstructionMixin()
    mix.llm_client = fx.FakeAnthropicClient(['A summary.', '```json\n[]\n```'])

    _, traces = mix._construct_narrative_with_llm(
        fx.CASE_ID, fx.case_document(), fx.foundation(),
        fx.canonical_points(), fx.conclusions())

    assert len(mix.llm_client.messages.prompts) == 2
    summary_prompt, timeline_prompt = mix.llm_client.messages.prompts
    assert summary_prompt == golden('step4_case_summary')
    assert timeline_prompt == golden('step4_timeline_phases')
    assert len(traces) == 2
    assert traces[0].prompt == summary_prompt
    assert traces[1].prompt == timeline_prompt
