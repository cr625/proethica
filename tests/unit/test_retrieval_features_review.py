"""Review of the retrieval-features lessons (case 24-1 review, brief 2).

Defects found by tracing the merged code from its production callers, each
with the scenario that broke:

1. The integration merge placed the competing-obligation branch of
   NarrativeElementExtractor._extract_conflicts (step4-synthesis, lesson L4)
   ahead of the pair dedup the retrieval-features branch added to the
   constraint-slot branch (lesson L5), and the new branch neither checked nor
   registered the pair. Two stored decision points over the same obligation
   pair, case 24-1 DP2 and DP3 once CanonicalDecisionPoint.from_storage
   restores their competing_obligation fields, produced the exact duplicate
   tension D-41 names (conflict_3), and the heuristic branch could repeat the
   pair as well.

2. board_outcome_for_case derived ('unclear', 0.0) for a case whose
   board_explicit conclusions carry only non-polar boardConclusionType values
   (the 'unknown' fall-through of the detector, or interpretation and
   recommendation holdings). extract_outcome_for_case then replaced the
   conclusion-text classification with 'unclear', and the phase 4 connector
   overwrote the stored outcome on every run. The rule names the text regex
   as the fallback for a case without typed board conclusions; a case whose
   typed conclusions carry no verdict is such a case.

The branch tests exercise entity_classes_from_graph on hand-built graphs; the
golden TTL of the commit service (the real emitter output) stands in for them
here. No database and no model: storage queries and sessions are patched.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import rdflib

from app.models.case_precedent_features import CasePrecedentFeatures
from app.services.commit.precedent_features import entity_classes_from_graph
from app.services.narrative.narrative_element_extractor import NarrativeElementExtractor
from app.services.precedent import case_feature_extractor as cfe
from app.services.precedent import phase4_connector
from app.services.precedent.case_feature_extractor import CaseFeatureExtractor, board_outcome_for_case
from app.services.precedent.phase4_connector import update_precedent_features_from_phase4

CASE = 'http://proethica.org/ontology/case/8#'
O_SAFETY = (CASE + 'Engineer_L_Watershed_Safety_Duty', 'Engineer L Watershed Safety Duty')
O_AGENT = (CASE + 'Engineer_L_Faithful_Agent_Duty', 'Engineer L Faithful Agent Duty')
C_SCOPE = (CASE + 'Client_Directive_Constraint', 'Client Directive Constraint')
ROLE = CASE + 'Engineer_L'

GOLDEN_TTL = Path(__file__).resolve().parents[1] / 'fixtures' / 'commit_golden' / 'individuals_case_501.ttl'
INTERMEDIATE = 'http://proethica.org/ontology/intermediate#'
CORE = 'http://proethica.org/ontology/core#'
CASES = 'http://proethica.org/ontology/cases#'


# =============================================================================
# Defect 1: the competing-obligation branch of _extract_conflicts
# =============================================================================

def _entity(uri, label):
    return SimpleNamespace(uri=uri, label=label, definition='', entity_type='')


def _foundation(safety_label=O_SAFETY[1], agent_label=O_AGENT[1]):
    return SimpleNamespace(
        case_id=None,
        roles=[_entity(ROLE, 'Engineer L')],
        states=[], resources=[], principles=[], capabilities=[], actions=[], events=[],
        obligations=[_entity(O_SAFETY[0], safety_label), _entity(O_AGENT[0], agent_label)],
        constraints=[_entity(C_SCOPE[0], C_SCOPE[1])],
    )


def _point(focus_id, obligation, competing=None, constraint=None):
    """A stored decision point as CanonicalDecisionPoint.from_storage restores
    it: the competition is the committed obligation pair
    (competing_obligation_*) or the constraint slot."""
    return SimpleNamespace(
        focus_id=focus_id, uri=CASE + focus_id, role_uri=ROLE, role_label='Engineer L',
        obligation_uri=obligation[0], obligation_label=obligation[1],
        competing_obligation_uri=competing[0] if competing else None,
        competing_obligation_label=competing[1] if competing else None,
        constraint_uri=constraint[0] if constraint else None,
        constraint_label=constraint[1] if constraint else None,
    )


def _pair(a, b):
    return tuple(sorted((a[0], b[0])))


class TestCompetingPairDedup:

    def setup_method(self):
        self.extractor = NarrativeElementExtractor(use_llm=False)

    def test_two_points_over_the_committed_pair_yield_one_tension(self):
        # Case 24-1 DP2 and DP3, plus a point naming the pair the other way round.
        points = [_point('DP2', O_SAFETY, competing=O_AGENT),
                  _point('DP3', O_SAFETY, competing=O_AGENT),
                  _point('DP4', O_AGENT, competing=O_SAFETY)]
        conflicts = self.extractor._extract_conflicts(_foundation(), points)
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict.conflict_id == 'conflict_1'
        assert conflict.conflict_type == 'obligation_vs_obligation'
        assert (conflict.entity1_uri, conflict.entity2_uri) == (O_SAFETY[0], O_AGENT[0])

    def test_committed_pair_and_constraint_slot_pair_collapse_to_one(self):
        committed = _point('DP2', O_SAFETY, competing=O_AGENT)
        slot = _point('DP1', O_SAFETY, constraint=O_AGENT)
        for order in ([committed, slot], [slot, committed]):
            conflicts = self.extractor._extract_conflicts(_foundation(), order)
            assert len(conflicts) == 1, [p.focus_id for p in order]
            assert conflicts[0].conflict_type == 'obligation_vs_obligation'

    def test_distinct_pairs_are_all_kept_in_order(self):
        points = [_point('DP2', O_SAFETY, competing=O_AGENT),
                  _point('DP1', O_SAFETY, constraint=C_SCOPE)]
        conflicts = self.extractor._extract_conflicts(_foundation(), points)
        assert [tuple(sorted((c.entity1_uri, c.entity2_uri))) for c in conflicts] == [
            _pair(O_SAFETY, O_AGENT), _pair(O_SAFETY, C_SCOPE)]
        assert [c.conflict_id for c in conflicts] == ['conflict_1', 'conflict_2']
        assert [c.conflict_type for c in conflicts] == ['obligation_vs_obligation', 'obligation_vs_constraint']

    def test_heuristic_branch_does_not_repeat_the_committed_pair(self):
        # 'protect' / 'inform' is a heuristic conflict pair of the foundation scan.
        foundation = _foundation('Protect the public', 'Inform the client')
        point = _point('DP2', (O_SAFETY[0], 'Protect the public'),
                       competing=(O_AGENT[0], 'Inform the client'))
        conflicts = self.extractor._extract_conflicts(foundation, [point])
        assert len(conflicts) == 1
        assert conflicts[0].description == 'Tension between Protect the public and Inform the client'


# =============================================================================
# Defect 2: non-polar board conclusion types
# =============================================================================

def _conclusion_rows(*board_types):
    return [SimpleNamespace(rdf_json_ld={'conclusionNumber': n, 'conclusionType': 'board_explicit',
                                         'boardConclusionType': t})
            for n, t in enumerate(board_types, 1)]


def _storage(rows):
    storage = MagicMock()
    storage.query.filter_by.return_value.all.return_value = rows
    return storage


UNETHICAL_TEXT = "It was unethical for Engineer A to sign the plans."


class TestNonPolarBoardTypesKeepTheTextOutcome:

    def test_board_outcome_is_none_without_a_polar_value(self):
        rows = _conclusion_rows('unknown', 'interpretation', 'recommendation')
        with patch.object(cfe, 'TemporaryRDFStorage', _storage(rows)):
            assert board_outcome_for_case(8) is None

    def test_feature_extraction_falls_back_to_the_text(self):
        extractor = CaseFeatureExtractor(embedding_service=MagicMock())
        with patch.object(cfe, 'TemporaryRDFStorage', _storage(_conclusion_rows('unknown'))):
            outcome, _, reasoning = extractor.extract_outcome_for_case(8, UNETHICAL_TEXT)
        assert outcome == 'unethical'
        assert 'explicit unethical statement' in reasoning

    def test_one_polar_value_beside_unknowns_still_decides(self):
        with patch.object(cfe, 'TemporaryRDFStorage', _storage(_conclusion_rows('unknown', 'violation'))):
            outcome, confidence, reasoning = board_outcome_for_case(8)
        assert (outcome, confidence) == ('unethical', cfe.BOARD_DERIVED_CONFIDENCE)
        assert 'violation=1' in reasoning

    def test_connector_leaves_the_stored_outcome_alone(self):
        features = CasePrecedentFeatures(
            case_id=8, transformation_type='stalemate', outcome_type='ethical',
            outcome_confidence=0.65, outcome_reasoning='Ethical indicators: explicit ethical statement')
        model = MagicMock()
        model.query.filter_by.return_value.first.return_value = features
        rows = _conclusion_rows('unknown', 'recommendation')
        with patch.object(phase4_connector, 'CasePrecedentFeatures', model), \
             patch.object(phase4_connector, 'db', MagicMock()), \
             patch.object(cfe, 'TemporaryRDFStorage', _storage(rows)):
            assert update_precedent_features_from_phase4(case_id=8, transformation_type='phase_lag') is True
        assert features.transformation_type == 'phase_lag'
        assert (features.outcome_type, features.outcome_confidence) == ('ethical', 0.65)
        assert features.outcome_reasoning == 'Ethical indicators: explicit ethical statement'


# =============================================================================
# Lesson L7 against the real emitter output
# =============================================================================

class TestEntityClassesFromTheEmitterOutput:
    """entity_classes_from_graph over the TTL the commit service writes (the
    snapshot test_commit_service_golden.py holds the emitter to), in place of
    the hand-built graphs of the branch tests."""

    def setup_method(self):
        self.graph = rdflib.Graph()
        self.graph.parse(str(GOLDEN_TTL), format='turtle')
        self.classes = entity_classes_from_graph(self.graph)

    def test_committed_individuals_group_by_their_direct_core_category(self):
        assert set(self.classes) >= {'role', 'state', 'obligation'}
        assert set(self.classes['role']) == {INTERMEDIATE + 'EngineerRole',
                                             INTERMEDIATE + 'ProviderClientRole',
                                             INTERMEDIATE + 'DeveloperClient'}
        assert self.classes['state'] == [INTERMEDIATE + 'PeerReviewPendingStateDraft']
        assert self.classes['obligation'] == [INTERMEDIATE + 'DisclosureObligationDraft']

    def test_category_classes_markers_and_analysis_layer_are_not_in_the_mapping(self):
        flat = {uri for uris in self.classes.values() for uri in uris}
        assert not any(uri.startswith(CASES) for uri in flat)
        assert 'http://www.w3.org/2002/07/owl#NamedIndividual' not in flat
        for category in ('Role', 'State', 'Obligation', 'Action', 'Event'):
            assert CORE + category not in flat
        # Agents (core:Agent) are not one of the nine categories.
        assert 'agent' not in self.classes
