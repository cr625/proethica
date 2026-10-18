"""Matched-class honoring floor and type write-back (case-8 review, L4).

_matched_class_override honored the matcher's class at any confidence (0.75 for
a "matched to parent with medium confidence" decision) and did not write the
honored rdf:type back to the working-store row, so the review pages showed one
type and the TTL another for four individuals of case 8. The floor is the
match-link threshold shared with the class channel (default: the matcher's
auto-link band, 0.85), and both TTL writers write the honored type back onto
rdf_json_ld.types.

DB-free (tests/mocks/commit_service_stub.py, SimpleNamespace rows).
"""
import types

from rdflib import Graph, Namespace, RDF, URIRef

from app.services.commit.ontserve_commit_service import OntServeCommitService
from tests.mocks.commit_service_stub import make_stub_commit_service

INT_NS = "http://proethica.org/ontology/intermediate#"
CORE_NS = "http://proethica.org/ontology/core#"


def _bare(chain):
    svc = object.__new__(OntServeCommitService)
    svc._established_core_category = chain
    return svc


def _rdf_data(confidence, matched='AttributionObligation', minted='DisclosureObligationDraft'):
    return {
        'types': [f'{INT_NS}{minted}'],
        'match_decision': {'matches_existing': True, 'matched_uri': f'{INT_NS}{matched}',
                           'matched_label': matched, 'confidence': confidence, 'reasoning': 'test'},
    }


def test_medium_confidence_match_is_not_honored(monkeypatch):
    monkeypatch.delenv('PROETHICA_MATCH_LINK_THRESHOLD', raising=False)
    svc = _bare(lambda local: 'Obligation')
    data = _rdf_data(0.75)
    assert svc._matched_class_override(data, 'Obligation', data['types']) is None
    assert svc._matched_class_override(_rdf_data(0.85), 'Obligation', data['types']) == 'AttributionObligation'
    assert svc._matched_class_override(_rdf_data(0.9), 'Obligation', data['types']) == 'AttributionObligation'
    # A decision without a usable confidence is below any floor.
    nodata = _rdf_data(None)
    assert svc._matched_class_override(nodata, 'Obligation', nodata['types']) is None


def test_floor_configurable_per_instance_and_by_environment(monkeypatch):
    svc = _bare(lambda local: 'Obligation')
    svc.match_link_threshold = 0.7
    assert svc._matched_class_override(_rdf_data(0.75), 'Obligation', [f'{INT_NS}X']) == 'AttributionObligation'
    env_svc = _bare(lambda local: 'Obligation')
    monkeypatch.setenv('PROETHICA_MATCH_LINK_THRESHOLD', '0.95')
    assert env_svc._matched_class_override(_rdf_data(0.9), 'Obligation', [f'{INT_NS}X']) is None


def _row(label, rdf_data):
    return types.SimpleNamespace(
        extraction_type='obligations', entity_type='obligations', entity_label=label,
        entity_definition='A duty.', iao_document_uri=None, iao_document_label=None,
        cited_by_role=None, available_to_role=None, extraction_model=None,
        rdf_json_ld=rdf_data,
    )


def _service(tmp_path, monkeypatch):
    return make_stub_commit_service(
        tmp_path, monkeypatch,
        chain_resolver=lambda local: 'Obligation' if local == 'AttributionObligation' else None,
        header_fields={'title': 'Mock Case', 'case_number': None, 'decade': None})


def test_honored_type_written_back_on_the_append_path(tmp_path, monkeypatch):
    monkeypatch.delenv('PROETHICA_MATCH_LINK_THRESHOLD', raising=False)
    svc = _service(tmp_path, monkeypatch)
    data = _rdf_data(0.9)
    row = _row('Credit Attribution Duty', data)
    result = svc._commit_individuals_to_case_ontology(8, [(row, data)])
    assert result.get('error') is None, result
    assert data['types'] == [f'{INT_NS}AttributionObligation']
    assert row.rdf_json_ld['types'] == [f'{INT_NS}AttributionObligation']
    g = Graph()
    g.parse(result['file'], format='turtle')
    ind = Namespace('http://proethica.org/ontology/case/8#')['Credit_Attribution_Duty']
    assert (ind, RDF.type, URIRef(f'{INT_NS}AttributionObligation')) in g
    assert (ind, RDF.type, URIRef(f'{INT_NS}DisclosureObligationDraft')) not in g


def test_honored_type_written_back_on_the_versioned_path(tmp_path, monkeypatch):
    monkeypatch.delenv('PROETHICA_MATCH_LINK_THRESHOLD', raising=False)
    svc = _service(tmp_path, monkeypatch)
    data = _rdf_data(0.9)
    row = _row('Credit Attribution Duty', data)
    result = svc._write_case_ttl_fresh(9, [(row, data)])
    assert result.get('error') is None, result
    assert row.rdf_json_ld['types'] == [f'{INT_NS}AttributionObligation']
    g = Graph()
    g.parse(result['file'], format='turtle')
    ind = Namespace('http://proethica.org/ontology/case/9#')['Credit_Attribution_Duty']
    assert (ind, RDF.type, URIRef(f'{INT_NS}AttributionObligation')) in g


def test_below_floor_keeps_the_minted_type_in_both_stores(tmp_path, monkeypatch):
    monkeypatch.delenv('PROETHICA_MATCH_LINK_THRESHOLD', raising=False)
    svc = _service(tmp_path, monkeypatch)
    data = _rdf_data(0.75)
    row = _row('Credit Attribution Duty', data)
    result = svc._commit_individuals_to_case_ontology(10, [(row, data)])
    assert result.get('error') is None, result
    assert row.rdf_json_ld['types'] == [f'{INT_NS}DisclosureObligationDraft']
    g = Graph()
    g.parse(result['file'], format='turtle')
    ind = Namespace('http://proethica.org/ontology/case/10#')['Credit_Attribution_Duty']
    assert (ind, RDF.type, URIRef(f'{INT_NS}DisclosureObligationDraft')) in g
    assert (ind, RDF.type, URIRef(f'{INT_NS}AttributionObligation')) not in g
    assert (ind, RDF.type, URIRef(f'{CORE_NS}Obligation')) in g
