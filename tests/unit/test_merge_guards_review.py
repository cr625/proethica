"""Review of the merge-guards lessons (brief 2 of docs/reviews/lessons/cloud_briefs.md).

Three defects found in the merge review, each with the scenario that broke:

1. The exact-match auto merge folded a row into the kept row through a refused
   bridge. _exact_match_groups joins rows connected by a label OR an IRI, and
   the fold walked every member of the set against the first row. With rows
   A "Risk State" (matched RiskState), B "Risk State" (IRI and match
   HazardState) and C "Hazard State" (IRI HazardState, unmatched), B was
   refused (matched classes differ) and C, which shares neither label nor IRI
   with A, was folded into A with basis "label". On the base, label-only
   grouping left C alone. The fold now joins a row only through a label or an
   IRI the kept component already holds, the refused rows and the rows behind
   them fold among themselves, and the kept row of a set is its first matched
   row, so a fold no longer discards the match of the row it deletes.

2. The rename map left a matched individual typed to a class no row holds. A
   class row whose match sat below the link band (0.75, decision flag off) was
   reused onto its matched class, LegalObligation, as lesson L2 allows; its
   individual carried the same match and was "protected" by lesson L4 from the
   very rename onto that class, so it stayed typed to the compound IRI the
   class row had left. A rename onto the matched class is now applied; a rename
   onto any other class is still refused.

3. The canonicalizer minted its IRIs with the hyphen-keeping sanitizer while
   storage (storage-persistence, lesson L5) mints class rows and individual
   types with naming.safe_local_name. A REUSE of "Competence Self-Assessment
   Capability", a sheet label with a hyphen, wrote
   intermediate#CompetenceSelf-AssessmentCapability, so the collision veto and
   the entity_uri fold missed the row that already held the curated IRI, and
   the repointed individuals named an IRI no store declares. DomainConfig
   .class_iri now uses the storage sanitizer.

Hermetic: rows are plain objects, the ORM loaders and the model call are
stubbed, as in tests/unit/test_merge_guards_case8.py, whose helpers and
curated-tier fixture this module reuses.
"""
import pytest

from app.services.commit import naming
from app.services.entity.entity_reconciliation_service import EntityReconciliationService
from app.services.extraction.domain_config import active_domain
from app.services.extraction.extraction_graph import individual_type_iri
from tests.unit.test_merge_guards_case8 import (  # noqa: F401  (curated is a fixture, used by name)
    INT,
    _merge_harness,
    _row,
    _service,
    curated,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. Fold sets: a refused bridge, the basis of a transitive fold, the kept row
# ---------------------------------------------------------------------------

def test_a_refused_bridge_does_not_carry_the_rows_behind_it_into_the_kept_row():
    rows = [
        _row(1, 'states', 'Risk State', uri=INT + 'RiskState',
             matched=INT + 'RiskState', confidence=0.9),
        _row(2, 'states', 'Risk State', uri=INT + 'HazardState',
             matched=INT + 'HazardState', confidence=0.95),
        _row(3, 'states', 'Hazard State', uri=INT + 'HazardState'),
    ]
    svc, calls = _merge_harness(rows)
    result = svc.reconcile_auto(8)
    # B is refused against A; C shares an IRI with B only, so it folds into B, not into A.
    assert calls == [(2, 3)]
    assert [(r['kept_id'], r['refused_id'], r['reason']) for r in result.merge_refusals] == [
        (1, 2, 'matched_ontology_uri_differs')]
    assert result.merged_pairs == [{
        'merged_id': 3, 'merged_label': 'Hazard State',
        'kept_id': 2, 'surviving_label': 'Risk State', 'basis': 'entity_uri',
    }]
    assert [(r.id, r.entity_uri) for r in rows] == [(1, INT + 'RiskState'), (2, INT + 'HazardState')]


def test_a_bridge_processed_last_still_folds_the_set_with_the_basis_of_the_actual_link():
    rows = [
        _row(1, 'states', 'Risk State', uri=INT + 'RiskState'),
        _row(3, 'states', 'Hazard State', uri=INT + 'HazardState'),
        _row(2, 'states', 'risk state', uri=INT + 'HazardState'),
    ]
    svc, calls = _merge_harness(rows)
    result = svc.reconcile_auto(8)
    assert calls == [(1, 2), (1, 3)]
    assert [(p['merged_id'], p['basis']) for p in result.merged_pairs] == [
        (2, 'label'), (3, 'entity_uri')]
    assert [r.id for r in rows] == [1]


def test_the_kept_row_of_a_fold_set_is_its_matched_row():
    rows = [
        _row(2, 'obligations', 'Confidentiality Obligation (Present Case)',
             uri=INT + 'ConfidentialityObligationPresentCase'),
        _row(1, 'obligations', 'Confidentiality Obligation',
             matched=INT + 'ConfidentialityObligation', confidence=0.9),
    ]
    svc, calls = _merge_harness(rows)
    result = svc.reconcile_auto(8)
    assert calls == [(1, 2)]
    assert result.merged_pairs == [{
        'merged_id': 2, 'merged_label': 'Confidentiality Obligation (Present Case)',
        'kept_id': 1, 'surviving_label': 'Confidentiality Obligation', 'basis': 'label',
    }]
    assert [(r.id, r.entity_uri, r.matched_ontology_uri) for r in rows] == [
        (1, INT + 'ConfidentialityObligation', INT + 'ConfidentialityObligation')]


def test_rows_matched_to_different_classes_each_keep_their_own_set():
    # Three rows of one label, two matched to different classes: each matched row keeps its
    # set, the unmatched third row (sharing the label only) folds into the first kept row.
    rows = [
        _row(1, 'states', 'Risk State', uri=INT + 'RiskState',
             matched=INT + 'RiskState', confidence=0.9),
        _row(2, 'states', 'Risk State', uri=INT + 'HazardState',
             matched=INT + 'HazardState', confidence=0.95),
        _row(3, 'states', 'Risk State', uri=INT + 'RiskStateB'),
    ]
    svc, calls = _merge_harness(rows)
    result = svc.reconcile_auto(8)
    assert calls == [(1, 3)]
    assert [(r['kept_id'], r['refused_id']) for r in result.merge_refusals] == [(1, 2)]
    assert [r.id for r in rows] == [1, 2]


# ---------------------------------------------------------------------------
# 2. The rename map and a matched individual
# ---------------------------------------------------------------------------

def test_a_rename_onto_the_matched_class_reaches_a_protected_individual():
    svc = EntityReconciliationService()
    onto_match = _row(95625, 'obligations', 'Client X Environmental Compliance Duty',
                      storage_type='individual',
                      types=[INT + 'EnvironmentalStandardsComplianceObligation'],
                      matched=INT + 'LegalObligation', confidence=0.75, matches_existing=False)
    column_only = _row(95605, 'states', 'Column Only', storage_type='individual',
                       types=[INT + 'DamOvertoppingRiskState'],
                       matched=INT + 'RiskState', confidence=0.85, md=False)
    away = _row(95603, 'states', 'Project Failure Risk', storage_type='individual',
                types=[INT + 'ProjectFailureRiskState'],
                matched=INT + 'ProjectFailureRiskState', confidence=0.85)
    svc._load_individuals = lambda case_id: [onto_match, column_only, away]
    rename_map = {
        INT + 'EnvironmentalStandardsComplianceObligation': INT + 'LegalObligation',
        INT + 'DamOvertoppingRiskState': INT + 'RiskState',
        INT + 'ProjectFailureRiskState': INT + 'UnbuildableDesignState',
    }

    changed, protected = svc._repoint_individual_types(8, rename_map, write=True)

    assert (changed, protected) == (2, 1)
    assert onto_match.rdf_json_ld['types'] == [INT + 'LegalObligation']
    assert column_only.rdf_json_ld['types'] == [INT + 'RiskState']
    assert away.rdf_json_ld['types'] == [INT + 'ProjectFailureRiskState']


@pytest.mark.usefixtures('curated')
def test_class_row_and_its_individual_end_on_one_iri_after_a_below_band_reuse():
    # Row 95622 with its match below the link band and the decision flag off is sent to the
    # model, which reuses its matched class (the only target L2 admits). Its individual, which
    # carries the same match, follows the class row onto LegalObligation.
    cls = _row(95622, 'obligations', 'Environmental Standards Compliance Obligation',
               matched=INT + 'LegalObligation', confidence=0.75, matches_existing=False,
               definition='A duty to comply with the environmental standards and regulations '
                          'that govern stormwater discharge to a drinking water source.')
    ind = _row(95625, 'obligations', 'Client X Environmental Compliance Duty',
               storage_type='individual',
               types=[INT + 'EnvironmentalStandardsComplianceObligation'],
               matched=INT + 'LegalObligation', confidence=0.75, matches_existing=False)
    svc = _service([cls], [ind], {95622: {'action': 'reuse', 'canonical_label': 'Legal Obligation'}})

    summary = svc.canonicalize_labels(8)

    assert summary['changed'] == 1 and cls.entity_uri == INT + 'LegalObligation'
    assert ind.rdf_json_ld['types'] == [INT + 'LegalObligation']
    assert (summary['individuals_repointed'], summary['individuals_protected']) == (1, 0)


# ---------------------------------------------------------------------------
# 3. The canonical IRI follows the storage sanitizer
# ---------------------------------------------------------------------------

def test_class_iri_uses_the_sanitizer_storage_mints_with():
    label = 'Competence Self-Assessment Capability'
    cfg = active_domain()
    assert cfg.class_iri(label) == INT + 'CompetenceSelfAssessmentCapability'
    assert cfg.class_iri(label) == INT + naming.safe_local_name(label)
    assert cfg.class_iri(label) == individual_type_iri(label, None)
    assert cfg.class_iri('Provider-Client Role') == INT + 'ProviderClientRole'


@pytest.mark.usefixtures('curated')
def test_a_reuse_of_a_hyphenated_sheet_label_lands_on_the_curated_iri():
    row = _row(95626, 'capabilities', 'Engineering Design Capability',
               definition='The competence to produce an engineering design.')
    ind = _row(95631, 'capabilities', 'Engineer L Design Capability', storage_type='individual',
               types=[INT + 'EngineeringDesignCapability'])
    svc = _service([row], [ind], {95626: {
        'action': 'reuse', 'canonical_label': 'Competence Self-Assessment Capability'}})

    summary = svc.canonicalize_labels(8)

    assert summary['rejected'] == [] and summary['changed'] == 1
    assert row.entity_uri == INT + 'CompetenceSelfAssessmentCapability'
    assert summary['changes'][0]['new_uri'] == row.entity_uri
    assert ind.rdf_json_ld['types'] == [INT + 'CompetenceSelfAssessmentCapability']


@pytest.mark.usefixtures('curated')
def test_a_collision_with_a_storage_minted_iri_is_seen_through_a_hyphenated_label():
    # The holder carries the IRI storage minted for the curated class and is matched to a
    # different class; the row is matched to the curated class below the band and the model
    # reuses it by its hyphenated sheet label. The veto must find the holder.
    holder = _row(95627, 'capabilities', 'Competence Self-Assessment Capability',
                  uri=INT + 'CompetenceSelfAssessmentCapability',
                  matched=INT + 'DisclosureCapability', confidence=0.9)
    row = _row(95626, 'capabilities', 'Engineering Design Capability',
               matched=INT + 'CompetenceSelfAssessmentCapability', confidence=0.6,
               matches_existing=False)
    svc = _service([holder, row], [], {95626: {
        'action': 'reuse', 'canonical_label': 'Competence Self-Assessment Capability'}})

    summary = svc.canonicalize_labels(8)

    assert summary['changed'] == 0
    assert [(r['id'], r['reason']) for r in summary['rejected']] == [(95626, 'entity_uri_collision')]
    assert '95627' in summary['rejected'][0]['detail']
    assert row.entity_uri == INT + 'EngineeringDesignCapability'


@pytest.mark.usefixtures('curated')
def test_a_foldable_holder_with_a_storage_minted_iri_is_flagged_for_the_merge():
    holder = _row(95627, 'capabilities', 'Competence Self-Assessment Capability',
                  uri=INT + 'CompetenceSelfAssessmentCapability',
                  matched=INT + 'CompetenceSelfAssessmentCapability', confidence=0.95)
    row = _row(95626, 'capabilities', 'Engineering Design Capability')
    svc = _service([holder, row], [], {95626: {
        'action': 'reuse', 'canonical_label': 'Competence Self-Assessment Capability'}})

    summary = svc.canonicalize_labels(8)

    assert summary['changed'] == 1 and summary['changes'][0]['merge_expected_with'] == [95627]
    assert row.entity_uri == holder.entity_uri
