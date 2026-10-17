"""Verification gate and publish guard rules from the case-8 review (L5).

The gate dropped the class row ProactiveRiskDisclosureObligation as over-reach
(4 of 5 votes) but the individual typed to it was vetted and committed, and the
case TTL redeclared the rejected class. The gate also re-judged rows the matcher
linked at 0.9 and above with quotes already verbatim (the largest model cost of
the commit). The cascade now follows every class reference a row carries
(properties.*Class, rdf_json_ld.types, the matched class), linked verbatim rows
are left unjudged, the commit refuses to publish an individual whose type class
is an unpublished class row, and the writer never redeclares such a class.

DB-free: the model calls are patched, the service is built with __new__ or the
shared stub, rows are SimpleNamespace stand-ins.
"""
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

from rdflib import Graph, Namespace, OWL, RDF, URIRef

from app.services.commit.ontserve_commit_service import OntServeCommitService
from app.services.commit.publish_guard import (
    class_row_keys, individual_type_locals, normalize_class_key,
    partition_by_unpublished_type, unpublished_class_keys,
)
from app.services.extraction.extraction_verifier import OverreachVerdict
from app.services.extraction.verification_gate import (
    LINKED_SKIP_CONFIDENCE, class_ref_of, class_refs_of, match_confidence_of, verify_case_entities,
)
from tests.mocks.commit_service_stub import make_stub_commit_service

INT_NS = "http://proethica.org/ontology/intermediate#"
CORE_NS = "http://proethica.org/ontology/core#"
CASE_TEXT = ("Engineer L notified Client X of the increased runoff risk into the watershed. "
             "Client X declined to fund additional protective measures citing budget limitations.")
VERBATIM = "Engineer L notified Client X of the increased runoff risk"


def _row(idx, label, component='obligations', storage_type='class', quotes=None, **extra):
    row = {'id': idx, 'label': label, 'definition': 'a duty', 'component': component,
           'storage_type': storage_type, 'quotes': quotes if quotes is not None else [VERBATIM],
           'class_ref': ''}
    row.update(extra)
    return row


def _verdict(label, votes_for):
    return OverreachVerdict(label=label, overreach=votes_for > 0, votes_for=votes_for, votes_total=5,
                            reason='broader than the case holds', limiting_quote='')


def _gate(entities, verdicts, reground=None):
    reground_mock = MagicMock(side_effect=reground) if reground else MagicMock(
        side_effect=lambda text, rows, model=None: [
            MagicMock(kept_verbatim=list(r['quotes']), regrounded=[], unsupported=[]) for r in rows])
    with patch('app.services.extraction.verification_gate.detect_overreach', return_value=verdicts) as over, \
         patch('app.services.extraction.verification_gate.verify_and_reground', reground_mock), \
         patch('model_config.ModelConfig') as cfg:
        cfg.get_claude_model.return_value = 'test-model'
        res = verify_case_entities(entities, CASE_TEXT, case_id=8)
    return res, over, reground_mock


def test_class_refs_of_collects_every_class_reference():
    jl = {'properties': {'obligationClass': ['Proactive Risk Disclosure Obligation']},
          'types': [f'{INT_NS}ProactiveRiskDisclosureObligation'],
          'match_decision': {'matches_existing': True, 'matched_uri': f'{INT_NS}DisclosureObligation',
                             'confidence': 0.8}}
    assert class_ref_of(jl) == 'Proactive Risk Disclosure Obligation'
    assert class_refs_of(jl) == ['Proactive Risk Disclosure Obligation',
                                 'ProactiveRiskDisclosureObligation', 'DisclosureObligation']
    assert class_refs_of({'types': [f'{INT_NS}X']}) == ['X']
    assert class_refs_of({}) == []


def test_match_confidence_of_prefers_the_column_then_the_linked_decision():
    linked = {'match_decision': {'matches_existing': True, 'confidence': 0.92}}
    assert match_confidence_of(linked, 0.5) == 0.5
    assert match_confidence_of(linked) == 0.92
    assert match_confidence_of({'match_decision': {'matches_existing': False, 'confidence': 0.92}}) is None
    assert match_confidence_of({}) is None


def test_class_drop_cascades_through_a_types_only_reference():
    """The individual carried no properties.obligationClass; its class reference lived in
    rdf_json_ld.types only, so the former class_ref cascade missed it."""
    entities = [
        _row(1, 'ProactiveRiskDisclosureObligation'),
        _row(2, 'Engineer L Proactive Risk Disclosure Duty', storage_type='individual',
             class_refs=[f'ProactiveRiskDisclosureObligation']),
        _row(3, 'Engineer L Watershed Safety Duty', storage_type='individual',
             class_refs=['SafetyObligation']),
    ]
    res, _over, _re = _gate(entities, [_verdict('ProactiveRiskDisclosureObligation', 4)])
    assert res.dropped_ids == {1, 2}
    reasons = {i: r for i, _l, r in res.dropped}
    assert reasons[2].startswith("over-reach cascade: instance of dropped class 'ProactiveRiskDisclosureObligation'")


def test_cascade_covers_a_non_duty_component_typed_to_the_dropped_class():
    entities = [
        _row(1, 'ProactiveRiskDisclosureObligation'),
        _row(2, 'Disclosure Action', component='temporal_dynamics_enhanced', storage_type='individual',
             class_refs=['Proactive Risk Disclosure Obligation']),
    ]
    res, _over, _re = _gate(entities, [_verdict('ProactiveRiskDisclosureObligation', 4)])
    assert res.dropped_ids == {1, 2}


def test_linked_verbatim_rows_are_left_unjudged():
    entities = [
        _row(1, 'Engineer L Watershed Safety Duty', storage_type='individual',
             match_confidence=0.95, class_refs=['SafetyObligation']),
        _row(2, 'Engineer L Faithful Agent Duty', storage_type='individual',
             match_confidence=0.95, quotes=['a paraphrase the case never states']),
        _row(3, 'Client X Compliance Duty', storage_type='individual', match_confidence=0.85),
    ]
    res, over, reground = _gate(entities, [])
    # Row 1 is linked at or above the threshold with verbatim quotes: no model call for it.
    judged_ids = [r['id'] for r in reground.call_args[0][1]]
    assert judged_ids == [2, 3]
    assert [s[0] for s in res.skipped] == [1]
    assert res.report['skipped'] == 1
    assert res.report['skipped_detail'][0]['reason'].startswith('linked at 0.95')
    assert res.dropped == []
    over.assert_not_called()   # no class rows: the panel never runs
    assert LINKED_SKIP_CONFIDENCE == 0.90


def test_all_rows_skipped_means_no_model_call_at_all():
    entities = [_row(1, 'Engineer L Watershed Safety Duty', storage_type='individual',
                     match_confidence=0.9)]
    res, over, reground = _gate(entities, [])
    reground.assert_not_called()
    over.assert_not_called()
    assert [s[0] for s in res.skipped] == [1]


def test_skipped_row_still_takes_the_cascade():
    entities = [
        _row(1, 'ProactiveRiskDisclosureObligation'),
        _row(2, 'Engineer L Proactive Risk Disclosure Duty', storage_type='individual',
             match_confidence=0.95, class_refs=['ProactiveRiskDisclosureObligation']),
    ]
    res, _over, reground = _gate(entities, [_verdict('ProactiveRiskDisclosureObligation', 4)])
    assert [r['id'] for r in reground.call_args[0][1]] == [1]
    assert res.dropped_ids == {1, 2}


# --- publish guard -----------------------------------------------------------

def _class_row(idx, label, published=False, extraction_type='obligations'):
    return types.SimpleNamespace(id=idx, storage_type='class', is_published=published,
                                 entity_label=label, extraction_type=extraction_type)


def test_publish_guard_helpers():
    assert normalize_class_key('Proactive Risk Disclosure Obligation') == normalize_class_key(
        'ProactiveRiskDisclosureObligation')
    assert individual_type_locals({'types': [f'{INT_NS}ProactiveRiskDisclosureObligation']}) == [
        'ProactiveRiskDisclosureObligation']
    assert class_row_keys('Design Engineer', 'roles') == {'designengineer', 'designengineerrole'}
    rows = [_class_row(5, 'Proactive Risk Disclosure Obligation'),
            _class_row(6, 'Published Duty', published=True),
            _class_row(7, 'In Batch Duty')]
    assert unpublished_class_keys(rows, batch_ids=[7]) == {'proactiveriskdisclosureobligation'}


def test_partition_refuses_unpublished_type_unless_established():
    refused_row = types.SimpleNamespace(entity_label='Engineer L Proactive Risk Disclosure Duty')
    kept_row = types.SimpleNamespace(entity_label='Engineer L Watershed Safety Duty')
    individuals = [
        (refused_row, {'types': [f'{INT_NS}ProactiveRiskDisclosureObligation']}),
        (kept_row, {'types': [f'{INT_NS}SafetyObligation']}),
    ]
    rejected = {'proactiveriskdisclosureobligation', 'safetyobligation'}
    kept, refused = partition_by_unpublished_type(
        individuals, rejected, lambda local: 'Obligation' if local == 'SafetyObligation' else None)
    assert [row for row, _ in kept] == [kept_row]
    assert [(row, cls) for row, _rdf, cls in refused] == [(refused_row, 'ProactiveRiskDisclosureObligation')]
    assert partition_by_unpublished_type(individuals, set(), lambda local: None) == (individuals, [])


def _stub_service(tmp_path, monkeypatch, chain):
    return make_stub_commit_service(tmp_path, monkeypatch, chain_resolver=chain,
                                    header_fields={'title': 'Mock Case', 'case_number': None, 'decade': None})


def _individual(label, type_local):
    entity = types.SimpleNamespace(
        extraction_type='obligations', entity_type='obligations', entity_label=label,
        entity_definition='A duty.', iao_document_uri=None, iao_document_label=None,
        cited_by_role=None, available_to_role=None, extraction_model=None)
    return entity, {'types': [f'{INT_NS}{type_local}']}


def test_writer_does_not_redeclare_a_rejected_class(tmp_path, monkeypatch):
    svc = _stub_service(tmp_path, monkeypatch, lambda local: None)
    result = svc._commit_individuals_to_case_ontology(
        8, [_individual('Engineer L Proactive Risk Disclosure Duty', 'ProactiveRiskDisclosureObligation')],
        rejected_class_keys={'proactiveriskdisclosureobligation'})
    assert result.get('error') is None, result
    g = Graph()
    g.parse(result['file'], format='turtle')
    ind = Namespace('http://proethica.org/ontology/case/8#')['Engineer_L_Proactive_Risk_Disclosure_Duty']
    rejected = URIRef(f'{INT_NS}ProactiveRiskDisclosureObligation')
    assert (ind, RDF.type, URIRef(f'{CORE_NS}Obligation')) in g
    assert (ind, RDF.type, rejected) not in g
    assert (rejected, RDF.type, OWL.Class) not in g
    # The same class, when the shared ontology establishes it, is typed as before.
    svc2 = _stub_service(tmp_path / 'b', monkeypatch,
                         lambda local: 'Obligation' if local == 'ProactiveRiskDisclosureObligation' else None)
    (tmp_path / 'b').mkdir()
    result2 = svc2._commit_individuals_to_case_ontology(
        9, [_individual('Engineer L Proactive Risk Disclosure Duty', 'ProactiveRiskDisclosureObligation')],
        rejected_class_keys={'proactiveriskdisclosureobligation'})
    g2 = Graph()
    g2.parse(result2['file'], format='turtle')
    ind2 = Namespace('http://proethica.org/ontology/case/9#')['Engineer_L_Proactive_Risk_Disclosure_Duty']
    assert (ind2, RDF.type, rejected) in g2


class _Row:
    def __init__(self, row_id, storage_type, label, rdf_json_ld=None, extraction_type='obligations',
                 published=False):
        self.id = row_id
        self.storage_type = storage_type
        self.rdf_json_ld = rdf_json_ld or {}
        self.is_published = published
        self.committed_at = None
        self.content_hash = None
        self.entity_uri = f"http://proethica.org/ontology/case/8#e{row_id}"
        self.entity_label = label
        self.entity_definition = "test definition"
        self.extraction_type = extraction_type
        self.ontology_target = 'proethica-case-8'


def test_commit_refuses_to_publish_an_individual_typed_to_an_unpublished_class():
    module = 'app.services.commit.ontserve_commit_service'
    individual = _Row(1, 'individual', 'Engineer L Proactive Risk Disclosure Duty',
                      {'types': [f'{INT_NS}ProactiveRiskDisclosureObligation']})
    kept = _Row(2, 'individual', 'Engineer L Watershed Safety Duty', {'types': [f'{INT_NS}SafetyObligation']})
    dropped_class = _Row(5, 'class', 'Proactive Risk Disclosure Obligation')   # gate-dropped, unpublished
    svc = OntServeCommitService.__new__(OntServeCommitService)
    svc.ontologies_dir = Path('/fake/OntServe/ontologies')
    svc._established_core_category = lambda local: 'Obligation' if local == 'SafetyObligation' else None
    svc._record_conformance_provenance = MagicMock()
    svc._record_ontology_commit = MagicMock()
    svc._sync_ontology_to_db = MagicMock(return_value={'success': True})
    svc._commit_individuals_to_case_ontology = MagicMock(
        return_value={'count': 1, 'merged': 0, 'file': 'x.ttl', 'role_axis_vetoes': 0,
                      'qc_edges_dropped': 0, 'role_axis_vetoes_post_canonicalization': 0})
    storage = MagicMock()
    storage.query.filter.return_value.all.return_value = [individual, kept]
    storage.query.filter_by.return_value.all.return_value = [dropped_class]
    storage.compute_content_hash.return_value = 'hash'

    with patch(f'{module}.TemporaryRDFStorage', storage), \
         patch('app.services.extraction.conformance_gate.gate_case_ttl', return_value={'status': 'skipped'}), \
         patch('app.services.commit.precedent_features.update_entity_classes_from_storage', return_value={}), \
         patch('app.db'):
        result = svc.commit_selected_entities(8, [1, 2])

    assert result['success'] is True, result
    assert result['refused_unpublished_type'] == [
        {'label': 'Engineer L Proactive Risk Disclosure Duty', 'type_class': 'ProactiveRiskDisclosureObligation'}]
    committed = svc._commit_individuals_to_case_ontology.call_args
    assert [row.id for row, _ in committed.args[1]] == [2]
    assert committed.kwargs['rejected_class_keys'] == {'proactiveriskdisclosureobligation'}
    assert individual.is_published is False
    assert kept.is_published is True
