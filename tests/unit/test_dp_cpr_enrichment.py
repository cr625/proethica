"""
Tests for the DecisionPoint/CPR enrichment (intermediate 2026-07-11 +
proethica-cases v3.7.0): the shared emission helpers the serializer and the
gold-15 backfill both call, and the appliesTo family in the analysis-edge
expectations (category-scoped label resolution, never fabricated).
"""

from types import SimpleNamespace
from unittest.mock import patch

from rdflib import Graph, Literal, Namespace, RDF, RDFS, XSD

from app.services.commit.ontserve_commit_service import (
    emit_cpr_enrichment,
    emit_decision_point_enrichment,
)
from app.services.extraction.analysis_edges import build_expectations

PROETH = Namespace("http://proethica.org/ontology/intermediate#")
CASES = Namespace("http://proethica.org/ontology/cases#")
CORE = Namespace("http://proethica.org/ontology/core#")
CASE = Namespace("http://proethica.org/ontology/case/9#")

DP_DATA = {
    'board_resolution': 'The board found the design ethical.',
    'intensity_score': 0.7,
    'qc_alignment_score': 0.75,
    'provision_labels': ['I.1', 'I.2'],
    'toulmin': {
        'claim': 'the claim', 'qualifier': 'the qualifier',
        'data_summary': 'the data', 'warrants_summary': 'the warrants',
        'rebuttals_summary': 'the rebuttals',
        'backing_provisions': ['I.1', 'I.2', 'II.2.a'],
    },
    'options': [
        {'option_id': 'O1', 'label': 'Finalize Design',
         'description': 'Proceed as engineered.', 'is_board_choice': True},
        {'option_id': 'O2', 'label': 'Alternative Design',
         'description': 'Adopt the costlier alternative.', 'is_board_choice': False},
    ],
}


def test_dp_enrichment_emits_all_literals():
    g = Graph()
    uri = CASE['DP1']
    emit_decision_point_enrichment(g, uri, DP_DATA)

    assert (uri, PROETH.boardResolution,
            Literal('The board found the design ethical.')) in g
    assert (uri, PROETH.intensityScore,
            Literal('0.7', datatype=XSD.decimal)) in g
    assert (uri, PROETH.qcAlignmentScore,
            Literal('0.75', datatype=XSD.decimal)) in g
    for pred, text in (('toulminClaim', 'the claim'),
                       ('toulminQualifier', 'the qualifier'),
                       ('toulminData', 'the data'),
                       ('toulminWarrant', 'the warrants'),
                       ('toulminRebuttal', 'the rebuttals')):
        assert (uri, PROETH[pred], Literal(text)) in g
    # One designation set: the backing provisions win over provision_labels
    # (they are the same list in practice; emitting both would double codes).
    codes = {str(o) for o in g.objects(uri, PROETH.citedProvision)}
    assert codes == {'I.1', 'I.2', 'II.2.a'}
    options = {str(o) for o in g.objects(uri, PROETH.option)}
    assert options == {'1. Finalize Design: Proceed as engineered.',
                       '2. Alternative Design: Adopt the costlier alternative.'}
    assert (uri, PROETH.boardChosenOption, Literal('Finalize Design')) in g


def test_dp_enrichment_is_idempotent_replace():
    g = Graph()
    uri = CASE['DP1']
    emit_decision_point_enrichment(g, uri, DP_DATA)
    first = len(g)
    emit_decision_point_enrichment(g, uri, DP_DATA)
    assert len(g) == first


def test_cpr_excerpts_flattened_and_idempotent():
    g = Graph()
    uri = CASE['CPR_II_4_e']
    data = {'relevantExcerpts': [
        {'text': 'Engineer A is ineligible.', 'section': 'discussion'},
        {'text': 'No section carried.'},
        'a stray string that must be skipped',
    ]}
    emit_cpr_enrichment(g, uri, data)
    excerpts = {str(o) for o in g.objects(uri, PROETH.relevantExcerpt)}
    assert excerpts == {'[discussion] Engineer A is ineligible.',
                        'No section carried.'}
    emit_cpr_enrichment(g, uri, data)
    assert len(list(g.objects(uri, PROETH.relevantExcerpt))) == 2


def test_applies_to_edges_resolved_and_guarded():
    """appliesTo resolves by category-scoped label match; an unknown label or
    category becomes a miss (never a fabricated endpoint), and the reasoning
    travels as the edge's provenance source."""
    g = Graph()
    cpr = CASE['CPR_II_4_e']
    g.add((cpr, RDF.type, CASES.CodeProvisionReference))
    g.add((cpr, RDFS.label, Literal('II.4.e')))
    role = CASE['Engineer_A_County_Surveyor_Appointee']
    g.add((role, RDF.type, CORE.Role))
    g.add((role, RDFS.label, Literal('Engineer A County Surveyor Appointee')))

    cpr_row = SimpleNamespace(entity_label='II.4.e', rdf_json_ld={
        'codeProvision': 'II.4.e',
        'appliesTo': [
            {'entity_label': 'Engineer A County Surveyor Appointee',
             'entity_type': 'role', 'reasoning': 'why it applies'},
            {'entity_label': 'Nonexistent Entity', 'entity_type': 'role',
             'reasoning': 'x'},
            {'entity_label': 'Mystery', 'entity_type': 'unknown_type',
             'reasoning': 'y'},
        ],
    })

    def rows(case_id, etype):
        return [cpr_row] if etype == 'code_provision_reference' else []

    with patch('app.services.extraction.analysis_edges._rows', side_effect=rows), \
         patch('app.models.db') as mock_db:
        mock_db.session.execute.return_value.fetchall.return_value = [('II.4.e.',)]
        edges, misses = build_expectations(9, g)

    applies = [(s, o, src) for s, p, o, src in edges if p == 'appliesTo']
    assert applies == [(cpr, role, 'why it applies')]
    assert any('Nonexistent Entity' in m for m in misses)
    assert any('known category' in m for m in misses)
