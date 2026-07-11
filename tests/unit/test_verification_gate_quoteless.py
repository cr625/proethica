"""
Tests for the quoteless-entity grounding pass in the verification gate.

Entities with text_references=[] previously skipped verify_and_reground entirely
(nothing to iterate), so a fabricated quoteless entity in the seven grounded
components passed the fabrication check untouched. The gate now requires a
confirmed grounding span for quoteless rows in those components (repair-first:
a found span becomes the entity's quotes; no span drops the row), while Step-4
synthesis families and Step-3 temporal records stay exempt. Also locks the two
temporal-shape helpers: quotes_of reading the top-level proeth:textReferences
key and apply_corrected_quotes writing it back without the pass-1/2 wrapper.
"""

from unittest.mock import MagicMock, patch

from app.services.extraction.verification_gate import (
    apply_corrected_quotes,
    quotes_of,
    verify_case_entities,
)

CASE_TEXT = ("Engineer A prepared the structural design for the municipal project. "
             "The Board concluded that Engineer A acted ethically in disclosing the defect.")


def _gate(entities, reground_response):
    """Run the gate with the LLM span-finding call mocked; over-reach never runs
    (no duty classes in these fixtures)."""
    with patch('app.services.extraction.extraction_verifier._structured_stream_json',
               return_value=reground_response), \
         patch('app.utils.llm_utils.get_llm_client', return_value=MagicMock()), \
         patch('model_config.ModelConfig') as mock_cfg:
        mock_cfg.get_claude_model.return_value = 'test-model'
        return verify_case_entities(entities, CASE_TEXT, case_id=9)


def test_quoteless_grounded_component_repaired_when_span_found():
    entities = [{'id': 1, 'label': 'Structural Design Role', 'definition': 'prepares designs',
                 'component': 'roles', 'storage_type': 'individual', 'quotes': [],
                 'class_ref': ''}]
    span = 'Engineer A prepared the structural design'
    res = _gate(entities, {'results': [{'id': 0, 'supported': True, 'spans': [span]}]})
    assert res.dropped == []
    assert res.corrected_quotes[1] == [span]


def test_quoteless_grounded_component_dropped_when_no_span():
    entities = [{'id': 2, 'label': 'Invented Duty', 'definition': 'never in the case',
                 'component': 'obligations', 'storage_type': 'individual', 'quotes': [],
                 'class_ref': ''}]
    res = _gate(entities, {'results': [{'id': 0, 'supported': False, 'spans': []}]})
    assert len(res.dropped) == 1
    assert res.dropped[0][0] == 2
    assert 'quoteless' in res.dropped[0][2]


def test_quoteless_synthesis_component_exempt():
    """Step-4 families are derived analysis records: no grounding requirement,
    and no LLM call at all when nothing else is pending."""
    entities = [{'id': 3, 'label': 'Q1 emergence', 'definition': 'synthesized',
                 'component': 'question_emergence', 'storage_type': 'individual',
                 'quotes': [], 'class_ref': ''}]
    with patch('app.services.extraction.extraction_verifier._structured_stream_json') as mock_llm, \
         patch('model_config.ModelConfig') as mock_cfg:
        mock_cfg.get_claude_model.return_value = 'test-model'
        res = verify_case_entities(entities, CASE_TEXT, case_id=9)
    assert res.dropped == []
    assert res.corrected_quotes == {}
    mock_llm.assert_not_called()


def test_gate_does_not_mutate_caller_dicts():
    entities = [{'id': 4, 'label': 'Engineer A Role', 'definition': 'x',
                 'component': 'roles', 'storage_type': 'individual',
                 'quotes': ['Engineer A prepared the structural design'],
                 'class_ref': ''}]
    _gate(entities, {'results': []})
    assert 'require_quote' not in entities[0]


def test_quotes_of_reads_temporal_jsonld_shape():
    jl = {'@id': 'x', '@type': 'proeth:Action',
          'proeth:textReferences': ['Engineer A prepared the structural design']}
    assert quotes_of(jl) == ['Engineer A prepared the structural design']


def test_apply_corrected_quotes_temporal_shape_stays_prefixed():
    jl = {'@id': 'x', '@type': 'proeth:Action',
          'proeth:textReferences': ['a paraphrase']}
    out = apply_corrected_quotes(jl, ['the verified span'])
    assert out['proeth:textReferences'] == ['the verified span']
    assert 'properties' not in out
    assert 'source_text' not in out


def test_apply_corrected_quotes_pass12_shape_unchanged_behavior():
    jl = {'properties': {'textReferences': ['old']}, 'source_text': 'old',
          'source_texts': {'facts': 'old'}}
    out = apply_corrected_quotes(jl, ['new span'])
    assert out['properties']['textReferences'] == ['new span']
    assert out['source_text'] == 'new span'
    assert out['source_texts'] == {'facts': 'new span'}
