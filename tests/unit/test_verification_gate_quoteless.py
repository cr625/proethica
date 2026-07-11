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


def test_empty_reground_results_raises():
    """A schema-valid but EMPTY results array is a whole-call model failure:
    it must surface (stage retry), not crash with AttributeError and not
    silently verdict every pending entity."""
    import pytest
    entities = [{'id': 5, 'label': 'Invented Duty', 'definition': 'x',
                 'component': 'obligations', 'storage_type': 'individual',
                 'quotes': [], 'class_ref': ''}]
    with pytest.raises(RuntimeError, match='no results'):
        _gate(entities, {'results': []})


def test_missing_result_id_treated_unsupported_not_crash():
    """A partial results array (some ids answered, one missing) treats the
    missing item as unsupported instead of raising AttributeError."""
    entities = [
        {'id': 6, 'label': 'Grounded Role', 'definition': 'x', 'component': 'roles',
         'storage_type': 'individual', 'quotes': ['a paraphrase not in the case'],
         'class_ref': ''},
        {'id': 7, 'label': 'Also Pending', 'definition': 'y', 'component': 'roles',
         'storage_type': 'individual', 'quotes': ['another paraphrase'], 'class_ref': ''},
    ]
    span = 'Engineer A prepared the structural design'
    res = _gate(entities, {'results': [{'id': 0, 'supported': True, 'spans': [span]}]})
    assert res.corrected_quotes[6] == [span]
    assert len(res.dropped) == 1 and res.dropped[0][0] == 7
    assert 'fabrication' in res.dropped[0][2]


def test_short_span_rejected_by_token_floor():
    """A stopword-level span must not become an entity's sole grounding."""
    entities = [{'id': 8, 'label': 'Invented Duty', 'definition': 'x',
                 'component': 'obligations', 'storage_type': 'individual',
                 'quotes': [], 'class_ref': ''}]
    res = _gate(entities, {'results': [{'id': 0, 'supported': True, 'spans': ['the']}]})
    assert len(res.dropped) == 1
    assert res.corrected_quotes == {}


def test_verbatim_is_token_boundary_anchored():
    """A mid-word fragment ('pared the structural' inside 'prepared the
    structural') must not pass the verbatim confirmation."""
    from app.services.extraction.extraction_verifier import _verbatim
    from app.services.extraction.quote_grounding import _tokens
    ts = ' '.join(_tokens(CASE_TEXT))
    assert _verbatim('prepared the structural design', ts)
    assert not _verbatim('pared the structural design', ts)


def test_temporal_ungrounded_flagged_not_dropped():
    """Temporal rows are referenced by sibling rows (Allen relations,
    timeline, chains); an ungrounded one is flagged for review, never
    auto-dropped -- a drop would commit dangling case-ns references."""
    entities = [{'id': 9, 'label': 'Some Action', 'definition': 'x',
                 'component': 'temporal_dynamics_enhanced', 'storage_type': 'individual',
                 'quotes': ['a paraphrase with no supporting span'], 'class_ref': ''}]
    res = _gate(entities, {'results': [{'id': 0, 'supported': False, 'spans': []}]})
    assert res.dropped == []
    assert len(res.flagged) == 1 and res.flagged[0][0] == 9
    assert 'ungrounded' in res.flagged[0][2]


def _duty(idx, label, storage_type='class', class_ref=''):
    return {'id': idx, 'label': label, 'definition': 'a duty', 'component': 'obligations',
            'storage_type': storage_type,
            'quotes': ['Engineer A prepared the structural design'], 'class_ref': class_ref}


def test_overreach_drop_covers_label_variant_twins():
    """Label variants collapse to the SAME committed URI, so a 5/5 drop on one
    variant must drop the whole group (and cascade to individuals referencing
    either spelling) -- otherwise the twin silently commits the dropped duty."""
    from app.services.extraction.verification_gate import verify_case_entities
    from app.services.extraction.extraction_verifier import OverreachVerdict
    entities = [
        _duty(1, 'ProfessionalAccountabilityObligation'),
        _duty(2, 'Professional Accountability Obligation'),
        _duty(3, 'Some Individual', storage_type='individual',
              class_ref='Professional Accountability Obligation'),
    ]
    verdict = OverreachVerdict(label='ProfessionalAccountabilityObligation', overreach=True,
                               votes_for=5, votes_total=5, reason='broader than the case holds',
                               limiting_quote='')
    with patch('app.services.extraction.verification_gate.detect_overreach',
               return_value=[verdict]) as mock_over, \
         patch('app.services.extraction.verification_gate.verify_and_reground',
               return_value=[MagicMock(kept_verbatim=['q'], regrounded=[], unsupported=[])] * 3), \
         patch('model_config.ModelConfig') as mock_cfg:
        mock_cfg.get_claude_model.return_value = 'test-model'
        res = verify_case_entities(entities, CASE_TEXT, case_id=9)
    # One panel for the deduped group, all three rows dropped.
    assert len(mock_over.call_args[0][1]) == 1
    assert res.dropped_ids == {1, 2, 3}


def test_overreach_flag_applies_to_variant_group():
    from app.services.extraction.verification_gate import verify_case_entities
    from app.services.extraction.extraction_verifier import OverreachVerdict
    entities = [_duty(4, 'Disclosure Duty'), _duty(5, 'DisclosureDuty')]
    verdict = OverreachVerdict(label='Disclosure Duty', overreach=True, votes_for=2,
                               votes_total=5, reason='conditional in the case',
                               limiting_quote='acted ethically in disclosing the defect')
    with patch('app.services.extraction.verification_gate.detect_overreach',
               return_value=[verdict]), \
         patch('app.services.extraction.verification_gate.verify_and_reground',
               return_value=[MagicMock(kept_verbatim=['q'], regrounded=[], unsupported=[])] * 2), \
         patch('model_config.ModelConfig') as mock_cfg:
        mock_cfg.get_claude_model.return_value = 'test-model'
        res = verify_case_entities(entities, CASE_TEXT, case_id=9)
    assert res.dropped == []
    assert {f[0] for f in res.flagged} == {4, 5}
    assert res.report['flagged'] == 2


def test_quoteless_repair_tracked_for_audit_marker():
    """A quoteless entity that gains a span is recorded in repaired_quoteless
    (the pipeline writes the gate-attached marker from it)."""
    entities = [{'id': 10, 'label': 'Structural Design Role', 'definition': 'x',
                 'component': 'roles', 'storage_type': 'individual', 'quotes': [],
                 'class_ref': ''}]
    span = 'Engineer A prepared the structural design'
    res = _gate(entities, {'results': [{'id': 0, 'supported': True, 'spans': [span]}]})
    assert res.repaired_quoteless == {10}
    assert res.report['quoteless_repaired_ids'] == [10]


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
