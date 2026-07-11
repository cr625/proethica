"""Byte-parity gate for the batch-rich-dp Step-4 prompt migration (P6-P12).

Golden files under tests/fixtures/step4_prompt_golden/ were captured from the
UNCONVERTED builders driven with hand-built fixtures (no DB, no LLM); each
golden's .vars.json carries the exact template variables the builder passes to
render. The test renders the sidecar body directly (no seeded DB required)
with jinja2.Template defaults, matching ExtractionPromptTemplate.render(), and
asserts byte-equality with the golden.

Variant coverage where the template body carries a conditional:
- step4_causal_reasoning: '{{ causal_text or "  (none)" }}' -- full (chains
  present) and reduced (empty string) goldens.
- step4_resolution_patterns: '{{ norm_structure or "  (not available)" }}' --
  full (foundation subgraph) and reduced (foundation=None, plus the code-built
  'No questions extracted'/'No provisions extracted' fallbacks) goldens.

No deliberate deviations in this batch: every golden is the old builder's
output byte-for-byte (the P26/P27 STYLE-line and P16 treatment deviations
belong to other batches).
"""
import json
from pathlib import Path

import pytest
from jinja2 import Environment, Template, meta as jinja_meta

REPO = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO / 'tests' / 'fixtures' / 'step4_prompt_golden'
SIDECAR_DIR = REPO / 'app' / 'utils' / 'prompts' / 'step4'

BATCH_CONCEPTS = [
    'step4_causal_reasoning',
    'step4_question_emergence',
    'step4_resolution_patterns',
    'step4_dp_causal',
    'step4_dp_qc_direct',
    'step4_dp_refine',
    'step4_dp_board_verify',
]

CASES = [
    ('step4_causal_reasoning', 'step4_causal_reasoning'),
    ('step4_causal_reasoning.reduced', 'step4_causal_reasoning'),
    ('step4_question_emergence', 'step4_question_emergence'),
    ('step4_resolution_patterns', 'step4_resolution_patterns'),
    ('step4_resolution_patterns.reduced', 'step4_resolution_patterns'),
    ('step4_dp_causal', 'step4_dp_causal'),
    ('step4_dp_qc_direct', 'step4_dp_qc_direct'),
    ('step4_dp_refine', 'step4_dp_refine'),
    ('step4_dp_board_verify', 'step4_dp_board_verify'),
]


def _sidecar(concept_type):
    text = (SIDECAR_DIR / f'{concept_type}.md').read_text()
    parts = text.split('---\n', 2)
    assert len(parts) == 3, f'{concept_type}.md: malformed meta fences'
    return json.loads(parts[1]), parts[2].lstrip('\n')


@pytest.mark.parametrize('golden_name,concept_type', CASES)
def test_sidecar_renders_golden(golden_name, concept_type):
    golden = (GOLDEN_DIR / f'{golden_name}.txt').read_text()
    variables = json.loads((GOLDEN_DIR / f'{golden_name}.vars.json').read_text())
    _, body = _sidecar(concept_type)
    rendered = Template(body).render(**variables)
    assert rendered == golden, (
        f'{concept_type} sidecar render diverges from golden {golden_name}'
    )


@pytest.mark.parametrize('concept_type', BATCH_CONCEPTS)
def test_sidecar_declares_all_body_variables(concept_type):
    """Mirror of the seeder's silent-empty-Jinja-slot guard, runnable without a DB."""
    meta, body = _sidecar(concept_type)
    undeclared = jinja_meta.find_undeclared_variables(Environment().parse(body))
    declared = set(meta['variable_builders'].keys())
    missing = sorted(undeclared - declared)
    assert not missing, f'{concept_type}: undeclared template variables {missing}'
