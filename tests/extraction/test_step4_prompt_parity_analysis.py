"""Byte-parity tests for the batch-analysis Step-4 prompt migration:
P13 step4_provision_validate, P14 step4_provision_link, P16 step4_precedents,
P17 step4_transformation, P18 step4_obligation_relevance.

The golden files in tests/fixtures/step4_prompt_golden/ were captured from the
PRE-migration inline builders with the shared fixture inputs
(step4_parity_fixtures_analysis.py). Each test drives the MIGRATED builder
with the same inputs, with get_step4_template stubbed by a sidecar-backed
template (the sidecar body is read from app/utils/prompts/step4/ and rendered
with plain jinja2.Template, matching ExtractionPromptTemplate.render), and
asserts byte-equality against the golden.

Deliberate deviations: none of the batch-analysis goldens carry a textual
deviation. P16's import-time treatments-block concatenation became render-time
assembly (build_precedent_prompt), but the rendered text is unchanged, so its
golden is the old constant's .format output verbatim.

Conditional-assembly coverage: P14 runs a full variant (role type, case
summary present) and a reduced variant (obligation type, empty summary ->
default-context branch, different applicability sentence); P17 runs a full
variant and a reduced variant (no facts/entities/patterns/questions/
conclusions -> every fallback branch).

DB/LLM-free.
"""

from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest

from app.utils.seed_step4_prompts import SIDECAR_DIR, check_variables, parse_sidecar
from tests.extraction import step4_parity_fixtures_analysis as fx

GOLDEN_DIR = Path(__file__).resolve().parents[1] / 'fixtures' / 'step4_prompt_golden'

BATCH_CONCEPT_TYPES = [
    'step4_provision_validate',
    'step4_provision_link',
    'step4_precedents',
    'step4_transformation',
    'step4_obligation_relevance',
]


class _SidecarTemplate:
    """Sidecar-backed stand-in for an ExtractionPromptTemplate row."""

    def __init__(self, concept_type):
        _, body = parse_sidecar(SIDECAR_DIR / f'{concept_type}.md')
        self._template = jinja2.Template(body)

    def render(self, **variables):
        return self._template.render(**variables)


@pytest.fixture
def sidecar_templates(monkeypatch):
    """Route get_step4_template to the sidecar files instead of the DB."""
    import app.services.step4_synthesis.template_loader as template_loader

    monkeypatch.setattr(
        template_loader, 'get_step4_template',
        lambda concept_type: _SidecarTemplate(concept_type),
    )


def _golden(name):
    return (GOLDEN_DIR / f'{name}.txt').read_text()


@pytest.mark.parametrize('concept_type', BATCH_CONCEPT_TYPES)
def test_sidecar_variables_declared(concept_type):
    """Seed-time guard, replicated here: every variable the body references
    must be declared in variable_builders (an unbound Jinja variable renders
    as an empty string silently at run time)."""
    path = SIDECAR_DIR / f'{concept_type}.md'
    meta, body = parse_sidecar(path)
    check_variables(path, meta, body)


def test_provision_validate_parity(sidecar_templates):
    from app.services.provision.provision_group_validator import ProvisionGroupValidator

    inp = fx.provision_validate_inputs()
    prompt = ProvisionGroupValidator()._create_validation_prompt(
        inp['provision_code'], inp['provision_text'], inp['mentions'])
    assert prompt == _golden('step4_provision_validate')


@pytest.mark.parametrize('variant,golden_name', [
    ('full', 'step4_provision_link'),
    ('reduced', 'step4_provision_link_reduced'),
])
def test_provision_link_parity(sidecar_templates, variant, golden_name):
    from app.services.provision.code_provision_linker import CodeProvisionLinker

    inp = fx.provision_link_inputs(variant)
    prompt = CodeProvisionLinker()._create_batch_linking_prompt(
        inp['provisions'], inp['entity_type'], inp['type_label'],
        inp['entities'], inp['case_summary'])
    assert prompt == _golden(golden_name)


def test_precedents_parity(sidecar_templates):
    from app.routes.scenario_pipeline.step4.precedents import build_precedent_prompt

    inp = fx.precedents_inputs()
    assert build_precedent_prompt(inp['case_text']) == _golden('step4_precedents')


@pytest.mark.parametrize('variant,golden_name', [
    ('full', 'step4_transformation'),
    ('reduced', 'step4_transformation_reduced'),
])
def test_transformation_parity(sidecar_templates, monkeypatch, variant, golden_name):
    from app.services.case_analysis.transformation_classifier import TransformationClassifier
    import app.utils.llm_utils as llm_utils

    def _no_llm(*args, **kwargs):
        raise RuntimeError('parity test: no LLM call')

    monkeypatch.setattr(llm_utils, 'streaming_completion', _no_llm)

    inp = fx.transformation_inputs(variant)
    classifier = TransformationClassifier(llm_client=object())
    with pytest.raises(RuntimeError):
        classifier._llm_classification(
            inp['case_id'], inp['questions'], inp['conclusions'],
            inp['resolution_patterns'], case_title=inp['case_title'],
            case_facts=inp['case_facts'], all_entities=inp['all_entities'])
    assert classifier.last_prompt == _golden(golden_name)


def test_obligation_relevance_parity(sidecar_templates, monkeypatch):
    from app.services.entity_analysis.obligation_coverage_analyzer import (
        ObligationCoverageAnalyzer,
    )
    import app.utils.llm_utils as llm_utils

    stub_message = SimpleNamespace(
        content=[SimpleNamespace(
            type='text',
            text='{"decision_relevant_indices": [1], "reasoning": "stub"}',
        )],
        stop_reason='end_turn',
    )
    monkeypatch.setattr(
        llm_utils, 'get_llm_client',
        lambda: SimpleNamespace(messages=SimpleNamespace(
            create=lambda **kwargs: stub_message)),
    )

    inp = fx.obligation_relevance_inputs()
    analyzer = ObligationCoverageAnalyzer.__new__(ObligationCoverageAnalyzer)
    relevant_uris, trace = analyzer._llm_identify_decision_relevant(
        inp['obligations'], inp['constraints'],
        inp['questions'], inp['conclusions'])
    assert trace.prompt == _golden('step4_obligation_relevance')
    # Index contract: [1] maps to the first obligation.
    assert relevant_uris == [inp['obligations'][0].entity_uri]
