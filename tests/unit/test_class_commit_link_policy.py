"""Class-channel rules from the case-8 review (L3).

class_commit minted shared classes from rows whose match decision said
matches_existing true: PublicSafetyObligation (matched SafetyObligation at
0.95) and UnbuildableDesignState (matched ProjectFailureRiskState at 0.85,
and committed under a reference-sheet IRI with the case-8 text as its
definition). The accumulate path appended case context onto
RegulatoryComplianceObligation, a class the extraction had declined to match,
and vetoed only cross core-category parents, so RegulatoryViolationState
accumulated four state-archetype parents.

DB-free: the service is built with __new__ against a tmp ontologies dir, the
immutable-base map is planted empty, and the reference sheet is a tmp YAML.
"""
import types
import textwrap

import pytest
from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS, URIRef, XSD
from rdflib.namespace import SKOS

from app.services.commit.match_policy import (
    DEFAULT_MATCH_LINK_THRESHOLD, linked_existing_class, match_link_threshold,
)
from app.services.commit.ontserve_commit_service import OntServeCommitService
from app.services.extraction.entity_matcher import HIGH_BAND_MIN

INT = Namespace("http://proethica.org/ontology/intermediate#")
CORE = Namespace("http://proethica.org/ontology/core#")
PROV_NS = Namespace("http://proethica.org/provenance#")


def _svc(tmp_path, sheet=None):
    svc = OntServeCommitService.__new__(OntServeCommitService)
    svc.ontologies_dir = tmp_path
    svc._base_ontology_index._base_cat_cache = {}   # nothing reserved in the immutable base
    if sheet is None:
        svc._reference_sheet_definition = lambda local, label: None
    else:
        svc.reference_sheet_dir = str(sheet)
    return svc


def _entity(label, extraction_type='obligations', definition='Row definition.'):
    return types.SimpleNamespace(
        extraction_type=extraction_type, entity_type=extraction_type, entity_label=label,
        entity_definition=definition, iao_document_uri=None, iao_document_label=None,
        cited_by_role=None, available_to_role=None, extraction_model=None,
    )


def _match(matched_local, confidence, matches_existing=True):
    return {'matches_existing': matches_existing, 'matched_uri': str(INT[matched_local]),
            'matched_label': matched_local, 'confidence': confidence, 'reasoning': 'test'}


def _extended(tmp_path):
    g = Graph()
    g.parse(tmp_path / 'proethica-intermediate-extended.ttl', format='turtle')
    return g


def test_default_link_threshold_is_the_auto_link_band(monkeypatch):
    monkeypatch.delenv('PROETHICA_MATCH_LINK_THRESHOLD', raising=False)
    assert DEFAULT_MATCH_LINK_THRESHOLD == HIGH_BAND_MIN == 0.85
    assert match_link_threshold() == 0.85
    assert match_link_threshold(0.7) == 0.7
    monkeypatch.setenv('PROETHICA_MATCH_LINK_THRESHOLD', '0.9')
    assert match_link_threshold() == 0.9
    assert linked_existing_class({'match_decision': _match('SafetyObligation', 0.95)}, 0.85) == 'SafetyObligation'
    assert linked_existing_class({'match_decision': _match('SafetyObligation', 0.75)}, 0.85) is None
    assert linked_existing_class({'match_decision': _match('SafetyObligation', 0.95, False)}, 0.85) is None
    assert linked_existing_class({}, 0.85) is None


def test_row_linked_at_or_above_threshold_is_not_minted(tmp_path):
    svc = _svc(tmp_path)
    rows = [(_entity('Public Safety Obligation'),
             {'properties': {'obligation_type': ['safety'], 'discoveredInCase': [8]},
              'match_decision': _match('SafetyObligation', 0.95)})]
    result = svc._commit_classes_to_intermediate(rows)
    assert result.get('error') is None, result
    assert result['count'] == 0 and result['linked_existing'] == 1
    assert (INT.PublicSafetyObligation, RDF.type, OWL.Class) not in _extended(tmp_path)


def test_link_honoring_cannot_follow_is_minted(tmp_path):
    """Honoring keeps the minted type when the matched local name is not URI-safe, so the
    class channel declares it instead of treating the match as reuse."""
    svc = _svc(tmp_path)
    md = {'matches_existing': True,
          'matched_uri': 'http://proethica.org/ontology/concepts#Conflict_of_Interest_Avoidance',
          'matched_label': 'Conflict of Interest Avoidance (Constraint)', 'confidence': 0.9,
          'reasoning': 'test'}
    rows = [(_entity('Conflict of Interest Avoidance Constraint', extraction_type='constraints'),
             {'properties': {'discoveredInCase': [144]}, 'match_decision': md})]
    result = svc._commit_classes_to_intermediate(rows)
    assert result.get('error') is None, result
    assert result['count'] == 1 and result['linked_existing'] == 0
    assert (INT.ConflictofInterestAvoidanceConstraint, RDF.type, OWL.Class) in _extended(tmp_path)


def test_row_below_threshold_is_minted(tmp_path):
    svc = _svc(tmp_path)
    rows = [(_entity('Public Safety Obligation'),
             {'properties': {'obligation_type': ['safety'], 'discoveredInCase': [8]},
              'match_decision': _match('SafetyObligation', 0.75)})]
    result = svc._commit_classes_to_intermediate(rows)
    assert result['count'] == 1 and result['linked_existing'] == 0
    g = _extended(tmp_path)
    assert (INT.PublicSafetyObligation, RDF.type, OWL.Class) in g
    assert (INT.PublicSafetyObligation, RDFS.subClassOf, INT.SafetyObligation) in g


def test_threshold_is_configurable(tmp_path, monkeypatch):
    svc = _svc(tmp_path)
    svc.match_link_threshold = 0.7
    rows = [(_entity('Public Safety Obligation'),
             {'properties': {'obligation_type': ['safety']},
              'match_decision': _match('SafetyObligation', 0.75)})]
    assert svc._commit_classes_to_intermediate(rows)['count'] == 0

    svc2 = _svc(tmp_path)
    monkeypatch.setenv('PROETHICA_MATCH_LINK_THRESHOLD', '0.97')
    rows2 = [(_entity('Watershed Safety Obligation'),
              {'properties': {'obligation_type': ['safety']},
               'match_decision': _match('SafetyObligation', 0.95)})]
    assert svc2._commit_classes_to_intermediate(rows2)['count'] == 1


def test_self_match_rediscovery_still_accumulates(tmp_path):
    """A row matched to ITS OWN IRI is a re-discovery of the same class."""
    svc = _svc(tmp_path)
    g = Graph()
    g.add((INT.ProactiveDisclosureObligation, RDF.type, OWL.Class))
    g.add((INT.ProactiveDisclosureObligation, RDFS.subClassOf, INT.DisclosureObligation))
    g.add((INT.ProactiveDisclosureObligation, PROV_NS.discoveredInCase, Literal(3, datatype=XSD.integer)))
    g.serialize(destination=tmp_path / 'proethica-intermediate-extended.ttl', format='turtle')
    rows = [(_entity('Proactive Disclosure Obligation'),
             {'properties': {'obligation_type': ['disclosure'], 'discoveredInCase': [8]},
              'match_decision': _match('ProactiveDisclosureObligation', 0.95)})]
    result = svc._commit_classes_to_intermediate(rows)
    assert result['count'] == 0 and result['linked_existing'] == 0
    g2 = _extended(tmp_path)
    assert (INT.ProactiveDisclosureObligation, PROV_NS.discoveredInCase, Literal(8, datatype=XSD.integer)) in g2


def test_declined_match_does_not_accumulate_onto_the_existing_class(tmp_path):
    svc = _svc(tmp_path)
    g = Graph()
    g.add((INT.RegulatoryComplianceObligation, RDF.type, OWL.Class))
    g.add((INT.RegulatoryComplianceObligation, RDFS.subClassOf, INT.LegalObligation))
    g.add((INT.RegulatoryComplianceObligation, SKOS.definition, Literal('Procurement compliance duty.')))
    g.add((INT.RegulatoryComplianceObligation, PROV_NS.discoveredInCase, Literal(3, datatype=XSD.integer)))
    g.serialize(destination=tmp_path / 'proethica-intermediate-extended.ttl', format='turtle')
    rows = [(_entity('Regulatory Compliance Obligation', definition='Environmental compliance in case 8.'),
             {'properties': {'obligation_type': ['legal'], 'discoveredInCase': [8]},
              'match_decision': _match('RegulatoryComplianceObligation', 0.6, matches_existing=False)})]
    result = svc._commit_classes_to_intermediate(rows)
    assert result['count'] == 0 and result['declined_accumulations'] == 1
    g2 = _extended(tmp_path)
    assert (INT.RegulatoryComplianceObligation, PROV_NS.discoveredInCase, Literal(8, datatype=XSD.integer)) not in g2
    assert not list(g2.objects(INT.RegulatoryComplianceObligation, SKOS.scopeNote))


def test_one_archetype_parent_per_state_class(tmp_path):
    svc = _svc(tmp_path)
    g = Graph()
    g.add((INT.RegulatoryViolationState, RDF.type, OWL.Class))
    g.add((INT.RegulatoryViolationState, RDFS.subClassOf, INT.RegulatoryState))
    g.serialize(destination=tmp_path / 'proethica-intermediate-extended.ttl', format='turtle')
    # Re-discovered under three other state archetypes: every incoming archetype is vetoed.
    rows = [(_entity('Regulatory Violation State', extraction_type='states'),
             {'properties': {'state_category': [cat], 'discoveredInCase': [8]}})
            for cat in ('competence', 'disclosure', 'epistemic')]
    result = svc._commit_classes_to_intermediate(rows)
    assert result.get('error') is None, result
    g2 = _extended(tmp_path)
    assert set(g2.objects(INT.RegulatoryViolationState, RDFS.subClassOf)) == {INT.RegulatoryState}
    # The same archetype is admissible (already present), and a non-archetype parent passes the gate.
    assert svc._archetype_axis_conflict(str(INT.RegulatoryState), {INT.RegulatoryState}) is None
    assert svc._archetype_axis_conflict(str(INT.CompetenceState), {INT.RegulatoryState}) == str(INT.RegulatoryState)
    assert svc._archetype_axis_conflict(str(CORE.State), {INT.RegulatoryState}) is None
    assert svc._archetype_axis_conflict(str(INT.RiskState), set()) is None


def _sheet(tmp_path):
    sheet = tmp_path / 'sheet'
    sheet.mkdir()
    (sheet / 'manifest.yaml').write_text('{}\n', encoding='utf-8')
    (sheet / 'state.yaml').write_text(textwrap.dedent('''\
        component: State
        canonical:
          - iri: UnbuildableDesignState
            label: Unbuildable Design State
            parent: RiskState
            definition: >-
              A condition in which a design cannot be constructed as specified,
              independent of which project exposed it.
            status: canonical
    '''), encoding='utf-8')
    return sheet


def test_reference_sheet_iri_takes_the_sheet_definition(tmp_path):
    svc = _svc(tmp_path, sheet=_sheet(tmp_path))
    rows = [(_entity('Unbuildable Design State', extraction_type='states',
                     definition='The case-8 design could not be built after the rainfall.'),
             {'properties': {'state_category': ['risk'], 'discoveredInCase': [8]},
              'definitions': [{'text': 'The case-8 design could not be built after the rainfall.',
                               'is_primary': True, 'source_section': 'facts'}]})]
    result = svc._commit_classes_to_intermediate(rows)
    assert result.get('error') is None, result
    assert result['count'] == 1
    g = _extended(tmp_path)
    cls = INT.UnbuildableDesignState
    sheet_text = ('A condition in which a design cannot be constructed as specified, '
                  'independent of which project exposed it.')
    assert str(g.value(cls, SKOS.definition)) == sheet_text
    assert str(g.value(cls, RDFS.comment)) == sheet_text
    assert set(str(o) for o in g.objects(cls, SKOS.scopeNote)) == {
        '[Case 8] The case-8 design could not be built after the rainfall.'}


def test_class_outside_the_sheet_keeps_the_row_definition(tmp_path):
    svc = _svc(tmp_path, sheet=_sheet(tmp_path))
    rows = [(_entity('Novel Site Condition State', extraction_type='states',
                     definition='A site condition first seen in case 8.'),
             {'properties': {'state_category': ['risk']}})]
    assert svc._commit_classes_to_intermediate(rows)['count'] == 1
    g = _extended(tmp_path)
    assert str(g.value(INT.NovelSiteConditionState, SKOS.definition)) == 'A site condition first seen in case 8.'
