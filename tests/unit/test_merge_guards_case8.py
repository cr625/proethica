"""Merge-stage guards from the NSPE case 24-1 (ProEthica case 8) review.

Pipeline run 48 canonicalized 21 class rows and auto-merged one after ``matching.py`` had
already linked the rows to existing ontology classes. The commit honored the matcher, so the
committed TTL was right while the working store (temporary_rdf_storage) was wrong. Each
observed row is replayed here against the guards:

  L1  a class row the matcher linked to an existing class is left unchanged
  L2  a canonicalization decision is vetoed on matched-class, specialization, sheet-offer,
      IRI-collision, extended-definition and role-axis grounds, with the reason recorded
  L3  the auto merge groups by entity_uri as well as by label, refuses to fold rows whose
      matched classes differ, and reports the pairs
  L4  the rename map never repoints an individual whose own match decision names an
      existing class
  L5  per-value principle duplicates and near-identical constraints become review candidates

DB/LLM-free: rows are plain objects, the ORM loaders and the model call are stubbed on the
service instance, the curated tiers are small fixture TTLs in tmp_path, and the reference
sheet is a stub (or, for its own test, a fixture directory of YAML files).
"""
from types import SimpleNamespace

import pytest

import app.services.entity.entity_reconciliation_service as ers
from app.services.entity.entity_reconciliation_service import (
    CONSTRAINT_STATEMENT_SIMILARITY_MIN,
    EXTENDED_DEFINITION_OVERLAP_MIN,
    MATCH_LINK_THRESHOLD,
    EntityReconciliationService,
    ReconciliationResult,
    _definition_overlap,
)
from app.services.extraction import category_resolver
from app.services.extraction import reference_sheet
from app.services.extraction.category_resolver import ClassHierarchyIndex, RoleAxisResolver
from app.services.extraction.entity_matcher import HIGH_BAND_MIN

pytestmark = pytest.mark.unit

INT = "http://proethica.org/ontology/intermediate#"
CORE = "http://proethica.org/ontology/core#"
CASE = "http://proethica.org/ontology/case/8#"

# ---------------------------------------------------------------------------
# Fixture curated tiers (the classes the case-8 rows touched)
# ---------------------------------------------------------------------------

_PREFIXES = """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix proeth: <http://proethica.org/ontology/intermediate#> .
@prefix proeth-core: <http://proethica.org/ontology/core#> .
"""

_CORE_TTL = _PREFIXES + """
proeth-core:Role a owl:Class . proeth-core:Obligation a owl:Class . proeth-core:State a owl:Class .
proeth-core:Capability a owl:Class . proeth-core:Principle a owl:Class .
proeth-core:Constraint a owl:Class . proeth-core:Resource a owl:Class .
proeth-core:Action a owl:Class . proeth-core:Event a owl:Class .
"""

_INTERMEDIATE_TTL = _PREFIXES + """
proeth:ProfessionalRole a owl:Class ; rdfs:subClassOf proeth-core:Role .
proeth:ParticipantRole a owl:Class ; rdfs:subClassOf proeth-core:Role .
proeth:PublicRole a owl:Class ; rdfs:subClassOf proeth:ParticipantRole .
proeth:PublicResponsibilityRole a owl:Class ; rdfs:subClassOf proeth:ProfessionalRole .
proeth:SafetyObligation a owl:Class ; rdfs:subClassOf proeth-core:Obligation ;
    skos:definition "Duty to hold paramount the safety, health, and welfare of the public (NSPE I.1)" .
proeth:LegalObligation a owl:Class ; rdfs:subClassOf proeth-core:Obligation .
proeth:RiskState a owl:Class ; rdfs:subClassOf proeth-core:State .
proeth:EpistemicState a owl:Class ; rdfs:subClassOf proeth-core:State .
proeth:DisclosureCapability a owl:Class ; rdfs:subClassOf proeth-core:Capability ;
    skos:definition "The competence to communicate material facts, risks, limitations, or affiliations to the parties entitled to them." .
proeth:CompetenceSelfAssessmentCapability a owl:Class ; rdfs:subClassOf proeth-core:Capability ;
    skos:definition "The competence to honestly appraise and verify one's own qualifications before undertaking work." .
"""

_EXTENDED_TTL = _PREFIXES + """
proeth:PublicSafetyObligation a owl:Class ; rdfs:subClassOf proeth:SafetyObligation ;
    skos:definition "A professional duty to hold paramount the safety, health, and welfare of the public, here the duty to ensure that stormwater from a new development will not impact a community's primary drinking water source." .
proeth:RegulatoryComplianceObligation a owl:Class ; rdfs:subClassOf proeth:LegalObligation ;
    skos:definition "A professional duty of public-entity engineers and public entities to comply with qualifications-based selection procurement requirements, including conducting an RFQ process and obtaining governing-body authorization when contract dollar amounts exceed the threshold." .
proeth:ProjectFailureRiskState a owl:Class ; rdfs:subClassOf proeth:RiskState ;
    skos:definition "A condition of exposure in which going forward with a project carries a risk of unsuccessful outcome and disastrous consequences." .
proeth:UnbuildableDesignState a owl:Class ; rdfs:subClassOf proeth:RiskState ;
    skos:definition "A condition in which a design or contract as specified cannot be constructed as intended, bearing on constructability and disclosure obligations." .
proeth:ConfirmedRiskFindingState a owl:Class ; rdfs:subClassOf proeth:EpistemicState ;
    skos:definition "An epistemic condition in which a professional's identification of a risk has risen from preliminary concern to the technical and moral level of fact." .
proeth:UnquantifiedRiskState a owl:Class ; rdfs:subClassOf proeth:EpistemicState ;
    skos:definition "An epistemic condition in which a professional is aware of a potential risk but has not yet quantified or fully characterized it." .
proeth:EngineeringDesignCapability a owl:Class ; rdfs:subClassOf proeth-core:Capability ;
    skos:definition "The competence to produce an engineering design, including the plans, analyses, and system configuration for a project system." .
proeth:EngineeringAdvisoryCapability a owl:Class ; rdfs:subClassOf proeth-core:Capability ;
    skos:definition "The competence to advise a client or governing body on engineering problems and offer recommendations on engineering project considerations." .
"""

# Curated-chain core categories of the targets the run-48 decisions named (stub for the
# cross-category guard, which the case-8 rows all pass).
_CORE_CATEGORIES = {
    'UnbuildableDesignState': 'State', 'UnquantifiedRiskState': 'State',
    'PublicSafetyObligation': 'Obligation', 'RegulatoryComplianceObligation': 'Obligation',
    'LegalObligation': 'Obligation', 'SafetyObligation': 'Obligation',
    'CompetenceSelfAssessmentCapability': 'Capability', 'DisclosureCapability': 'Capability',
    'PublicResponsibilityRole': 'Role', 'PublicRole': 'Role',
}

# What the reference sheet offers per category (the stub sheet).
_OFFERED = {
    'State': {'unbuildabledesignstate', 'unquantifiedriskstate', 'riskstate'},
    'Obligation': {'publicsafetyobligation', 'safetyobligation', 'legalobligation',
                   'regulatorycomplianceobligation'},
    'Capability': {'disclosurecapability', 'competenceselfassessmentcapability'},
    'Role': {'publicresponsibilityrole', 'publicrole', 'engineerrole'},
}


def _stub_resolve_core_category(ref):
    local = str(ref or '').rsplit('#', 1)[-1].replace(' ', '')
    return _CORE_CATEGORIES.get(local)


class _StubSheet:
    def offered_targets(self, category):
        return _OFFERED.get(category, set())


@pytest.fixture
def curated(tmp_path, monkeypatch):
    """Fixture curated tiers wired into the module-level resolvers the service reads."""
    (tmp_path / "proethica-core.ttl").write_text(_CORE_TTL)
    (tmp_path / "proethica-intermediate.ttl").write_text(_INTERMEDIATE_TTL)
    (tmp_path / "proethica-intermediate-extended.ttl").write_text(_EXTENDED_TTL)
    hierarchy = ClassHierarchyIndex(tmp_path)
    axis = RoleAxisResolver(tmp_path)
    monkeypatch.setattr(category_resolver, 'is_strict_subclass', hierarchy.is_strict_subclass)
    monkeypatch.setattr(category_resolver, 'extended_class_definition', hierarchy.extended_definition)
    monkeypatch.setattr(category_resolver, 'resolve_role_axis', axis.resolve)
    monkeypatch.setattr(category_resolver, 'resolve_core_category', _stub_resolve_core_category)
    monkeypatch.setattr(reference_sheet, 'reuse_block_for_concept', lambda concept_type: 'REUSE BLOCK')
    monkeypatch.setattr(reference_sheet, 'get_sheet', lambda sheet_dir=None: _StubSheet())
    monkeypatch.setattr(ers, 'db', SimpleNamespace(session=SimpleNamespace(commit=lambda: None)))
    return hierarchy


# ---------------------------------------------------------------------------
# Rows (ids and values from the run-48 replay)
# ---------------------------------------------------------------------------

def _md(matched_uri=None, confidence=0.0, matches_existing=None):
    if matches_existing is None:
        matches_existing = bool(matched_uri)
    return {'matches_existing': matches_existing, 'matched_uri': matched_uri,
            'matched_label': matched_uri.rsplit('#', 1)[-1] if matched_uri else None,
            'confidence': confidence, 'reasoning': 'test'}


def _row(id, extraction_type, label, *, storage_type='class', uri=None, definition='',
         matched=None, confidence=None, matches_existing=None, props=None, types=None,
         md=True):
    """A temporary_rdf_storage row as a plain object. ``matched`` sets both the column and
    (unless md=False) the stored match decision, the way rdf_storage_service writes them."""
    if uri is None:
        uri = (INT if storage_type == 'class' else CASE) + label.replace(' ', '')
    rdf = {'label': label, 'definition': definition, 'properties': dict(props or {})}
    if storage_type == 'individual':
        rdf['types'] = list(types or [])
    if md:
        rdf['match_decision'] = _md(matched, confidence or 0.0, matches_existing)
    return SimpleNamespace(
        id=id, case_id=8, extraction_type=extraction_type, storage_type=storage_type,
        entity_label=label, entity_uri=uri, entity_definition=definition,
        rdf_json_ld=rdf, provenance_metadata={}, is_published=False,
        matched_ontology_uri=matched,
        matched_ontology_label=matched.rsplit('#', 1)[-1] if matched else None,
        match_confidence=confidence, match_method='llm' if matched else None,
        match_reasoning='test' if matched else None,
        extraction_session_id='s1',
    )


def _case8_rows():
    """The seven class rows of the review (plus the DisclosureCapability row 95630 collided
    with) as the matcher left them, and the three individuals the rename map retyped."""
    classes = [
        _row(95601, 'states', 'Project Failure Risk State',
             matched=INT + 'ProjectFailureRiskState', confidence=0.85,
             definition='A condition in which going forward with the project risks failure.'),
        _row(95584, 'states', 'Unquantified Risk State',
             matched=INT + 'UnquantifiedRiskState', confidence=0.9),
        _row(95585, 'states', 'Confirmed Risk Finding State',
             matched=INT + 'ConfirmedRiskFindingState', confidence=0.97),
        _row(95626, 'capabilities', 'Engineering Design Capability',
             matched=INT + 'EngineeringDesignCapability', confidence=0.95),
        _row(95628, 'capabilities', 'Disclosure Capability',
             matched=INT + 'DisclosureCapability', confidence=0.95),
        _row(95630, 'capabilities', 'Engineering Advisory Capability',
             matched=INT + 'EngineeringAdvisoryCapability', confidence=0.9),
        _row(95620, 'obligations', 'Safety Obligation',
             matched=INT + 'SafetyObligation', confidence=0.95),
        _row(95622, 'obligations', 'Environmental Standards Compliance Obligation',
             matched=INT + 'LegalObligation', confidence=0.75,
             definition='A duty to comply with the environmental standards and regulations '
                        'that govern stormwater discharge to a drinking water source.'),
        _row(95580, 'roles', 'Affected Community',
             matched=INT + 'PublicRole', confidence=0.9,
             props={'roleKind': ['participant']}),
    ]
    individuals = [
        _row(95603, 'states', 'Project Failure Risk', storage_type='individual',
             types=[INT + 'ProjectFailureRiskState'],
             matched=INT + 'ProjectFailureRiskState', confidence=0.85),
        _row(95631, 'capabilities', 'Engineer L Design Capability', storage_type='individual',
             types=[INT + 'EngineeringDesignCapability'],
             matched=INT + 'EngineeringDesignCapability', confidence=0.95),
        _row(95592, 'states', 'Confirmed Heavy Rain Risk Finding', storage_type='individual',
             types=[INT + 'ConfirmedRiskFindingState'],
             matched=INT + 'ConfirmedRiskFindingState', confidence=0.97),
    ]
    return classes, individuals


# The run-48 decisions, keyed by row id.
_RUN48_DECISIONS = {
    95601: {'action': 'generalize', 'canonical_label': 'Unbuildable Design State'},
    95626: {'action': 'reuse', 'canonical_label': 'Competence Self-Assessment Capability'},
    95630: {'action': 'reuse', 'canonical_label': 'Disclosure Capability'},
    95620: {'action': 'generalize', 'canonical_label': 'Public Safety Obligation',
            'reason': 'the same concept as the canonical Safety Obligation'},
    95585: {'action': 'reuse', 'canonical_label': 'Unquantified Risk State'},
    95580: {'action': 'reuse', 'canonical_label': 'Public Responsibility Role'},
    95622: {'action': 'reuse', 'canonical_label': 'Regulatory Compliance Obligation'},
}


def _groups(rows):
    groups = {}
    for r in rows:
        groups.setdefault((r.extraction_type, r.storage_type), []).append(r)
    return groups


def _service(classes, individuals, decisions):
    """A service whose ORM loaders and model call are stubbed. ``prompted`` collects the
    rows the model was asked about, ``calls`` counts the model calls."""
    svc = EntityReconciliationService()
    svc._group_for_canonicalization = lambda case_id, include_published, storage_types: _groups(classes)
    svc._load_individuals = lambda case_id: list(individuals)
    svc.prompted = []
    svc.calls = 0

    def _build(extraction_type, reuse_block, entities):
        svc.prompted.extend(entities)
        return 'PROMPT'

    def _call(prompt):
        svc.calls += 1
        return {'entities': [dict(d, id=i) for i, d in decisions.items()]}

    svc._build_canonicalize_prompt = _build
    svc._call_llm = _call
    return svc


# ---------------------------------------------------------------------------
# L1: matched class rows are already canonical
# ---------------------------------------------------------------------------

def test_link_threshold_is_the_matcher_auto_link_band():
    assert MATCH_LINK_THRESHOLD == HIGH_BAND_MIN == 0.85


def test_case8_replay_leaves_every_matched_row_unchanged(curated):
    classes, individuals = _case8_rows()
    before = {c.id: (c.entity_label, c.entity_uri) for c in classes}
    before_types = {i.id: list(i.rdf_json_ld['types']) for i in individuals}
    svc = _service(classes, individuals, _RUN48_DECISIONS)

    summary = svc.canonicalize_labels(8)

    assert summary['changed'] == 0 and summary['changes'] == []
    assert summary['individuals_repointed'] == 0
    assert {k['id'] for k in summary['kept_matched']} == set(before)
    assert summary['entities'] == len(classes)
    # No row reached the model: every row was linked by the matcher.
    assert svc.prompted == [] and svc.calls == 0 and summary['groups'] == 0
    for c in classes:
        assert (c.entity_label, c.entity_uri) == before[c.id]
        assert c.provenance_metadata == {}
    for i in individuals:
        assert i.rdf_json_ld['types'] == before_types[i.id]


def test_row_matched_at_threshold_without_decision_flag_is_kept(curated):
    # Column-only link at exactly the band floor (0.85, the row-95601 confidence) with a
    # missing stored match decision: still canonical.
    row = _row(95601, 'states', 'Project Failure Risk State',
               matched=INT + 'ProjectFailureRiskState', confidence=0.85, md=False)
    svc = _service([row], [], _RUN48_DECISIONS)
    summary = svc.canonicalize_labels(8)
    assert summary['kept_matched'][0]['id'] == 95601
    assert row.entity_label == 'Project Failure Risk State'
    assert svc.calls == 0


def test_row_matched_below_threshold_without_decision_flag_is_canonicalized(curated):
    # 0.75 with a stale decision flag is not a link: the row goes to the model, and the
    # matched class then governs the target (L2).
    row = _row(95622, 'obligations', 'Environmental Standards Compliance Obligation',
               matched=INT + 'LegalObligation', confidence=0.75, matches_existing=False)
    svc = _service([row], [], {95622: {'action': 'reuse', 'canonical_label': 'Legal Obligation'}})
    summary = svc.canonicalize_labels(8)
    assert summary['kept_matched'] == []
    assert svc.prompted == [row]
    assert summary['changed'] == 1 and row.entity_label == 'Legal Obligation'
    assert row.entity_uri == INT + 'LegalObligation'
    assert row.provenance_metadata['canonicalization']['status'] == 'applied'


# ---------------------------------------------------------------------------
# L2: vetoes with recorded reasons
# ---------------------------------------------------------------------------

def _assert_rejected(summary, row, reason):
    assert summary['changed'] == 0
    rejected = [r for r in summary['rejected'] if r['id'] == row.id]
    assert len(rejected) == 1 and rejected[0]['reason'] == reason, summary['rejected']
    meta = row.provenance_metadata['canonicalization']
    assert meta['status'] == 'rejected' and meta['reason'] == reason
    assert meta['proposed_label'] == rejected[0]['proposed']
    assert meta['original_label'] == row.entity_label  # the row kept its label
    return rejected[0]


def test_case7_target_differing_from_matched_class_is_rejected(curated):
    # Row 95622 matched LegalObligation at 0.75 and was sent to RegulatoryComplianceObligation.
    row = _row(95622, 'obligations', 'Environmental Standards Compliance Obligation',
               matched=INT + 'LegalObligation', confidence=0.75, matches_existing=False)
    svc = _service([row], [], _RUN48_DECISIONS)
    summary = svc.canonicalize_labels(8)
    rej = _assert_rejected(summary, row, 'target_differs_from_match')
    assert 'LegalObligation' in rej['detail']
    assert row.entity_uri == INT + 'EnvironmentalStandardsComplianceObligation'


def test_case4_generalize_to_strict_specialization_is_rejected(curated):
    # Row 95620 "Safety Obligation" generalized to PublicSafetyObligation, a subclass of it.
    row = _row(95620, 'obligations', 'Safety Obligation')
    svc = _service([row], [], _RUN48_DECISIONS)
    summary = svc.canonicalize_labels(8)
    rej = _assert_rejected(summary, row, 'generalize_to_specialization')
    assert 'PublicSafetyObligation' in rej['detail'] and 'SafetyObligation' in rej['detail']


def test_generalize_to_specialization_of_matched_class_is_rejected(curated):
    # The row is matched (below the link band) to SafetyObligation and the target is its
    # subclass: the matched class is the base the specialization test runs against.
    row = _row(95620, 'obligations', 'Safety Obligation',
               uri=INT + 'EngineerSafetyDuty',
               matched=INT + 'SafetyObligation', confidence=0.6, matches_existing=False)
    svc = _service([row], [], _RUN48_DECISIONS)
    summary = svc.canonicalize_labels(8)
    # The matched-class rule fires first: the target is a different class than the match.
    _assert_rejected(summary, row, 'target_differs_from_match')
    row2 = _row(95621, 'obligations', 'Safety Obligation', uri=INT + 'EngineerSafetyDuty')
    svc = _service([row2], [], {95621: _RUN48_DECISIONS[95620]})
    summary = svc.canonicalize_labels(8)
    assert summary['rejected'][0]['reason'] == 'generalize_to_specialization'


def test_generalize_to_a_class_the_sheet_never_offered_is_rejected(curated):
    row = _row(95700, 'states', 'Dam Overtopping Risk State')
    svc = _service([row], [], {95700: {'action': 'generalize',
                                       'canonical_label': 'Novel Invented State'}})
    summary = svc.canonicalize_labels(8)
    _assert_rejected(summary, row, 'generalize_target_not_offered')


def test_generalize_to_an_offered_general_class_is_applied(curated):
    # The untouched path: a compound state generalizes to the offered RiskState parent.
    row = _row(95700, 'states', 'Dam Overtopping Risk State',
               definition='A condition in which the dam may be overtopped in a heavy rain.')
    ind = _row(95701, 'states', 'Dam Overtopping Risk', storage_type='individual',
               types=[INT + 'DamOvertoppingRiskState'])
    svc = _service([row], [ind], {95700: {'action': 'generalize', 'canonical_label': 'Risk State',
                                          'externalized_context': 'dam overtopping'}})
    summary = svc.canonicalize_labels(8)
    assert summary['rejected'] == [] and summary['changed'] == 1
    assert row.entity_label == 'Risk State' and row.entity_uri == INT + 'RiskState'
    meta = row.provenance_metadata['canonicalization']
    assert meta['status'] == 'applied' and meta['original_label'] == 'Dam Overtopping Risk State'
    assert meta['externalized_context'] == 'dam overtopping'
    assert summary['individuals_repointed'] == 1 and ind.rdf_json_ld['types'] == [INT + 'RiskState']
    assert summary['changes'][0]['old'] == 'Dam Overtopping Risk State'
    assert summary['changes'][0]['new'] == 'Risk State'


def test_case3_reuse_onto_an_iri_the_auto_merge_cannot_fold_is_rejected(curated):
    # Row 95630 lands on DisclosureCapability, the IRI row 95628 already holds. Here 95628 is
    # matched to a different class, so the auto merge would refuse the fold: reject.
    holder = _row(95628, 'capabilities', 'disclosurecapability',
                  uri=INT + 'DisclosureCapability',
                  matched=INT + 'CompetenceSelfAssessmentCapability', confidence=0.9)
    row = _row(95630, 'capabilities', 'Engineering Advisory Capability',
               matched=INT + 'DisclosureCapability', confidence=0.6, matches_existing=False)
    svc = _service([holder, row], [], _RUN48_DECISIONS)
    summary = svc.canonicalize_labels(8)
    rej = _assert_rejected(summary, row, 'entity_uri_collision')
    assert '95628' in rej['detail'] and 'matched_ontology_uri_differs' in rej['detail']


def test_case3_reuse_onto_a_foldable_iri_is_applied_and_flagged_for_merge(curated):
    # The holder is matched to the very class: the two rows are one concept and the auto
    # merge folds them in the same reconcile step (entity_uri grouping, L3).
    holder = _row(95628, 'capabilities', 'disclosurecapability',
                  uri=INT + 'DisclosureCapability',
                  matched=INT + 'DisclosureCapability', confidence=0.95)
    row = _row(95630, 'capabilities', 'Engineering Advisory Capability',
               definition='The competence to communicate material facts and risks to a client.')
    svc = _service([holder, row], [], _RUN48_DECISIONS)
    summary = svc.canonicalize_labels(8)
    assert summary['rejected'] == [] and summary['changed'] == 1
    assert row.entity_uri == INT + 'DisclosureCapability'
    assert summary['changes'][0]['merge_expected_with'] == [95628]


def test_case7_extended_iri_with_a_different_definition_is_a_collision(curated):
    # Unmatched variant of row 95622: RegulatoryComplianceObligation exists in the extended
    # store as a procurement duty, the row is an environmental-compliance duty.
    row = _row(95622, 'obligations', 'Environmental Standards Compliance Obligation',
               definition='A duty to comply with the environmental standards and regulations '
                          'that govern stormwater discharge to a drinking water source.')
    svc = _service([row], [], _RUN48_DECISIONS)
    summary = svc.canonicalize_labels(8)
    rej = _assert_rejected(summary, row, 'extended_iri_collision')
    assert 'procurement' in rej['detail']


def test_case1_extended_iri_collision_catches_the_constructability_fold(curated):
    # Unmatched variant of row 95601: UnbuildableDesignState carries a constructability
    # definition that shares nothing with a project-failure risk.
    row = _row(95601, 'states', 'Project Failure Risk State',
               definition='A condition in which going forward with the project risks an '
                          'unsuccessful outcome because relevant information was not disclosed.')
    svc = _service([row], [], _RUN48_DECISIONS)
    summary = svc.canonicalize_labels(8)
    _assert_rejected(summary, row, 'extended_iri_collision')


def test_reuse_of_a_curated_base_class_is_not_a_collision(curated):
    # DisclosureCapability is declared in the immutable base: a curated reuse target, whatever
    # the definitions' overlap.
    row = _row(95800, 'capabilities', 'AI Tool Disclosure Capability',
               definition='Being able to tell the client that generative AI drafted the report.')
    svc = _service([row], [], {95800: {'action': 'reuse', 'canonical_label': 'Disclosure Capability'}})
    summary = svc.canonicalize_labels(8)
    assert summary['rejected'] == [] and row.entity_uri == INT + 'DisclosureCapability'


def test_case6_participant_role_is_never_folded_into_a_professional_role(curated):
    # Row 95580 "Affected Community" (roleKind participant) was reused onto
    # PublicResponsibilityRole, a ProfessionalRole descendant, via a sheet alt_label.
    row = _row(95580, 'roles', 'Affected Community', props={'roleKind': ['participant']})
    svc = _service([row], [], _RUN48_DECISIONS)
    summary = svc.canonicalize_labels(8)
    rej = _assert_rejected(summary, row, 'role_axis_conflict')
    assert 'participant' in rej['detail'] and 'professional' in rej['detail']


def test_role_axis_falls_back_to_the_matched_class_axis(curated):
    # No roleKind on the row: the axis comes from the matched PublicRole (participant).
    row = _row(95580, 'roles', 'Affected Community',
               matched=INT + 'PublicRole', confidence=0.6, matches_existing=False)
    svc = _service([row], [], {95580: {'action': 'reuse', 'canonical_label': 'Public Role'}})
    assert svc.canonicalize_labels(8)['rejected'] == []
    row = _row(95580, 'roles', 'Affected Community', uri=INT + 'PublicRole')
    svc = _service([row], [], _RUN48_DECISIONS)
    summary = svc.canonicalize_labels(8)
    _assert_rejected(summary, row, 'role_axis_conflict')


def test_same_axis_role_reuse_is_applied(curated):
    row = _row(95900, 'roles', 'Impacted Neighbourhood', props={'roleKind': ['participant']})
    svc = _service([row], [], {95900: {'action': 'reuse', 'canonical_label': 'Public Role'}})
    summary = svc.canonicalize_labels(8)
    assert summary['rejected'] == [] and row.entity_uri == INT + 'PublicRole'


def test_dry_run_reports_vetoes_without_writing(curated):
    row = _row(95620, 'obligations', 'Safety Obligation')
    svc = _service([row], [], _RUN48_DECISIONS)
    summary = svc.canonicalize_labels(8, dry_run=True)
    assert summary['rejected'][0]['reason'] == 'generalize_to_specialization'
    assert row.provenance_metadata == {}


def test_cross_category_rejection_is_recorded_with_a_reason(curated):
    row = _row(95950, 'constraints', 'Public Safety Limit')
    svc = _service([row], [], {95950: {'action': 'reuse', 'canonical_label': 'Public Safety Obligation'}})
    summary = svc.canonicalize_labels(8)
    assert len(summary['rejected_cross_category']) == 1
    _assert_rejected(summary, row, 'cross_category')


# ---------------------------------------------------------------------------
# L3: auto merge grouping, refusal and pair reporting
# ---------------------------------------------------------------------------

def _merge_harness(rows):
    svc = EntityReconciliationService()
    by_id = {r.id: r for r in rows}
    calls = []

    def fake_merge(keep_id, merge_id):
        calls.append((keep_id, merge_id))
        keep, other = by_id[keep_id], by_id[merge_id]
        keep.entity_label = svc._pick_preferred_label(keep.entity_label, other.entity_label)
        rows.remove(other)
        return {'success': True}

    svc.merge_entities = fake_merge
    svc._group_entities = lambda case_id: _groups(rows)
    return svc, calls


def test_case5_rows_matched_to_different_classes_are_not_folded():
    # Row 95585 (matched ConfirmedRiskFindingState) carrying the label "Unquantified Risk
    # State" must not be folded into row 95584 (matched UnquantifiedRiskState).
    rows = [
        _row(95584, 'states', 'Unquantified Risk State',
             matched=INT + 'UnquantifiedRiskState', confidence=0.9),
        _row(95585, 'states', 'Unquantified Risk State',
             uri=INT + 'ConfirmedRiskFindingState',
             matched=INT + 'ConfirmedRiskFindingState', confidence=0.97),
    ]
    svc, calls = _merge_harness(rows)
    result = svc.reconcile_auto(8)
    assert calls == [] and result.auto_merged == 0 and len(rows) == 2
    assert result.merged_pairs == []
    assert result.merge_refusals == [{
        'kept_id': 95584, 'kept_label': 'Unquantified Risk State',
        'kept_matched_uri': INT + 'UnquantifiedRiskState',
        'refused_id': 95585, 'refused_label': 'Unquantified Risk State',
        'refused_matched_uri': INT + 'ConfirmedRiskFindingState',
        'reason': 'matched_ontology_uri_differs',
    }]


def test_case3_rows_sharing_an_entity_uri_are_folded_whatever_their_labels():
    # "disclosurecapability" and "Disclosure Capability" on one IRI: the label normalizer keeps
    # them apart, the IRI makes them one node.
    rows = [
        _row(95628, 'capabilities', 'disclosurecapability', uri=INT + 'DisclosureCapability',
             matched=INT + 'DisclosureCapability', confidence=0.95),
        _row(95630, 'capabilities', 'Disclosure Capability', uri=INT + 'DisclosureCapability'),
    ]
    svc, calls = _merge_harness(rows)
    result = svc.reconcile_auto(8)
    assert calls == [(95628, 95630)] and result.auto_merged == 1
    # The surviving label follows the existing shorter-label preference of merge_entities.
    assert result.merged_pairs == [{
        'merged_id': 95630, 'merged_label': 'Disclosure Capability',
        'kept_id': 95628, 'surviving_label': 'disclosurecapability',
        'basis': 'entity_uri',
    }]


def test_identical_labels_with_one_unmatched_row_still_fold():
    rows = [
        _row(1, 'obligations', 'Confidentiality Obligation',
             matched=INT + 'ConfidentialityObligation', confidence=0.9),
        _row(2, 'obligations', 'Confidentiality Obligation (Present Case)',
             uri=INT + 'ConfidentialityObligationPresentCase'),
    ]
    svc, calls = _merge_harness(rows)
    result = svc.reconcile_auto(8)
    assert calls == [(1, 2)]
    assert result.merged_pairs[0]['basis'] == 'label'
    assert result.merged_pairs[0]['merged_label'] == 'Confidentiality Obligation (Present Case)'
    assert result.merged_pairs[0]['surviving_label'] == 'Confidentiality Obligation'
    assert result.merge_refusals == []


def test_exact_match_groups_chain_label_and_uri_links():
    svc = EntityReconciliationService()
    a = _row(1, 'states', 'Risk State', uri=INT + 'RiskState')
    b = _row(2, 'states', 'risk state', uri=INT + 'RiskStateB')
    c = _row(3, 'states', 'Hazard State', uri=INT + 'RiskStateB')
    d = _row(4, 'states', 'Other State', uri=INT + 'OtherState')
    groups = svc._exact_match_groups([a, b, c, d])
    assert [[r.id for r in g] for g in groups] == [[1, 2, 3], [4]]


# ---------------------------------------------------------------------------
# L4: the rename map respects an individual's own match decision
# ---------------------------------------------------------------------------

def test_rename_map_never_repoints_an_individual_matched_to_an_existing_class():
    svc = EntityReconciliationService()
    protected = _row(95603, 'states', 'Project Failure Risk', storage_type='individual',
                     types=[INT + 'ProjectFailureRiskState'],
                     matched=INT + 'ProjectFailureRiskState', confidence=0.85)
    free = _row(95604, 'states', 'Dam Overtopping Risk', storage_type='individual',
                types=[INT + 'ProjectFailureRiskState'])
    column_only = _row(95605, 'states', 'Column Only', storage_type='individual',
                       types=[INT + 'ProjectFailureRiskState'],
                       matched=INT + 'ProjectFailureRiskState', confidence=0.85, md=False)
    svc._load_individuals = lambda case_id: [protected, free, column_only]
    rename_map = {INT + 'ProjectFailureRiskState': INT + 'UnbuildableDesignState'}

    changed, kept = svc._repoint_individual_types(8, rename_map, write=True)

    assert (changed, kept) == (1, 2)
    assert protected.rdf_json_ld['types'] == [INT + 'ProjectFailureRiskState']
    assert column_only.rdf_json_ld['types'] == [INT + 'ProjectFailureRiskState']
    assert free.rdf_json_ld['types'] == [INT + 'UnbuildableDesignState']


def test_rename_map_dry_run_counts_without_writing():
    svc = EntityReconciliationService()
    free = _row(1, 'states', 'X', storage_type='individual', types=[INT + 'A'])
    svc._load_individuals = lambda case_id: [free]
    assert svc._repoint_individual_types(8, {INT + 'A': INT + 'B'}, write=False) == (1, 0)
    assert free.rdf_json_ld['types'] == [INT + 'A']
    assert svc._repoint_individual_types(8, {}, write=True) == (0, 0)


# ---------------------------------------------------------------------------
# L5: review candidates, never merges
# ---------------------------------------------------------------------------

def test_two_principle_individuals_of_one_class_are_a_review_candidate():
    rows = [
        _row(1, 'principles', 'Public Safety Paramount', storage_type='individual',
             types=[INT + 'PublicSafetyPrinciple']),
        _row(2, 'principles', 'Public Welfare First', storage_type='individual',
             types=[INT + 'PublicSafetyPrinciple']),
        _row(3, 'principles', 'Honesty', storage_type='individual',
             types=[INT + 'HonestyPrinciple']),
    ]
    svc, calls = _merge_harness(rows)
    result = svc.reconcile_auto(8)
    assert calls == [] and result.auto_merged == 0
    assert len(result.review_candidates) == 1
    cand = result.review_candidates[0]
    assert (cand.entity_a_id, cand.entity_b_id) == (1, 2)
    assert cand.recommendation == 'review' and cand.rule == 'principle_per_value'
    assert 'one individual per value' in cand.llm_reason


def test_principle_class_ref_falls_back_to_the_class_property():
    svc = EntityReconciliationService()
    rows = [
        _row(1, 'principles', 'A', storage_type='individual',
             props={'principleClass': ['Public Safety Principle']}),
        _row(2, 'principles', 'B', storage_type='individual',
             props={'principleClass': ['PublicSafetyPrinciple']}),
    ]
    cands = svc._detect_review_candidates(_groups(rows))
    assert [(c.entity_a_id, c.entity_b_id) for c in cands] == [(1, 2)]


def test_near_identical_constraints_of_one_class_and_entity_are_a_review_candidate():
    stmt = 'Engineer L must not certify the stormwater design as adequate without quantifying the risk.'
    near = 'Engineer L must not certify the stormwater design as adequate without quantifying the heavy-rain risk.'
    other = 'Engineer L must not disclose the confidential client report to the city council.'
    rows = [
        _row(1, 'constraints', 'No certification without risk quantification', storage_type='individual',
             types=[INT + 'CertificationConstraint'],
             props={'constrainedEntity': ['Engineer L'], 'constraintStatement': [stmt]}),
        _row(2, 'constraints', 'No adequacy certification', storage_type='individual',
             types=[INT + 'CertificationConstraint'],
             props={'constrainedEntity': ['Engineer L'], 'constraintStatement': [near]}),
        _row(3, 'constraints', 'No disclosure of the report', storage_type='individual',
             types=[INT + 'CertificationConstraint'],
             props={'constrainedEntity': ['Engineer L'], 'constraintStatement': [other]}),
        _row(4, 'constraints', 'Client version', storage_type='individual',
             types=[INT + 'CertificationConstraint'],
             props={'constrainedEntity': ['Client X'], 'constraintStatement': [stmt]}),
    ]
    svc, calls = _merge_harness(rows)
    result = svc.reconcile_auto(8)
    assert calls == []
    assert [(c.entity_a_id, c.entity_b_id) for c in result.review_candidates] == [(1, 2)]
    cand = result.review_candidates[0]
    assert cand.rule == 'constraint_statement_similarity'
    assert cand.similarity >= CONSTRAINT_STATEMENT_SIMILARITY_MIN
    assert 'engineer l' in cand.llm_reason


def test_constraint_statement_falls_back_to_the_definition():
    svc = EntityReconciliationService()
    stmt = 'Engineer L must not certify the design without quantifying the risk.'
    rows = [
        _row(1, 'constraints', 'A', storage_type='individual', definition=stmt,
             types=[INT + 'C'], props={'constrainedEntity': ['Engineer L']}),
        _row(2, 'constraints', 'B', storage_type='individual', definition=stmt,
             types=[INT + 'C'], props={'constrainedEntity': ['Engineer L']}),
    ]
    assert len(svc._detect_review_candidates(_groups(rows))) == 1


# ---------------------------------------------------------------------------
# Supporting resolvers
# ---------------------------------------------------------------------------

def test_class_hierarchy_index_strict_subclass_and_extended_definitions(curated):
    idx = curated
    assert idx.is_strict_subclass(INT + 'PublicSafetyObligation', INT + 'SafetyObligation')
    assert idx.is_strict_subclass('PublicSafetyObligation', CORE + 'Obligation')
    assert idx.is_strict_subclass('proeth:UnbuildableDesignState', 'RiskState')
    assert not idx.is_strict_subclass('SafetyObligation', 'SafetyObligation')
    assert not idx.is_strict_subclass('SafetyObligation', 'PublicSafetyObligation')
    assert not idx.is_strict_subclass('UnknownClass', 'SafetyObligation')
    assert not idx.is_strict_subclass(None, 'SafetyObligation')
    assert 'procurement' in idx.extended_definition(INT + 'RegulatoryComplianceObligation')
    assert idx.extended_definition('DisclosureCapability') is None  # declared in the base
    assert idx.extended_definition('NoSuchClass') is None
    assert idx.extended_definition('') is None


def test_module_level_resolvers_delegate_to_the_singleton(monkeypatch, tmp_path):
    (tmp_path / "proethica-core.ttl").write_text(_CORE_TTL)
    (tmp_path / "proethica-intermediate.ttl").write_text(_INTERMEDIATE_TTL)
    (tmp_path / "proethica-intermediate-extended.ttl").write_text(_EXTENDED_TTL)
    monkeypatch.setattr(category_resolver, '_hierarchy_index', ClassHierarchyIndex(tmp_path))
    assert category_resolver.is_strict_subclass('PublicSafetyObligation', 'SafetyObligation')
    assert category_resolver.extended_class_definition('ProjectFailureRiskState')


def test_definition_overlap_separates_paraphrase_from_different_concept():
    environmental = ('A duty to comply with the environmental standards and regulations that '
                     'govern stormwater discharge to a drinking water source.')
    procurement = ('A professional duty of public-entity engineers and public entities to comply '
                   'with qualifications-based selection procurement requirements, including '
                   'conducting an RFQ process and obtaining governing-body authorization.')
    paraphrase_a = ('The competence to communicate material facts, risks, limitations, or '
                    'affiliations to the parties entitled to them.')
    paraphrase_b = 'The capability to disclose material facts and risks to the client and the public.'
    assert _definition_overlap(environmental, procurement) < EXTENDED_DEFINITION_OVERLAP_MIN
    assert _definition_overlap(paraphrase_a, paraphrase_b) >= EXTENDED_DEFINITION_OVERLAP_MIN
    assert _definition_overlap('', procurement) == 0.0


_SHEET_MANIFEST = "global_rules: []\nconcepts: []\nconstraint_fold: []\n"
_SHEET_CAPABILITY = """\
component: Capability
canonical_parents:
  - AdequacyAssessmentCapability
canonical:
  - iri: DisclosureCapability
    label: Disclosure Capability
    definition: Communicating material facts.
    alt_labels:
      - AI Tool Disclosure Capability
  - iri: CompetenceSelfAssessmentCapability
    label: Competence Self-Assessment Capability
    definition: Appraising one's own qualifications.
do_not_mint:
  - label: Constructability Assessment Capability
    decompose: { note: "subject is context" }
  - label: Client Pushback Capability
    decompose: { state: ToolAttributionCapability }
"""
_SHEET_STATE = """\
component: State
canonical:
  - iri: RiskState
    label: Risk State
    definition: A condition of exposure.
"""


def test_reference_sheet_offered_targets(tmp_path):
    (tmp_path / 'manifest.yaml').write_text(_SHEET_MANIFEST)
    (tmp_path / 'capability.yaml').write_text(_SHEET_CAPABILITY)
    (tmp_path / 'state.yaml').write_text(_SHEET_STATE)
    sheet = reference_sheet.ReferenceSheet.load(str(tmp_path))
    offered = sheet.offered_targets('Capability')
    assert {'disclosurecapability', 'competenceselfassessmentcapability',
            'adequacyassessmentcapability', 'toolattributioncapability'} <= offered
    assert 'aitooldisclosurecapability' not in offered  # a synonym is not a target
    assert 'subjectiscontext' not in offered  # a do_not_mint note is not a class
    assert 'riskstate' not in offered
    assert sheet.offered_targets('State') == {'riskstate'}
    assert sheet.offered_targets('Role') == set()
    assert sheet.offered_targets('Capability') is offered  # memoized


def test_reconciliation_result_carries_pairs_and_refusals():
    result = ReconciliationResult(case_id=8)
    assert result.merged_pairs == [] and result.merge_refusals == []
